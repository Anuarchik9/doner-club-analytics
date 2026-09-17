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
        if len(_cache) > 60:
            oldest = sorted(_cache, key=lambda k: _cache[k]["expires_at"])[:15]
            for old in oldest:
                _cache.pop(old, None)


def _shift_month(year, month, offset):
    index = year * 12 + (month - 1) + offset
    return index // 12, index % 12 + 1


def _month_end(year, month):
    ny, nm = _shift_month(year, month, 1)
    return date.fromordinal(date(ny, nm, 1).toordinal() - 1)


def _month_keys(start_year, start_month, count):
    result = []
    for offset in range(count):
        y, m = _shift_month(start_year, start_month, offset)
        result.append(f"{y:04d}-{m:02d}")
    return result


def _shares(online, offline):
    total = float(online or 0) + float(offline or 0)
    if total <= 0:
        return total, 0.0, 0.0
    return total, round(float(online or 0) / total * 100, 2), round(float(offline or 0) / total * 100, 2)


def _daily_series(rows, date_from, date_to):
    totals = {
        day: {"onlineRevenue": 0.0, "offlineRevenue": 0.0}
        for day in core.date_range(date_from, date_to)
    }
    for row in rows:
        group = sales_channel._group_for_row(row)
        if group not in {"online", "offline"}:
            continue
        day = sales_channel._date_value(row.get("OpenDate.Typed"))
        if day not in totals:
            continue
        revenue = float(row.get("DishDiscountSumInt") or 0)
        key = "onlineRevenue" if group == "online" else "offlineRevenue"
        totals[day][key] += revenue

    result = []
    for day in sorted(totals):
        online = round(totals[day]["onlineRevenue"], 2)
        offline = round(totals[day]["offlineRevenue"], 2)
        total, online_share, offline_share = _shares(online, offline)
        result.append({
            "date": day,
            "onlineRevenue": online,
            "offlineRevenue": offline,
            "totalRevenue": round(total, 2),
            "onlineShare": online_share,
            "offlineShare": offline_share,
        })
    return result


def _monthly_series(rows, start_year, start_month, count=12):
    keys = _month_keys(start_year, start_month, count)
    totals = {key: {"onlineRevenue": 0.0, "offlineRevenue": 0.0} for key in keys}
    for row in rows:
        group = sales_channel._group_for_row(row)
        if group not in {"online", "offline"}:
            continue
        day = sales_channel._date_value(row.get("OpenDate.Typed"))
        month = str(day or "")[:7]
        if month not in totals:
            continue
        revenue = float(row.get("DishDiscountSumInt") or 0)
        key = "onlineRevenue" if group == "online" else "offlineRevenue"
        totals[month][key] += revenue

    result = []
    for month in keys:
        online = round(totals[month]["onlineRevenue"], 2)
        offline = round(totals[month]["offlineRevenue"], 2)
        total, online_share, offline_share = _shares(online, offline)
        result.append({
            "month": month,
            "onlineRevenue": online,
            "offlineRevenue": offline,
            "totalRevenue": round(total, 2),
            "onlineShare": online_share,
            "offlineShare": offline_share,
        })
    return result


def _find_department(point, departments):
    department = core.find_iiko_server_department(point, departments)
    if department:
        return department

    raw = str(point or "").strip().lower()
    aliases = []
    if any(token in raw for token in ("сыганак", "сығанақ", "syganak", "syganaq")):
        aliases = ["сыганак", "сығанақ", "syganak", "syganaq"]
    elif any(token in raw for token in ("манас", "manas")):
        aliases = ["манас", "manas"]

    for item in departments:
        haystack = f"{item.get('code') or ''} {item.get('name') or ''}".lower()
        if aliases and any(alias in haystack for alias in aliases):
            return item
    return None


def build_online_offline_trends(point, compare_offset=2):
    compare_offset = max(1, min(int(compare_offset or 2), 11))
    today = core.datetime.now(core.LOCAL_TZ).date()

    current_from = today.replace(day=1)
    current_to = today

    compare_y, compare_m = _shift_month(today.year, today.month, -compare_offset)
    compare_from = date(compare_y, compare_m, 1)
    compare_to = _month_end(compare_y, compare_m)

    history_y, history_m = _shift_month(today.year, today.month, -11)
    history_from = date(history_y, history_m, 1)
    history_to = today

    cache_key = ((point or "").strip().lower(), today.isoformat(), compare_offset)
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
        department = _find_department(point, departments)
        if not department:
            raise ValueError(f"Point '{point}' not found in iikoServer departments")

        department_id = department.get("id")
        groups = ["OpenDate.Typed", *sales_channel.CHANNEL_FIELDS]
        aggregates = ["DishDiscountSumInt"]

        def fetch_period(a, b):
            return sales_channel._olap_request(
                base_url,
                token,
                a.isoformat(),
                b.isoformat(),
                department_id,
                groups,
                aggregates,
            )

        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="online-offline") as executor:
            f_current = executor.submit(fetch_period, current_from, current_to)
            f_compare = executor.submit(fetch_period, compare_from, compare_to)
            f_history = executor.submit(fetch_period, history_from, history_to)
            current_rows = f_current.result()
            compare_rows = f_compare.result()
            history_rows = f_history.result()

        current = _daily_series(current_rows, current_from.isoformat(), current_to.isoformat())
        comparison = _daily_series(compare_rows, compare_from.isoformat(), compare_to.isoformat())
        monthly = _monthly_series(history_rows, history_y, history_m, 12)

        def totals(series):
            online = round(sum(float(x.get("onlineRevenue") or 0) for x in series), 2)
            offline = round(sum(float(x.get("offlineRevenue") or 0) for x in series), 2)
            total, online_share, offline_share = _shares(online, offline)
            return {
                "onlineRevenue": online,
                "offlineRevenue": offline,
                "totalRevenue": round(total, 2),
                "onlineShare": online_share,
                "offlineShare": offline_share,
            }

        result = {
            "success": True,
            "source": "iikoServer OLAP SALES",
            "point": {
                "id": department.get("id"),
                "code": department.get("code"),
                "name": department.get("name") or point,
            },
            "today": today.isoformat(),
            "current": {
                "from": current_from.isoformat(),
                "to": current_to.isoformat(),
                "series": current,
                "totals": totals(current),
                "incomplete": True,
            },
            "comparison": {
                "offset": compare_offset,
                "from": compare_from.isoformat(),
                "to": compare_to.isoformat(),
                "series": comparison,
                "totals": totals(comparison),
            },
            "monthly": {
                "from": history_from.isoformat(),
                "to": history_to.isoformat(),
                "series": monthly,
                "totals": totals(monthly),
            },
            "rules": {
                "online": ["Glovo", "Wolt", "Yandex", "Chocofood", "Starter без баллов"],
                "offline": ["Kaspi QR", "карта", "наличные", "CALL CENTER"],
                "denominator": "online + offline recognized revenue",
            },
            "cache": {"hit": False, "ttlSeconds": TTL_SECONDS},
        }
        _cache_set(cache_key, result)
        return result
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def install_online_offline_trends(app):
    if getattr(app, "_doner_online_offline_trends_installed", False):
        return
    app._doner_online_offline_trends_installed = True

    @app.before_request
    def _protect_online_offline_api():
        if core.request.path == "/online-offline-trends" and not session.get("dc_authenticated"):
            return jsonify({
                "success": False,
                "code": "AUTH_REQUIRED",
                "message": "Authentication required",
                "login": "/login",
            }), 401
        return None

    @app.route("/online-offline-trends")
    def online_offline_trends():
        try:
            point = (core.request.args.get("point") or "Arai").strip()
            compare_offset = core.request.args.get("compareOffset") or 2
            return jsonify(build_online_offline_trends(point, compare_offset))
        except requests.Timeout:
            return jsonify({
                "success": False,
                "code": "ONLINE_OFFLINE_TIMEOUT",
                "message": "iikoServer did not answer in time. Please retry the request.",
            }), 504
        except requests.HTTPError as error:
            response = error.response
            return jsonify({
                "success": False,
                "code": "ONLINE_OFFLINE_OLAP_ERROR",
                "statusCode": response.status_code if response is not None else None,
                "details": response.text[:1200] if response is not None else str(error),
            }), 502
        except ValueError as error:
            return jsonify({"success": False, "code": "ONLINE_OFFLINE_INVALID", "message": str(error)}), 400
        except Exception as error:
            return jsonify({"success": False, "code": "ONLINE_OFFLINE_ERROR", "message": str(error)}), 500

    @app.after_request
    def _inject_online_offline_trends(response):
        if (
            core.request.path.endswith("dashboard-v2.html")
            and response.status_code == 200
            and response.mimetype == "text/html"
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/online-offline-trends.js?v=20260917-1"></script>'
                if "online-offline-trends.js" not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
