import json
import os
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta

import requests
from flask import jsonify, session

import app as core


STATE_FILE = "/tmp/doner-club-stop-state.json"
STOP_TTL_SECONDS = 2 * 60
HISTORY_DAYS = 28
_cache = {}
_cache_lock = threading.Lock()
_state_lock = threading.Lock()


def _cache_get(key):
    with _cache_lock:
        item = _cache.get(key)
        if not item or item["expires_at"] <= time.time():
            if item:
                _cache.pop(key, None)
            return None
        return item["value"]


def _cache_set(key, value):
    with _cache_lock:
        _cache[key] = {"value": value, "expires_at": time.time() + STOP_TTL_SECONDS}
        if len(_cache) > 40:
            oldest = sorted(_cache, key=lambda k: _cache[k]["expires_at"])[:10]
            for old in oldest:
                _cache.pop(old, None)


def _load_state():
    with _state_lock:
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as fh:
                value = json.load(fh)
                return value if isinstance(value, dict) else {}
        except Exception:
            return {}


def _save_state(value):
    with _state_lock:
        try:
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(value, fh, ensure_ascii=False)
            os.replace(tmp, STATE_FILE)
        except Exception:
            pass


def _parse_dt(value):
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=core.LOCAL_TZ)
        return parsed.astimezone(core.LOCAL_TZ)
    except (ValueError, TypeError):
        return None


def _timestamp_from_node(node):
    if not isinstance(node, dict):
        return None
    keys = (
        "stopSince", "since", "startTime", "createdAt", "createTime", "dateAdd",
        "addedAt", "dateFrom", "timestamp", "creationTime",
    )
    for key in keys:
        parsed = _parse_dt(node.get(key))
        if parsed:
            return parsed
    return None


def _flatten_stop_items(payload):
    found = []

    def walk(value, terminal_group_id=None, inherited_time=None):
        if isinstance(value, dict):
            terminal = value.get("terminalGroupId") or terminal_group_id
            stamp = _timestamp_from_node(value) or inherited_time
            product_id = value.get("productId")
            if product_id:
                balance_raw = value.get("balance")
                try:
                    balance = float(balance_raw) if balance_raw is not None else None
                except (TypeError, ValueError):
                    balance = None
                found.append({
                    "productId": str(product_id),
                    "terminalGroupId": terminal,
                    "balance": balance,
                    "sourceTime": stamp.isoformat() if stamp else None,
                })
            for child in value.values():
                if isinstance(child, (dict, list)):
                    walk(child, terminal, stamp)
        elif isinstance(value, list):
            for child in value:
                walk(child, terminal_group_id, inherited_time)

    walk(payload)

    # One menu position can be present for several terminal groups. For the point-level
    # dashboard it is enough to show it once. A zero/negative balance wins over a positive one.
    by_product = {}
    for item in found:
        pid = item["productId"]
        existing = by_product.get(pid)
        if not existing:
            by_product[pid] = item
            continue
        a = existing.get("balance")
        b = item.get("balance")
        if b is None or (a is not None and b <= a):
            by_product[pid] = item
    return list(by_product.values())


def _current_stop_list(organization_id):
    response = core.iiko_post(
        "/api/1/stop_lists",
        {"organizationIds": [organization_id]},
        timeout=30,
    )
    response.raise_for_status()
    return _flatten_stop_items(response.json())


def _iiko_server_history(point, product_ids, start_date, end_date):
    if not product_ids:
        return []
    base_url = None
    token = None
    try:
        base_url, token = core.iiko_server_auth()
        departments = core.iiko_server_departments(base_url, token)
        department = core.find_iiko_server_department(point, departments)
        if not department:
            return []
        filters = {
            "OpenDate.Typed": {
                "filterType": "DateRange",
                "periodType": "CUSTOM",
                "from": start_date,
                "to": end_date,
                "includeLow": True,
                "includeHigh": True,
            },
            "OrderDeleted": {
                "filterType": "IncludeValues",
                "values": ["NOT_DELETED"],
            },
            "Department.Id": {
                "filterType": "IncludeValues",
                "values": [department.get("id")],
            },
            "DishId": {
                "filterType": "IncludeValues",
                "values": list(product_ids),
            },
        }
        body = {
            "reportType": "SALES",
            "buildSummary": False,
            "groupByRowFields": ["CloseTime", "DishId", "DishName"],
            "groupByColFields": [],
            "aggregateFields": ["DishAmountInt", "DishDiscountSumInt", "Cost"],
            "filters": filters,
        }
        response = requests.post(
            f"{base_url}/api/v2/reports/olap",
            params={"key": token},
            json=body,
            headers={"Content-Type": "application/json"},
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", []) if isinstance(payload, dict) else []
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def _history_stats(rows, history_start, history_end):
    qty_by_slot = defaultdict(float)
    totals = defaultdict(lambda: {"qty": 0.0, "revenue": 0.0, "cost": 0.0, "name": None})
    start = datetime.strptime(history_start, "%Y-%m-%d").date()
    end = datetime.strptime(history_end, "%Y-%m-%d").date()
    weekday_occurrences = defaultdict(int)
    day = start
    while day <= end:
        weekday_occurrences[day.weekday()] += 1
        day += timedelta(days=1)

    for row in rows:
        pid = str(row.get("DishId") or "")
        if not pid:
            continue
        close_time = _parse_dt(row.get("CloseTime"))
        qty = float(row.get("DishAmountInt") or 0)
        revenue = float(row.get("DishDiscountSumInt") or 0)
        cost = float(row.get("Cost") or 0)
        if close_time:
            qty_by_slot[(pid, close_time.weekday(), close_time.hour)] += qty
        item = totals[pid]
        item["qty"] += qty
        item["revenue"] += revenue
        item["cost"] += cost
        item["name"] = item["name"] or row.get("DishName")

    return qty_by_slot, totals, weekday_occurrences


def _expected_units(pid, start_at, end_at, qty_by_slot, weekday_occurrences):
    if end_at <= start_at:
        return 0.0
    cursor = start_at
    expected = 0.0
    while cursor < end_at:
        next_hour = cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        segment_end = min(next_hour, end_at)
        hours = (segment_end - cursor).total_seconds() / 3600.0
        weekday = cursor.weekday()
        denominator = max(weekday_occurrences.get(weekday, 0), 1)
        avg_qty_hour = qty_by_slot.get((pid, weekday, cursor.hour), 0.0) / denominator
        expected += avg_qty_hour * hours
        cursor = segment_end
    return expected


def build_stop_loss(point):
    point = (point or "Arai").strip()
    cache_key = point.lower()
    cached = _cache_get(cache_key)
    if cached is not None:
        result = dict(cached)
        result["cache"] = {"hit": True, "ttlSeconds": STOP_TTL_SECONDS}
        return result

    department, available = core.find_department(point)
    if not department:
        raise ValueError(f"Point '{point}' not found")
    organization_id = department.get("organizationId")
    raw_items = _current_stop_list(organization_id)

    # Positive balance means the item is limited, but not fully stopped yet.
    active = [item for item in raw_items if item.get("balance") is None or item.get("balance") <= 0]
    limited = [item for item in raw_items if item.get("balance") is not None and item.get("balance") > 0]

    now = datetime.now(core.LOCAL_TZ)
    state = _load_state()
    org_state = state.setdefault(organization_id, {})
    active_ids = {item["productId"] for item in active}
    for pid in list(org_state.keys()):
        if pid not in active_ids:
            org_state.pop(pid, None)

    for item in active:
        pid = item["productId"]
        source_time = _parse_dt(item.get("sourceTime"))
        if source_time:
            org_state[pid] = source_time.isoformat()
        elif pid not in org_state:
            org_state[pid] = now.isoformat()
    _save_state(state)

    product_map = core.get_products_map()
    history_end = (now.date() - timedelta(days=1))
    history_start = history_end - timedelta(days=HISTORY_DAYS - 1)
    rows = _iiko_server_history(
        point,
        active_ids,
        history_start.isoformat(),
        history_end.isoformat(),
    )
    qty_by_slot, totals, weekday_occurrences = _history_stats(
        rows, history_start.isoformat(), history_end.isoformat()
    )

    items = []
    total_lost_revenue = 0.0
    total_lost_gross_profit = 0.0
    total_expected_units = 0.0

    for item in active:
        pid = item["productId"]
        since = _parse_dt(org_state.get(pid)) or now
        expected_units = _expected_units(pid, since, now, qty_by_slot, weekday_occurrences)
        hist = totals.get(pid, {})
        hist_qty = float(hist.get("qty", 0) or 0)
        avg_price = float(hist.get("revenue", 0) or 0) / hist_qty if hist_qty else 0.0
        avg_cost = float(hist.get("cost", 0) or 0) / hist_qty if hist_qty else 0.0
        lost_revenue = expected_units * avg_price
        lost_gp = expected_units * max(avg_price - avg_cost, 0)
        duration_minutes = max(int((now - since).total_seconds() // 60), 0)
        name = (product_map.get(pid) or {}).get("name") or hist.get("name") or "Позиция iiko"
        items.append({
            "productId": pid,
            "name": name,
            "balance": item.get("balance"),
            "observedSince": since.isoformat(),
            "durationMinutes": duration_minutes,
            "expectedUnits": round(expected_units, 2),
            "averagePrice": round(avg_price, 2),
            "averageCost": round(avg_cost, 2),
            "estimatedLostRevenue": round(lost_revenue, 2),
            "estimatedLostGrossProfit": round(lost_gp, 2),
            "historyQty": round(hist_qty, 2),
        })
        total_expected_units += expected_units
        total_lost_revenue += lost_revenue
        total_lost_gross_profit += lost_gp

    items.sort(key=lambda x: x["estimatedLostRevenue"], reverse=True)
    limited_items = []
    for item in limited:
        pid = item["productId"]
        name = (product_map.get(pid) or {}).get("name") or "Позиция iiko"
        limited_items.append({"productId": pid, "name": name, "balance": item.get("balance")})

    result = {
        "success": True,
        "source": "iikoCloud stop_lists + iikoServer SALES history",
        "point": {"code": department.get("code"), "name": department.get("name")},
        "checkedAt": now.isoformat(),
        "history": {"from": history_start.isoformat(), "to": history_end.isoformat(), "days": HISTORY_DAYS},
        "summary": {
            "stoppedPositions": len(items),
            "limitedPositions": len(limited_items),
            "expectedLostUnits": round(total_expected_units, 2),
            "estimatedLostRevenue": round(total_lost_revenue, 2),
            "estimatedLostGrossProfit": round(total_lost_gross_profit, 2),
        },
        "items": items,
        "limited": limited_items,
        "trackingNote": (
            "If iiko does not provide the stop start time, duration is counted from the first time "
            "this dashboard detected the position in the stop list. The local tracker resets if the Render instance restarts."
        ),
        "cache": {"hit": False, "ttlSeconds": STOP_TTL_SECONDS},
    }
    _cache_set(cache_key, result)
    return result


def install_stop_loss(app):
    if getattr(app, "_doner_stop_loss_installed", False):
        return
    app._doner_stop_loss_installed = True

    @app.before_request
    def _protect_stop_loss_api():
        if core.request.path == "/stop-loss" and not session.get("dc_authenticated"):
            return jsonify({
                "success": False,
                "code": "AUTH_REQUIRED",
                "message": "Authentication required",
                "login": "/login",
            }), 401
        return None

    @app.route("/stop-loss")
    def stop_loss():
        try:
            point = (core.request.args.get("point") or "Arai").strip()
            return jsonify(build_stop_loss(point))
        except requests.HTTPError as error:
            response = error.response
            return jsonify({
                "success": False,
                "code": "STOP_LIST_API_ERROR",
                "statusCode": response.status_code if response is not None else None,
                "details": response.text[:1200] if response is not None else str(error),
            }), 502
        except ValueError as error:
            return jsonify({"success": False, "code": "STOP_LIST_INVALID", "message": str(error)}), 400
        except Exception as error:
            return jsonify({"success": False, "code": "STOP_LIST_ERROR", "message": str(error)}), 500

    @app.after_request
    def _inject_stop_loss(response):
        if (
            core.request.path.endswith("dashboard-v2.html")
            and response.status_code == 200
            and response.mimetype == "text/html"
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/stop-loss.js"></script>'
                if tag not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
