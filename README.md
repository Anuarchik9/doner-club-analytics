# Doner Club Analytics

## Local run (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app wsgi run --host 127.0.0.1 --port 10001
```

Open http://127.0.0.1:10001. Use `wsgi`, not bare `app`, so authentication,
report endpoints and UI extensions are installed just as on Render.
`python app.py` also installs the full runtime. Gunicorn remains `gunicorn app:app`
with its existing worker hook. Installation is idempotent and preserves hook order.
The tzdata dependency supplies Asia/Almaty on systems without a timezone database.

Set the existing iiko credentials and DASHBOARD_SECRET_KEY in the environment.
Without iiko credentials the login page and health check work, but real login and
reports require iiko. No demo login or authentication bypass is provided.
Production secure-cookie settings are unchanged; use local HTTPS when testing login
in a browser that rejects Secure cookies on localhost HTTP.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover runtime startup, authentication responses, all main pages and their local
assets, invalid reporting periods, redirect validation and Telegram non-text payloads.
External requests and Telegram sending are blocked/mocked during these tests.
The UI sizing rules remain in UI_STANDARD.md.
