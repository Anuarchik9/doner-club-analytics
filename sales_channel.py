import threading
import time
from collections import defaultdict
from datetime import datetime

import requests

import app as core


CHANNEL_TTL_SECONDS = 5 * 60
_channel_cache = {}
_channel_lock = threading.Lock()

# These fields are available in the iikoServer SALES OLAP used by the dashboard.
# PayTypes identifies payment methods; OriginName/PublicExternalData carry order/integration origin metadata.
CHANNEL_FIELDS = ["PayTypes", "OriginName", "PublicExternalData"]

ONLINE_TOKENS = (
    "glovo",
    "wolt",
    "yandex",
    "яндекс",
    "chocofood",
    "chokofood",
    "choco food",
    "starter",
)
OFFLINE_TOKENS = (
    "kaspi",
    "каспи",
    " qr",
    "qr ",
    "qr",
    "жусан",
    "jusan",
    "jysan",
    "centercredit",
    "centrecredit",
    "центркредит",
    "bcc",
    "bank card",
    "bankcard",
    "банковск",
    "карта",
    "card",
    "visa",
    "mastercard",
    "налич",
    "cash",
    "call center",
    "call-center",
    "callcenter",
    "колл",
)
BONUS_TOKENS = (
    "балл",
    "bonus",
    "бонус",
    "points",
    "point",
    "loyalty",
)


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
        if len(_channel_cache) > 50:
            oldest = sorted(_channel_cache, key=lambda k: _channel_cache[k]["expires_at"])[:10]
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


def _classify(row):
    text = _text_for_row(row)
    if not text:
        return "other"
    # Bonus/points are intentionally excluded from both online and offline according to Doner Club rules.
    if any(token in text for token in BONUS_TOKENS):
        return "excluded"
    # Source has priority over payment method: an aggregator order paid by card is still online.
    if any(token in text for token in ONLINE_TOKENS):
        return "online"
    if any(token in text for token in OFFLINE_TOKENS):
        return "offline"
    return "other"


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


def _channel_breakdown(rows):
    totals = defaultdict(lambda: {"rows": 0, "revenue": 0.0, "quantity": 0.0, "checks": 0.0})
    values = {field: set() for field in CHANNEL_FIELDS}
    for row in rows:
        category = _classify(row)
        item = totals[category]
        item["rows"] += 1
        item["revenue"] += float(row.get("DishDiscountSumInt") or 0)
        item["quantity"] += float(row.get("DishAmountInt") or 0)
        item["checks"] += float(row.get("UniqOrderId") or 0)
        for field in CHANNEL_FIELDS:
            value = row.get(field)
            if value not in (None, "") and len(values[field]) < 60:
                values[field].add(str(value))
    return {
        "totals": {
            key: {
                "rows": value["rows"],
                "revenue": round(value["revenue"], 2),
                "quantity": round(value["quantity"], 3),
                "checks": round(value["checks"], 3),
            }
            for key, value in totals.items()
        },
        "dimensionValues": {field: sorted(vals) for field, vals in values.items()},
    }


def _receipt_metrics(rows, date_from, date_to, channel):
    selected = [row for row in rows if _classify(row) == channel]
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


def _build_filtered(point, date_from, date_to, channel):
    core.date_range(date_from, date_to)
    if channel not in {"online", "offline"}:
        raise ValueError("channel must be online or offline")

    cache_key = (point.strip().lower(), date_from, date_to, channel)
    cached = _cache_get(cache_key)
    if cached is not None:
        result = dict(cached)
        result["cache"] = {"hit": True, "ttlSeconds": CHANNEL_TTL_SECONDS}
        return result

    base_url = None
    token = None
    try:
        base_url, token = core.iiko_server_auth()
        departments = core.iiko_server_departments(base_url, token)
        department = core.find_iiko_server_department(point, departments)
        if not department:
            raise ValueError(f"Point '{point}' not found in iikoServer departments")
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

        selected_products = [row for row in product_rows if _classify(row) == channel]
        all_dates = core.date_range(date_from, date_to)
        daily = {
            day: {"date": day, "revenue": 0.0, "itemsRevenue": 0.0, "quantity": 0.0, "documentsCount": 0}
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
        product_breakdown = _channel_breakdown(product_rows)
        receipt_breakdown = _channel_breakdown(receipt_rows)

        result = {
            "success": True,
            "channel": channel,
            "channelLabel": "Онлайн" if channel == "online" else "Оффлайн",
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
            "classification": {
                "rules": {
                    "online": ["Glovo", "Wolt", "Yandex", "Chocofood", "Starter"],
                    "offline": ["Kaspi QR", "карта/Jusan/BCC", "наличные", "CALL CENTER"],
                    "excluded": ["баллы/бонусы"],
                },
                "productRows": product_breakdown,
                "receiptRows": receipt_breakdown,
            },
            "cache": {"hit": False, "ttlSeconds": CHANNEL_TTL_SECONDS},
        }
        _cache_set(cache_key, result)
        return result
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def _filter_ui_script():
    return r'''
<style id="dc-channel-style">
@media(min-width:901px){.filters{grid-template-columns:1.15fr .9fr 1fr 1fr auto!important}}
.channel-note{margin-top:10px;color:#8e8e88;font-size:11px}.channel-note b{color:#ff8e5e}
</style>
<script id="dc-channel-script">
(function(){
  const pointField=document.querySelector('.filters .field');
  if(!pointField||document.getElementById('salesChannel'))return;
  const field=document.createElement('div');field.className='field';field.innerHTML='<label>Канал продаж</label><select id="salesChannel"><option value="all">Все продажи</option><option value="online">Онлайн</option><option value="offline">Оффлайн</option></select>';
  pointField.insertAdjacentElement('afterend',field);
  const originalLoad=document.getElementById('go').onclick;
  function selectedLabel(){const s=document.getElementById('salesChannel');return s.options[s.selectedIndex].textContent}
  async function channelLoad(){
    const channel=document.getElementById('salesChannel').value;
    if(channel==='all'){return originalLoad.call(document.getElementById('go'))}
    let point=$('point').value||'Arai',a=$('from').value,b=$('to').value;
    if(!a||!b){$('error').innerHTML='<div class="error">Сначала выберите период.</div>';return}
    if(a>b){$('error').innerHTML='<div class="error">Дата «с» не может быть позже даты «по».</div>';return}
    if(daysBetween(a,b)>62){$('error').innerHTML='<div class="error">Максимальный период — 62 дня.</div>';return}
    $('loading').classList.add('show');$('error').innerHTML='';clearDashboard('Загружаем '+selectedLabel().toLowerCase()+'…');
    try{
      let[pa,pb]=prevPeriod(a,b),compareRange=pa===pb?dateText(pa):`${dateText(pa)} — ${dateText(pb)}`;compareCaption=compareRange;
      $('comparePeriodLabel').textContent=`Сравнение с ${compareRange} — те же дни недели`;$('chartCompareLabel').textContent=`Неделей ранее: ${compareRange}`;
      let base=`/channel-analytics?point=${encodeURIComponent(point)}&channel=${channel}`;
      let[j,prev]=await Promise.all([get(`${base}&from=${a}&to=${b}`),optionalGet(`${base}&from=${pa}&to=${pb}`)]);if(prev?._error)prev=null;
      currentData=j;previousData=prev;receiptCurrent=j.receipt;receiptPrevious=prev?.receipt||null;products=j.products||[];
      let s=j.summary||{},ps=prev?.summary||{};
      $('title').textContent=j.point?.name||j.point?.code||point;$('eyebrow').textContent=`${selectedLabel()} · ${a===b?'Пульс дня':'Пульс периода'}`;
      $('period').textContent=a===b?dateText(a):`${dateText(a)} — ${dateText(b)}`;$('range').textContent=$('period').textContent;$('updated').textContent=`Обновлено ${new Date().toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'})}`;
      $('revenue').textContent=cash(s.revenue);$('qty').textContent=fmt.format(s.itemsQuantity||0);$('unique').textContent=money.format(s.uniqueProducts||0);$('dailyAvg').textContent=cash(s.averageDailyRevenue||0);
      $('revenueDelta').innerHTML=delta(s.revenue,ps.revenue);$('qtyDelta').innerHTML=delta(s.itemsQuantity,ps.itemsQuantity);$('uniqueDelta').innerHTML=delta(s.uniqueProducts,ps.uniqueProducts);$('dailyDelta').innerHTML=delta(s.averageDailyRevenue,ps.averageDailyRevenue);
      bars('revBars',j.topByRevenue,'revenue',true);bars('qtyBars',j.topByQuantity,'quantity',false);renderChart(j,prev);renderReceipt(j.receipt,prev?.receipt||null);renderPulse(j);renderCategories(j);renderInsights(j,prev);table();
      const other=j.classification?.receiptRows?.totals?.other||{};const excluded=j.classification?.receiptRows?.totals?.excluded||{};
      if(Number(other.revenue||0)>0||Number(excluded.revenue||0)>0){$('receiptError').innerHTML=`<div class="soft-error">Фильтр применён по источникам/типам оплат iiko. Не распределено: ${cash(other.revenue||0)}. Баллы/бонусы исключены: ${cash(excluded.revenue||0)}.</div>`}
      $('receiptNote').textContent=`${selectedLabel()} · iikoServer OLAP · ${j.period?.daysCount||1} дн. · баллы/бонусы не входят в онлайн/оффлайн`;
    }catch(e){clearDashboard('Данные за выбранный канал не загружены');$('updated').textContent='Последняя попытка завершилась ошибкой';$('error').innerHTML=`<div class="error">Не удалось загрузить данные: ${esc(e.message)}</div>`}
    finally{$('loading').classList.remove('show')}
  }
  document.getElementById('go').onclick=channelLoad;
})();
</script>
'''


def install_sales_channel(app):
    if getattr(app, "_doner_sales_channel_installed", False):
        return
    app._doner_sales_channel_installed = True

    @app.route("/channel-analytics")
    def channel_analytics():
        try:
            point = (core.request.args.get("point") or "Arai").strip()
            channel = (core.request.args.get("channel") or "online").strip().lower()
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
