import hashlib
import os
import threading
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

IIKO_BASE_URL = "https://api-ru.iiko.services"
LOCAL_TZ = ZoneInfo("Asia/Almaty")

TOKEN_TTL_SECONDS = 50 * 60
PRODUCTS_TTL_SECONDS = 6 * 60 * 60
DEPARTMENTS_TTL_SECONDS = 10 * 60
ANALYTICS_TTL_SECONDS = 5 * 60
OLAP_TTL_SECONDS = 5 * 60
DETAIL_WORKERS = max(2, min(int(os.environ.get("IIKO_DETAIL_WORKERS", "8")), 12))
MAX_ANALYTICS_DAYS = 62

_token_cache = {"value": None, "expires_at": 0.0}
_kiosk_token_cache = {"value": None, "expires_at": 0.0}
_products_cache = {"value": None, "last_good": None, "expires_at": 0.0}
_departments_cache = {"value": None, "expires_at": 0.0}
_analytics_cache = {}
_olap_cache = {}

_token_lock = threading.Lock()
_kiosk_token_lock = threading.Lock()
_products_lock = threading.Lock()
_departments_lock = threading.Lock()
_analytics_lock = threading.Lock()
_olap_lock = threading.Lock()


def _cache_valid(cache):
    return cache.get("value") is not None and cache.get("expires_at", 0) > time.time()


def get_iiko_token(force_refresh=False):
    if not force_refresh and _cache_valid(_token_cache):
        return _token_cache["value"]
    with _token_lock:
        if not force_refresh and _cache_valid(_token_cache):
            return _token_cache["value"]
        app_id = os.environ.get("IIKO_APP_ID")
        client_secret = os.environ.get("IIKO_CLIENT_SECRET")
        api_key = os.environ.get("IIKO_API_KEY")
        if not all([app_id, client_secret, api_key]):
            raise RuntimeError("iikoCloud credentials are not configured")
        response = requests.post(
            f"{IIKO_BASE_URL}/api/v2/access_token",
            json={"appId": app_id, "clientSecret": client_secret, "apiKey": api_key},
            timeout=20,
        )
        response.raise_for_status()
        token = response.json()["token"]
        _token_cache["value"] = token
        _token_cache["expires_at"] = time.time() + TOKEN_TTL_SECONDS
        return token


def iiko_headers():
    return {
        "Authorization": f"Bearer {get_iiko_token()}",
        "Content-Type": "application/json",
    }


def iiko_post(path, payload, timeout=30, retry_auth=True):
    response = requests.post(
        f"{IIKO_BASE_URL}{path}",
        headers=iiko_headers(),
        json=payload,
        timeout=timeout,
    )
    if response.status_code == 401 and retry_auth:
        get_iiko_token(force_refresh=True)
        return iiko_post(path, payload, timeout=timeout, retry_auth=False)
    return response


def get_iiko_kiosk_token(force_refresh=False):
    if not force_refresh and _cache_valid(_kiosk_token_cache):
        return _kiosk_token_cache["value"]
    with _kiosk_token_lock:
        if not force_refresh and _cache_valid(_kiosk_token_cache):
            return _kiosk_token_cache["value"]
        app_id = os.environ.get("IIKO_KIOSK_APP_ID") or os.environ.get("IIKO_APP_ID")
        client_secret = os.environ.get("IIKO_KIOSK_CLIENT_SECRET") or os.environ.get("IIKO_CLIENT_SECRET")
        api_key = os.environ.get("IIKO_KIOSK_API_KEY")
        if not all([app_id, client_secret, api_key]):
            raise RuntimeError("Dedicated iiko Kiosk API key is not configured")
        response = requests.post(
            f"{IIKO_BASE_URL}/api/v2/access_token",
            json={"appId": app_id, "clientSecret": client_secret, "apiKey": api_key},
            timeout=20,
        )
        response.raise_for_status()
        token = response.json()["token"]
        _kiosk_token_cache["value"] = token
        _kiosk_token_cache["expires_at"] = time.time() + TOKEN_TTL_SECONDS
        return token


def iiko_kiosk_post(path, payload, timeout=30, retry_auth=True):
    response = requests.post(
        f"{IIKO_BASE_URL}{path}",
        headers={
            "Authorization": f"Bearer {get_iiko_kiosk_token()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    if response.status_code == 401 and retry_auth:
        get_iiko_kiosk_token(force_refresh=True)
        return iiko_kiosk_post(path, payload, timeout=timeout, retry_auth=False)
    return response


def get_departments(force_refresh=False):
    if not force_refresh and _cache_valid(_departments_cache):
        return _departments_cache["value"]
    with _departments_lock:
        if not force_refresh and _cache_valid(_departments_cache):
            return _departments_cache["value"]
        response = iiko_post("/api/inventory/v1/organizations/tree", {}, timeout=30)
        response.raise_for_status()
        tree = response.json()
        departments = []

        def walk(value):
            if isinstance(value, dict):
                if value.get("type") == "DEPARTMENT" and value.get("organizationId"):
                    departments.append({
                        "organizationId": value.get("organizationId"),
                        "name": value.get("name"),
                        "code": value.get("code"),
                        "parentId": value.get("parentId"),
                    })
                for child in value.values():
                    if isinstance(child, (dict, list)):
                        walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(tree)
        _departments_cache["value"] = departments
        _departments_cache["expires_at"] = time.time() + DEPARTMENTS_TTL_SECONDS
        return departments


def find_department(point):
    point_normalized = point.strip().lower()
    departments = get_departments()
    for department in departments:
        code = (department.get("code") or "").strip().lower()
        name = (department.get("name") or "").strip().lower()
        if code == point_normalized or name == point_normalized:
            return department, departments
    for department in departments:
        code = (department.get("code") or "").strip().lower()
        name = (department.get("name") or "").strip().lower()
        if point_normalized in code or point_normalized in name:
            return department, departments
    return None, departments


def get_sales_documents(organization_id, date_from, date_to):
    response = iiko_post(
        "/api/inventory/v1/sales_document/list",
        {"organizationId": organization_id, "from": date_from, "to": date_to},
        timeout=35,
    )
    response.raise_for_status()
    return response.json()


def get_sales_document(organization_id, document_id):
    response = iiko_post(
        "/api/inventory/v1/sales_document/get",
        {"organizationId": organization_id, "documentId": document_id},
        timeout=35,
    )
    response.raise_for_status()
    return response.json()


def get_products_map(force_refresh=False):
    if not force_refresh and _cache_valid(_products_cache):
        return _products_cache["value"]
    with _products_lock:
        if not force_refresh and _cache_valid(_products_cache):
            return _products_cache["value"]
        last_error = None
        for attempt in range(3):
            try:
                products = {}
                offset = 0
                limit = 1000
                while True:
                    response = iiko_post(
                        "/api/nomenclature/v1/product/list",
                        {"limit": limit, "offset": offset},
                        timeout=45,
                    )
                    if response.status_code == 429 or response.status_code >= 500:
                        raise requests.HTTPError(response=response)
                    response.raise_for_status()
                    data = response.json()
                    items = data.get("items", [])
                    for product in items:
                        product_id = product.get("productId")
                        if product_id:
                            products[product_id] = {
                                "name": product.get("name") or "Позиция без названия",
                                "article": product.get("productArticle"),
                            }
                    total_count = data.get("totalCount")
                    offset += len(items)
                    if not items:
                        break
                    if total_count is not None and offset >= total_count:
                        break
                    if len(items) < limit:
                        break
                _products_cache["value"] = products
                _products_cache["last_good"] = products
                _products_cache["expires_at"] = time.time() + PRODUCTS_TTL_SECONDS
                return products
            except Exception as error:
                last_error = error
                if attempt < 2:
                    time.sleep(1.2 * (attempt + 1))
        if _products_cache.get("last_good"):
            return _products_cache["last_good"]
        raise last_error




def get_external_menus(organization_id):
    response = iiko_post(
        "/api/2/menu",
        {"organizationIds": [organization_id]},
        timeout=35,
    )
    response.raise_for_status()
    return response.json()


def get_external_menu_by_id(external_menu_id, organization_id):
    response = iiko_post(
        "/api/2/menu/by_id",
        {
            "externalMenuId": str(external_menu_id),
            "organizationIds": [organization_id],
        },
        timeout=45,
    )
    response.raise_for_status()
    return response.json()


def _menu_price(prices, organization_id):
    prices = prices or []
    for entry in prices:
        if str(entry.get("organizationId")) == str(organization_id):
            try:
                return round(float(entry.get("price")), 2)
            except (TypeError, ValueError):
                pass
    for entry in prices:
        try:
            return round(float(entry.get("price")), 2)
        except (TypeError, ValueError):
            continue
    return None


def _normalize_modifier_item(item, organization_id):
    # Modifier items in iiko external menu use their own compact schema:
    # prices/restrictions live directly on the modifier item (not only in itemSizes).
    prices = item.get("prices") or []
    image_url = item.get("buttonImage") or item.get("buttonImageUrl")
    restrictions = item.get("restrictions") or {}

    # Keep compatibility with alternate/full MenuItem-shaped modifier payloads.
    if not prices:
        sizes = item.get("itemSizes") or []
        size = next((s for s in sizes if s.get("isDefault")), None) or (sizes[0] if sizes else {})
        prices = size.get("prices") or []
        image_url = image_url or size.get("buttonImageUrl")
        if not restrictions:
            restrictions = size.get("restrictions") or {}

    return {
        "id": item.get("itemId"),
        "sku": item.get("sku"),
        "name": item.get("name"),
        "price": _menu_price(prices, organization_id) or 0,
        "imageUrl": image_url,
        "isHidden": bool(item.get("isHidden")),
        "minQuantity": restrictions.get("minQuantity") or 0,
        "maxQuantity": restrictions.get("maxQuantity") or 0,
        "freeQuantity": restrictions.get("freeQuantity") or 0,
        "byDefault": restrictions.get("byDefault") or 0,
    }


def normalize_external_menu(menu_data, organization_id):
    categories = []
    products = []
    for category in menu_data.get("itemCategories", []) or []:
        if category.get("isHidden"):
            continue
        category_id = category.get("id")
        categories.append({
            "id": category_id,
            "name": category.get("name"),
            "description": category.get("description"),
            "imageUrl": category.get("buttonImageUrl") or category.get("headerImageUrl"),
        })
        for item in category.get("items", []) or []:
            if item.get("isHidden"):
                continue
            sizes = item.get("itemSizes") or []
            if not sizes:
                continue
            for idx, size in enumerate(sizes):
                if size.get("isHidden"):
                    continue
                price = _menu_price(size.get("prices"), organization_id)
                if price is None:
                    continue
                modifier_groups = []
                for group in size.get("itemModifierGroups", []) or []:
                    group_restrictions = group.get("restrictions") or {}
                    modifier_groups.append({
                        "id": group.get("id") or group.get("itemGroupId"),
                        "name": group.get("name"),
                        "minQuantity": (
                            group.get("minQuantity")
                            if group.get("minQuantity") is not None
                            else group_restrictions.get("minQuantity") or 0
                        ),
                        "maxQuantity": (
                            group.get("maxQuantity")
                            if group.get("maxQuantity") is not None
                            else group_restrictions.get("maxQuantity") or 0
                        ),
                        "freeQuantity": group_restrictions.get("freeQuantity") or 0,
                        "byDefault": group_restrictions.get("byDefault") or 0,
                        "items": [
                            _normalize_modifier_item(modifier, organization_id)
                            for modifier in (group.get("items") or [])
                            if not modifier.get("isHidden")
                        ],
                    })
                size_name = (size.get("sizeName") or "").strip()
                display_name = item.get("name") or "Позиция"
                if len(sizes) > 1 and size_name:
                    display_name = f"{display_name} — {size_name}"
                products.append({
                    "id": f"{item.get('itemId')}:{size.get('sizeId') or idx}",
                    "itemId": item.get("itemId"),
                    "sizeId": size.get("sizeId"),
                    "sku": item.get("sku"),
                    "categoryId": category_id,
                    "name": display_name,
                    "description": item.get("description") or "",
                    "price": price,
                    "weightGrams": size.get("portionWeightGrams") or 0,
                    "imageUrl": (
                        size.get("buttonImageUrl")
                        or category.get("buttonImageUrl")
                        or category.get("headerImageUrl")
                    ),
                    "modifierGroups": modifier_groups,
                })
    return categories, products

def get_kiosk_nomenclature(organization_id):
    response = iiko_post(
        "/api/1/nomenclature",
        {"organizationId": organization_id, "startRevision": 0},
        timeout=45,
    )
    response.raise_for_status()
    return response.json()


def kiosk_product_price(product):
    prices = []
    for size_price in product.get("sizePrices", []) or []:
        price_info = size_price.get("price") or {}
        current_price = price_info.get("currentPrice")
        if current_price is None:
            continue
        try:
            price_value = float(current_price)
        except (TypeError, ValueError):
            continue
        prices.append({
            "sizeId": size_price.get("sizeId"),
            "price": round(price_value, 2),
        })
    return prices

def document_date(document, fallback):
    raw = document.get("date") or document.get("dateCreated") or fallback
    if isinstance(raw, str) and len(raw) >= 10:
        return raw[:10]
    return fallback


def date_range(date_from, date_to):
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    if end < start:
        raise ValueError("date_to must not be earlier than date_from")
    days_count = (end - start).days + 1
    if days_count > MAX_ANALYTICS_DAYS:
        raise ValueError(f"Maximum period is {MAX_ANALYTICS_DAYS} days")
    return [(start + timedelta(days=offset)).isoformat() for offset in range(days_count)]


def get_delivery_orders(organization_id, date_from, date_to):
    return iiko_post(
        "/api/1/deliveries/by_delivery_date_and_status",
        {
            "organizationIds": [organization_id],
            "deliveryDateFrom": f"{date_from} 00:00:00.000",
            "deliveryDateTo": f"{date_to} 23:59:59.999",
        },
        timeout=30,
    )


def flatten_orders_response(data):
    orders = []
    for block in data.get("ordersByOrganizations", []) or []:
        organization_id = block.get("organizationId")
        for order in block.get("orders", []) or []:
            if isinstance(order, dict):
                item = dict(order)
                item["_organizationId"] = organization_id
                orders.append(item)
    return orders


def safe_order_sample(order):
    guests = order.get("guestsInfo") or {}
    payments = order.get("payments") or []
    return {
        "id": order.get("id"),
        "posOrderId": order.get("posOrderId"),
        "number": order.get("number"),
        "status": order.get("status"),
        "sum": order.get("sum"),
        "sourceKey": order.get("sourceKey"),
        "whenBillPrinted": order.get("whenBillPrinted"),
        "whenClosed": order.get("whenClosed"),
        "terminalGroupId": order.get("terminalGroupId"),
        "orderServiceType": order.get("orderServiceType"),
        "guestsCount": guests.get("count"),
        "paymentsCount": len(payments),
    }


def fetch_document_details_parallel(organization_id, processed_documents):
    document_errors = []
    details = {}
    jobs = [d.get("documentId") for d in processed_documents if d.get("documentId")]
    if not jobs:
        return details, document_errors
    workers = min(DETAIL_WORKERS, len(jobs))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="iiko-detail") as executor:
        future_to_id = {
            executor.submit(get_sales_document, organization_id, document_id): document_id
            for document_id in jobs
        }
        for future in as_completed(future_to_id):
            document_id = future_to_id[future]
            try:
                details[document_id] = future.result()
            except requests.HTTPError as error:
                response = error.response
                document_errors.append({
                    "documentId": document_id,
                    "statusCode": response.status_code if response is not None else None,
                    "details": response.text[:1000] if response is not None else str(error),
                })
            except Exception as error:
                document_errors.append({
                    "documentId": document_id,
                    "statusCode": None,
                    "details": str(error),
                })
    return details, document_errors


def _analytics_cache_get(key):
    with _analytics_lock:
        cached = _analytics_cache.get(key)
        if not cached:
            return None
        if cached["expires_at"] <= time.time():
            _analytics_cache.pop(key, None)
            return None
        return cached["value"]


def _analytics_cache_set(key, value):
    with _analytics_lock:
        _analytics_cache[key] = {
            "value": value,
            "expires_at": time.time() + ANALYTICS_TTL_SECONDS,
        }
        if len(_analytics_cache) > 40:
            oldest_keys = sorted(_analytics_cache, key=lambda k: _analytics_cache[k]["expires_at"])[:10]
            for old_key in oldest_keys:
                _analytics_cache.pop(old_key, None)


def build_analytics(point, date_from, date_to):
    all_dates = date_range(date_from, date_to)
    department, available_departments = find_department(point)
    if not department:
        return None, {
            "success": False,
            "message": f"Point '{point}' not found",
            "availablePoints": [
                {"code": d.get("code"), "name": d.get("name")}
                for d in available_departments
            ],
        }, 404

    organization_id = department["organizationId"]
    cache_key = (organization_id, date_from, date_to)
    cached = _analytics_cache_get(cache_key)
    if cached is not None:
        payload = dict(cached)
        payload["cache"] = {"hit": True, "ttlSeconds": ANALYTICS_TTL_SECONDS}
        return payload, None, 200

    try:
        product_map = get_products_map()
        nomenclature_warning = None
    except Exception as error:
        product_map = {}
        nomenclature_warning = str(error)

    documents = get_sales_documents(organization_id, date_from, date_to)
    processed_documents = [
        document
        for document in documents
        if not document.get("status") or document.get("status") == "PROCESSED"
    ]
    details_by_id, document_errors = fetch_document_details_parallel(
        organization_id, processed_documents
    )

    totals = defaultdict(lambda: {"quantity": 0.0, "revenue": 0.0, "article": None})
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

    for document in processed_documents:
        document_id = document.get("documentId")
        day = document_date(document, date_from)
        if day not in daily:
            daily[day] = {
                "date": day,
                "revenue": 0.0,
                "itemsRevenue": 0.0,
                "quantity": 0.0,
                "documentsCount": 0,
            }
        daily[day]["revenue"] += float(document.get("sum") or 0)
        daily[day]["documentsCount"] += 1
        detail = details_by_id.get(document_id)
        if not detail:
            continue
        for item in detail.get("items", []):
            product_id = item.get("product")
            if not product_id:
                continue
            quantity = float(item.get("amount") or 0)
            revenue = float(item.get("sum") or 0)
            totals[product_id]["quantity"] += quantity
            totals[product_id]["revenue"] += revenue
            daily[day]["quantity"] += quantity
            daily[day]["itemsRevenue"] += revenue
            if item.get("productArticle"):
                totals[product_id]["article"] = item.get("productArticle")

    products = []
    for product_id, values in totals.items():
        product_info = product_map.get(product_id, {})
        fallback_name = values.get("article") or "Позиция iiko"
        products.append({
            "productId": product_id,
            "name": product_info.get("name") or fallback_name,
            "article": product_info.get("article") or values.get("article"),
            "quantity": round(values["quantity"], 3),
            "revenue": round(values["revenue"], 2),
        })

    by_revenue = sorted(products, key=lambda item: item["revenue"], reverse=True)
    by_quantity = sorted(products, key=lambda item: item["quantity"], reverse=True)
    revenue_from_documents = round(
        sum(float(document.get("sum") or 0) for document in processed_documents), 2
    )
    revenue_from_items = round(sum(product["revenue"] for product in products), 2)
    total_quantity = round(sum(product["quantity"] for product in products), 3)

    daily_series = []
    for day in sorted(daily.keys()):
        item = daily[day]
        daily_series.append({
            "date": day,
            "revenue": round(item["revenue"], 2),
            "itemsRevenue": round(item["itemsRevenue"], 2),
            "quantity": round(item["quantity"], 3),
            "documentsCount": item["documentsCount"],
        })

    days_count = len(all_dates)
    requested_details = len([d for d in processed_documents if d.get("documentId")])
    payload = {
        "success": True,
        "point": {
            "code": department.get("code"),
            "name": department.get("name"),
            "organizationId": organization_id,
        },
        "period": {"from": date_from, "to": date_to, "daysCount": days_count},
        "summary": {
            "documentsCount": len(processed_documents),
            "revenue": revenue_from_documents,
            "itemsRevenue": revenue_from_items,
            "itemsQuantity": total_quantity,
            "uniqueProducts": len(products),
            "averageDailyRevenue": round(revenue_from_documents / days_count, 2) if days_count else 0,
        },
        "daily": daily_series,
        "topByRevenue": by_revenue[:20],
        "topByQuantity": by_quantity[:20],
        "products": by_revenue,
        "warnings": {
            "nomenclature": nomenclature_warning,
            "documentDetails": document_errors,
            "note": (
                "Revenue is based on iiko inventory sales documents. "
                "Receipt analytics is available through iikoServer OLAP when configured."
            ),
        },
        "performance": {
            "detailWorkers": min(DETAIL_WORKERS, max(requested_details, 1)),
            "detailsRequested": requested_details,
            "detailsLoaded": len(details_by_id),
        },
        "cache": {"hit": False, "ttlSeconds": ANALYTICS_TTL_SECONDS},
    }
    _analytics_cache_set(cache_key, payload)
    return payload, None, 200


# ---------------- iikoServer / OLAP ----------------

def iiko_server_settings():
    base_url = (
        os.environ.get("IIKO_SERVER_URL")
        or "https://dc-firdaws-co-arm.iiko.it/resto"
    ).rstrip("/")
    login = os.environ.get("IIKO_SERVER_LOGIN")
    password = os.environ.get("IIKO_SERVER_PASSWORD")
    if not login or not password:
        raise RuntimeError("iikoServer credentials are not configured in Render Environment")
    return base_url, login, password


def iiko_server_auth():
    base_url, login, password = iiko_server_settings()
    password_hash = hashlib.sha1(password.encode("utf-8")).hexdigest()
    response = requests.get(
        f"{base_url}/api/auth",
        params={"login": login, "pass": password_hash},
        timeout=25,
    )
    response.raise_for_status()
    token = response.text.strip().strip('"')
    if not token or "<html" in token.lower():
        raise RuntimeError("iikoServer authentication did not return an API token")
    return base_url, token


def iiko_server_logout(base_url, token):
    try:
        requests.get(
            f"{base_url}/api/logout",
            params={"key": token},
            timeout=10,
        )
    except Exception:
        pass



def iiko_server_products(base_url, token):
    response = requests.get(
        f"{base_url}/api/v2/entities/products/list",
        params={"key": token, "includeDeleted": "false"},
        headers={"Accept": "application/json"},
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else (data.get("items") or data.get("response") or [])

def iiko_server_departments(base_url, token):
    response = requests.get(
        f"{base_url}/api/corporation/departments",
        params={"key": token},
        timeout=30,
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    result = []
    for node in root.iter():
        children = {
            child.tag.split("}")[-1]: (child.text or "").strip()
            for child in list(node)
        }
        if children.get("type") == "DEPARTMENT" and children.get("id"):
            result.append({
                "id": children.get("id"),
                "name": children.get("name"),
                "code": children.get("code"),
                "parentId": children.get("parentId"),
            })
    return result


def find_iiko_server_department(point, departments):
    normalized = (point or "").strip().lower()
    for department in departments:
        code = (department.get("code") or "").strip().lower()
        name = (department.get("name") or "").strip().lower()
        if code == normalized or name == normalized:
            return department
    for department in departments:
        code = (department.get("code") or "").strip().lower()
        name = (department.get("name") or "").strip().lower()
        if normalized and (normalized in code or normalized in name):
            return department
    return None


def run_iiko_server_olap(base_url, token, date_from, date_to, department_id=None):
    filters = {
        "OpenDate.Typed": {
            "filterType": "DateRange",
            "periodType": "CUSTOM",
            "from": date_from,
            "to": date_to,
            "includeLow": True,
            "includeHigh": True,
        },
        "OrderDeleted": {
            "filterType": "IncludeValues",
            "values": ["NOT_DELETED"],
        },
    }
    if department_id:
        filters["Department.Id"] = {
            "filterType": "IncludeValues",
            "values": [department_id],
        }
    body = {
        "reportType": "SALES",
        "buildSummary": False,
        "groupByRowFields": ["Department.Id", "CloseTime"],
        "groupByColFields": [],
        "aggregateFields": [
            "GuestNum",
            "DishDiscountSumInt.average",
            "DishDiscountSumInt",
            "UniqOrderId",
        ],
        "filters": filters,
    }
    response = requests.post(
        f"{base_url}/api/v2/reports/olap",
        params={"key": token},
        json=body,
        headers={"Content-Type": "application/json"},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def _olap_cache_get(key):
    with _olap_lock:
        cached = _olap_cache.get(key)
        if not cached:
            return None
        if cached["expires_at"] <= time.time():
            _olap_cache.pop(key, None)
            return None
        return cached["value"]


def _olap_cache_set(key, value):
    with _olap_lock:
        _olap_cache[key] = {
            "value": value,
            "expires_at": time.time() + OLAP_TTL_SECONDS,
        }
        if len(_olap_cache) > 60:
            oldest = sorted(_olap_cache, key=lambda k: _olap_cache[k]["expires_at"])[:15]
            for key_to_remove in oldest:
                _olap_cache.pop(key_to_remove, None)


def aggregate_olap_rows(rows, date_from, date_to):
    days_count = len(date_range(date_from, date_to))
    total_checks = 0.0
    total_revenue = 0.0
    total_guests = 0.0
    hourly = [
        {"hour": hour, "label": f"{hour:02d}:00", "checks": 0.0, "revenue": 0.0, "guests": 0.0}
        for hour in range(24)
    ]

    for row in rows:
        checks = float(row.get("UniqOrderId") or 0)
        revenue = float(row.get("DishDiscountSumInt") or 0)
        guests = float(row.get("GuestNum") or 0)
        total_checks += checks
        total_revenue += revenue
        total_guests += guests

        close_time = row.get("CloseTime")
        if close_time:
            try:
                hour = datetime.fromisoformat(str(close_time).replace("Z", "+00:00")).hour
                hourly[hour]["checks"] += checks
                hourly[hour]["revenue"] += revenue
                hourly[hour]["guests"] += guests
            except (ValueError, TypeError):
                pass

    max_hour_revenue = max((item["revenue"] for item in hourly), default=0) or 1
    for item in hourly:
        item["checks"] = round(item["checks"], 3)
        item["revenue"] = round(item["revenue"], 2)
        item["guests"] = round(item["guests"], 3)
        item["averageCheck"] = round(item["revenue"] / item["checks"], 2) if item["checks"] else 0
        item["averageRevenuePerDay"] = round(item["revenue"] / days_count, 2) if days_count else 0
        item["intensity"] = round(item["revenue"] / max_hour_revenue, 4) if max_hour_revenue else 0

    active_hours = [item for item in hourly if item["checks"] > 0]
    peak = max(active_hours, key=lambda item: item["revenue"], default=None)
    weak = min(active_hours, key=lambda item: item["revenue"], default=None)

    return {
        "checks": round(total_checks, 3),
        "revenue": round(total_revenue, 2),
        "guests": round(total_guests, 3),
        "averageCheck": round(total_revenue / total_checks, 2) if total_checks else 0,
        "averageGuestsPerCheck": round(total_guests / total_checks, 2) if total_checks else 0,
        "daysCount": days_count,
        "hourly": hourly,
        "peakHour": peak,
        "weakHour": weak,
    }


def build_receipt_analytics(point, date_from, date_to):
    date_range(date_from, date_to)
    cache_key = ((point or "").strip().lower(), date_from, date_to)
    cached = _olap_cache_get(cache_key)
    if cached is not None:
        result = dict(cached)
        result["cache"] = {"hit": True, "ttlSeconds": OLAP_TTL_SECONDS}
        return result

    base_url = None
    token = None
    try:
        base_url, token = iiko_server_auth()
        departments = iiko_server_departments(base_url, token)
        department = find_iiko_server_department(point, departments)
        if not department:
            raise ValueError(f"Point '{point}' not found in iikoServer departments")
        data = run_iiko_server_olap(
            base_url,
            token,
            date_from,
            date_to,
            department.get("id"),
        )
        rows = data.get("data", []) if isinstance(data, dict) else []
        metrics = aggregate_olap_rows(rows, date_from, date_to)
        result = {
            "success": True,
            "source": "iikoServer OLAP SALES",
            "point": {
                "id": department.get("id"),
                "code": department.get("code"),
                "name": department.get("name"),
            },
            "period": {"from": date_from, "to": date_to, "daysCount": metrics["daysCount"]},
            "summary": {
                "checks": metrics["checks"],
                "revenue": metrics["revenue"],
                "guests": metrics["guests"],
                "averageCheck": metrics["averageCheck"],
                "averageGuestsPerCheck": metrics["averageGuestsPerCheck"],
            },
            "hourly": metrics["hourly"],
            "peakHour": metrics["peakHour"],
            "weakHour": metrics["weakHour"],
            "rows": len(rows),
            "cache": {"hit": False, "ttlSeconds": OLAP_TTL_SECONDS},
        }
        _olap_cache_set(cache_key, result)
        return result
    finally:
        if base_url and token:
            iiko_server_logout(base_url, token)


@app.route("/kiosk")
def kiosk():
    return app.send_static_file("kiosk-preview.html")


@app.route("/")
def home():
    if os.environ.get("APP_MODE", "").strip().lower() == "kiosk":
        return app.send_static_file("kiosk-preview.html")
    return jsonify({
        "service": "Doner Club Analytics",
        "status": "online",
        "dashboard": "/static/dashboard.html",
        "examples": {
            "arai_day": "/analytics?point=Arai&date=2026-09-15",
            "arai_period": "/analytics?point=Arai&from=2026-09-01&to=2026-09-15",
            "receipt_analytics": "/receipt-analytics?point=Arai&date=2026-09-15",
            "departments": "/departments",
            "orders_access_test": "/orders-access-test?point=Arai",
            "olap_access_test": "/olap-access-test?date=2026-09-15",
            "olap_departments": "/olap-departments",
        },
    })


@app.route("/departments")
def departments():
    try:
        return jsonify({"success": True, "departments": get_departments()})
    except requests.HTTPError as error:
        response = error.response
        return jsonify({
            "success": False,
            "statusCode": response.status_code if response is not None else None,
            "details": response.text[:1200] if response is not None else str(error),
        }), 500
    except Exception as error:
        return jsonify({"success": False, "message": str(error)}), 500


@app.route("/orders-access-test")
def orders_access_test():
    try:
        point = request.args.get("point", "Arai").strip()
        default_date = (datetime.now(LOCAL_TZ).date() - timedelta(days=1)).isoformat()
        date_from = request.args.get("from") or request.args.get("date") or default_date
        date_to = request.args.get("to") or date_from
        department, available_departments = find_department(point)
        if not department:
            return jsonify({
                "success": False,
                "message": f"Point '{point}' not found",
                "availablePoints": [
                    {"code": d.get("code"), "name": d.get("name")}
                    for d in available_departments
                ],
            }), 404
        organization_id = department["organizationId"]
        response = get_delivery_orders(organization_id, date_from, date_to)
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text[:4000]}
        if not response.ok:
            return jsonify({
                "success": False,
                "access": False,
                "endpoint": "/api/1/deliveries/by_delivery_date_and_status",
                "requiredRestrictionGroup": "Orders: receiving",
                "statusCode": response.status_code,
                "point": {
                    "code": department.get("code"),
                    "name": department.get("name"),
                    "organizationId": organization_id,
                },
                "period": {"from": date_from, "to": date_to},
                "details": data,
            }), response.status_code
        orders = flatten_orders_response(data)
        sums = [float(o.get("sum") or 0) for o in orders]
        closed = [o for o in orders if o.get("whenClosed")]
        return jsonify({
            "success": True,
            "access": True,
            "endpoint": "/api/1/deliveries/by_delivery_date_and_status",
            "requiredRestrictionGroup": "Orders: receiving",
            "point": {
                "code": department.get("code"),
                "name": department.get("name"),
                "organizationId": organization_id,
            },
            "period": {"from": date_from, "to": date_to},
            "orderCount": len(orders),
            "closedOrderCount": len(closed),
            "sumOfReturnedOrders": round(sum(sums), 2),
            "sample": [safe_order_sample(o) for o in orders[:5]],
            "diagnosis": (
                "Access granted and order-level records were returned."
                if orders
                else "Access granted, but this delivery endpoint returned no orders."
            ),
        })
    except Exception as error:
        return jsonify({"success": False, "access": False, "message": str(error)}), 500


@app.route("/olap-departments")
def olap_departments():
    base_url = None
    token = None
    try:
        base_url, token = iiko_server_auth()
        departments_data = iiko_server_departments(base_url, token)
        return jsonify({
            "success": True,
            "count": len(departments_data),
            "departments": departments_data,
        })
    except requests.HTTPError as error:
        response = error.response
        return jsonify({
            "success": False,
            "statusCode": response.status_code if response is not None else None,
            "message": "iikoServer request failed",
            "details": response.text[:1200] if response is not None else str(error),
        }), 502
    except Exception as error:
        return jsonify({"success": False, "message": str(error)}), 500
    finally:
        if base_url and token:
            iiko_server_logout(base_url, token)


@app.route("/olap-access-test")
def olap_access_test():
    base_url = None
    token = None
    try:
        default_date = (datetime.now(LOCAL_TZ).date() - timedelta(days=1)).isoformat()
        date_from = request.args.get("from") or request.args.get("date") or default_date
        date_to = request.args.get("to") or date_from
        department_id = request.args.get("departmentId") or None
        date_range(date_from, date_to)
        base_url, token = iiko_server_auth()
        data = run_iiko_server_olap(base_url, token, date_from, date_to, department_id)
        rows = data.get("data", []) if isinstance(data, dict) else []
        metrics = aggregate_olap_rows(rows, date_from, date_to)
        department_ids = sorted({row.get("Department.Id") for row in rows if row.get("Department.Id")})
        return jsonify({
            "success": True,
            "access": True,
            "source": "iikoServer OLAP SALES",
            "period": {"from": date_from, "to": date_to},
            "departmentFilter": department_id,
            "rows": len(rows),
            "departmentIds": department_ids,
            "totals": {
                "checks": metrics["checks"],
                "revenue": metrics["revenue"],
                "guests": metrics["guests"],
                "averageCheck": metrics["averageCheck"],
            },
            "sample": rows[:10],
        })
    except requests.HTTPError as error:
        response = error.response
        return jsonify({
            "success": False,
            "access": False,
            "statusCode": response.status_code if response is not None else None,
            "message": "iikoServer authorization or OLAP request failed",
            "details": response.text[:1200] if response is not None else str(error),
        }), 502
    except Exception as error:
        return jsonify({"success": False, "access": False, "message": str(error)}), 500
    finally:
        if base_url and token:
            iiko_server_logout(base_url, token)


@app.route("/receipt-analytics")
def receipt_analytics():
    try:
        point = request.args.get("point", "Arai").strip()
        single_date = request.args.get("date")
        date_from = request.args.get("from")
        date_to = request.args.get("to")
        if single_date:
            date_from = single_date
            date_to = single_date
        if not date_from:
            date_from = (datetime.now(LOCAL_TZ).date() - timedelta(days=1)).isoformat()
        if not date_to:
            date_to = date_from
        return jsonify(build_receipt_analytics(point, date_from, date_to))
    except ValueError as error:
        return jsonify({"success": False, "code": "INVALID_PERIOD_OR_POINT", "message": str(error)}), 400
    except requests.Timeout:
        return jsonify({
            "success": False,
            "code": "OLAP_TIMEOUT",
            "message": "iikoServer did not answer in time. Please retry the request.",
        }), 504
    except requests.HTTPError as error:
        response = error.response
        return jsonify({
            "success": False,
            "code": "OLAP_HTTP_ERROR",
            "statusCode": response.status_code if response is not None else None,
            "message": "iikoServer OLAP request failed",
            "details": response.text[:1500] if response is not None else str(error),
        }), 502
    except Exception as error:
        return jsonify({"success": False, "code": "OLAP_ERROR", "message": str(error)}), 500



def get_terminal_groups_for_organization(organization_id):
    response = iiko_post(
        "/api/1/terminal_groups",
        {
            "organizationIds": [organization_id],
            "includeDisabled": False,
        },
        timeout=35,
    )
    response.raise_for_status()
    data = response.json()
    groups = []
    for block in data.get("terminalGroups", []) or []:
        if str(block.get("organizationId")) != str(organization_id):
            continue
        for item in block.get("items", []) or []:
            group_id = item.get("id")
            if not group_id:
                continue
            groups.append({
                "id": group_id,
                "name": item.get("name") or "Terminal group",
                "organizationId": item.get("organizationId") or organization_id,
            })
    return groups, data


def get_terminal_groups_alive(organization_id, terminal_group_ids):
    if not terminal_group_ids:
        return {}
    response = iiko_post(
        "/api/1/terminal_groups/is_alive",
        {
            "organizationIds": [organization_id],
            "terminalGroupIds": terminal_group_ids,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return {
        str(item.get("terminalGroupId")): bool(item.get("isAlive"))
        for item in (data.get("isAliveStatus") or [])
        if item.get("terminalGroupId")
    }


def get_restaurant_sections_for_terminal_groups(terminal_group_ids):
    if not terminal_group_ids:
        return [], {}
    response = iiko_post(
        "/api/1/reserve/available_restaurant_sections",
        {
            "terminalGroupIds": terminal_group_ids,
            "returnSchema": True,
            "revision": 0,
        },
        timeout=40,
    )
    response.raise_for_status()
    data = response.json()
    sections = []
    for section in data.get("restaurantSections", []) or []:
        section_id = section.get("id")
        terminal_group_id = section.get("terminalGroupId")
        section_name = section.get("name") or "Зал"
        tables = []
        for table in section.get("tables", []) or []:
            if table.get("isDeleted"):
                continue
            table_id = table.get("id")
            if not table_id:
                continue
            tables.append({
                "id": table_id,
                "number": table.get("number"),
                "name": table.get("name") or "",
                "seatingCapacity": table.get("seatingCapacity"),
                "sectionId": section_id,
                "sectionName": section_name,
                "terminalGroupId": terminal_group_id,
            })
        sections.append({
            "id": section_id,
            "name": section_name,
            "terminalGroupId": terminal_group_id,
            "tables": tables,
        })
    return sections, data


@app.route("/kiosk-iiko-config")
def kiosk_iiko_config():
    point = request.args.get("point", "Arai").strip()
    try:
        department, available_departments = find_department(point)
        if not department:
            return jsonify({
                "success": False,
                "code": "POINT_NOT_FOUND",
                "message": f"Point '{point}' not found",
                "availablePoints": [
                    {"code": d.get("code"), "name": d.get("name")}
                    for d in available_departments
                ],
            }), 404

        organization_id = department["organizationId"]
        terminal_groups, _ = get_terminal_groups_for_organization(organization_id)
        terminal_group_ids = [group["id"] for group in terminal_groups]
        alive = get_terminal_groups_alive(organization_id, terminal_group_ids)
        sections, _ = get_restaurant_sections_for_terminal_groups(terminal_group_ids)

        for group in terminal_groups:
            group["isAlive"] = alive.get(str(group["id"]))

        tables = []
        for section in sections:
            tables.extend(section.get("tables") or [])

        response = jsonify({
            "success": True,
            "point": {
                "code": department.get("code"),
                "name": department.get("name"),
                "organizationId": organization_id,
            },
            "terminalGroups": terminal_groups,
            "restaurantSections": sections,
            "tables": tables,
            "canSendTestOrder": bool(terminal_groups and tables),
        })
        response.headers["Cache-Control"] = "no-store"
        return response
    except requests.Timeout:
        return jsonify({
            "success": False,
            "code": "IIKO_TIMEOUT",
            "message": "iiko did not answer in time.",
        }), 504
    except requests.HTTPError as error:
        response = error.response
        return jsonify({
            "success": False,
            "code": "IIKO_HTTP_ERROR",
            "statusCode": response.status_code if response is not None else None,
            "details": response.text[:1500] if response is not None else str(error),
        }), 502
    except Exception as error:
        return jsonify({
            "success": False,
            "code": "KIOSK_IIKO_CONFIG_ERROR",
            "message": str(error),
        }), 500


@app.route("/kiosk-test-order", methods=["POST"])
def kiosk_test_order():
    data = request.get_json(silent=True) or {}

    # Hard safety gate: this endpoint cannot create anything unless the caller
    # explicitly sends this confirmation value from the final confirmation click.
    if data.get("confirm") != "SEND_TEST_ORDER":
        return jsonify({
            "success": False,
            "code": "EXPLICIT_CONFIRMATION_REQUIRED",
            "message": "Test order was NOT sent. Explicit confirmation is required.",
        }), 400

    point = (data.get("point") or "Arai").strip()
    terminal_group_id = str(data.get("terminalGroupId") or "").strip()
    table_id = str(data.get("tableId") or "").strip()
    incoming_items = data.get("items") or []

    if not terminal_group_id or not table_id or not incoming_items:
        return jsonify({
            "success": False,
            "code": "INVALID_TEST_ORDER",
            "message": "terminalGroupId, tableId and items are required.",
        }), 400

    try:
        if not all([
            os.environ.get("IIKO_KIOSK_API_KEY"),
            os.environ.get("IIKO_KIOSK_APP_ID") or os.environ.get("IIKO_APP_ID"),
            os.environ.get("IIKO_KIOSK_CLIENT_SECRET") or os.environ.get("IIKO_CLIENT_SECRET"),
        ]):
            return jsonify({
                "success": False,
                "code": "KIOSK_API_NOT_CONFIGURED",
                "message": "Test order was NOT sent. Configure IIKO_KIOSK_API_KEY for the Doner Club Kiosk integration first.",
            }), 503

        department, available_departments = find_department(point)
        if not department:
            return jsonify({
                "success": False,
                "code": "POINT_NOT_FOUND",
                "message": f"Point '{point}' not found",
                "availablePoints": [
                    {"code": d.get("code"), "name": d.get("name")}
                    for d in available_departments
                ],
            }), 404

        organization_id = department["organizationId"]
        terminal_groups, _ = get_terminal_groups_for_organization(organization_id)
        allowed_group_ids = {str(group["id"]) for group in terminal_groups}
        if terminal_group_id not in allowed_group_ids:
            return jsonify({
                "success": False,
                "code": "INVALID_TERMINAL_GROUP",
                "message": "Selected terminal group does not belong to Arai.",
            }), 400

        sections, _ = get_restaurant_sections_for_terminal_groups([terminal_group_id])
        allowed_table_ids = {
            str(table.get("id"))
            for section in sections
            for table in (section.get("tables") or [])
            if table.get("id")
        }
        if table_id not in allowed_table_ids:
            return jsonify({
                "success": False,
                "code": "INVALID_TABLE",
                "message": "Selected table is not available for this terminal group.",
            }), 400

        order_items = []
        for source_item in incoming_items:
            product_id = str(source_item.get("productId") or "").strip()
            if not product_id:
                continue
            try:
                amount = float(source_item.get("amount") or 0)
            except (TypeError, ValueError):
                amount = 0
            if amount <= 0:
                continue

            order_item = {
                "productId": product_id,
                "type": "Product",
                "amount": amount,
            }
            product_size_id = source_item.get("productSizeId")
            if product_size_id:
                order_item["productSizeId"] = str(product_size_id)

            modifiers = []
            for modifier in source_item.get("modifiers") or []:
                modifier_product_id = str(modifier.get("productId") or "").strip()
                if not modifier_product_id:
                    continue
                modifier_payload = {
                    "productId": modifier_product_id,
                    "amount": float(modifier.get("amount") or 1),
                }
                product_group_id = modifier.get("productGroupId")
                if product_group_id:
                    modifier_payload["productGroupId"] = str(product_group_id)
                modifiers.append(modifier_payload)
            if modifiers:
                order_item["modifiers"] = modifiers

            order_items.append(order_item)

        if not order_items:
            return jsonify({
                "success": False,
                "code": "NO_VALID_ITEMS",
                "message": "No valid order items were supplied.",
            }), 400

        payload = {
            "organizationId": organization_id,
            "terminalGroupId": terminal_group_id,
            "createOrderSettings": {
                # Ask iikoFront to save/send the order with service printing,
                # while keeping the test order completely unpaid.
                "servicePrint": True,
                "transportToFrontTimeout": 10,
                "checkStopList": True,
            },
            "order": {
                "tableIds": [table_id],
                "items": order_items,
                "guests": {
                    "count": 1,
                    "splitBetweenPersons": False,
                },
                "comment": "TEST KIOSK — БЕЗ ОПЛАТЫ",
            },
        }

        response = iiko_kiosk_post("/api/1/order/create", payload, timeout=45)
        if not response.ok:
            return jsonify({
                "success": False,
                "code": "IIKO_ORDER_CREATE_FAILED",
                "statusCode": response.status_code,
                "details": response.text[:2500],
            }), 502

        result = response.json()

        # iiko table-order creation may be asynchronous. If it answers
        # InProgress, check the command state for a few seconds so the kiosk
        # can distinguish "request accepted" from "processed by iikoFront".
        command_status = None
        correlation_id = result.get("correlationId")
        order_info = result.get("orderInfo") or {}
        if correlation_id and order_info.get("creationStatus") == "InProgress":
            for _ in range(6):
                time.sleep(1)
                status_response = iiko_kiosk_post(
                    "/api/1/commands/status",
                    {
                        "organizationId": organization_id,
                        "correlationId": correlation_id,
                    },
                    timeout=20,
                )
                if status_response.ok:
                    command_status = status_response.json()
                    if command_status.get("state") in ("Success", "Error"):
                        break
                else:
                    break

        return jsonify({
            "success": True,
            "message": "Test order request was sent to iiko.",
            "organizationId": organization_id,
            "terminalGroupId": terminal_group_id,
            "tableId": table_id,
            "servicePrintRequested": True,
            "commandStatus": command_status,
            "iiko": result,
        })
    except requests.Timeout:
        return jsonify({
            "success": False,
            "code": "IIKO_TIMEOUT",
            "message": "iiko did not answer in time.",
        }), 504
    except requests.HTTPError as error:
        response = error.response
        return jsonify({
            "success": False,
            "code": "IIKO_HTTP_ERROR",
            "statusCode": response.status_code if response is not None else None,
            "details": response.text[:2500] if response is not None else str(error),
        }), 502
    except Exception as error:
        return jsonify({
            "success": False,
            "code": "KIOSK_TEST_ORDER_ERROR",
            "message": str(error),
        }), 500


@app.route("/kiosk-test-paid-order", methods=["POST"])
def kiosk_test_paid_order():
    data = request.get_json(silent=True) or {}

    # Paid-test safety: this endpoint is available only on the dedicated kiosk
    # Render service and only after an explicit final confirmation from the UI.
    if os.environ.get("APP_MODE", "").strip().lower() != "kiosk":
        return jsonify({
            "success": False,
            "code": "KIOSK_MODE_REQUIRED",
            "message": "Paid test order was NOT sent. This endpoint is available only in kiosk mode.",
        }), 403

    if (
        data.get("confirm") != "SEND_PAID_TEST_ORDER"
        or data.get("acknowledgeFinancialEffect") is not True
    ):
        return jsonify({
            "success": False,
            "code": "PAID_TEST_CONFIRMATION_REQUIRED",
            "message": "Paid test order was NOT sent. Explicit financial confirmation is required.",
        }), 400

    point = (data.get("point") or "Arai").strip()
    terminal_group_id = str(data.get("terminalGroupId") or "").strip()
    table_id = str(data.get("tableId") or "").strip()
    incoming_items = data.get("items") or []

    try:
        payment_sum = round(float(data.get("paymentSum") or 0), 2)
    except (TypeError, ValueError):
        payment_sum = 0

    # Keep the temporary test endpoint intentionally small. The production
    # ForteBank flow will use a separate verified-payment endpoint later.
    if payment_sum <= 0 or payment_sum > 5000:
        return jsonify({
            "success": False,
            "code": "PAID_TEST_SUM_OUT_OF_RANGE",
            "message": "For the temporary paid test, paymentSum must be greater than 0 and no more than 5000 KZT.",
        }), 400

    if not terminal_group_id or not table_id or not incoming_items:
        return jsonify({
            "success": False,
            "code": "INVALID_PAID_TEST_ORDER",
            "message": "terminalGroupId, tableId and items are required.",
        }), 400

    try:
        if not all([
            os.environ.get("IIKO_KIOSK_API_KEY"),
            os.environ.get("IIKO_KIOSK_APP_ID") or os.environ.get("IIKO_APP_ID"),
            os.environ.get("IIKO_KIOSK_CLIENT_SECRET") or os.environ.get("IIKO_CLIENT_SECRET"),
        ]):
            return jsonify({
                "success": False,
                "code": "KIOSK_API_NOT_CONFIGURED",
                "message": "Paid test order was NOT sent. Doner Club Kiosk iikoCloud credentials are not configured.",
            }), 503

        department, available_departments = find_department(point)
        if not department:
            return jsonify({
                "success": False,
                "code": "POINT_NOT_FOUND",
                "message": f"Point '{point}' not found",
                "availablePoints": [
                    {"code": d.get("code"), "name": d.get("name")}
                    for d in available_departments
                ],
            }), 404

        organization_id = department["organizationId"]
        terminal_groups, _ = get_terminal_groups_for_organization(organization_id)
        allowed_group_ids = {str(group["id"]) for group in terminal_groups}
        if terminal_group_id not in allowed_group_ids:
            return jsonify({
                "success": False,
                "code": "INVALID_TERMINAL_GROUP",
                "message": "Selected terminal group does not belong to Arai.",
            }), 400

        sections, _ = get_restaurant_sections_for_terminal_groups([terminal_group_id])
        allowed_table_ids = {
            str(table.get("id"))
            for section in sections
            for table in (section.get("tables") or [])
            if table.get("id")
        }
        if table_id not in allowed_table_ids:
            return jsonify({
                "success": False,
                "code": "INVALID_TABLE",
                "message": "Selected table is not available for this terminal group.",
            }), 400

        order_items = []
        for source_item in incoming_items:
            product_id = str(source_item.get("productId") or "").strip()
            if not product_id:
                continue
            try:
                amount = float(source_item.get("amount") or 0)
            except (TypeError, ValueError):
                amount = 0
            if amount <= 0:
                continue

            order_item = {
                "productId": product_id,
                "type": "Product",
                "amount": amount,
            }
            product_size_id = source_item.get("productSizeId")
            if product_size_id:
                order_item["productSizeId"] = str(product_size_id)

            modifiers = []
            for modifier in source_item.get("modifiers") or []:
                modifier_product_id = str(modifier.get("productId") or "").strip()
                if not modifier_product_id:
                    continue
                modifier_payload = {
                    "productId": modifier_product_id,
                    "amount": float(modifier.get("amount") or 1),
                }
                product_group_id = modifier.get("productGroupId")
                if product_group_id:
                    modifier_payload["productGroupId"] = str(product_group_id)
                modifiers.append(modifier_payload)
            if modifiers:
                order_item["modifiers"] = modifiers

            order_items.append(order_item)

        if not order_items:
            return jsonify({
                "success": False,
                "code": "NO_VALID_ITEMS",
                "message": "No valid order items were supplied.",
            }), 400

        payment_type_id = os.environ.get(
            "IIKO_KIOSK_PAYMENT_TYPE_ID",
            "d89a8bf4-b3d1-4625-8de3-6b0ef162e0c3",
        )

        payload = {
            "organizationId": organization_id,
            "terminalGroupId": terminal_group_id,
            "createOrderSettings": {
                "servicePrint": True,
                "transportToFrontTimeout": 10,
                "checkStopList": True,
            },
            "order": {
                "tableIds": [table_id],
                "items": order_items,
                "guests": {
                    "count": 1,
                    "splitBetweenPersons": False,
                },
                "payments": [
                    {
                        "paymentTypeKind": "Card",
                        "sum": payment_sum,
                        "paymentTypeId": payment_type_id,
                        "isProcessedExternally": True,
                        "isFiscalizedExternally": False,
                        "isPrepay": False,
                    }
                ],
                "comment": "PAID TEST KIOSK — ВНЕШНЯЯ ТЕСТОВАЯ ОПЛАТА",
            },
        }

        response = iiko_kiosk_post("/api/1/order/create", payload, timeout=45)
        if not response.ok:
            return jsonify({
                "success": False,
                "code": "IIKO_PAID_ORDER_CREATE_FAILED",
                "statusCode": response.status_code,
                "details": response.text[:3000],
            }), 502

        result = response.json()
        command_status = None
        correlation_id = result.get("correlationId")
        order_info = result.get("orderInfo") or {}

        if correlation_id:
            for _ in range(10):
                if order_info.get("creationStatus") != "InProgress" and command_status:
                    break
                time.sleep(1)
                status_response = iiko_kiosk_post(
                    "/api/1/commands/status",
                    {
                        "organizationId": organization_id,
                        "correlationId": correlation_id,
                    },
                    timeout=20,
                )
                if status_response.ok:
                    command_status = status_response.json()
                    if command_status.get("state") in ("Success", "Error"):
                        break
                else:
                    break

        # IMPORTANT: adding a processed external payment to a table order is not
        # the same operation as paying/closing the order in iikoFront. The order
        # stays open until /api/1/order/close is called. Closing is the step that
        # asks iikoFront to actually finalize/fiscalize the already-paid order.
        order_id = str(order_info.get("id") or "").strip()
        if not order_id:
            return jsonify({
                "success": False,
                "code": "PAID_TEST_ORDER_ID_MISSING",
                "message": "Order was created but iiko did not return an order ID, so it was NOT closed.",
                "iiko": result,
                "commandStatus": command_status,
            }), 502

        if command_status and command_status.get("state") == "Error":
            return jsonify({
                "success": False,
                "code": "PAID_TEST_CREATE_COMMAND_ERROR",
                "message": "iikoFront reported an error while creating the paid test order. Close was NOT requested.",
                "iiko": result,
                "commandStatus": command_status,
            }), 502

        close_response = iiko_kiosk_post(
            "/api/1/order/close",
            {
                "organizationId": organization_id,
                "orderId": order_id,
            },
            timeout=45,
        )
        if not close_response.ok:
            return jsonify({
                "success": False,
                "code": "IIKO_PAID_ORDER_CLOSE_FAILED",
                "statusCode": close_response.status_code,
                "details": close_response.text[:3000],
                "orderId": order_id,
                "iiko": result,
            }), 502

        close_result = close_response.json()
        close_status = None
        close_correlation_id = close_result.get("correlationId")
        if close_correlation_id:
            for _ in range(12):
                time.sleep(1)
                close_status_response = iiko_kiosk_post(
                    "/api/1/commands/status",
                    {
                        "organizationId": organization_id,
                        "correlationId": close_correlation_id,
                    },
                    timeout=20,
                )
                if close_status_response.ok:
                    close_status = close_status_response.json()
                    if close_status.get("state") in ("Success", "Error"):
                        break
                else:
                    break

        return jsonify({
            "success": bool(not close_status or close_status.get("state") != "Error"),
            "message": "Paid test order was created and close was requested in iiko.",
            "organizationId": organization_id,
            "terminalGroupId": terminal_group_id,
            "tableId": table_id,
            "payment": {
                "paymentTypeId": payment_type_id,
                "paymentTypeKind": "Card",
                "sum": payment_sum,
                "isProcessedExternally": True,
                "isFiscalizedExternally": False,
            },
            "servicePrintRequested": True,
            "commandStatus": command_status,
            "close": {
                "requested": True,
                "correlationId": close_correlation_id,
                "commandStatus": close_status,
                "response": close_result,
            },
            "iiko": result,
        })
    except requests.Timeout:
        return jsonify({
            "success": False,
            "code": "IIKO_TIMEOUT",
            "message": "iiko did not answer in time.",
        }), 504
    except requests.HTTPError as error:
        response = error.response
        return jsonify({
            "success": False,
            "code": "IIKO_HTTP_ERROR",
            "statusCode": response.status_code if response is not None else None,
            "details": response.text[:3000] if response is not None else str(error),
        }), 502
    except Exception as error:
        return jsonify({
            "success": False,
            "code": "KIOSK_PAID_TEST_ORDER_ERROR",
            "message": str(error),
        }), 500


@app.route("/kiosk-menu")
def kiosk_menu():
    point = request.args.get("point", "Arai").strip()
    requested_menu = request.args.get("menu", "Kiosk Арай").strip()
    try:
        department, available_departments = find_department(point)
        if not department:
            return jsonify({
                "success": False,
                "code": "POINT_NOT_FOUND",
                "message": f"Point '{point}' not found",
                "availablePoints": [
                    {"code": d.get("code"), "name": d.get("name")}
                    for d in available_departments
                ],
            }), 404

        organization_id = department["organizationId"]
        menus_payload = get_external_menus(organization_id)
        external_menus = menus_payload.get("externalMenus", []) or []

        selected = next(
            (
                menu for menu in external_menus
                if (menu.get("name") or "").strip().casefold() == requested_menu.casefold()
            ),
            None,
        )
        if not selected:
            response = jsonify({
                "success": False,
                "code": "EXTERNAL_MENU_NOT_FOUND",
                "message": f"External menu '{requested_menu}' is not available for point '{point}' via iikoCloud yet.",
                "point": {
                    "code": department.get("code"),
                    "name": department.get("name"),
                    "organizationId": organization_id,
                },
                "requestedMenu": requested_menu,
                "availableMenus": [
                    {"id": m.get("id"), "name": m.get("name")}
                    for m in external_menus
                ],
                "hint": "Assign this external menu to the Arai restaurant in iikoWeb and make it active for API access.",
            })
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Cache-Control"] = "no-store"
            return response, 404

        menu_data = get_external_menu_by_id(selected.get("id"), organization_id)
        categories, products = normalize_external_menu(menu_data, organization_id)

        response = jsonify({
            "success": True,
            "source": "iikoCloud external menu",
            "point": {
                "code": department.get("code"),
                "name": department.get("name"),
                "organizationId": organization_id,
            },
            "menu": {
                "id": selected.get("id"),
                "name": selected.get("name"),
                "description": menu_data.get("description"),
                "revision": menu_data.get("revision"),
            },
            "categories": categories,
            "products": products,
            "priceCategories": menus_payload.get("priceCategories", []) or [],
        })
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Cache-Control"] = "no-store"
        return response
    except requests.Timeout:
        return jsonify({
            "success": False,
            "code": "IIKO_TIMEOUT",
            "message": "iiko did not answer in time.",
        }), 504
    except requests.HTTPError as error:
        response = error.response
        return jsonify({
            "success": False,
            "code": "IIKO_HTTP_ERROR",
            "statusCode": response.status_code if response is not None else None,
            "details": response.text[:1500] if response is not None else str(error),
        }), 502
    except Exception as error:
        return jsonify({
            "success": False,
            "code": "KIOSK_MENU_ERROR",
            "message": str(error),
        }), 500


@app.route("/analytics")
def analytics():
    try:
        point = request.args.get("point", "Arai").strip()
        single_date = request.args.get("date")
        date_from = request.args.get("from")
        date_to = request.args.get("to")
        if single_date:
            date_from = single_date
            date_to = single_date
        if not date_from:
            date_from = datetime.now(LOCAL_TZ).date().isoformat()
        if not date_to:
            date_to = date_from
        payload, error_payload, status = build_analytics(point, date_from, date_to)
        if error_payload:
            return jsonify(error_payload), status
        return jsonify(payload), status
    except requests.Timeout:
        return jsonify({
            "success": False,
            "code": "IIKO_TIMEOUT",
            "message": "iiko did not answer in time. Please retry the request.",
        }), 504
    except requests.HTTPError as error:
        response = error.response
        return jsonify({
            "success": False,
            "code": "IIKO_HTTP_ERROR",
            "statusCode": response.status_code if response is not None else None,
            "details": response.text[:1500] if response is not None else str(error),
        }), 502
    except ValueError as error:
        return jsonify({
            "success": False,
            "code": "INVALID_PERIOD",
            "message": str(error),
        }), 400
    except Exception as error:
        return jsonify({
            "success": False,
            "code": "ANALYTICS_ERROR",
            "message": str(error),
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
