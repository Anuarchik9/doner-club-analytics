from collections import defaultdict

import app as core
import sales_channel


ARCHIVED_TOKENS = ("манас", "manas", "сыганак", "syganak", "syganak")


def _is_archived_point(point):
    text = str(point or "").strip().lower()
    return any(token in text for token in ARCHIVED_TOKENS) and "||" not in text


def _date_value(value):
    text = str(value or "")
    return text[:10] if len(text) >= 10 else None


def _archived_from_server(point, date_from, date_to):
    base_url = None
    token = None
    try:
        base_url, token = core.iiko_server_auth()
        departments = core.iiko_server_departments(base_url, token)
        department = core.find_iiko_server_department(point, departments)
        if not department:
            raise ValueError(f"Point '{point}' not found in iikoServer departments")

        department_id = department.get("id")
        product_rows = sales_channel._olap_request(
            base_url,
            token,
            date_from,
            date_to,
            department_id,
            ["OpenDate.Typed", "DishId", "DishName"],
            ["DishDiscountSumInt", "DishAmountInt"],
        )
        daily_rows = sales_channel._olap_request(
            base_url,
            token,
            date_from,
            date_to,
            department_id,
            ["OpenDate.Typed"],
            ["DishDiscountSumInt", "DishAmountInt", "UniqOrderId"],
        )

        products_map = {}
        for row in product_rows:
            product_id = str(row.get("DishId") or row.get("DishName") or "unknown")
            item = products_map.setdefault(product_id, {
                "productId": product_id,
                "name": row.get("DishName") or "Позиция iiko",
                "article": None,
                "quantity": 0.0,
                "revenue": 0.0,
            })
            item["quantity"] += float(row.get("DishAmountInt") or 0)
            item["revenue"] += float(row.get("DishDiscountSumInt") or 0)

        products = []
        for item in products_map.values():
            item["quantity"] = round(item["quantity"], 3)
            item["revenue"] = round(item["revenue"], 2)
            products.append(item)
        products.sort(key=lambda x: x["revenue"], reverse=True)

        all_dates = core.date_range(date_from, date_to)
        daily = {
            day: {
                "date": day,
                "revenue": 0.0,
                "itemsRevenue": 0.0,
                "quantity": 0.0,
                "documentsCount": 0,
            }
            for day in all_dates
        }
        for row in daily_rows:
            day = _date_value(row.get("OpenDate.Typed"))
            if not day:
                continue
            bucket = daily.setdefault(day, {
                "date": day,
                "revenue": 0.0,
                "itemsRevenue": 0.0,
                "quantity": 0.0,
                "documentsCount": 0,
            })
            revenue = float(row.get("DishDiscountSumInt") or 0)
            bucket["revenue"] += revenue
            bucket["itemsRevenue"] += revenue
            bucket["quantity"] += float(row.get("DishAmountInt") or 0)
            bucket["documentsCount"] += int(round(float(row.get("UniqOrderId") or 0)))

        daily_series = []
        for day in sorted(daily):
            item = daily[day]
            daily_series.append({
                "date": day,
                "revenue": round(item["revenue"], 2),
                "itemsRevenue": round(item["itemsRevenue"], 2),
                "quantity": round(item["quantity"], 3),
                "documentsCount": item["documentsCount"],
            })

        revenue = round(sum(item["revenue"] for item in daily_series), 2)
        quantity = round(sum(item["quantity"] for item in daily_series), 3)
        checks = sum(item["documentsCount"] for item in daily_series)
        days_count = len(all_dates)

        payload = {
            "success": True,
            "source": "iikoServer OLAP historical fallback",
            "point": {
                "id": department.get("id"),
                "code": department.get("code"),
                "name": department.get("name") or point,
                "archived": True,
                "status": "reconstruction",
            },
            "period": {"from": date_from, "to": date_to, "daysCount": days_count},
            "summary": {
                "documentsCount": checks,
                "revenue": revenue,
                "itemsRevenue": revenue,
                "itemsQuantity": quantity,
                "uniqueProducts": len(products),
                "averageDailyRevenue": round(revenue / days_count, 2) if days_count else 0,
            },
            "daily": daily_series,
            "topByRevenue": products[:20],
            "topByQuantity": sorted(products, key=lambda x: x["quantity"], reverse=True)[:20],
            "products": products,
            "warnings": {
                "nomenclature": None,
                "documentDetails": [],
                "note": "Исторические данные закрытой точки загружены из iikoServer OLAP, потому что текущий inventory API iikoCloud может не отдавать документы закрытых подразделений.",
            },
            "performance": {"detailWorkers": 0, "detailsRequested": 0, "detailsLoaded": 0},
            "cache": {"hit": False, "ttlSeconds": core.ANALYTICS_TTL_SECONDS},
        }
        return payload, None, 200
    finally:
        if base_url and token:
            try:
                core.iiko_server_logout(base_url, token)
            except Exception:
                pass


def install_archived_points(app):
    if getattr(app, "_doner_archived_points_installed", False):
        return
    app._doner_archived_points_installed = True

    original_build_analytics = core.build_analytics

    def build_analytics_with_archive(point, date_from, date_to):
        if not _is_archived_point(point):
            return original_build_analytics(point, date_from, date_to)

        try:
            payload, error_payload, status = original_build_analytics(point, date_from, date_to)
            if payload is not None and not error_payload:
                return payload, error_payload, status
        except Exception:
            pass

        try:
            return _archived_from_server(point, date_from, date_to)
        except Exception as error:
            return None, {
                "success": False,
                "message": "Не удалось получить исторические данные закрытой точки из iikoServer.",
                "details": str(error),
                "archivedPoint": True,
            }, 503

    core.build_analytics = build_analytics_with_archive

    @app.after_request
    def _inject_archive_ui(response):
        if (
            response.status_code == 200
            and response.mimetype == "text/html"
            and core.request.path.endswith("dashboard-v2.html")
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/point-archive-polish.js?v=20260917-1"></script>'
                if "point-archive-polish.js" not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
