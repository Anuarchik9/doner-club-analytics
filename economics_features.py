import threading
import time
from collections import defaultdict

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


def _category(name):
    text = (name or "").strip().lower()
    if "комбо" in text or "combo" in text:
        return "Комбо"
    if "донер" in text or "doner" in text:
        return "Донеры"
    if any(token in text for token in ("фри", "картоф", "fri", "fries")):
        return "Фри"
    if any(token in text for token in ("соус", "sauce", "кетчуп", "майонез")):
        return "Соусы"
    if any(token in text for token in ("сыр", "халап", "jalap", "добав", "extra")):
        return "Добавки"
    if any(token in text for token in (
        "pepsi", "cola", "coca", "fanta", "sprite", "айран", "вода", "water",
        "сок", "juice", "чай", "tea", "кофе", "coffee", "напит"
    )):
        return "Напитки"
    return "Прочее"


def _metric(revenue, cost):
    revenue = float(revenue or 0)
    cost = float(cost or 0)
    gross_profit = revenue - cost
    return {
        "revenue": round(revenue, 2),
        "cost": round(cost, 2),
        "foodCostPct": round(cost / revenue * 100, 2) if revenue else 0,
        "grossProfit": round(gross_profit, 2),
        "grossMarginPct": round(gross_profit / revenue * 100, 2) if revenue else 0,
    }


def build_economics(point, date_from, date_to, channel="all"):
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

        rows = sales_channel._olap_request(
            base_url,
            token,
            date_from,
            date_to,
            department.get("id"),
            ["DishId", "DishName", *sales_channel.CHANNEL_FIELDS],
            ["DishDiscountSumInt", "Cost", "DishAmountInt"],
        )

        selected = []
        for row in rows:
            classified = sales_channel._specific_channel(row)
            if classified == "team_meal":
                continue
            if channel != "all" and classified != channel:
                continue
            selected.append(row)

        products = {}
        categories = defaultdict(lambda: {"revenue": 0.0, "cost": 0.0, "quantity": 0.0})
        total_revenue = 0.0
        total_cost = 0.0
        total_quantity = 0.0

        for row in selected:
            name = str(row.get("DishName") or "Позиция iiko")
            product_id = str(row.get("DishId") or name)
            revenue = float(row.get("DishDiscountSumInt") or 0)
            cost = float(row.get("Cost") or 0)
            quantity = float(row.get("DishAmountInt") or 0)

            item = products.setdefault(product_id, {
                "productId": product_id,
                "name": name,
                "revenue": 0.0,
                "cost": 0.0,
                "quantity": 0.0,
            })
            item["revenue"] += revenue
            item["cost"] += cost
            item["quantity"] += quantity

            category = categories[_category(name)]
            category["revenue"] += revenue
            category["cost"] += cost
            category["quantity"] += quantity

            total_revenue += revenue
            total_cost += cost
            total_quantity += quantity

        product_list = []
        zero_cost_positions = []
        for item in products.values():
            metrics = _metric(item["revenue"], item["cost"])
            prepared = {
                **item,
                **metrics,
                "quantity": round(item["quantity"], 3),
            }
            product_list.append(prepared)
            if prepared["revenue"] > 0 and abs(prepared["cost"]) < 0.005:
                zero_cost_positions.append({
                    "name": prepared["name"],
                    "revenue": prepared["revenue"],
                    "quantity": prepared["quantity"],
                })

        product_list.sort(key=lambda x: x["revenue"], reverse=True)

        category_list = []
        for name, item in categories.items():
            metrics = _metric(item["revenue"], item["cost"])
            category_list.append({
                "name": name,
                **metrics,
                "quantity": round(item["quantity"], 3),
            })
        category_list.sort(key=lambda x: x["revenue"], reverse=True)

        result = {
            "success": True,
            "source": "iikoServer OLAP SALES / Cost",
            "point": {
                "id": department.get("id"),
                "code": department.get("code"),
                "name": department.get("name"),
            },
            "period": {"from": date_from, "to": date_to},
            "channel": channel,
            "summary": {
                **_metric(total_revenue, total_cost),
                "quantity": round(total_quantity, 3),
                "positions": len(product_list),
                "positionsWithoutCost": len(zero_cost_positions),
            },
            "categories": category_list,
            "products": product_list,
            "positionsWithoutCost": zero_cost_positions[:30],
            "cache": {"hit": False, "ttlSeconds": TTL_SECONDS},
        }
        _cache_set(key, result)
        return result
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def install_economics_features(app):
    if getattr(app, "_doner_economics_features_installed", False):
        return
    app._doner_economics_features_installed = True

    @app.before_request
    def _protect_economics_api():
        if core.request.path == "/economics-analytics" and not session.get("dc_authenticated"):
            return jsonify({
                "success": False,
                "code": "AUTH_REQUIRED",
                "message": "Authentication required",
                "login": "/login",
            }), 401
        return None

    @app.route("/economics-analytics")
    def economics_analytics():
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
            return jsonify(build_economics(point, date_from, date_to, channel))
        except requests.HTTPError as error:
            response = error.response
            return jsonify({
                "success": False,
                "code": "ECONOMICS_OLAP_ERROR",
                "statusCode": response.status_code if response is not None else None,
                "details": response.text[:1200] if response is not None else str(error),
            }), 502
        except ValueError as error:
            return jsonify({"success": False, "code": "ECONOMICS_INVALID", "message": str(error)}), 400
        except Exception as error:
            return jsonify({"success": False, "code": "ECONOMICS_ERROR", "message": str(error)}), 500

    @app.after_request
    def _inject_economics_features(response):
        if (
            core.request.path.endswith("dashboard-v2.html")
            and response.status_code == 200
            and response.mimetype == "text/html"
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/economics-features.js"></script>'
                if tag not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
