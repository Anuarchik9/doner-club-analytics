import math
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta

import requests
from flask import jsonify, request

import app as core


_CACHE = {}
_CACHE_TTL = 5 * 60
_MAX_DAYS = 93


def _tag(value):
    return str(value or "").split("}")[-1]


def _text(node, name, default=""):
    if node is None:
        return default
    for child in list(node):
        if _tag(child.tag) == name:
            return (child.text or "").strip()
    return default


def _child(node, name):
    if node is None:
        return None
    for child in list(node):
        if _tag(child.tag) == name:
            return child
    return None


def _num(value):
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace("\u00a0", "").replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _bool(value):
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _parse_dt(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(text[:19], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=core.LOCAL_TZ)
    return dt.astimezone(core.LOCAL_TZ)


def _xml_nodes(response, node_tag):
    response.raise_for_status()
    root = ET.fromstring(response.content)
    return [node for node in root.iter() if _tag(node.tag) == node_tag]


def _server_get(base_url, token, path, params=None, timeout=60):
    query = {"key": token}
    if params:
        query.update(params)
    response = requests.get(f"{base_url}{path}", params=query, timeout=timeout)
    response.raise_for_status()
    return response


def _payment_details(node):
    pd = _child(node, "paymentDetails")
    if pd is None:
        return {
            "regularMinutes": 0.0,
            "overtimeMinutes": 0.0,
            "regularPayment": 0.0,
            "overtimePayment": 0.0,
            "otherPayments": 0.0,
            "departmentId": "",
            "departmentName": "",
            "available": False,
        }
    return {
        "regularMinutes": _num(_text(pd, "regularPayedMinutes")),
        "overtimeMinutes": _num(_text(pd, "overtimePayedMinutes")),
        "regularPayment": _num(_text(pd, "regularPaymentSum")),
        "overtimePayment": _num(_text(pd, "overtimePaymentSum")),
        "otherPayments": _num(_text(pd, "otherPaymentsSum")),
        "departmentId": _text(pd, "salaryDepartmentId"),
        "departmentName": _text(pd, "salaryDepartmentName"),
        "available": True,
    }


def _duration_minutes(start, end, now=None):
    if not start:
        return 0.0
    if not end:
        end = now or datetime.now(core.LOCAL_TZ)
    seconds = max(0.0, (end - start).total_seconds())
    return min(seconds / 60.0, 24.0 * 60.0)


def _parse_employees(nodes):
    result = {}
    for node in nodes:
        employee_flag = _bool(_text(node, "employee"))
        deleted = _bool(_text(node, "deleted"))
        if deleted is True or employee_flag is False:
            continue
        employee_id = _text(node, "id")
        name = _text(node, "name") or "Без имени"
        if not employee_id:
            continue
        result[employee_id] = {
            "id": employee_id,
            "code": _text(node, "code"),
            "name": name,
            "login": _text(node, "login"),
            "mainRoleId": _text(node, "mainRoleId"),
            "mainRoleCode": _text(node, "mainRoleCode"),
            "preferredDepartmentCode": _text(node, "preferredDepartmentCode"),
            "hireDate": _text(node, "hireDate"),
            "fireDate": _text(node, "fireDate"),
        }
    return result


def _parse_roles(nodes):
    by_id = {}
    by_code = {}
    for node in nodes:
        if _bool(_text(node, "deleted")) is True:
            continue
        item = {
            "id": _text(node, "id"),
            "code": _text(node, "code"),
            "name": _text(node, "name") or _text(node, "code") or "Должность",
            "paymentPerHour": _num(_text(node, "paymentPerHour")),
            "steadySalary": _num(_text(node, "steadySalary")),
            "scheduleType": _text(node, "scheduleType"),
        }
        if item["id"]:
            by_id[item["id"]] = item
        if item["code"]:
            by_code[item["code"]] = item
    return by_id, by_code


def _parse_salaries(nodes):
    result = defaultdict(list)
    for node in nodes:
        employee_id = _text(node, "employeeId")
        if not employee_id:
            continue
        result[employee_id].append({
            "dateFrom": _text(node, "dateFrom"),
            "dateTo": _text(node, "dateTo"),
            "payment": _num(_text(node, "payment")),
            "salarySpecification": _text(node, "salarySpecification"),
        })
    return result


def _current_salary(items, date_to):
    target = datetime.strptime(date_to, "%Y-%m-%d").date()
    candidates = []
    for item in items or []:
        start = _parse_dt(item.get("dateFrom"))
        end = _parse_dt(item.get("dateTo"))
        if start and start.date() > target:
            continue
        if end and end.date() < target:
            continue
        candidates.append((start or datetime.min.replace(tzinfo=core.LOCAL_TZ), item))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _parse_attendance(nodes, now):
    result = []
    for node in nodes:
        start = _parse_dt(_text(node, "dateFrom"))
        end = _parse_dt(_text(node, "dateTo"))
        personal_start = _parse_dt(_text(node, "personalDateFrom"))
        personal_end = _parse_dt(_text(node, "personalDateTo"))
        pd = _payment_details(node)
        minutes = _duration_minutes(start, end, now=now)
        paid_minutes = pd["regularMinutes"] + pd["overtimeMinutes"]
        result.append({
            "id": _text(node, "id"),
            "employeeId": _text(node, "employeeId"),
            "roleId": _text(node, "roleId"),
            "attendanceType": _text(node, "attendanceType"),
            "departmentId": _text(node, "departmentId"),
            "departmentName": _text(node, "departmentName"),
            "dateFrom": start.isoformat() if start else "",
            "dateTo": end.isoformat() if end else "",
            "personalDateFrom": personal_start.isoformat() if personal_start else "",
            "personalDateTo": personal_end.isoformat() if personal_end else "",
            "minutes": round(minutes, 2),
            "paidMinutes": round(paid_minutes, 2),
            "regularMinutes": round(pd["regularMinutes"], 2),
            "overtimeMinutes": round(pd["overtimeMinutes"], 2),
            "regularPayment": round(pd["regularPayment"], 2),
            "overtimePayment": round(pd["overtimePayment"], 2),
            "otherPayments": round(pd["otherPayments"], 2),
            "paymentTotal": round(pd["regularPayment"] + pd["overtimePayment"] + pd["otherPayments"], 2),
            "paymentDetailsAvailable": pd["available"],
            "open": bool(start and not end),
        })
    return result


def _period_bounds(date_from, date_to):
    start = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=core.LOCAL_TZ)
    end = datetime.strptime(date_to, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=core.LOCAL_TZ
    )
    return start, end


def _attendance_in_period(item, period_start, period_end, now):
    start = _parse_dt(item.get("dateFrom"))
    end = _parse_dt(item.get("dateTo"))
    if not start:
        return False
    if end:
        return start <= period_end and end >= period_start
    # iikoServer can return ancient unfinished attendances regardless of the
    # requested period. Count an open attendance only when it actually started
    # inside the selected period and is still plausibly an active shift.
    if not (period_start <= start <= period_end):
        return False
    return (now - start).total_seconds() <= 30 * 60 * 60


def _schedule_in_period(item, period_start, period_end):
    start = _parse_dt(item.get("dateFrom"))
    end = _parse_dt(item.get("dateTo"))
    if not start:
        return False
    if not end:
        return period_start <= start <= period_end
    return start <= period_end and end >= period_start


def _parse_schedule(nodes):
    result = []
    for node in nodes:
        start = _parse_dt(_text(node, "dateFrom"))
        end = _parse_dt(_text(node, "dateTo"))
        non_paid = _num(_text(node, "nonPaidMinutes"))
        minutes = max(0.0, _duration_minutes(start, end) - non_paid)
        pd = _payment_details(node)
        result.append({
            "id": _text(node, "id"),
            "employeeId": _text(node, "employeeId"),
            "roleId": _text(node, "roleId"),
            "departmentId": _text(node, "departmentId"),
            "departmentName": _text(node, "departmentName"),
            "scheduleTypeCode": _text(node, "scheduleTypeCode"),
            "dateFrom": start.isoformat() if start else "",
            "dateTo": end.isoformat() if end else "",
            "nonPaidMinutes": round(non_paid, 2),
            "minutes": round(minutes, 2),
            "paymentTotal": round(pd["regularPayment"] + pd["overtimePayment"] + pd["otherPayments"], 2),
            "paymentDetailsAvailable": pd["available"],
        })
    return result


def _department_key(value):
    return "".join(ch for ch in str(value or "").strip().casefold().replace("ё", "е") if ch.isalnum())


def _role_for(employee, role_id, roles_by_id, roles_by_code):
    role = roles_by_id.get(role_id) if role_id else None
    if not role:
        role = roles_by_id.get(employee.get("mainRoleId"))
    if not role:
        role = roles_by_code.get(employee.get("mainRoleCode"))
    return role or {}


def _build_plan_variance(attendance, schedules):
    by_employee = defaultdict(list)
    for item in attendance:
        by_employee[item.get("employeeId")].append(item)

    late_by_employee = defaultdict(float)
    early_by_employee = defaultdict(float)
    matched_by_employee = defaultdict(int)

    for schedule in schedules:
        employee_id = schedule.get("employeeId")
        start = _parse_dt(schedule.get("dateFrom"))
        end = _parse_dt(schedule.get("dateTo"))
        if not employee_id or not start or not end:
            continue
        candidates = []
        for att in by_employee.get(employee_id, []):
            att_start = _parse_dt(att.get("dateFrom"))
            att_end = _parse_dt(att.get("dateTo"))
            if not att_start:
                continue
            if att_start.date() != start.date():
                continue
            distance = abs((att_start - start).total_seconds())
            candidates.append((distance, att_start, att_end))
        if not candidates:
            continue
        candidates.sort(key=lambda x: x[0])
        _, att_start, att_end = candidates[0]
        matched_by_employee[employee_id] += 1
        late_by_employee[employee_id] += max(0.0, (att_start - start).total_seconds() / 60.0)
        if att_end:
            early_by_employee[employee_id] += max(0.0, (end - att_end).total_seconds() / 60.0)

    return late_by_employee, early_by_employee, matched_by_employee


def build_staff_analytics(date_from, date_to):
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    finish = datetime.strptime(date_to, "%Y-%m-%d").date()
    if finish < start:
        raise ValueError("date_to must be greater than or equal to date_from")
    days = (finish - start).days + 1
    if days > _MAX_DAYS:
        raise ValueError(f"Maximum period is {_MAX_DAYS} days")

    cache_key = (date_from, date_to)
    cached = _CACHE.get(cache_key)
    if cached and cached["expires_at"] > time.time():
        return cached["value"]

    try:
        current_departments = core.get_departments()
    except Exception:
        current_departments = []
    current_department_keys = {
        _department_key(item.get("name"))
        for item in current_departments
        if item.get("name")
    }

    base_url = token = None
    try:
        base_url, token = core.iiko_server_auth()

        employees_response = _server_get(base_url, token, "/api/employees", {"includeDeleted": "false"}, timeout=45)
        roles_response = _server_get(base_url, token, "/api/employees/roles", timeout=45)
        salary_response = _server_get(base_url, token, "/api/employees/salary", timeout=45)

        attendance_response = _server_get(
            base_url,
            token,
            "/api/employees/attendance",
            {"from": date_from, "to": date_to, "withPaymentDetails": "true"},
            timeout=75,
        )

        schedule_error = ""
        try:
            schedule_response = _server_get(
                base_url,
                token,
                "/api/employees/schedule/",
                {"from": date_from, "to": date_to, "withPaymentDetails": "true"},
                timeout=75,
            )
            schedule_nodes = _xml_nodes(schedule_response, "schedule")
        except Exception as error:
            schedule_nodes = []
            schedule_error = str(error)[:400]

        employees = _parse_employees(_xml_nodes(employees_response, "employee"))
        roles_by_id, roles_by_code = _parse_roles(_xml_nodes(roles_response, "role"))
        salaries = _parse_salaries(_xml_nodes(salary_response, "salary"))
        now = datetime.now(core.LOCAL_TZ)
        period_start, period_end = _period_bounds(date_from, date_to)
        attendance_all = _parse_attendance(_xml_nodes(attendance_response, "attendance"), now)
        schedules_all = _parse_schedule(schedule_nodes)
        attendance = [
            item for item in attendance_all
            if _attendance_in_period(item, period_start, period_end, now)
        ]
        schedules = [
            item for item in schedules_all
            if _schedule_in_period(item, period_start, period_end)
        ]

        late_by_employee, early_by_employee, matched_by_employee = _build_plan_variance(attendance, schedules)

        att_by_employee = defaultdict(list)
        sch_by_employee = defaultdict(list)
        for item in attendance:
            if item.get("employeeId"):
                att_by_employee[item["employeeId"]].append(item)
        for item in schedules:
            if item.get("employeeId"):
                sch_by_employee[item["employeeId"]].append(item)

        all_employee_ids = set(employees) | set(att_by_employee) | set(sch_by_employee)
        employee_rows = []

        total_minutes = 0.0
        total_paid_minutes = 0.0
        total_overtime_minutes = 0.0
        total_payment = 0.0
        employees_with_attendance = 0
        open_attendances = 0
        attendance_payment_rows = 0

        department_rollup = defaultdict(lambda: {
            "minutes": 0.0,
            "paidMinutes": 0.0,
            "payment": 0.0,
            "employees": set(),
            "attendances": 0,
        })
        role_rollup = defaultdict(lambda: {
            "minutes": 0.0,
            "payment": 0.0,
            "employees": set(),
            "attendances": 0,
        })

        for employee_id in all_employee_ids:
            employee = employees.get(employee_id, {
                "id": employee_id,
                "name": "Сотрудник iiko",
                "code": "",
                "mainRoleId": "",
                "mainRoleCode": "",
            })
            employee_att = sorted(att_by_employee.get(employee_id, []), key=lambda x: x.get("dateFrom") or "")
            employee_sch = sorted(sch_by_employee.get(employee_id, []), key=lambda x: x.get("dateFrom") or "")

            minutes = sum(x.get("minutes", 0) for x in employee_att)
            paid_minutes = sum(x.get("paidMinutes", 0) for x in employee_att)
            overtime_minutes = sum(x.get("overtimeMinutes", 0) for x in employee_att)
            payment = sum(x.get("paymentTotal", 0) for x in employee_att)
            planned_minutes = sum(x.get("minutes", 0) for x in employee_sch)
            open_count = sum(1 for x in employee_att if x.get("open"))
            payment_rows = sum(1 for x in employee_att if x.get("paymentDetailsAvailable"))

            if employee_att:
                employees_with_attendance += 1
            total_minutes += minutes
            total_paid_minutes += paid_minutes
            total_overtime_minutes += overtime_minutes
            total_payment += payment
            open_attendances += open_count
            attendance_payment_rows += payment_rows

            role_ids = [x.get("roleId") for x in employee_att if x.get("roleId")]
            role = _role_for(employee, role_ids[-1] if role_ids else "", roles_by_id, roles_by_code)
            salary = _current_salary(salaries.get(employee_id), date_to)

            departments = []
            for x in employee_att:
                name = x.get("departmentName") or "Без подразделения"
                if name not in departments:
                    departments.append(name)
                roll = department_rollup[name]
                roll["minutes"] += x.get("minutes", 0)
                roll["paidMinutes"] += x.get("paidMinutes", 0)
                roll["payment"] += x.get("paymentTotal", 0)
                roll["employees"].add(employee_id)
                roll["attendances"] += 1

            if employee_att:
                role_name = role.get("name") or employee.get("mainRoleCode") or "Без должности"
                r = role_rollup[role_name]
                r["minutes"] += minutes
                r["payment"] += payment
                r["employees"].add(employee_id)
                r["attendances"] += len(employee_att)

            last_attendance = employee_att[-1] if employee_att else None
            row = {
                "id": employee_id,
                "code": employee.get("code") or "",
                "name": employee.get("name") or "Сотрудник iiko",
                "role": role.get("name") or employee.get("mainRoleCode") or "—",
                "roleScheduleType": role.get("scheduleType") or "",
                "rolePaymentPerHour": round(_num(role.get("paymentPerHour")), 2),
                "roleSteadySalary": round(_num(role.get("steadySalary")), 2),
                "personalSalary": round(_num((salary or {}).get("payment")), 2) if salary else None,
                "departments": departments,
                "attendances": len(employee_att),
                "plannedShifts": len(employee_sch),
                "hours": round(minutes / 60.0, 2),
                "paidHours": round(paid_minutes / 60.0, 2),
                "overtimeHours": round(overtime_minutes / 60.0, 2),
                "plannedHours": round(planned_minutes / 60.0, 2),
                "payment": round(payment, 2),
                "effectivePaymentPerHour": round(payment / (minutes / 60.0), 2) if minutes > 0 and payment else None,
                "lateMinutes": round(late_by_employee.get(employee_id, 0.0), 1),
                "earlyLeaveMinutes": round(early_by_employee.get(employee_id, 0.0), 1),
                "matchedPlannedShifts": matched_by_employee.get(employee_id, 0),
                "openAttendances": open_count,
                "lastAttendanceFrom": last_attendance.get("dateFrom") if last_attendance else "",
                "lastAttendanceTo": last_attendance.get("dateTo") if last_attendance else "",
                "attendanceDetails": employee_att,
                "scheduleDetails": employee_sch,
            }
            employee_rows.append(row)

        employee_rows.sort(
            key=lambda x: (
                0 if x["attendances"] else 1,
                -x["hours"],
                x["name"].casefold(),
            )
        )

        departments = []
        for name, values in department_rollup.items():
            key = _department_key(name)
            current_in_iiko = key in current_department_keys if current_department_keys else None
            departments.append({
                "name": name,
                "employees": len(values["employees"]),
                "attendances": values["attendances"],
                "hours": round(values["minutes"] / 60.0, 2),
                "paidHours": round(values["paidMinutes"] / 60.0, 2),
                "payment": round(values["payment"], 2),
                "paymentPerHour": round(values["payment"] / (values["minutes"] / 60.0), 2)
                    if values["minutes"] > 0 and values["payment"] else None,
                "currentInIikoCloud": current_in_iiko,
            })
        departments.sort(key=lambda x: (-x["hours"], x["name"].casefold()))
        archived_departments = [
            item for item in departments
            if item.get("currentInIikoCloud") is False
        ]

        roles = []
        for name, values in role_rollup.items():
            roles.append({
                "name": name,
                "employees": len(values["employees"]),
                "attendances": values["attendances"],
                "hours": round(values["minutes"] / 60.0, 2),
                "payment": round(values["payment"], 2),
                "paymentPerHour": round(values["payment"] / (values["minutes"] / 60.0), 2)
                    if values["minutes"] > 0 and values["payment"] else None,
            })
        roles.sort(key=lambda x: (-x["hours"], x["name"].casefold()))

        total_hours = total_minutes / 60.0
        total_paid_hours = total_paid_minutes / 60.0
        total_overtime_hours = total_overtime_minutes / 60.0

        result = {
            "success": True,
            "source": "iikoServer employees/attendance/schedule",
            "period": {"from": date_from, "to": date_to, "days": days},
            "summary": {
                "directoryEmployees": len(employees),
                "employeesWithAttendance": employees_with_attendance,
                "attendanceRows": len(attendance),
                "actualHours": round(total_hours, 2),
                "paidHours": round(total_paid_hours, 2),
                "overtimeHours": round(total_overtime_hours, 2),
                "payment": round(total_payment, 2),
                "payrollAvailable": bool(total_payment > 0),
                "paymentPerActualHour": round(total_payment / total_hours, 2) if total_hours > 0 and total_payment else None,
                "averageAttendanceHours": round(total_hours / len(attendance), 2) if attendance else 0,
                "openAttendances": open_attendances,
                "paymentDetailRows": attendance_payment_rows,
                "plannedShifts": len(schedules),
                "plannedHours": round(sum(x.get("minutes", 0) for x in schedules) / 60.0, 2),
                "planAvailable": bool(schedules),
            },
            "employees": employee_rows,
            "departments": departments,
            "archivedDepartments": archived_departments,
            "roles": roles,
            "diagnostics": {
                "currentDepartmentNames": sorted(
                    item.get("name") for item in current_departments if item.get("name")
                ),
                "scheduleError": schedule_error,
                "salesByEmployeeAvailable": False,
                "rawAttendanceRows": len(attendance_all),
                "filteredAttendanceRows": len(attendance),
                "rawScheduleRows": len(schedules_all),
                "filteredScheduleRows": len(schedules),
                "note": "iiko SALES OLAP does not expose employee-linked sales fields for this installation.",
            },
        }

        _CACHE[cache_key] = {
            "value": result,
            "expires_at": time.time() + _CACHE_TTL,
        }
        if len(_CACHE) > 30:
            for key in sorted(_CACHE, key=lambda k: _CACHE[k]["expires_at"])[:10]:
                _CACHE.pop(key, None)
        return result
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def install_staff_analytics(app):
    if getattr(app, "_doner_staff_analytics_installed", False):
        return
    app._doner_staff_analytics_installed = True

    @app.route("/staff-analytics", methods=["GET"], endpoint="staff_analytics_api")
    def staff_analytics_api():
        try:
            today = datetime.now(core.LOCAL_TZ).date()
            date_to = request.args.get("to") or today.isoformat()
            date_from = request.args.get("from") or (today - timedelta(days=6)).isoformat()
            return jsonify(build_staff_analytics(date_from, date_to))
        except ValueError as error:
            return jsonify({"success": False, "code": "INVALID_PERIOD", "message": str(error)}), 400
        except requests.Timeout:
            return jsonify({
                "success": False,
                "code": "IIKO_TIMEOUT",
                "message": "iikoServer не успел ответить. Повторите запрос.",
            }), 504
        except requests.HTTPError as error:
            response = error.response
            return jsonify({
                "success": False,
                "code": "IIKO_HTTP_ERROR",
                "statusCode": response.status_code if response is not None else None,
                "details": response.text[:1200] if response is not None else str(error),
            }), 502
        except Exception as error:
            return jsonify({
                "success": False,
                "code": "STAFF_ANALYTICS_ERROR",
                "message": str(error),
            }), 500
