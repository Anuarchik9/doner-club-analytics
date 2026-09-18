import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests
from flask import jsonify

import app as core


def _json_list(payload, preferred=()):
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in preferred:
            value = payload.get(key)
            if isinstance(value, list):
                # Some endpoints wrap per-org containers.
                flattened = []
                for item in value:
                    if isinstance(item, dict) and isinstance(item.get("items"), list):
                        flattened.extend(x for x in item["items"] if isinstance(x, dict))
                    elif isinstance(item, dict):
                        flattened.append(item)
                return flattened
    return []


def _schema_from_json(items):
    if not items:
        return []
    keys = set()
    for item in items[:5]:
        if isinstance(item, dict):
            keys.update(str(k) for k in item.keys())
    return sorted(keys)


def _xml_probe(response, tag):
    if not response.ok:
        return {
            "ok": False,
            "status": response.status_code,
            "error": response.text[:300],
            "count": 0,
            "fields": [],
        }
    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        return {
            "ok": False,
            "status": response.status_code,
            "error": "Non-XML response",
            "count": 0,
            "fields": [],
        }
    nodes = [n for n in root.iter() if n.tag.split("}")[-1] == tag]
    fields = []
    if nodes:
        fields = sorted({child.tag.split("}")[-1] for child in list(nodes[0])})
    return {
        "ok": True,
        "status": response.status_code,
        "count": len(nodes),
        "fields": fields,
    }


def _cloud_probe(path, payload, preferred):
    response = core.iiko_post(path, payload, timeout=45)
    try:
        data = response.json()
    except Exception:
        data = {}
    rows = _json_list(data, preferred)
    return {
        "ok": response.ok,
        "status": response.status_code,
        "count": len(rows),
        "fields": _schema_from_json(rows),
        "error": "" if response.ok else str(data or response.text[:300])[:300],
    }


def build_staff_capability_check():
    departments = core.get_departments()
    organization_ids = sorted({
        d.get("organizationId")
        for d in departments
        if d.get("organizationId")
    })
    today = datetime.now(core.LOCAL_TZ).date()
    date_from = (today - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00.000")
    date_to = today.strftime("%Y-%m-%d 23:59:59.000")
    day_from = (today - timedelta(days=7)).isoformat()
    day_to = today.isoformat()

    result = {
        "success": True,
        "period": {"from": day_from, "to": day_to},
        "organizations": len(organization_ids),
        "cloud": {},
        "server": {},
        "salesOlap": {},
    }

    # iikoCloud staff APIs.
    try:
        result["cloud"]["employees"] = _cloud_probe(
            "/api/1/employees/info",
            {"organizationIds": organization_ids},
            ("employees",),
        )
    except Exception as error:
        result["cloud"]["employees"] = {"ok": False, "status": None, "count": 0, "fields": [], "error": str(error)[:300]}

    try:
        result["cloud"]["shifts"] = _cloud_probe(
            "/api/1/employees/shift",
            {"organizationIds": organization_ids, "dateFrom": date_from, "dateTo": date_to},
            ("shifts",),
        )
    except Exception as error:
        result["cloud"]["shifts"] = {"ok": False, "status": None, "count": 0, "fields": [], "error": str(error)[:300]}

    try:
        result["cloud"]["schedule"] = _cloud_probe(
            "/api/1/employees/schedule",
            {"organizationIds": organization_ids, "from": date_from, "to": date_to},
            ("schedules", "items"),
        )
    except Exception as error:
        result["cloud"]["schedule"] = {"ok": False, "status": None, "count": 0, "fields": [], "error": str(error)[:300]}

    # iikoServer staff APIs.
    base_url = token = None
    try:
        base_url, token = core.iiko_server_auth()

        def get(path, params=None, timeout=45):
            query = {"key": token}
            if params:
                query.update(params)
            return requests.get(f"{base_url}{path}", params=query, timeout=timeout)

        result["server"]["employees"] = _xml_probe(
            get("/api/employees", {"includeDeleted": "false"}),
            "employee",
        )
        result["server"]["roles"] = _xml_probe(
            get("/api/employees/roles"),
            "role",
        )
        result["server"]["salary"] = _xml_probe(
            get("/api/employees/salary"),
            "salary",
        )

        attendance_with_pay = get(
            "/api/employees/attendance",
            {"from": day_from, "to": day_to, "withPaymentDetails": "true"},
            timeout=60,
        )
        attendance_probe = _xml_probe(attendance_with_pay, "attendance")
        if not attendance_probe["ok"]:
            fallback = get(
                "/api/employees/attendance",
                {"from": day_from, "to": day_to, "withPaymentDetails": "false"},
                timeout=60,
            )
            basic = _xml_probe(fallback, "attendance")
            basic["paymentDetailsAvailable"] = False
            basic["paymentDetailsError"] = attendance_probe.get("error", "")
            attendance_probe = basic
        else:
            attendance_probe["paymentDetailsAvailable"] = "paymentDetails" in attendance_probe.get("fields", [])
        result["server"]["attendance"] = attendance_probe

        schedule_with_pay = get(
            "/api/employees/schedule/",
            {"from": day_from, "to": day_to, "withPaymentDetails": "true"},
            timeout=60,
        )
        schedule_probe = _xml_probe(schedule_with_pay, "schedule")
        if not schedule_probe["ok"]:
            fallback = get(
                "/api/employees/schedule/",
                {"from": day_from, "to": day_to, "withPaymentDetails": "false"},
                timeout=60,
            )
            basic = _xml_probe(fallback, "schedule")
            basic["paymentDetailsAvailable"] = False
            basic["paymentDetailsError"] = schedule_probe.get("error", "")
            schedule_probe = basic
        else:
            schedule_probe["paymentDetailsAvailable"] = "paymentDetails" in schedule_probe.get("fields", [])
        result["server"]["schedule"] = schedule_probe

        # SALES OLAP capability only: report field names, never employee values.
        columns = requests.get(
            f"{base_url}/api/v2/reports/olap/columns",
            params={"key": token, "reportType": "SALES"},
            timeout=35,
        )
        if columns.ok:
            payload = columns.json()
            def walk_fields(value, out):
                if isinstance(value, dict):
                    name = value.get("name") or value.get("fieldName") or value.get("id")
                    if isinstance(name, str):
                        low = name.lower()
                        if any(t in low for t in ("waiter", "cashier", "employee", "operator", "user", "courier")):
                            out.add(name)
                    for child in value.values():
                        if isinstance(child, (dict, list)):
                            walk_fields(child, out)
                elif isinstance(value, list):
                    for child in value:
                        walk_fields(child, out)
            fields = set()
            walk_fields(payload, fields)
            result["salesOlap"] = {"ok": True, "status": columns.status_code, "employeeFields": sorted(fields)}
        else:
            result["salesOlap"] = {"ok": False, "status": columns.status_code, "employeeFields": [], "error": columns.text[:300]}

    except Exception as error:
        result["server"]["error"] = str(error)[:500]
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)

    # Capability summary, without any personal data.
    emp = result["server"].get("employees") or result["cloud"].get("employees") or {}
    att = result["server"].get("attendance") or {}
    sch = result["server"].get("schedule") or result["cloud"].get("schedule") or {}
    roles = result["server"].get("roles") or {}
    salary = result["server"].get("salary") or {}
    result["capabilities"] = {
        "employeeDirectory": bool(emp.get("ok")),
        "actualHours": bool(att.get("ok")),
        "plannedSchedule": bool(sch.get("ok")),
        "roles": bool(roles.get("ok")),
        "payRatesOrSalary": bool(salary.get("ok")) or bool(roles.get("ok") and any(x in roles.get("fields", []) for x in ("paymentPerHour", "steadySalary"))),
        "paymentDetails": bool(att.get("paymentDetailsAvailable") or sch.get("paymentDetailsAvailable")),
        "salesByEmployeePossible": bool((result.get("salesOlap") or {}).get("employeeFields")),
    }
    return result


def install_staff_diagnostics(app):
    if getattr(app, "_doner_staff_diagnostics_installed", False):
        return
    app._doner_staff_diagnostics_installed = True

    @app.route("/staff-capability-check-20260919", methods=["GET"], endpoint="staff_capability_check_temp")
    def staff_capability_check_temp():
        return jsonify(build_staff_capability_check())
