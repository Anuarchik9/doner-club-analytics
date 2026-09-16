import threading
import time

import requests
from flask import jsonify, session

import app as core
import sales_channel


TTL_SECONDS = 5 * 60
_field_cache = {"field": None, "label": None, "expires_at": 0.0}
_data_cache = {}
_lock = threading.Lock()


def _entries(payload):
    if isinstance(payload, dict):
        direct = []
        for key, value in payload.items():
            if isinstance(value, dict) and any(
                k in value for k in ("name", "groupingAllowed", "aggregationAllowed", "filteringAllowed")
            ):
                direct.append((str(key), value))
        if direct:
            return direct
        for value in payload.values():
            found = _entries(value)
            if found:
                return found
    elif isinstance(payload, list):
        result = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            field = item.get("id") or item.get("field") or item.get("fieldName") or item.get("key")
            if field:
                result.append((str(field), item))
        if result:
            return result
    return []


def discover_cashier_field(base_url, token):
    now = time.time()
    if _field_cache.get("field") and _field_cache.get("expires_at", 0) > now:
        return _field_cache["field"], _field_cache.get("label")

    with _lock:
        if _field_cache.get("field") and _field_cache.get("expires_at", 0) > time.time():
            return _field_cache["field"], _field_cache.get("label")
        response = requests.get(
            f"{base_url}/api/v2/reports/olap/columns",
            params={"key": token, "reportType": "SALES"},
            timeout=30,
        )
        response.raise_for_status()
        entries = _entries(response.json())
        by_id = {field: meta for field, meta in entries}
        candidates = (
            "Cashier",
            "Cashier.Name",
            "OrderCashier",
            "OrderCashier.Name",
            "CashierName",
        )
        chosen = None
        for field in candidates:
            meta = by_id.get(field)
            if meta and meta.get("groupingAllowed", True):
                chosen = (field, str(meta.get("name") or field))
                break
        if not chosen:
            scored = []
            for field, meta in entries:
                if meta.get("groupingAllowed") is False:
                    continue
                label = str(meta.get("name") or "")
                text = f"{field} {label}".lower()
                if "кассир" not in text and "cashier" not in text:
                    continue
                score = 0
                if label.strip().lower() == "кассир":
                    score += 100
                if "name" in field.lower() or "имя" in text:
                    score += 25
                if "id" in field.lower():
                    score -= 25
                scored.append((score, field, label or field))
            if scored:
                scored.sort(reverse=True)
                _, field, label = scored[0]
                chosen = (field, label)
        if not chosen:
            raise RuntimeError("iikoServer SALES OLAP does not expose a cashier grouping field")
        _field_cache["field"], _field_cache["label"] = chosen
        _field_cache["expires_at"] = time.time() + 6 * 60 * 60
        return chosen


def _cache_get(key):
    with _lock:
        item = _data_cache.get(key)
        if not item or item["expires_at"] <= time.time():
            if item:
                _data_cache.pop(key, None)
            return None
        return item["value"]


def _cache_set(key, value):
    with _lock:
        _data_cache[key] = {"value": value, "expires_at": time.time() + TTL_SECONDS}
        if len(_data_cache) > 80:
            oldest = sorted(_data_cache, key=lambda k: _data_cache[k]["expires_at"])[:20]
            for old in oldest:
                _data_cache.pop(old, None)


def build_cashier_analytics(point, date_from, date_to, channel="all"):
    core.date_range(date_from, date_to)
    channel = (channel or "all").strip().lower()
    if channel != "all" and channel not in sales_channel.CHANNELS:
        raise ValueError("Unknown sales channel")

    key = ((point or "").strip().lower(), date_from, date_to, channel)
    cached = _cache_get(key)
    if cached is not None:
        result = dict(cached)
        result["cache"] = {"hit": True, "ttlSeconds": TTL_SECONDS}
        return result

    base_url = None
    token = None
    try:
        base_url, token = core.iiko_server_auth()
        departments = core.iiko_server_departments(base_url, token)
        department = core.find_iiko_server_department(point, departments)
        if not department:
            raise ValueError(f"Point '{point}' not found in iikoServer departments")

        cashier_field, cashier_label = discover_cashier_field(base_url, token)
        rows = sales_channel._olap_request(
            base_url,
            token,
            date_from,
            date_to,
            department.get("id"),
            [cashier_field, *sales_channel.CHANNEL_FIELDS],
            ["DishDiscountSumInt", "UniqOrderId", "GuestNum"],
        )

        totals = {}
        for row in rows:
            classified = sales_channel._specific_channel(row)
            if classified in {"excluded", "team_meal"}:
                continue
            if channel != "all" and classified != channel:
                continue
            cashier = str(row.get(cashier_field) or "Не указан").strip() or "Не указан"
            item = totals.setdefault(cashier, {"cashier": cashier, "checks": 0.0, "revenue": 0.0, "guests": 0.0})
            item["checks"] += float(row.get("UniqOrderId") or 0)
            item["revenue"] += float(row.get("DishDiscountSumInt") or 0)
            item["guests"] += float(row.get("GuestNum") or 0)

        cashiers = []
        for item in totals.values():
            checks = float(item["checks"] or 0)
            revenue = float(item["revenue"] or 0)
            cashiers.append({
                "cashier": item["cashier"],
                "checks": round(checks, 2),
                "revenue": round(revenue, 2),
                "guests": round(float(item["guests"] or 0), 2),
                "averageCheck": round(revenue / checks, 2) if checks else 0,
            })
        cashiers.sort(key=lambda x: x["revenue"], reverse=True)

        total_checks = sum(x["checks"] for x in cashiers)
        total_revenue = sum(x["revenue"] for x in cashiers)
        result = {
            "success": True,
            "source": "iikoServer SALES OLAP / cashier",
            "cashierField": cashier_field,
            "cashierLabel": cashier_label,
            "point": {"id": department.get("id"), "code": department.get("code"), "name": department.get("name")},
            "period": {"from": date_from, "to": date_to},
            "channel": channel,
            "summary": {
                "cashiers": len(cashiers),
                "checks": round(total_checks, 2),
                "revenue": round(total_revenue, 2),
                "averageCheck": round(total_revenue / total_checks, 2) if total_checks else 0,
            },
            "cashiers": cashiers,
            "cache": {"hit": False, "ttlSeconds": TTL_SECONDS},
        }
        _cache_set(key, result)
        return result
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def install_cashier_features(app):
    if getattr(app, "_doner_cashier_features_installed", False):
        return
    app._doner_cashier_features_installed = True

    @app.before_request
    def _protect_cashier_api():
        if core.request.path == "/cashier-analytics" and not session.get("dc_authenticated"):
            return jsonify({"success": False, "code": "AUTH_REQUIRED", "message": "Authentication required", "login": "/login"}), 401
        return None

    @app.route("/cashier-analytics")
    def cashier_analytics():
        try:
            point = (core.request.args.get("point") or "Arai").strip()
            single_date = core.request.args.get("date")
            date_from = core.request.args.get("from") or single_date
            date_to = core.request.args.get("to") or date_from
            channel = (core.request.args.get("channel") or "all").strip().lower()
            if not date_from:
                date_from = core.datetime.now(core.LOCAL_TZ).date().isoformat()
            if not date_to:
                date_to = date_from
            return jsonify(build_cashier_analytics(point, date_from, date_to, channel))
        except requests.HTTPError as error:
            response = error.response
            return jsonify({
                "success": False,
                "code": "CASHIER_OLAP_ERROR",
                "statusCode": response.status_code if response is not None else None,
                "details": response.text[:1200] if response is not None else str(error),
            }), 502
        except ValueError as error:
            return jsonify({"success": False, "code": "CASHIER_INVALID", "message": str(error)}), 400
        except Exception as error:
            return jsonify({"success": False, "code": "CASHIER_ERROR", "message": str(error)}), 500

    @app.after_request
    def _inject_cashier_features(response):
        if (
            core.request.path.endswith("dashboard-v2.html")
            and response.status_code == 200
            and response.mimetype == "text/html"
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/cashier-features.js"></script>'
                if tag not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
