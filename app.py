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

    data = response.json()
    return data["token"]


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

    except requests.HTTPError as error:
        return jsonify({
            "success": False,
            "message": "iikoCloud authentication failed",
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
