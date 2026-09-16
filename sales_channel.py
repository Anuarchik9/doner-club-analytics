import threading
import time
from collections import defaultdict
from datetime import datetime

import requests
from flask import jsonify, session

import app as core


CHANNEL_TTL_SECONDS = 5 * 60
_channel_cache = {}
_channel_lock = threading.Lock()

# iikoServer SALES OLAP dimensions used to identify delivery sources and payment methods.
CHANNEL_FIELDS = ["PayTypes", "OriginName", "PublicExternalData"]

BONUS_TOKENS = (
    "балл",
    "bonus",
    "бонус",
    "points",
    "point",
    "loyalty",
)

CHANNELS = {
    "glovo": {"label": "Glovo", "group": "online", "tokens": ("glovo",)},
    "wolt": {"label": "Wolt", "group": "online", "tokens": ("wolt",)},
    "yandex": {"label": "Yandex", "group": "online", "tokens": ("yandex", "яндекс")},
    "chocofood": {
        "label": "Chocofood",
        "group": "online",
        "tokens": ("chocofood", "chokofood", "choco food"),
    },
    "starter": {"label": "Starter", "group": "online", "tokens": ("starter",)},
    "call_center": {
        "label": "CALL CENTER",
        "group": "offline",
        "tokens": ("call center", "call-center", "callcenter", "колл"),
    },
    "kaspi_qr": {
        "label": "Kaspi QR",
        "group": "offline",
        "tokens": ("kaspi", "каспи"),
    },
    "jusan_card": {
        "label": "Карта — Jusan",
        "group": "offline",
        "tokens": ("jusan", "жусан", "jysan"),
    },
    "bcc_card": {
        "label": "Карта — CenterCredit / BCC",
        "group": "offline",
        "tokens": ("centercredit", "centrecredit", "центркредит", "bcc"),
    },
    "cash": {
        "label": "Наличные",
        "group": "offline",
        "tokens": ("налич", "cash"),
    },
    "card": {
        "label": "Оплата картой",
        "group": "offline",
        "tokens": ("bank card", "bankcard", "банковск", "карта", "card", "visa", "mastercard"),
    },
}

# Source/integration channels must win over the payment method in the same OLAP row.
SOURCE_PRIORITY = ("glovo", "wolt", "yandex", "chocofood", "starter", "call_center")
PAYMENT_PRIORITY = ("kaspi_qr", "jusan_card", "bcc_card", "cash", "card")


def _cache_get(key):
    with _channel_lock:
        item = _channel_cache.get(key)
        if not item:
            return None
        if item["expires_at"] <= time.time():
            _channel_cache.pop(key, None)
            return None
        return item["value"]


def _cache_set(key, value):
    with _channel_lock:
        _channel_cache[key] = {
            "value": value,
            "expires_at": time.time() + CHANNEL_TTL_SECONDS,
        }
        if len(_channel_cache) > 70:
            oldest = sorted(_channel_cache, key=lambda k: _channel_cache[k]["expires_at"])[:15]
            for old_key in oldest:
                _channel_cache.pop(old_key, None)


def _olap_request(base_url, token, date_from, date_to, department_id, group_fields, aggregate_fields):
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
        "Department.Id": {
            "filterType": "IncludeValues",
            "values": [department_id],
        },
    }
    body = {
        "reportType": "SALES",
        "buildSummary": False,
        "groupByRowFields": group_fields,
        "groupByColFields": [],
        "aggregateFields": aggregate_fields,
        "filters": filters,
    }
    response = requests.post(
        f"{base_url}/api/v2/reports/olap",
        params={"key": token},
        json=body,
        headers={"Content-Type": "application/json"},
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("data", []) if isinstance(payload, dict) else []


def _text_for_row(row):
    values = []
    for field in CHANNEL_FIELDS:
        value = row.get(field)
        if value is not None:
            values.append(str(value))
    return " | ".join(values).strip().lower()


def _specific_channel(row):
    text = _text_for_row(row)
    if not text:
        return "other"
    if any(token in text for token in BONUS_TOKENS):
        return "excluded"
    for channel in SOURCE_PRIORITY:
        if any(token in text for token in CHANNELS[channel]["tokens"]):
            return channel
    for channel in PAYMENT_PRIORITY:
        if any(token in text for token in CHANNELS[channel]["tokens"]):
            return channel
    return "other"


def _group_for_row(row):
    channel = _specific_channel(row)
    if channel in {"excluded", "other"}:
        return channel
    return CHANNELS[channel]["group"]


def _date_value(value):
    if not value:
        return None
    text = str(value)
    return text[:10] if len(text) >= 10 else None


def _hour_value(value):
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).hour
    except (ValueError, TypeError):
        try:
            return int(str(value)[11:13])
        except (ValueError, TypeError, IndexError):
            return None


def _new_total():
    return {"rows": 0, "revenue": 0.0, "quantity": 0.0, "checks": 0.0, "guests": 0.0}


def _row_totals(rows):
    groups = defaultdict(_new_total)
    channels = defaultdict(_new_total)
    values = {field: set() for field in CHANNEL_FIELDS}

    for row in rows:
        channel = _specific_channel(row)
        group = _group_for_row(row)
        revenue = float(row.get("DishDiscountSumInt") or 0)
        quantity = float(row.get("DishAmountInt") or 0)
        checks = float(row.get("UniqOrderId") or 0)
        guests = float(row.get("GuestNum") or 0)

        for bucket in (groups[group], channels[channel]):
            bucket["rows"] += 1
            bucket["revenue"] += revenue
            bucket["quantity"] += quantity
            bucket["checks"] += checks
            bucket["guests"] += guests

        for field in CHANNEL_FIELDS:
            value = row.get(field)
            if value not in (None, "") and len(values[field]) < 80:
                values[field].add(str(value))

    def clean(bucket_map):
        return {
            key: {
                "rows": value["rows"],
                "revenue": round(value["revenue"], 2),
                "quantity": round(value["quantity"], 3),
                "checks": round(value["checks"], 3),
                "guests": round(value["guests"], 3),
            }
            for key, value in bucket_map.items()
        }

    return {
        "groups": clean(groups),
        "channels": clean(channels),
        "dimensionValues": {field: sorted(vals) for field, vals in values.items()},
    }


def _receipt_metrics(rows, date_from, date_to, channel):
    selected = [row for row in rows if _specific_channel(row) == channel]
    checks = 0.0
    revenue = 0.0
    guests = 0.0
    hourly = [
        {"hour": hour, "label": f"{hour:02d}:00", "checks": 0.0, "revenue": 0.0, "guests": 0.0}
        for hour in range(24)
    ]

    for row in selected:
        row_checks = float(row.get("UniqOrderId") or 0)
        row_revenue = float(row.get("DishDiscountSumInt") or 0)
        row_guests = float(row.get("GuestNum") or 0)
        checks += row_checks
        revenue += row_revenue
        guests += row_guests
        hour = _hour_value(row.get("CloseTime"))
        if hour is not None and 0 <= hour <= 23:
            hourly[hour]["checks"] += row_checks
            hourly[hour]["revenue"] += row_revenue
            hourly[hour]["guests"] += row_guests

    max_revenue = max((item["revenue"] for item in hourly), default=0) or 1
    for item in hourly:
        item["checks"] = round(item["checks"], 3)
        item["revenue"] = round(item["revenue"], 2)
        item["guests"] = round(item["guests"], 3)
        item["averageCheck"] = round(item["revenue"] / item["checks"], 2) if item["checks"] else 0
        item["intensity"] = round(item["revenue"] / max_revenue, 4) if max_revenue else 0

    active = [item for item in hourly if item["checks"] > 0]
    peak = max(active, key=lambda x: x["revenue"], default=None)
    weak = min(active, key=lambda x: x["revenue"], default=None)
    return {
        "success": True,
        "period": {
            "from": date_from,
            "to": date_to,
            "daysCount": len(core.date_range(date_from, date_to)),
        },
        "summary": {
            "checks": round(checks, 3),
            "revenue": round(revenue, 2),
            "guests": round(guests, 3),
            "averageCheck": round(revenue / checks, 2) if checks else 0,
        },
        "hourly": hourly,
        "peakHour": peak,
        "weakHour": weak,
    }


def _department_session(point):
    base_url, token = core.iiko_server_auth()
    departments = core.iiko_server_departments(base_url, token)
    department = core.find_iiko_server_department(point, departments)
    if not department:
        core.iiko_server_logout(base_url, token)
        raise ValueError(f"Point '{point}' not found in iikoServer departments")
    return base_url, token, department


def _build_mix(point, date_from, date_to):
    core.date_range(date_from, date_to)
    cache_key = ("mix", point.strip().lower(), date_from, date_to)
    cached = _cache_get(cache_key)
    if cached is not None:
        result = dict(cached)
        result["cache"] = {"hit": True, "ttlSeconds": CHANNEL_TTL_SECONDS}
        return result

    base_url = None
    token = None
    try:
        base_url, token, department = _department_session(point)
        rows = _olap_request(
            base_url,
            token,
            date_from,
            date_to,
            department.get("id"),
            ["CloseTime", *CHANNEL_FIELDS],
            ["GuestNum", "DishDiscountSumInt", "UniqOrderId"],
        )
        breakdown = _row_totals(rows)
        groups = breakdown["groups"]
        online = groups.get("online", _new_total())
        offline = groups.get("offline", _new_total())
        excluded = groups.get("excluded", _new_total())
        other = groups.get("other", _new_total())
        recognized = float(online.get("revenue", 0)) + float(offline.get("revenue", 0))

        def summary(item):
            revenue = float(item.get("revenue", 0))
            checks = float(item.get("checks", 0))
            return {
                "revenue": round(revenue, 2),
                "checks": round(checks, 3),
                "guests": round(float(item.get("guests", 0)), 3),
                "averageCheck": round(revenue / checks, 2) if checks else 0,
                "share": round(revenue / recognized * 100, 1) if recognized else 0,
            }

        result = {
            "success": True,
            "point": {
                "id": department.get("id"),
                "code": department.get("code"),
                "name": department.get("name"),
            },
            "period": {
                "from": date_from,
                "to": date_to,
                "daysCount": len(core.date_range(date_from, date_to)),
            },
            "online": summary(online),
            "offline": summary(offline),
            "excluded": summary(excluded),
            "other": summary(other),
            "channels": breakdown["channels"],
            "dimensionValues": breakdown["dimensionValues"],
            "rules": {
                "online": ["Glovo", "Wolt", "Yandex", "Chocofood", "Starter (без баллов)"],
                "offline": ["Kaspi QR", "Jusan", "CenterCredit/BCC", "наличные", "CALL CENTER", "карта"],
                "excluded": ["баллы/бонусы"],
            },
            "cache": {"hit": False, "ttlSeconds": CHANNEL_TTL_SECONDS},
        }
        _cache_set(cache_key, result)
        return result
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def _build_filtered(point, date_from, date_to, channel):
    core.date_range(date_from, date_to)
    if channel not in CHANNELS:
        raise ValueError("Unknown sales channel")

    cache_key = ("specific", point.strip().lower(), date_from, date_to, channel)
    cached = _cache_get(cache_key)
    if cached is not None:
        result = dict(cached)
        result["cache"] = {"hit": True, "ttlSeconds": CHANNEL_TTL_SECONDS}
        return result

    base_url = None
    token = None
    try:
        base_url, token, department = _department_session(point)
        department_id = department.get("id")

        product_rows = _olap_request(
            base_url,
            token,
            date_from,
            date_to,
            department_id,
            ["OpenDate.Typed", "DishId", "DishName", *CHANNEL_FIELDS],
            ["DishDiscountSumInt", "DishAmountInt"],
        )
        receipt_rows = _olap_request(
            base_url,
            token,
            date_from,
            date_to,
            department_id,
            ["CloseTime", *CHANNEL_FIELDS],
            ["GuestNum", "DishDiscountSumInt", "UniqOrderId"],
        )

        selected_products = [row for row in product_rows if _specific_channel(row) == channel]
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
        products = {}
        for row in selected_products:
            product_id = str(row.get("DishId") or row.get("DishName") or "unknown")
            name = str(row.get("DishName") or "Позиция iiko")
            revenue = float(row.get("DishDiscountSumInt") or 0)
            quantity = float(row.get("DishAmountInt") or 0)
            if product_id not in products:
                products[product_id] = {
                    "productId": product_id,
                    "name": name,
                    "article": None,
                    "quantity": 0.0,
                    "revenue": 0.0,
                }
            products[product_id]["quantity"] += quantity
            products[product_id]["revenue"] += revenue
            day = _date_value(row.get("OpenDate.Typed"))
            if day in daily:
                daily[day]["revenue"] += revenue
                daily[day]["itemsRevenue"] += revenue
                daily[day]["quantity"] += quantity

        product_list = []
        for item in products.values():
            item["quantity"] = round(item["quantity"], 3)
            item["revenue"] = round(item["revenue"], 2)
            product_list.append(item)

        by_revenue = sorted(product_list, key=lambda x: x["revenue"], reverse=True)
        by_quantity = sorted(product_list, key=lambda x: x["quantity"], reverse=True)
        daily_series = []
        for day in sorted(daily):
            item = daily[day]
            daily_series.append({
                "date": day,
                "revenue": round(item["revenue"], 2),
                "itemsRevenue": round(item["itemsRevenue"], 2),
                "quantity": round(item["quantity"], 3),
                "documentsCount": 0,
            })

        total_revenue = round(sum(x["revenue"] for x in product_list), 2)
        total_quantity = round(sum(x["quantity"] for x in product_list), 3)
        days_count = len(all_dates)
        receipt = _receipt_metrics(receipt_rows, date_from, date_to, channel)
        breakdown = _row_totals(receipt_rows)

        result = {
            "success": True,
            "channel": channel,
            "channelLabel": CHANNELS[channel]["label"],
            "channelGroup": CHANNELS[channel]["group"],
            "point": {
                "id": department_id,
                "code": department.get("code"),
                "name": department.get("name"),
            },
            "period": {"from": date_from, "to": date_to, "daysCount": days_count},
            "summary": {
                "documentsCount": 0,
                "revenue": total_revenue,
                "itemsRevenue": total_revenue,
                "itemsQuantity": total_quantity,
                "uniqueProducts": len(product_list),
                "averageDailyRevenue": round(total_revenue / days_count, 2) if days_count else 0,
            },
            "daily": daily_series,
            "topByRevenue": by_revenue[:20],
            "topByQuantity": by_quantity[:20],
            "products": by_revenue,
            "receipt": receipt,
            "classification": breakdown,
            "cache": {"hit": False, "ttlSeconds": CHANNEL_TTL_SECONDS},
        }
        _cache_set(cache_key, result)
        return result
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def _filter_ui_script():
    options = [
        ("all", "Все каналы"),
        ("glovo", "Glovo"),
        ("wolt", "Wolt"),
        ("yandex", "Yandex"),
        ("chocofood", "Chocofood"),
        ("starter", "Starter (без баллов)"),
        ("kaspi_qr", "Kaspi QR"),
        ("call_center", "CALL CENTER"),
        ("jusan_card", "Карта — Jusan"),
        ("bcc_card", "Карта — CenterCredit / BCC"),
        ("cash", "Наличные"),
        ("card", "Оплата картой"),
    ]
    options_html = "".join(f'<option value="{value}">{label}</option>' for value, label in options)

    return f'''
<style id="dc-channel-style">
@media(min-width:901px){{.filters{{grid-template-columns:1.1fr 1fr 1fr 1fr auto!important}}}}
.channel-mix-wrap{{margin-top:13px}}
.channel-mix-title{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 10px}}
.channel-mix-title strong{{font-size:13px}}
.channel-mix-title span{{font-size:10px;color:#777}}
.channel-mix-grid{{display:grid;grid-template-columns:1fr 1fr;gap:13px}}
.channel-mix-card{{position:relative;overflow:hidden;min-height:135px;padding:19px 20px;border:1px solid var(--line);border-radius:20px;background:linear-gradient(160deg,#151515,#101010)}}
.channel-mix-card:after{{content:"";position:absolute;width:100px;height:100px;border-radius:50%;right:-50px;top:-50px;background:rgba(255,90,31,.07)}}
.channel-mix-card .mix-label{{color:var(--muted);font-size:12px;font-weight:750}}
.channel-mix-card .mix-value{{font-size:34px;font-weight:950;letter-spacing:-.045em;margin-top:14px;white-space:nowrap}}
.channel-mix-card .mix-sub{{color:var(--muted);font-size:11px;margin-top:7px}}
.channel-mix-note{{color:#777;font-size:10px;margin-top:8px;line-height:1.45}}
@media(max-width:600px){{.channel-mix-grid{{grid-template-columns:1fr}}}}
</style>
<script id="dc-channel-script">
(function(){{
  const pointField=document.querySelector('.filters .field');
  if(!pointField||document.getElementById('salesChannel'))return;

  const field=document.createElement('div');
  field.className='field';
  field.innerHTML='<label>Канал / оплата</label><select id="salesChannel">{options_html}</select>';
  pointField.insertAdjacentElement('afterend',field);

  const mainCards=document.querySelector('.section + .cards');
  if(mainCards&&!document.getElementById('channelMixWrap')){{
    const wrap=document.createElement('div');
    wrap.id='channelMixWrap';
    wrap.className='channel-mix-wrap';
    wrap.innerHTML=`<div class="channel-mix-title"><strong>Онлайн и оффлайн продажи</strong><span id="mixPeriodLabel">По выбранному периоду</span></div><div class="channel-mix-grid"><div class="channel-mix-card"><div class="mix-label">Онлайн продажи</div><div class="mix-value" id="onlineSales">—</div><div class="mix-sub" id="onlineSalesSub">—</div></div><div class="channel-mix-card"><div class="mix-label">Оффлайн продажи</div><div class="mix-value" id="offlineSales">—</div><div class="mix-sub" id="offlineSalesSub">—</div></div></div><div class="channel-mix-note" id="mixNote">Онлайн: Glovo, Wolt, Yandex, Chocofood, Starter без баллов. Оффлайн: Kaspi QR, карты, наличные, CALL CENTER.</div>`;
    mainCards.insertAdjacentElement('afterend',wrap);
  }}

  const go=document.getElementById('go');
  const originalLoad=go.onclick;
  const select=document.getElementById('salesChannel');

  function selectedLabel(){{return select.options[select.selectedIndex].textContent}}
  function setMixLoading(){{
    if($('onlineSales'))$('onlineSales').textContent='…';
    if($('offlineSales'))$('offlineSales').textContent='…';
    if($('onlineSalesSub'))$('onlineSalesSub').textContent='Считаем по iiko';
    if($('offlineSalesSub'))$('offlineSalesSub').textContent='Считаем по iiko';
  }}
  function renderMix(mix,a,b){{
    if(!mix||mix._error){{
      if($('onlineSales'))$('onlineSales').textContent='—';
      if($('offlineSales'))$('offlineSales').textContent='—';
      if($('onlineSalesSub'))$('onlineSalesSub').textContent='Не удалось загрузить';
      if($('offlineSalesSub'))$('offlineSalesSub').textContent='Не удалось загрузить';
      return;
    }}
    const on=mix.online||{{}},off=mix.offline||{{}},other=mix.other||{{}},excluded=mix.excluded||{{}};
    $('onlineSales').textContent=cash(on.revenue||0);
    $('offlineSales').textContent=cash(off.revenue||0);
    $('onlineSalesSub').textContent=`${{money.format(on.checks||0)}} чек. · ${{fmt.format(on.share||0)}}% распознанной выручки`;
    $('offlineSalesSub').textContent=`${{money.format(off.checks||0)}} чек. · ${{fmt.format(off.share||0)}}% распознанной выручки`;
    $('mixPeriodLabel').textContent=a===b?dateText(a):`${{dateText(a)}} — ${{dateText(b)}}`;
    let note='Онлайн: Glovo, Wolt, Yandex, Chocofood, Starter без баллов. Оффлайн: Kaspi QR, карты, наличные, CALL CENTER.';
    if(Number(excluded.revenue||0)>0)note+=` Баллы/бонусы исключены: ${{cash(excluded.revenue)}}.`;
    if(Number(other.revenue||0)>0)note+=` Не распределено: ${{cash(other.revenue)}}.`;
    $('mixNote').textContent=note;
  }}
  async function loadMix(point,a,b){{
    try{{return await get(`/sales-mix?point=${{encodeURIComponent(point)}}&from=${{a}}&to=${{b}}`)}}
    catch(e){{return {{_error:e.message}}}}
  }}

  async function specificLoad(){{
    const channel=select.value;
    let point=$('point').value||'Arai',a=$('from').value,b=$('to').value;
    if(!a||!b){{$('error').innerHTML='<div class="error">Сначала выберите период.</div>';return}}
    if(a>b){{$('error').innerHTML='<div class="error">Дата «с» не может быть позже даты «по».</div>';return}}
    if(daysBetween(a,b)>62){{$('error').innerHTML='<div class="error">Максимальный период — 62 дня.</div>';return}}

    setMixLoading();
    if(channel==='all'){{
      await originalLoad.call(go);
      const mix=await loadMix(point,a,b);
      renderMix(mix,a,b);
      $('eyebrow').textContent=a===b?'Пульс дня':'Пульс периода';
      return;
    }}

    $('loading').classList.add('show');$('error').innerHTML='';clearDashboard('Загружаем '+selectedLabel()+'…');
    try{{
      let[pa,pb]=prevPeriod(a,b),compareRange=pa===pb?dateText(pa):`${{dateText(pa)}} — ${{dateText(pb)}}`;compareCaption=compareRange;
      $('comparePeriodLabel').textContent=`Сравнение с ${{compareRange}} — те же дни недели`;$('chartCompareLabel').textContent=`Неделей ранее: ${{compareRange}}`;
      let base=`/channel-analytics?point=${{encodeURIComponent(point)}}&channel=${{encodeURIComponent(channel)}}`;
      let[j,prev,mix]=await Promise.all([get(`${{base}}&from=${{a}}&to=${{b}}`),optionalGet(`${{base}}&from=${{pa}}&to=${{pb}}`),loadMix(point,a,b)]);
      if(prev?._error)prev=null;
      currentData=j;previousData=prev;receiptCurrent=j.receipt;receiptPrevious=prev?.receipt||null;products=j.products||[];
      let s=j.summary||{{}},ps=prev?.summary||{{}};
      $('title').textContent=j.point?.name||j.point?.code||point;$('eyebrow').textContent=`${{selectedLabel()}} · ${{a===b?'Пульс дня':'Пульс периода'}}`;
      $('period').textContent=a===b?dateText(a):`${{dateText(a)}} — ${{dateText(b)}}`;$('range').textContent=$('period').textContent;$('updated').textContent=`Обновлено ${{new Date().toLocaleTimeString('ru-RU',{{hour:'2-digit',minute:'2-digit'}})}}`;
      $('revenue').textContent=cash(s.revenue);$('qty').textContent=fmt.format(s.itemsQuantity||0);$('unique').textContent=money.format(s.uniqueProducts||0);$('dailyAvg').textContent=cash(s.averageDailyRevenue||0);
      $('revenueDelta').innerHTML=delta(s.revenue,ps.revenue);$('qtyDelta').innerHTML=delta(s.itemsQuantity,ps.itemsQuantity);$('uniqueDelta').innerHTML=delta(s.uniqueProducts,ps.uniqueProducts);$('dailyDelta').innerHTML=delta(s.averageDailyRevenue,ps.averageDailyRevenue);
      bars('revBars',j.topByRevenue,'revenue',true);bars('qtyBars',j.topByQuantity,'quantity',false);renderChart(j,prev);renderReceipt(j.receipt,prev?.receipt||null);renderPulse(j);renderCategories(j);renderInsights(j,prev);table();
      renderMix(mix,a,b);
      $('receiptNote').textContent=`${{selectedLabel()}} · iikoServer OLAP · ${{j.period?.daysCount||1}} дн.`;
    }}catch(e){{clearDashboard('Данные за выбранный канал не загружены');$('updated').textContent='Последняя попытка завершилась ошибкой';$('error').innerHTML=`<div class="error">Не удалось загрузить данные: ${{esc(e.message)}}</div>`}}
    finally{{$('loading').classList.remove('show')}}
  }}

  go.onclick=specificLoad;
}})();
</script>
'''


def install_sales_channel(app):
    if getattr(app, "_doner_sales_channel_installed", False):
        return
    app._doner_sales_channel_installed = True

    @app.before_request
    def _protect_channel_api():
        if core.request.path in {"/channel-analytics", "/sales-mix"} and not session.get("dc_authenticated"):
            return jsonify({
                "success": False,
                "code": "AUTH_REQUIRED",
                "message": "Authentication required",
                "login": "/login",
            }), 401
        return None

    @app.route("/channel-analytics")
    def channel_analytics():
        try:
            point = (core.request.args.get("point") or "Arai").strip()
            channel = (core.request.args.get("channel") or "glovo").strip().lower()
            single_date = core.request.args.get("date")
            date_from = core.request.args.get("from") or single_date
            date_to = core.request.args.get("to") or date_from
            if not date_from:
                date_from = core.datetime.now(core.LOCAL_TZ).date().isoformat()
            if not date_to:
                date_to = date_from
            return core.jsonify(_build_filtered(point, date_from, date_to, channel))
        except requests.HTTPError as error:
            response = error.response
            return core.jsonify({
                "success": False,
                "code": "CHANNEL_OLAP_ERROR",
                "statusCode": response.status_code if response is not None else None,
                "details": response.text[:1200] if response is not None else str(error),
            }), 502
        except ValueError as error:
            return core.jsonify({"success": False, "code": "CHANNEL_INVALID", "message": str(error)}), 400
        except Exception as error:
            return core.jsonify({"success": False, "code": "CHANNEL_ERROR", "message": str(error)}), 500

    @app.route("/sales-mix")
    def sales_mix():
        try:
            point = (core.request.args.get("point") or "Arai").strip()
            single_date = core.request.args.get("date")
            date_from = core.request.args.get("from") or single_date
            date_to = core.request.args.get("to") or date_from
            if not date_from:
                date_from = core.datetime.now(core.LOCAL_TZ).date().isoformat()
            if not date_to:
                date_to = date_from
            return core.jsonify(_build_mix(point, date_from, date_to))
        except requests.HTTPError as error:
            response = error.response
            return core.jsonify({
                "success": False,
                "code": "SALES_MIX_OLAP_ERROR",
                "statusCode": response.status_code if response is not None else None,
                "details": response.text[:1200] if response is not None else str(error),
            }), 502
        except ValueError as error:
            return core.jsonify({"success": False, "code": "SALES_MIX_INVALID", "message": str(error)}), 400
        except Exception as error:
            return core.jsonify({"success": False, "code": "SALES_MIX_ERROR", "message": str(error)}), 500

    @app.after_request
    def _inject_sales_channel(response):
        if (
            core.request.path.endswith("dashboard-v2.html")
            and response.status_code == 200
            and response.mimetype == "text/html"
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                marker = "</body>"
                if marker in body and "dc-channel-script" not in body:
                    response.set_data(body.replace(marker, _filter_ui_script() + marker, 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
