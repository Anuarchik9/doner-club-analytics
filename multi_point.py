"""Multi-point support for the Doner Club management dashboard.

The native APIs were originally written for one iiko department at a time.  This
module keeps that contract for single-point requests and adds a compact `||`
point-spec for combined reports (for example `Arai||Republic`).  OLAP endpoints
can query several department ids in one request; inventory-document analytics
and stop-list analytics are merged from the existing, well-tested single-point
builders.
"""

from collections import defaultdict

import requests

import app as core
import sales_channel
import stop_loss


POINT_SEPARATOR = "||"


def _points(value):
    raw = str(value or "").strip()
    parts = [part.strip() for part in raw.split(POINT_SEPARATOR) if part.strip()]
    if not parts:
        parts = ["Arai"]
    result = []
    seen = set()
    for part in parts:
        key = part.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(part)
    return result


def _pretty_name(value):
    text = str(value or "").strip()
    lowered = text.casefold()
    if "республика" in lowered or "republic" in lowered:
        return "Республика"
    return text


def _combined_name(items):
    names = []
    seen = set()
    for item in items:
        name = _pretty_name((item or {}).get("name") or (item or {}).get("code") or "Точка")
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            names.append(name)
    return " + ".join(names) if names else "Выбранные точки"


def _merge_products(payloads):
    merged = {}
    for payload in payloads:
        for item in payload.get("products") or []:
            key = str(item.get("productId") or item.get("name") or item.get("article") or "unknown")
            row = merged.setdefault(key, {
                "productId": item.get("productId") or key,
                "name": item.get("name") or "Позиция iiko",
                "article": item.get("article"),
                "quantity": 0.0,
                "revenue": 0.0,
            })
            row["quantity"] += float(item.get("quantity") or 0)
            row["revenue"] += float(item.get("revenue") or 0)
            if not row.get("article") and item.get("article"):
                row["article"] = item.get("article")
            if (not row.get("name") or row.get("name") == "Позиция iiko") and item.get("name"):
                row["name"] = item.get("name")
    result = []
    for row in merged.values():
        row["quantity"] = round(row["quantity"], 3)
        row["revenue"] = round(row["revenue"], 2)
        result.append(row)
    result.sort(key=lambda x: x["revenue"], reverse=True)
    return result


def _merge_daily(payloads, date_from, date_to):
    days = {
        day: {"date": day, "revenue": 0.0, "itemsRevenue": 0.0, "quantity": 0.0, "documentsCount": 0}
        for day in core.date_range(date_from, date_to)
    }
    for payload in payloads:
        for item in payload.get("daily") or []:
            day = item.get("date")
            if not day:
                continue
            row = days.setdefault(day, {"date": day, "revenue": 0.0, "itemsRevenue": 0.0, "quantity": 0.0, "documentsCount": 0})
            row["revenue"] += float(item.get("revenue") or 0)
            row["itemsRevenue"] += float(item.get("itemsRevenue") or 0)
            row["quantity"] += float(item.get("quantity") or 0)
            row["documentsCount"] += int(item.get("documentsCount") or 0)
    return [
        {
            "date": row["date"],
            "revenue": round(row["revenue"], 2),
            "itemsRevenue": round(row["itemsRevenue"], 2),
            "quantity": round(row["quantity"], 3),
            "documentsCount": row["documentsCount"],
        }
        for _, row in sorted(days.items())
    ]


def install_multi_point(app):
    if getattr(app, "_doner_multi_point_installed", False):
        return
    app._doner_multi_point_installed = True

    original_build_analytics = core.build_analytics
    original_find_server_department = core.find_iiko_server_department
    original_run_server_olap = core.run_iiko_server_olap
    original_channel_olap = sales_channel._olap_request
    original_stop_loss = stop_loss.build_stop_loss

    def find_server_department_multi(point, departments):
        requested = _points(point)
        if len(requested) == 1:
            return original_find_server_department(requested[0], departments)

        matched = []
        for value in requested:
            department = original_find_server_department(value, departments)
            if not department:
                return None
            matched.append(department)
        ids = []
        for department in matched:
            value = department.get("id")
            if value and value not in ids:
                ids.append(value)
        return {
            "id": ids,
            "code": POINT_SEPARATOR.join(str(d.get("code") or d.get("name") or "") for d in matched),
            "name": _combined_name(matched),
            "parentId": None,
            "multiple": True,
            "points": matched,
        }

    def channel_olap_multi(base_url, token, date_from, date_to, department_id, group_fields, aggregate_fields):
        ids = list(department_id) if isinstance(department_id, (list, tuple, set)) else [department_id]
        ids = [value for value in ids if value]
        if len(ids) <= 1:
            return original_channel_olap(base_url, token, date_from, date_to, ids[0] if ids else None, group_fields, aggregate_fields)
        filters = {
            "OpenDate.Typed": {
                "filterType": "DateRange", "periodType": "CUSTOM", "from": date_from, "to": date_to,
                "includeLow": True, "includeHigh": True,
            },
            "OrderDeleted": {"filterType": "IncludeValues", "values": ["NOT_DELETED"]},
            "Department.Id": {"filterType": "IncludeValues", "values": ids},
        }
        body = {
            "reportType": "SALES",
            "buildSummary": False,
            "groupByRowFields": group_fields,
            "groupByColFields": [],
            "aggregateFields": aggregate_fields,
            "filters": filters,
        }
        response = requests.post(
            f"{base_url}/api/v2/reports/olap",
            params={"key": token}, json=body,
            headers={"Content-Type": "application/json"}, timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", []) if isinstance(payload, dict) else []

    def run_server_olap_multi(base_url, token, date_from, date_to, department_id=None):
        ids = list(department_id) if isinstance(department_id, (list, tuple, set)) else ([department_id] if department_id else [])
        ids = [value for value in ids if value]
        if len(ids) <= 1:
            return original_run_server_olap(base_url, token, date_from, date_to, ids[0] if ids else None)
        filters = {
            "OpenDate.Typed": {
                "filterType": "DateRange", "periodType": "CUSTOM", "from": date_from, "to": date_to,
                "includeLow": True, "includeHigh": True,
            },
            "OrderDeleted": {"filterType": "IncludeValues", "values": ["NOT_DELETED"]},
            "Department.Id": {"filterType": "IncludeValues", "values": ids},
        }
        body = {
            "reportType": "SALES",
            "buildSummary": False,
            "groupByRowFields": ["Department.Id", "CloseTime"],
            "groupByColFields": [],
            "aggregateFields": ["GuestNum", "DishDiscountSumInt.average", "DishDiscountSumInt", "UniqOrderId"],
            "filters": filters,
        }
        response = requests.post(
            f"{base_url}/api/v2/reports/olap",
            params={"key": token}, json=body,
            headers={"Content-Type": "application/json"}, timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def build_analytics_multi(point, date_from, date_to):
        requested = _points(point)
        if len(requested) == 1:
            return original_build_analytics(requested[0], date_from, date_to)

        payloads = []
        for value in requested:
            payload, error_payload, status = original_build_analytics(value, date_from, date_to)
            if error_payload:
                return None, error_payload, status
            payloads.append(payload)

        products = _merge_products(payloads)
        daily = _merge_daily(payloads, date_from, date_to)
        days_count = len(core.date_range(date_from, date_to))
        points_meta = [payload.get("point") or {} for payload in payloads]
        revenue = round(sum(float((p.get("summary") or {}).get("revenue") or 0) for p in payloads), 2)
        items_revenue = round(sum(float((p.get("summary") or {}).get("itemsRevenue") or 0) for p in payloads), 2)
        quantity = round(sum(float((p.get("summary") or {}).get("itemsQuantity") or 0) for p in payloads), 3)
        documents = sum(int((p.get("summary") or {}).get("documentsCount") or 0) for p in payloads)

        warnings = []
        document_warnings = []
        for payload in payloads:
            point_name = _pretty_name((payload.get("point") or {}).get("name") or (payload.get("point") or {}).get("code"))
            w = payload.get("warnings") or {}
            if w.get("nomenclature"):
                warnings.append(f"{point_name}: {w.get('nomenclature')}")
            for item in w.get("documentDetails") or []:
                row = dict(item)
                row["point"] = point_name
                document_warnings.append(row)

        result = {
            "success": True,
            "point": {
                "code": POINT_SEPARATOR.join(str((p or {}).get("code") or "") for p in points_meta),
                "name": _combined_name(points_meta),
                "organizationIds": [(p or {}).get("organizationId") for p in points_meta],
                "multiple": True,
                "points": points_meta,
            },
            "period": {"from": date_from, "to": date_to, "daysCount": days_count},
            "summary": {
                "documentsCount": documents,
                "revenue": revenue,
                "itemsRevenue": items_revenue,
                "itemsQuantity": quantity,
                "uniqueProducts": len(products),
                "averageDailyRevenue": round(revenue / days_count, 2) if days_count else 0,
            },
            "daily": daily,
            "topByRevenue": products[:20],
            "topByQuantity": sorted(products, key=lambda x: x["quantity"], reverse=True)[:20],
            "products": products,
            "warnings": {
                "nomenclature": " | ".join(warnings) if warnings else None,
                "documentDetails": document_warnings,
                "note": "Combined report for selected iiko departments.",
            },
            "performance": {
                "detailWorkers": sum(int((p.get("performance") or {}).get("detailWorkers") or 0) for p in payloads),
                "detailsRequested": sum(int((p.get("performance") or {}).get("detailsRequested") or 0) for p in payloads),
                "detailsLoaded": sum(int((p.get("performance") or {}).get("detailsLoaded") or 0) for p in payloads),
            },
            "cache": {"hit": all(bool((p.get("cache") or {}).get("hit")) for p in payloads), "ttlSeconds": core.ANALYTICS_TTL_SECONDS},
        }
        return result, None, 200

    def build_stop_loss_multi(point):
        requested = _points(point)
        if len(requested) == 1:
            return original_stop_loss(requested[0])
        payloads = [original_stop_loss(value) for value in requested]
        points_meta = [p.get("point") or {} for p in payloads]
        items = []
        limited = []
        for payload in payloads:
            label = _pretty_name((payload.get("point") or {}).get("name") or (payload.get("point") or {}).get("code"))
            for source in payload.get("items") or []:
                row = dict(source)
                row["point"] = label
                row["name"] = f"{row.get('name') or 'Позиция iiko'} · {label}"
                items.append(row)
            for source in payload.get("limited") or []:
                row = dict(source)
                row["point"] = label
                row["name"] = f"{row.get('name') or 'Позиция iiko'} · {label}"
                limited.append(row)
        items.sort(key=lambda x: float(x.get("estimatedLostRevenue") or 0), reverse=True)
        gp_values = [(p.get("summary") or {}).get("estimatedLostGrossProfit") for p in payloads]
        return {
            "success": True,
            "source": "Combined iikoCloud stop_lists + iikoServer SALES history",
            "costField": payloads[0].get("costField") if payloads else None,
            "point": {"name": _combined_name(points_meta), "multiple": True, "points": points_meta},
            "checkedAt": max((p.get("checkedAt") or "" for p in payloads), default=""),
            "history": payloads[0].get("history") if payloads else {},
            "summary": {
                "stoppedPositions": sum(int((p.get("summary") or {}).get("stoppedPositions") or 0) for p in payloads),
                "limitedPositions": sum(int((p.get("summary") or {}).get("limitedPositions") or 0) for p in payloads),
                "expectedLostUnits": round(sum(float((p.get("summary") or {}).get("expectedLostUnits") or 0) for p in payloads), 2),
                "estimatedLostRevenue": round(sum(float((p.get("summary") or {}).get("estimatedLostRevenue") or 0) for p in payloads), 2),
                "estimatedLostGrossProfit": round(sum(float(v or 0) for v in gp_values), 2) if all(v is not None for v in gp_values) else None,
            },
            "items": items,
            "limited": limited,
            "trackingNote": "Combined stop-list view for the selected points; each position keeps its source point in the label.",
            "cache": {"hit": all(bool((p.get("cache") or {}).get("hit")) for p in payloads), "ttlSeconds": stop_loss.STOP_TTL_SECONDS},
        }

    core.find_iiko_server_department = find_server_department_multi
    core.run_iiko_server_olap = run_server_olap_multi
    core.build_analytics = build_analytics_multi
    sales_channel._olap_request = channel_olap_multi
    stop_loss.build_stop_loss = build_stop_loss_multi

    @app.after_request
    def _inject_multi_point(response):
        if (
            response.status_code == 200
            and response.mimetype == "text/html"
            and core.request.path.endswith("dashboard-v2.html")
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/point-multiselect.js?v=20260917-1"></script>'
                if "point-multiselect.js" not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
