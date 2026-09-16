import threading
import time

import requests
from flask import jsonify, session

import app as core
import sales_channel


TTL_SECONDS = 5 * 60
_cache = {}
_lock = threading.Lock()


def _cache_get(key):
    with _lock:
        item = _cache.get(key)
        if not item or item["expires_at"] <= time.time():
            if item:
                _cache.pop(key, None)
            return None
        return item["value"]


def _cache_set(key, value):
    with _lock:
        _cache[key] = {"value": value, "expires_at": time.time() + TTL_SECONDS}
        if len(_cache) > 80:
            oldest = sorted(_cache, key=lambda k: _cache[k]["expires_at"])[:20]
            for old in oldest:
                _cache.pop(old, None)


def _record_check(point, date_from, date_to, channel="all"):
    core.date_range(date_from, date_to)
    channel = (channel or "all").strip().lower()
    if channel != "all" and channel not in sales_channel.CHANNELS:
        raise ValueError("Unknown sales channel")

    key = ((point or "").strip().lower(), date_from, date_to, channel)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    base_url = None
    token = None
    try:
        base_url, token = core.iiko_server_auth()
        departments = core.iiko_server_departments(base_url, token)
        department = core.find_iiko_server_department(point, departments)
        if not department:
            raise ValueError(f"Point '{point}' not found in iikoServer departments")

        group_fields = ["CloseTime"]
        if channel != "all":
            group_fields += sales_channel.CHANNEL_FIELDS

        rows = sales_channel._olap_request(
            base_url,
            token,
            date_from,
            date_to,
            department.get("id"),
            group_fields,
            ["DishDiscountSumInt", "UniqOrderId"],
        )

        if channel != "all":
            rows = [row for row in rows if sales_channel._specific_channel(row) == channel]

        valid = [
            row for row in rows
            if float(row.get("DishDiscountSumInt") or 0) > 0
            and float(row.get("UniqOrderId") or 0) > 0
        ]
        winner = max(valid, key=lambda row: float(row.get("DishDiscountSumInt") or 0), default=None)
        record = None
        if winner:
            close_time = str(winner.get("CloseTime") or "")
            record = {
                "amount": round(float(winner.get("DishDiscountSumInt") or 0), 2),
                "closeTime": close_time,
                "date": close_time[:10] if len(close_time) >= 10 else None,
                "time": close_time[11:16] if len(close_time) >= 16 else None,
            }

        result = {
            "success": True,
            "point": department.get("name") or department.get("code") or point,
            "period": {"from": date_from, "to": date_to},
            "channel": channel,
            "recordCheck": record,
        }
        _cache_set(key, result)
        return result
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def install_management_features(app):
    if getattr(app, "_doner_management_features_installed", False):
        return
    app._doner_management_features_installed = True

    @app.before_request
    def _protect_management_api():
        if core.request.path == "/management-metrics" and not session.get("dc_authenticated"):
            return jsonify({
                "success": False,
                "code": "AUTH_REQUIRED",
                "message": "Authentication required",
                "login": "/login",
            }), 401
        return None

    @app.route("/management-metrics")
    def management_metrics():
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
            return jsonify(_record_check(point, date_from, date_to, channel))
        except requests.HTTPError as error:
            response = error.response
            return jsonify({
                "success": False,
                "code": "MANAGEMENT_OLAP_ERROR",
                "statusCode": response.status_code if response is not None else None,
                "details": response.text[:1200] if response is not None else str(error),
            }), 502
        except ValueError as error:
            return jsonify({"success": False, "code": "MANAGEMENT_INVALID", "message": str(error)}), 400
        except Exception as error:
            return jsonify({"success": False, "code": "MANAGEMENT_ERROR", "message": str(error)}), 500

    @app.after_request
    def _inject_management_features(response):
        if (
            core.request.path.endswith("dashboard-v2.html")
            and response.status_code == 200
            and response.mimetype == "text/html"
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/management-features.js"></script>'
                if tag not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
