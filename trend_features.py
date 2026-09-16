import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

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


def _month_shift(year, month, offset):
    index = year * 12 + (month - 1) - offset
    return index // 12, index % 12 + 1


def _month_end(year, month):
    if month == 12:
        return date(year + 1, 1, 1).fromordinal(date(year + 1, 1, 1).toordinal() - 1)
    return date(year, month + 1, 1).fromordinal(date(year, month + 1, 1).toordinal() - 1)


def _series(rows, start_date, end_date, channel):
    dates = core.date_range(start_date, end_date)
    totals = {day: 0.0 for day in dates}

    for row in rows:
        classified = sales_channel._specific_channel(row)
        if channel == "all":
            # Keep commercial sales, but do not distort the revenue trend with loyalty points
            # or team meals booked through Deposit / PITANIE.
            if classified in {"excluded", "team_meal"}:
                continue
        elif classified != channel:
            continue

        day = sales_channel._date_value(row.get("OpenDate.Typed"))
        if day in totals:
            totals[day] += float(row.get("DishDiscountSumInt") or 0)

    return [{"date": day, "revenue": round(totals[day], 2)} for day in dates]


def build_month_trends(point, channel="all", compare_offset=1):
    channel = (channel or "all").strip().lower()
    if channel != "all" and channel not in sales_channel.CHANNELS:
        raise ValueError("Unknown sales channel")
    compare_offset = max(1, min(int(compare_offset or 1), 3))

    today = core.datetime.now(core.LOCAL_TZ).date()
    current_from = today.replace(day=1).isoformat()
    current_to = today.isoformat()

    cy, cm = _month_shift(today.year, today.month, compare_offset)
    compare_start = date(cy, cm, 1)
    compare_end = _month_end(cy, cm)
    compare_from = compare_start.isoformat()
    compare_to = compare_end.isoformat()

    cache_key = ((point or "").strip().lower(), channel, current_to, compare_offset)
    cached = _cache_get(cache_key)
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
        department_id = department.get("id")
        groups = ["OpenDate.Typed", *sales_channel.CHANNEL_FIELDS]
        aggregates = ["DishDiscountSumInt"]

        def fetch_period(a, b):
            return sales_channel._olap_request(
                base_url,
                token,
                a,
                b,
                department_id,
                groups,
                aggregates,
            )

        # Current month and comparison month are independent OLAP queries, so run them in parallel.
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="trend") as executor:
            f_current = executor.submit(fetch_period, current_from, current_to)
            f_compare = executor.submit(fetch_period, compare_from, compare_to)
            current_rows = f_current.result()
            compare_rows = f_compare.result()

        current = _series(current_rows, current_from, current_to, channel)
        comparison = _series(compare_rows, compare_from, compare_to, channel)
        result = {
            "success": True,
            "source": "iikoServer OLAP SALES",
            "point": {
                "id": department_id,
                "code": department.get("code"),
                "name": department.get("name"),
            },
            "channel": channel,
            "today": current_to,
            "todayIncomplete": True,
            "current": {
                "from": current_from,
                "to": current_to,
                "series": current,
                "revenue": round(sum(x["revenue"] for x in current), 2),
            },
            "comparison": {
                "offset": compare_offset,
                "from": compare_from,
                "to": compare_to,
                "series": comparison,
                "revenue": round(sum(x["revenue"] for x in comparison), 2),
            },
            "cache": {"hit": False, "ttlSeconds": TTL_SECONDS},
        }
        _cache_set(cache_key, result)
        return result
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def install_trend_features(app):
    if getattr(app, "_doner_trend_features_installed", False):
        return
    app._doner_trend_features_installed = True

    @app.before_request
    def _protect_trend_api():
        if core.request.path == "/trend-analytics" and not session.get("dc_authenticated"):
            return jsonify({
                "success": False,
                "code": "AUTH_REQUIRED",
                "message": "Authentication required",
                "login": "/login",
            }), 401
        return None

    @app.route("/trend-analytics")
    def trend_analytics():
        try:
            point = (core.request.args.get("point") or "Arai").strip()
            channel = (core.request.args.get("channel") or "all").strip().lower()
            compare_offset = core.request.args.get("compareOffset") or 1
            return jsonify(build_month_trends(point, channel, compare_offset))
        except requests.HTTPError as error:
            response = error.response
            return jsonify({
                "success": False,
                "code": "TREND_OLAP_ERROR",
                "statusCode": response.status_code if response is not None else None,
                "details": response.text[:1200] if response is not None else str(error),
            }), 502
        except ValueError as error:
            return jsonify({"success": False, "code": "TREND_INVALID", "message": str(error)}), 400
        except Exception as error:
            return jsonify({"success": False, "code": "TREND_ERROR", "message": str(error)}), 500

    @app.after_request
    def _inject_trend_features(response):
        if (
            core.request.path.endswith("dashboard-v2.html")
            and response.status_code == 200
            and response.mimetype == "text/html"
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/trend-features.js"></script>'
                if tag not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
