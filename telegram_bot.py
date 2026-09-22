import hashlib
import hmac
import os
import threading
from datetime import datetime, timedelta

import requests
from flask import jsonify, request

import app as core
import telegram_daily_report as report


_processed_lock = threading.Lock()
_processed_updates = set()


def _settings():
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    base_url = (os.environ.get("TELEGRAM_WEBHOOK_BASE_URL") or "https://analytics.donerclub.kz").strip().rstrip("/")
    if not token or not chat_id:
        return None
    secret = hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
    return token, chat_id, base_url, secret


def _telegram(token, method, payload):
    response = requests.post(
        f"https://api.telegram.org/bot{token}/{method}",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data


def _setup_webhook():
    settings = _settings()
    if not settings:
        print("[telegram-bot] disabled: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID missing", flush=True)
        return
    token, _chat_id, base_url, secret = settings
    webhook_url = f"{base_url}/telegram/webhook/{secret}"
    try:
        _telegram(token, "setWebhook", {
            "url": webhook_url,
            "secret_token": secret,
            "allowed_updates": ["message"],
            "drop_pending_updates": False,
        })
        _telegram(token, "setMyCommands", {
            "commands": [
                {"command": "go", "description": "Отчет за последний полный день"},
            ],
        })
        print("[telegram-bot] webhook and /go command configured", flush=True)
    except Exception as exc:
        print(f"[telegram-bot] setup failed: {exc}", flush=True)


def _remember_update(update_id):
    if update_id is None:
        return True
    with _processed_lock:
        if update_id in _processed_updates:
            return False
        _processed_updates.add(update_id)
        if len(_processed_updates) > 500:
            for old in sorted(_processed_updates)[:250]:
                _processed_updates.discard(old)
        return True


def _command(text):
    parts = str(text or "").strip().split(maxsplit=1)
    if not parts:
        return ""
    first = parts[0].lower()
    first = first.split("@", 1)[0]
    return first


def _build_and_send(token, chat_id):
    day = (datetime.now(core.LOCAL_TZ).date() - timedelta(days=1)).isoformat()
    shown = datetime.strptime(day, "%Y-%m-%d").strftime("%d.%m.%Y")
    try:
        report.send(token, chat_id, f"⏳ Собираю отчёт за <b>{shown}</b>…")
        rows = [report.collect(point, day) for point in report.points()]
        messages = [report.network_message(rows, day)] + [report.point_message(row) for row in rows]
        for message in messages:
            report.send(token, chat_id, message)
        print(f"[telegram-bot] /go report sent for {day}", flush=True)
    except Exception as exc:
        print(f"[telegram-bot] /go failed: {exc}", flush=True)
        try:
            report.send(token, chat_id, "⚠️ Не удалось собрать отчёт. Попробуйте /go ещё раз через минуту.")
        except Exception:
            pass




def install_telegram_bot(app):
    if getattr(app, "_doner_telegram_bot_installed", False):
        return
    app._doner_telegram_bot_installed = True

    settings = _settings()
    if not settings:
        print("[telegram-bot] route not installed: Telegram environment is incomplete", flush=True)
        return

    token, allowed_chat_id, _base_url, secret = settings
    route_path = f"/telegram/webhook/{secret}"

    @app.route(route_path, methods=["POST"], endpoint="telegram_bot_webhook")
    def telegram_bot_webhook():
        header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(header_secret, secret):
            return jsonify({"ok": False}), 403

        update = request.get_json(silent=True) or {}
        if not isinstance(update, dict):
            return jsonify({"ok": False}), 400
        update_id = update.get("update_id")
        if update_id is not None and (not isinstance(update_id, int) or isinstance(update_id, bool)):
            return jsonify({"ok": False}), 400
        if not _remember_update(update_id):
            return jsonify({"ok": True, "duplicate": True})

        message = update.get("message") or {}
        if not isinstance(message, dict):
            return jsonify({"ok": False}), 400
        chat = message.get("chat") or {}
        if not isinstance(chat, dict):
            return jsonify({"ok": False}), 400
        incoming_chat_id = str(chat.get("id") or "")
        if incoming_chat_id != str(allowed_chat_id):
            return jsonify({"ok": True, "ignored": "chat"})

        command = _command(message.get("text"))
        if command == "/go":
            thread = threading.Thread(
                target=_build_and_send,
                args=(token, allowed_chat_id),
                name="telegram-go-report",
                daemon=True,
            )
            thread.start()
            return jsonify({"ok": True})

        return jsonify({"ok": True, "ignored": "command"})

    threading.Thread(
        target=_setup_webhook,
        name="telegram-webhook-setup",
        daemon=True,
    ).start()
