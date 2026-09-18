import argparse
import html
import os
from datetime import datetime, timedelta

import requests

import app as core
import sales_channel

TELEGRAM_API = "https://api.telegram.org"
DEFAULT_POINTS = ("Arai", "Republic")
POINT_LABELS = {"arai": "Арай", "republic": "Республика", "республика": "Республика"}


def money(value):
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0
    return f"{value:,.0f}".replace(",", " ") + " ₸"


def num(value, digits=0):
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0
    if digits:
        return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")
    return f"{value:,.0f}".replace(",", " ")


def delta(current, previous):
    current = float(current or 0)
    previous = float(previous or 0)
    if not previous:
        return "—"
    value = (current - previous) / previous * 100
    return (f"+{value:.1f}%" if value > 0 else f"{value:.1f}%").replace(".", ",")


def label(point):
    text = str(point or "").strip()
    return POINT_LABELS.get(text.casefold(), text or "Точка")


def starts(name, word):
    return name == word or name.startswith(word + " ") or name.startswith(word + "-") or name.startswith(word + "(")


def category(name):
    n = str(name or "").strip().casefold()
    if "комбо" in n or "combo" in n or "go!" in n:
        return "Комбо"
    if "батон" in n or "baton" in n:
        return "Батоны"
    if "донер" in n or "doner" in n:
        return "Донеры"
    if (
        "pepsi" in n or "пепси" in n or "айран" in n or "вода" in n or "сок" in n
        or "чай" in n or "кофе" in n or "напит" in n or "mirinda" in n or "миринда" in n
        or starts(n, "кинза") or starts(n, "kinza") or starts(n, "ава") or starts(n, "ava")
        or starts(n, "пиала") or starts(n, "piala") or starts(n, "да-да") or starts(n, "да да")
        or starts(n, "da-da") or starts(n, "da da") or starts(n, "dada")
    ):
        return "Напитки"
    if "фри" in n or "наггет" in n or "картоф" in n or "закуск" in n or "стрипс" in n or "strip" in n:
        return "Гарниры и закуски"
    if "соус" in n or "халап" in n or "сыр" in n or "добав" in n:
        return "Соусы и добавки"
    return "Другие позиции"


def true_doner(name):
    n = str(name or "").casefold()
    return ("донер" in n or "doner" in n) and "батон" not in n and "baton" not in n and "комбо" not in n and "combo" not in n and "go!" not in n


def baton(name):
    n = str(name or "").casefold()
    return ("батон" in n or "baton" in n) and "комбо" not in n and "combo" not in n and "go!" not in n


def meat(name):
    n = str(name or "").casefold()
    if "ассорти" in n or "assorti" in n or "mixed" in n:
        return "Ассорти"
    if "кур" in n or "chicken" in n:
        return "Курица"
    if "гов" in n or "beef" in n:
        return "Говядина"
    return "Не определено"


def size(name):
    n = str(name or "").casefold()
    if "мини" in n or "mini" in n:
        return "Мини"
    if "1.5" in n or "1,5" in n or "полутор" in n:
        return "1.5"
    if "двойн" in n or "double" in n:
        return "Двойной"
    return "Стандарт"


def analytics(point, day):
    payload, error, status = core.build_analytics(point, day, day)
    if error:
        raise RuntimeError(error.get("message") or error.get("details") or f"analytics HTTP {status}")
    return payload


def safe(func, *args):
    try:
        return func(*args), None
    except Exception as exc:
        return None, str(exc)


def collect(point, day):
    d = datetime.strptime(day, "%Y-%m-%d").date()
    cur, e1 = safe(analytics, point, day)
    receipt, e2 = safe(core.build_receipt_analytics, point, day, day)
    mix, e3 = safe(sales_channel._build_mix, point, day, day)
    prev, _ = safe(analytics, point, (d - timedelta(days=1)).isoformat())
    week, _ = safe(analytics, point, (d - timedelta(days=7)).isoformat())
    return {"point": point, "cur": cur, "receipt": receipt, "mix": mix, "prev": prev, "week": week, "errors": [e for e in (e1, e2, e3) if e]}


def categories(products):
    groups = {}
    for p in products:
        key = category(p.get("name"))
        row = groups.setdefault(key, {"revenue": 0.0, "qty": 0.0})
        row["revenue"] += float(p.get("revenue") or 0)
        row["qty"] += float(p.get("quantity") or 0)
    return sorted(groups.items(), key=lambda x: x[1]["revenue"], reverse=True)


def meat_sizes(products):
    meats, sizes = {}, {}
    for p in products:
        name = p.get("name")
        revenue = float(p.get("revenue") or 0)
        qty = float(p.get("quantity") or 0)
        if true_doner(name) or baton(name):
            key = meat(name)
            row = meats.setdefault(key, {"revenue": 0.0, "qty": 0.0})
            row["revenue"] += revenue
            row["qty"] += qty
        if true_doner(name):
            key = size(name)
            row = sizes.setdefault(key, {"revenue": 0.0, "qty": 0.0})
            row["revenue"] += revenue
            row["qty"] += qty
    return meats, sizes


def point_message(row):
    cur, receipt, mix = row["cur"], row["receipt"], row["mix"]
    point = html.escape(label(row["point"]))
    if not cur and not receipt and not mix:
        return f"<b>{point}</b>\nДанных за день нет. Возможно, точка не работала или продаж в iiko не было."

    s = (cur or {}).get("summary") or {}
    rs = (receipt or {}).get("summary") or {}
    ps = (row["prev"] or {}).get("summary") or {}
    ws = (row["week"] or {}).get("summary") or {}
    products = (cur or {}).get("products") or []
    revenue = float(s.get("revenue") or rs.get("revenue") or 0)

    lines = [
        f"<b>{point}</b>",
        f"Выручка: <b>{money(revenue)}</b>",
        f"Продано единиц: <b>{num(s.get('itemsQuantity'), 1)}</b> · уникальных позиций: <b>{int(s.get('uniqueProducts') or 0)}</b>",
        f"Чеков: <b>{num(rs.get('checks'))}</b> · гостей: <b>{num(rs.get('guests'))}</b> · средний чек: <b>{money(rs.get('averageCheck'))}</b>",
        f"К предыдущему дню: <b>{delta(revenue, ps.get('revenue'))}</b>",
        f"К тому же дню недели: <b>{delta(revenue, ws.get('revenue'))}</b>",
    ]

    if mix:
        on, off = mix.get("online") or {}, mix.get("offline") or {}
        lines += [
            "",
            "<b>Онлайн / оффлайн</b>",
            f"Онлайн: <b>{money(on.get('revenue'))}</b> · {num(on.get('share'), 1)}%",
            f"Оффлайн: <b>{money(off.get('revenue'))}</b> · {num(off.get('share'), 1)}%",
        ]

    top = (cur or {}).get("topByRevenue") or []
    if top:
        lines += ["", "<b>Топ-3 по выручке</b>"]
        for i, p in enumerate(top[:3], 1):
            lines.append(f"{i}. {html.escape(str(p.get('name') or 'Позиция'))} — {money(p.get('revenue'))} · {num(p.get('quantity'), 1)} ед.")

    cat = categories(products)
    if cat:
        lines += ["", "<b>Категории</b>"]
        for name, values in cat:
            lines.append(f"{html.escape(name)}: {money(values['revenue'])} · {num(values['qty'], 1)} ед.")

    meats, sizes = meat_sizes(products)
    if meats:
        lines += ["", "<b>Мясо — донеры + батоны</b>"]
        for name, values in meats.items():
            lines.append(f"{name}: {money(values['revenue'])} · {num(values['qty'], 1)} ед.")
    if sizes:
        lines += ["", "<b>Размеры донеров</b>"]
        for name in ("Мини", "Стандарт", "1.5", "Двойной"):
            if name in sizes:
                values = sizes[name]
                lines.append(f"{name}: {money(values['revenue'])} · {num(values['qty'], 1)} ед.")

    if row["errors"]:
        lines += ["", "<i>Часть источников iiko временно не ответила; отправлены доступные цифры.</i>"]
    return "\n".join(lines)


def network_message(rows, day):
    revenue = checks = guests = online = offline = 0.0
    active = 0
    for row in rows:
        cur, receipt, mix = row["cur"], row["receipt"], row["mix"]
        if cur or receipt or mix:
            active += 1
        revenue += float(((cur or {}).get("summary") or {}).get("revenue") or 0)
        checks += float(((receipt or {}).get("summary") or {}).get("checks") or 0)
        guests += float(((receipt or {}).get("summary") or {}).get("guests") or 0)
        online += float(((mix or {}).get("online") or {}).get("revenue") or 0)
        offline += float(((mix or {}).get("offline") or {}).get("revenue") or 0)
    recognized = online + offline
    on_share = online / recognized * 100 if recognized else 0
    off_share = offline / recognized * 100 if recognized else 0
    shown = datetime.strptime(day, "%Y-%m-%d").strftime("%d.%m.%Y")
    return "\n".join([
        "☀️ <b>DONER CLUB — ЕЖЕДНЕВНЫЙ ОТЧЁТ</b>",
        f"За <b>{shown}</b> · полный день",
        "",
        "<b>Итого по выбранным точкам</b>",
        f"Выручка: <b>{money(revenue)}</b>",
        f"Чеков: <b>{num(checks)}</b> · гостей: <b>{num(guests)}</b>",
        f"Средний чек: <b>{money(revenue / checks if checks else 0)}</b>",
        f"Онлайн: <b>{money(online)}</b> · {num(on_share, 1)}%",
        f"Оффлайн: <b>{money(offline)}</b> · {num(off_share, 1)}%",
        f"Точек с доступными данными: <b>{active}</b>",
    ])


def send(token, chat_id, text):
    response = requests.post(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")


def points():
    raw = (os.environ.get("DAILY_REPORT_POINTS") or "").strip()
    return [p.strip() for p in raw.split(",") if p.strip()] if raw else list(DEFAULT_POINTS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--date", help="YYYY-MM-DD; default is yesterday in Astana time")
    args = parser.parse_args()

    day = args.date or (datetime.now(core.LOCAL_TZ).date() - timedelta(days=1)).isoformat()
    report_points = points()
    print(f"[daily-report] start date={day} points={','.join(report_points)}", flush=True)

    rows = []
    for point in report_points:
        print(f"[daily-report] collecting point={point}", flush=True)
        row = collect(point, day)
        rows.append(row)
        available = any(row.get(key) for key in ("cur", "receipt", "mix"))
        print(
            f"[daily-report] collected point={point} available={str(available).lower()} partial_errors={len(row.get('errors') or [])}",
            flush=True,
        )

    messages = [network_message(rows, day)] + [point_message(row) for row in rows]

    if args.dry_run:
        print("\n\n---\n\n".join(messages))
        print("[daily-report] dry-run complete", flush=True)
        return

    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be configured")

    total = len(messages)
    for index, message in enumerate(messages, 1):
        send(token, chat_id, message)
        print(f"[daily-report] telegram sent {index}/{total}", flush=True)

    print("[daily-report] complete", flush=True)


if __name__ == "__main__":
    main()
