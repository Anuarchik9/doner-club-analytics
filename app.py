import os
import requests
from flask import Flask, jsonify

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
        timeout=15,
    )

    response.raise_for_status()
    return response.json()["token"]


def iiko_headers():
    return {
        "Authorization": f"Bearer {get_iiko_token()}",
        "Content-Type": "application/json",
    }


@app.route("/")
def home():
    return jsonify({
        "service": "Doner Club Analytics",
        "status": "online"
    })


@app.route("/test-iiko")
def test_iiko():
    try:
        token = get_iiko_token()

        return jsonify({
            "success": True,
            "message": "Connection to iikoCloud successful",
            "token_received": bool(token)
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 500


@app.route("/organizations")
def organizations():
    try:
        response = requests.post(
            f"{IIKO_BASE_URL}/api/1/organizations",
            headers=iiko_headers(),
            json={
                "returnAdditionalInfo": True,
                "includeDisabled": True
            },
            timeout=20,
        )

        response.raise_for_status()
        data = response.json()

        return jsonify({
            "success": True,
            "count": len(data.get("organizations", [])),
            "organizations": data.get("organizations", [])
        })

    except requests.HTTPError as error:
        return jsonify({
            "success": False,
            "status_code": error.response.status_code,
            "details": error.response.text
        }), 500

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 500

@app.route("/orders-test")
def orders_test():
    try:
        # Сначала получаем организации
        org_response = requests.post(
            f"{IIKO_BASE_URL}/api/1/organizations",
            headers=iiko_headers(),
            json={
                "returnAdditionalInfo": True,
                "includeDisabled": False
            },
            timeout=20,
        )

        org_response.raise_for_status()
        org_data = org_response.json()

        organizations = org_data.get("organizations", [])

        return jsonify({
            "success": True,
            "message": "Ready to request iiko orders",
            "count": len(organizations),
            "organizations": [
                {
                    "id": org.get("id"),
                    "name": org.get("name"),
                    "code": org.get("code")
                }
                for org in organizations
            ]
        })

    except requests.HTTPError as error:
        return jsonify({
            "success": False,
            "status_code": error.response.status_code,
            "details": error.response.text
        }), 500

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 500
@app.route("/orders")
def orders():
    try:
        # Получаем активные организации
        org_response = requests.post(
            f"{IIKO_BASE_URL}/api/1/organizations",
            headers=iiko_headers(),
            json={
                "returnAdditionalInfo": True,
                "includeDisabled": False
            },
            timeout=20,
        )

        org_response.raise_for_status()
        organizations = org_response.json().get("organizations", [])

        organization_ids = [
            org["id"] for org in organizations
            if org.get("id")
        ]

        # Запрашиваем заказы за 15 сентября 2026
        response = requests.post(
            f"{IIKO_BASE_URL}/api/1/deliveries/by_delivery_date_and_status",
            headers=iiko_headers(),
            json={
                "organizationIds": organization_ids,
                "deliveryDateFrom": "2026-09-15 00:00:00.000",
                "deliveryDateTo": "2026-09-15 23:59:59.999"
            },
            timeout=30,
        )

        response.raise_for_status()
        data = response.json()

        return jsonify({
            "success": True,
            "period": "2026-09-15",
            "organizationCount": len(organization_ids),
            "data": data
        })

    except requests.HTTPError as error:
        return jsonify({
            "success": False,
            "status_code": error.response.status_code,
            "details": error.response.text
        }), 500

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 500
@app.route("/sales-test")
def sales_test():
    try:
        # Сначала получаем организации Doner Club
        org_response = requests.post(
            f"{IIKO_BASE_URL}/api/1/organizations",
            headers=iiko_headers(),
            json={
                "returnAdditionalInfo": True,
                "includeDisabled": False
            },
            timeout=20,
        )

        org_response.raise_for_status()
        organizations = org_response.json().get("organizations", [])

        results = []

        # Проверяем продажи отдельно по каждой организации
        for org in organizations:
            department_id = org.get("id")

            response = requests.post(
                f"{IIKO_BASE_URL}/api/inventory/v1/sales_document/list",
                headers=iiko_headers(),
                json={
                    "organizationId": department_id,
                    "from": "2026-09-15",
                    "to": "2026-09-15"
                },
                timeout=30,
            )

            try:
                response_data = response.json()
            except Exception:
                response_data = response.text

            results.append({
                "organization": org.get("name"),
                "organizationId": department_id,
                "statusCode": response.status_code,
                "data": response_data
            })

        return jsonify({
            "success": True,
            "date": "2026-09-15",
            "organizationsChecked": len(organizations),
            "results": results
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 500
@app.route("/departments-test")
def departments_test():
    try:
        response = requests.post(
            f"{IIKO_BASE_URL}/api/inventory/v1/organizations/tree",
            headers=iiko_headers(),
            json={},
            timeout=30,
        )

        response.raise_for_status()
        tree = response.json()

        def collect_nodes(value, path="root"):
            nodes = []

            if isinstance(value, dict):
                if value.get("id"):
                    nodes.append({
                        "path": path,
                        "id": value.get("id"),
                        "name": value.get("name"),
                        "type": value.get("type"),
                        "keys": list(value.keys())
                    })

                for key, child in value.items():
                    if isinstance(child, (dict, list)):
                        nodes.extend(
                            collect_nodes(child, f"{path}.{key}")
                        )

            elif isinstance(value, list):
                for index, child in enumerate(value):
                    nodes.extend(
                        collect_nodes(child, f"{path}[{index}]")
                    )

            return nodes

        return jsonify({
            "success": True,
            "nodes": collect_nodes(tree),
            "tree": tree
        })

    except requests.HTTPError as error:
        return jsonify({
            "success": False,
            "statusCode": error.response.status_code,
            "details": error.response.text
        }), 500

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 500
@app.route("/sales-detail-test")
def sales_detail_test():
    try:
        # Находим организацию Arai
        org_response = requests.post(
            f"{IIKO_BASE_URL}/api/1/organizations",
            headers=iiko_headers(),
            json={
                "returnAdditionalInfo": True,
                "includeDisabled": False
            },
            timeout=20,
        )
        org_response.raise_for_status()

        organizations = org_response.json().get("organizations", [])

        arai = next(
            (
                org for org in organizations
                if (org.get("code") or "").lower() == "arai"
            ),
            None
        )

        if not arai:
            return jsonify({
                "success": False,
                "message": "Arai organization not found"
            }), 404

        organization_id = arai["id"]

        # Получаем документы продаж Арай
        list_response = requests.post(
            f"{IIKO_BASE_URL}/api/inventory/v1/sales_document/list",
            headers=iiko_headers(),
            json={
                "organizationId": organization_id,
                "from": "2026-09-15",
                "to": "2026-09-15"
            },
            timeout=30,
        )

        list_response.raise_for_status()
        documents = list_response.json()

        details = []

        # Получаем содержимое каждого документа
        for document in documents:
            document_id = document.get("documentId")

            if not document_id:
                continue

            detail_response = requests.post(
                f"{IIKO_BASE_URL}/api/inventory/v1/sales_document/get",
                headers=iiko_headers(),
                json={
                    "organizationId": organization_id,
                    "documentId": document_id
                },
                timeout=30,
            )

            if detail_response.ok:
                details.append(detail_response.json())
            else:
                details.append({
                    "documentId": document_id,
                    "error": detail_response.text,
                    "statusCode": detail_response.status_code
                })

        return jsonify({
            "success": True,
            "organization": "Arai",
            "date": "2026-09-15",
            "documentsCount": len(documents),
            "documents": documents,
            "details": details
        })

    except requests.HTTPError as error:
        return jsonify({
            "success": False,
            "statusCode": error.response.status_code,
            "details": error.response.text
        }), 500

    except Exception as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 500
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
