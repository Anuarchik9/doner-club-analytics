from collections import defaultdict
import re

import app as core
import sales_channel


ARCHIVED_TOKENS = (
    "манас", "manas",
    "сыганак", "сығанақ", "syganak", "syganaq",
)


def _compact(value):
    text = str(value or "").strip().lower().replace("ё", "е")
    return re.sub(r"[^0-9a-zа-яәіңғүұқөһ]+", "", text)


def _latinize(value):
    text = str(value or "").strip().lower().replace("ё", "е")
    table = {
        "а": "a", "ә": "a", "б": "b", "в": "v", "г": "g", "ғ": "g",
        "д": "d", "е": "e", "ж": "zh", "з": "z", "и": "i", "й": "i",
        "к": "k", "қ": "q", "л": "l", "м": "m", "н": "n", "ң": "n",
        "о": "o", "ө": "o", "п": "p", "р": "r", "с": "s", "т": "t",
        "у": "u", "ұ": "u", "ү": "u", "ф": "f", "х": "h", "һ": "h",
        "ц": "c", "ч": "ch", "ш": "sh", "щ": "sh", "ы": "y", "і": "i",
        "ъ": "", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    result = "".join(table.get(char, char) for char in text)
    return re.sub(r"[^0-9a-z]+", "", result)


def _archive_kind(point):
    compact = _compact(point)
    latin = _latinize(point)
    if any(token in compact for token in ("манас", "manas")) or "manas" in latin:
        return "manas"
    if (
        any(token in compact for token in ("сыганак", "сығанақ", "syganak", "syganaq"))
        or any(token in latin for token in ("syganak", "syganaq"))
    ):
        return "syganak"
    return None


def _resolve_archived_point(point):
    """Return (kind, lookup_name) even when dashboard sends an opaque iiko code.

    The point selector stores option.value as department code and option.text as the
    human name. Closed branches can therefore arrive here as a code that contains
    neither 'Сыганак' nor 'Манас'. Resolve that code through the already-loaded
    iikoCloud department tree before deciding whether this is an archived branch.
    """
    raw = str(point or "").strip()
    if "||" in raw:
        return None, raw

    direct_kind = _archive_kind(raw)
    if direct_kind:
        return direct_kind, raw

    try:
        department, _ = core.find_department(raw)
    except Exception:
        department = None

    if department:
        name = str(department.get("name") or "").strip()
        code = str(department.get("code") or "").strip()
        kind = _archive_kind(f"{name} {code}")
        if kind:
            # Prefer the human name for matching the historical iikoServer branch.
            return kind, name or code or raw

    return None, raw


def _is_archived_point(point):
    kind, _ = _resolve_archived_point(point)
    return kind is not None


def _department_matches(kind, department):
    haystacks = []
    for field in ("code", "name"):
        raw = department.get(field) or ""
        haystacks.extend((_compact(raw), _latinize(raw)))

    if kind == "manas":
        aliases = ("манас", "manas")
    else:
        aliases = ("сыганак", "сығанақ", "syganak", "syganaq")

    return any(alias in hay for hay in haystacks for alias in aliases)


def _find_archived_department(point, departments):
    # First keep the standard iiko matcher: if code/name is identical it is safest.
    department = core.find_iiko_server_department(point, departments)
    if department:
        return department

    # Closed points can have a Cyrillic name in iikoCloud and a Latin code/name in
    # iikoServer. Match those aliases explicitly (Сыганак <-> Syganak, Манас <-> Manas).
    kind = _archive_kind(point)
    if not kind:
        return None
    for item in departments:
        if _department_matches(kind, item):
            return item
    return None


def _date_value(value):
    text = str(value or "")
    return text[:10] if len(text) >= 10 else None


def _query_daily(base_url, token, date_from, date_to, department_id):
    """Load the essential historical series with graceful OLAP-field fallback."""
    attempts = (
        ["DishDiscountSumInt", "DishAmountInt", "UniqOrderId"],
        ["DishDiscountSumInt", "UniqOrderId"],
        ["DishDiscountSumInt"],
    )
    last_error = None
    for aggregates in attempts:
        try:
            rows = sales_channel._olap_request(
                base_url,
                token,
                date_from,
                date_to,
                department_id,
                ["OpenDate.Typed"],
                aggregates,
            )
            return rows, aggregates
        except Exception as error:
            last_error = error
    raise last_error


def _query_products(base_url, token, date_from, date_to, department_id):
    return sales_channel._olap_request(
        base_url,
        token,
        date_from,
        date_to,
        department_id,
        ["OpenDate.Typed", "DishId", "DishName"],
        ["DishDiscountSumInt", "DishAmountInt"],
    )


def _archived_from_server(point, date_from, date_to):
    base_url = None
    token = None
    try:
        base_url, token = core.iiko_server_auth()
        departments = core.iiko_server_departments(base_url, token)
        department = _find_archived_department(point, departments)
        if not department:
            visible = [
                f"{d.get('code') or '—'} / {d.get('name') or '—'}"
                for d in departments
                if d.get("code") or d.get("name")
            ]
            raise ValueError(
                f"Архивная точка '{point}' не найдена среди подразделений iikoServer. "
                f"Доступные подразделения: {', '.join(visible[:30])}"
            )

        department_id = department.get("id")
        if not department_id:
            raise ValueError(f"У подразделения '{department.get('name') or point}' нет iikoServer id")

        # Revenue is the essential historical layer. Some older iiko installations
        # reject newer quantity/check aggregate fields, so retry with a smaller set.
        daily_rows, daily_aggregates = _query_daily(
            base_url, token, date_from, date_to, department_id
        )

        product_warning = None
        try:
            product_rows = _query_products(base_url, token, date_from, date_to, department_id)
        except Exception as error:
            product_rows = []
            product_warning = f"Детализация по товарам временно недоступна: {error}"

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

        note = (
            "Исторические данные закрытой точки загружены из iikoServer OLAP, "
            "потому что текущий inventory API iikoCloud может не отдавать документы закрытых подразделений."
        )
        if daily_aggregates == ["DishDiscountSumInt"]:
            note += " Для старого периода iikoServer отдал только выручку; количество и число чеков недоступны в этом OLAP-срезе."
        elif "DishAmountInt" not in daily_aggregates:
            note += " Для старого периода iikoServer не отдал количество позиций; выручка и чеки доступны."
        if product_warning:
            note += " " + product_warning

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
                "nomenclature": product_warning,
                "documentDetails": [],
                "note": note,
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
        kind, resolved_point = _resolve_archived_point(point)
        if not kind:
            return original_build_analytics(point, date_from, date_to)

        # Archived branches should never depend on the current iikoCloud inventory
        # sales-document endpoint. Resolve the visible branch name from its code and
        # go straight to iikoServer, where historical SALES OLAP is kept.
        try:
            return _archived_from_server(resolved_point, date_from, date_to)
        except Exception as error:
            return None, {
                "success": False,
                "message": "Исторические данные этой точки пока не удалось получить из iikoServer.",
                "details": str(error),
                "archivedPoint": True,
                "point": resolved_point,
                "requestedPoint": point,
                "archiveKind": kind,
            }, 409

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
                tag = '<script src="/static/point-archive-polish.js?v=20260917-3"></script>'
                if "point-archive-polish.js" not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
