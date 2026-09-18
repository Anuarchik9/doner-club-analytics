import hashlib
import html
import os
import secrets
import threading
import time
from datetime import timedelta
from urllib.parse import quote

import requests
from flask import jsonify, redirect, request, session


_attempt_lock = threading.Lock()
_attempts = {}
_MAX_ATTEMPTS = 7
_ATTEMPT_WINDOW = 15 * 60
_SESSION_HOURS = 10


def _client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.remote_addr or "unknown"


def _rate_limited(ip):
    now = time.time()
    with _attempt_lock:
        recent = [ts for ts in _attempts.get(ip, []) if now - ts < _ATTEMPT_WINDOW]
        _attempts[ip] = recent
        return len(recent) >= _MAX_ATTEMPTS


def _record_failure(ip):
    now = time.time()
    with _attempt_lock:
        recent = [ts for ts in _attempts.get(ip, []) if now - ts < _ATTEMPT_WINDOW]
        recent.append(now)
        _attempts[ip] = recent


def _clear_failures(ip):
    with _attempt_lock:
        _attempts.pop(ip, None)


def _allowed_user(login):
    raw = (os.environ.get("IIKO_ALLOWED_USERS") or "").strip()
    if raw:
        allowed = {item.strip().lower() for item in raw.split(",") if item.strip()}
        return "*" in allowed or login.strip().lower() in allowed

    # Secure default: only the service-account login already configured in Render.
    service_login = (os.environ.get("IIKO_SERVER_LOGIN") or "").strip().lower()
    return bool(service_login) and login.strip().lower() == service_login


def _authenticate_iiko(login, password):
    if not login or not password or not _allowed_user(login):
        return False

    base_url = (
        os.environ.get("IIKO_SERVER_URL")
        or "https://dc-firdaws-co-arm.iiko.it/resto"
    ).rstrip("/")
    password_hash = hashlib.sha1(password.encode("utf-8")).hexdigest()
    token = None
    try:
        response = requests.get(
            f"{base_url}/api/auth",
            params={"login": login, "pass": password_hash},
            timeout=15,
        )
        if not response.ok:
            return False
        token = response.text.strip().strip('"')
        if not token or "<html" in token.lower():
            return False
        return True
    except requests.RequestException:
        return False
    finally:
        if token:
            try:
                requests.get(
                    f"{base_url}/api/logout",
                    params={"key": token},
                    timeout=6,
                )
            except requests.RequestException:
                pass


def _safe_next(value):
    value = (value or "").strip()
    if not value.startswith("/") or value.startswith("//"):
        return "/static/dashboard-v2.html"
    if value.startswith("/login") or value.startswith("/logout"):
        return "/static/dashboard-v2.html"
    return value


def _login_page(error="", next_url="/static/dashboard-v2.html"):
    error_html = (
        f'<div class="error">{html.escape(error)}</div>' if error else ""
    )
    safe_next = html.escape(_safe_next(next_url), quote=True)
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Вход — Doner Club Analytics</title>
<style>
:root{{--bg:#080808;--panel:#121212;--line:#2a2a2a;--text:#f7f7f2;--muted:#8e8e88;--orange:#ff5a1f;--red:#ff8b8b}}
*{{box-sizing:border-box}}
body{{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 80% 5%,rgba(255,90,31,.14),transparent 30%),var(--bg);color:var(--text);font:14px Inter,system-ui,-apple-system,Segoe UI,sans-serif}}
.shell{{width:min(430px,100%)}}
.brand{{display:flex;align-items:center;gap:13px;margin-bottom:22px}}
.logo{{width:48px;height:48px;border-radius:13px;background:var(--orange);display:grid;place-items:center;text-align:center;font-size:11px;font-weight:950;line-height:.85}}
.brand b{{letter-spacing:.04em}}.brand small{{color:var(--muted)}}
.card{{padding:28px;border:1px solid var(--line);border-radius:22px;background:linear-gradient(160deg,#151515,#101010);box-shadow:0 24px 70px rgba(0,0,0,.4)}}
h1{{font-size:30px;letter-spacing:-.04em;margin:0 0 7px}}p{{color:var(--muted);line-height:1.55;margin:0 0 22px}}
label{{display:block;margin:14px 0 7px;color:#aaa;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.07em}}
input{{width:100%;height:48px;border:1px solid #333;border-radius:12px;background:#090909;color:#fff;padding:0 13px;outline:none}}input:focus{{border-color:var(--orange)}}
button{{width:100%;height:49px;margin-top:20px;border:0;border-radius:12px;background:var(--orange);color:#fff;font-weight:900;cursor:pointer}}
.error{{border:1px solid #6b3030;background:#241111;color:#ffb2b2;border-radius:12px;padding:12px 13px;margin:0 0 16px}}
.note{{margin-top:16px;color:#777;font-size:11px;line-height:1.5}}
</style>
</head>
<body>
<div class="shell">
<div class="brand"><div class="logo">DONER<br>CLUB</div><div><b>DONER CLUB ANALYTICS</b><br><small>Защищённый доступ</small></div></div>
<div class="card">
<h1>Вход</h1>
<p>Используйте учётную запись iiko. Пароль проверяется напрямую на iikoServer и не сохраняется в Doner Club Analytics.</p>
{error_html}
<form method="post" action="/login" autocomplete="on">
<input type="hidden" name="next" value="{safe_next}">
<label for="login">Логин iiko</label>
<input id="login" name="login" autocomplete="username" required autofocus>
<label for="password">Пароль iiko</label>
<input id="password" name="password" type="password" autocomplete="current-password" required>
<button type="submit">Войти</button>
</form>
<div class="note">Доступ разрешён только авторизованным пользователям. Сессия автоматически завершится примерно через {_SESSION_HOURS} часов.</div>
</div>
</div>
</body>
</html>"""


def install_auth(app):
    if getattr(app, "_doner_auth_installed", False):
        return
    app._doner_auth_installed = True

    secret = os.environ.get("DASHBOARD_SECRET_KEY")
    if not secret:
        seed = os.environ.get("IIKO_CLIENT_SECRET") or secrets.token_hex(32)
        secret = hashlib.sha256(("doner-club-dashboard:" + seed).encode("utf-8")).hexdigest()
    app.secret_key = secret
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=_SESSION_HOURS),
    )

    @app.route("/login", methods=["GET", "POST"], endpoint="dashboard_login")
    def dashboard_login():
        next_url = _safe_next(request.values.get("next"))
        if session.get("dc_authenticated"):
            return redirect(next_url)

        error = ""
        if request.method == "POST":
            ip = _client_ip()
            if _rate_limited(ip):
                error = "Слишком много попыток входа. Подождите 15 минут и попробуйте снова."
            else:
                login = (request.form.get("login") or "").strip()
                password = request.form.get("password") or ""
                if _authenticate_iiko(login, password):
                    _clear_failures(ip)
                    session.clear()
                    session.permanent = True
                    session["dc_authenticated"] = True
                    session["dc_user"] = login
                    session["dc_login_at"] = int(time.time())
                    return redirect(next_url)
                _record_failure(ip)
                error = "Неверный логин/пароль или для этой учётной записи нет доступа к аналитике."

        return _login_page(error, next_url), 200, {"Cache-Control": "no-store"}

    @app.route("/logout", methods=["GET", "POST"], endpoint="dashboard_logout")
    def dashboard_logout():
        session.clear()
        return redirect("/login")

    @app.route("/healthz", methods=["GET"], endpoint="dashboard_health")
    def dashboard_health():
        return jsonify({"status": "ok"})

    api_prefixes = (
        "/analytics",
        "/receipt-analytics",
        "/departments",
        "/orders-access-test",
        "/olap-",
    )

    @app.before_request
    def _protect_dashboard():
        path = request.path
        if path in {"/login", "/logout", "/healthz", "/static/favicon.svg"} or path.startswith("/telegram/webhook/"):
            return None

        if session.get("dc_authenticated"):
            if path == "/":
                return redirect("/static/dashboard-v2.html")
            return None

        if path.startswith(api_prefixes):
            return jsonify({
                "success": False,
                "code": "AUTH_REQUIRED",
                "message": "Authentication required",
                "login": "/login",
            }), 401

        next_url = path
        if request.query_string:
            next_url += "?" + request.query_string.decode("utf-8", "ignore")
        return redirect("/login?next=" + quote(_safe_next(next_url), safe="/?=&%"))

    @app.after_request
    def _security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.path != "/healthz":
            response.headers["Cache-Control"] = "no-store, private"

        if (
            session.get("dc_authenticated")
            and request.path.endswith("dashboard-v2.html")
            and response.status_code == 200
            and response.mimetype == "text/html"
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                user = html.escape(str(session.get("dc_user") or "iiko"))
                badge = f'''<div id="dc-auth-badge" style="position:fixed;right:18px;bottom:18px;z-index:9999;display:flex;align-items:center;gap:9px;padding:8px 11px;border:1px solid #2a2a2a;border-radius:999px;background:rgba(12,12,12,.94);box-shadow:0 8px 30px rgba(0,0,0,.35);font:11px Inter,system-ui,sans-serif;color:#aaa"><span>{user}</span><a href="/logout" style="color:#ff6a32;text-decoration:none;font-weight:800">Выйти</a></div>'''
                if "</body>" in body:
                    response.set_data(body.replace("</body>", badge + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
