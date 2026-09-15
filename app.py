import os
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

IIKO_BASE_URL = "https://api-ru.iiko.services"


def get_iiko_token():
    app_id = os.environ.get("IIKO_APP_ID")
    client_secret = os.environ.get("IIKO_CLIENT_SECRET")
    api_key = os.environ.get("IIKO_API_KEY")

    if not all([app_id, client_secret, api_key]):
        raise RuntimeError("iiko credentials are not configured")

    response = requests.post(
        f"{IIKO_BASE_URL}/api/v2/access_token",
        json={
            "appId": app_id,
            "clientSecret": client_secret,
            "apiKey": api_key,
        },
        timeout=20,
    )

    response.raise_for_status()
    return response.json()["token"]


def iiko_headers():
    return {
        "Authorization": f"Bearer {get_iiko_token()}",
        "Content-Type": "application/json",
    }


def get_departments():
    response = requests.post(
        f"{IIKO_BASE_URL}/api/inventory/v1/organizations/tree",
        headers=iiko_headers(),
        json={},
        timeout=30,
    )

    response.raise_for_status()
    tree = response.json()

    departments = []

    def walk(value):
        if isinstance(value, dict):
            if (
                value.get("type") == "DEPARTMENT"
                and value.get("organizationId")
            ):
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
    response = requests.post(
        f"{IIKO_BASE_URL}/api/inventory/v1/sales_document/list",
        headers=iiko_headers(),
        json={
            "organizationId": organization_id,
            "from": date_from,
            "to": date_to,
        },
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def get_sales_document(organization_id, document_id):
    response = requests.post(
        f"{IIKO_BASE_URL}/api/inventory/v1/sales_document/get",
        headers=iiko_headers(),
        json={
            "organizationId": organization_id,
            "documentId": document_id,
        },
        timeout=30,
    )

    response.raise_for_status()
    return response.json()


def get_products_map():
    products = {}
    offset = 0
    limit = 1000

    while True:
        response = requests.post(
            f"{IIKO_BASE_URL}/api/nomenclature/v1/product/list",
            headers=iiko_headers(),
            json={
                "limit": limit,
                "offset": offset,
            },
            timeout=30,
        )

        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])

        for product in items:
            product_id = product.get("productId")
            if product_id:
                products[product_id] = {
                    "name": product.get("name") or product_id,
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

    return products


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

    result = []
    current = start
    while current <= end:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


@app.route("/")
def home():
    return jsonify({
        "service": "Doner Club Analytics",
        "status": "online",
        "dashboard": "/static/dashboard.html",
        "examples": {
            "arai_day": "/analytics?point=Arai&date=2026-09-15",
            "arai_period": "/analytics?point=Arai&from=2026-09-01&to=2026-09-15",
            "departments": "/departments",
        },
    })


@app.route("/departments")
def departments():
    try:
        return jsonify({
            "success": True,
            "departments": get_departments(),
        })

    except requests.HTTPError as error:
        return jsonify({
            "success": False,
            "statusCode": error.response.status_code,
            "details": error.response.text,
        }), 500

    except Exception as error:
        return jsonify({
            "success": False,
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
            date_from = datetime.now(
                ZoneInfo("Asia/Almaty")
            ).date().isoformat()

        if not date_to:
            date_to = date_from

        all_dates = date_range(date_from, date_to)
        department, available_departments = find_department(point)

        if not department:
            return jsonify({
                "success": False,
                "message": f"Point '{point}' not found",
                "availablePoints": [
                    {
                        "code": d.get("code"),
                        "name": d.get("name"),
                    }
                    for d in available_departments
                ],
            }), 404

        organization_id = department["organizationId"]
        documents = get_sales_documents(
            organization_id,
            date_from,
            date_to,
        )

        processed_documents = [
            document
            for document in documents
            if (
                not document.get("status")
                or document.get("status") == "PROCESSED"
            )
        ]

        totals = defaultdict(
            lambda: {
                "quantity": 0.0,
                "revenue": 0.0,
                "article": None,
            }
        )

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

        document_errors = []

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

            if not document_id:
                continue

            try:
                detail = get_sales_document(
                    organization_id,
                    document_id,
                )

            except requests.HTTPError as error:
                document_errors.append({
                    "documentId": document_id,
                    "statusCode": error.response.status_code,
                    "details": error.response.text,
                })
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

        try:
            product_map = get_products_map()
            nomenclature_warning = None
        except Exception as error:
            product_map = {}
            nomenclature_warning = str(error)

        products = []

        for product_id, values in totals.items():
            product_info = product_map.get(product_id, {})

            products.append({
                "productId": product_id,
                "name": product_info.get("name") or product_id,
                "article": (
                    product_info.get("article")
                    or values.get("article")
                ),
                "quantity": round(values["quantity"], 3),
                "revenue": round(values["revenue"], 2),
            })

        by_revenue = sorted(
            products,
            key=lambda item: item["revenue"],
            reverse=True,
        )

        by_quantity = sorted(
            products,
            key=lambda item: item["quantity"],
            reverse=True,
        )

        revenue_from_documents = round(
            sum(
                float(document.get("sum") or 0)
                for document in processed_documents
            ),
            2,
        )

        revenue_from_items = round(
            sum(product["revenue"] for product in products),
            2,
        )

        total_quantity = round(
            sum(product["quantity"] for product in products),
            3,
        )

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

        return jsonify({
            "success": True,
            "point": {
                "code": department.get("code"),
                "name": department.get("name"),
                "organizationId": organization_id,
            },
            "period": {
                "from": date_from,
                "to": date_to,
                "daysCount": days_count,
            },
            "summary": {
                "documentsCount": len(processed_documents),
                "revenue": revenue_from_documents,
                "itemsRevenue": revenue_from_items,
                "itemsQuantity": total_quantity,
                "uniqueProducts": len(products),
                "averageDailyRevenue": round(
                    revenue_from_documents / days_count,
                    2,
                ) if days_count else 0,
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
                    "Average check and hourly sales require receipt/order-level data."
                ),
            },
        })

    except requests.HTTPError as error:
        return jsonify({
            "success": False,
            "statusCode": error.response.status_code,
            "details": error.response.text,
        }), 500

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error),
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
