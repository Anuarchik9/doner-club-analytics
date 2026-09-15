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
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
