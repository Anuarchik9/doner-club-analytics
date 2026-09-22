import hashlib
import os
import re
from collections import defaultdict
from datetime import datetime

import requests
from flask import jsonify, request


SCOPES = {
    # Legacy API scope. Keep it for old bookmarks/scripts, but only use the
    # physical "АРАЙ общий" warehouse. Household inventory is a separate process
    # and must never move the "last revision" date for the sales point.
    "arai": {
        "label": "Арай · общий склад",
        "store_needles": ("арай",),
        "store_excludes": ("цех", "хоз"),
        "revision_kind": None,
    },
    "arai_kitchen": {
        "label": "Арай · кухня",
        "store_needles": ("арай",),
        "store_excludes": ("цех", "хоз"),
        "revision_kind": "kitchen",
    },
    "arai_counter": {
        "label": "Арай · напитки и товары точки",
        "store_needles": ("арай",),
        "store_excludes": ("цех", "хоз"),
        "revision_kind": "counter",
    },
    "workshop": {
        "label": "Цех",
        "store_needles": ("цех",),
        "store_excludes": (),
        "revision_kind": None,
    },
}

# Arai uses the same physical warehouse for two different responsibility zones.
# The kitchen inventory is the compact raw-material count. The cashier/point
# inventory contains drinks and items sold/issued together with the doner.
# Strong point markers win over kitchen markers because the wider point revision
# may legitimately contain meat/fries too (as seen in Arai0110).
ARAI_COUNTER_MARKERS = (
    "ava",
    "пиала",
    "piala",
    "pepsi",
    "mirinda",
    "7 up",
    "7up",
    "вода",
    "айран",
    "да да",
    "да-да",
    "kinza",
    "кинза",
    "салфет",
    "пакет",
    "ложк",
    "зубочист",
    "стакан",
    "крышк",
    "трубоч",
    "соус",
    "лажжан",
    "лаваш",
)
ARAI_KITCHEN_MARKERS = (
    "шаурм",
    "говяж",
    "курин",
    "картофель фри",
    "картофель фри очищ",
)


def _norm_product(value):
    text = str(value or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return " ".join(text.split())


def _arai_revision_kind(product_names):
    normalized = [_norm_product(value) for value in product_names if str(value or "").strip()]
    if not normalized:
        return None

    counter_hits = sum(
        1 for name in normalized
        if any(marker in name for marker in ARAI_COUNTER_MARKERS)
    )
    kitchen_hits = sum(
        1 for name in normalized
        if any(marker in name for marker in ARAI_KITCHEN_MARKERS)
    )

    if counter_hits:
        return "counter"
    if kitchen_hits:
        return "kitchen"

    # Wide inventories on the general Arai warehouse are point/cashier counts
    # even when their individual product names do not hit the known vocabulary.
    if len(set(normalized)) >= 8:
        return "counter"
    return None


def _scope_revision_kind(scope_key):
    return (SCOPES.get(scope_key) or {}).get("revision_kind")

# Different iiko builds expose inventory reconciliation under different labels.
# We therefore inspect transaction type, document and accounting fields, not only TransactionType.
INVENTORY_MARKERS = (
    "invtr",
    "inventory",
    "invent",
    "reconciliation",
    "инвентар",
    "ревиз",
    "недостач",
    "излишк",
)


def _settings():
    base_url = (os.environ.get("IIKO_SERVER_URL") or "https://dc-firdaws-co-arm.iiko.it/resto").rstrip("/")
    login = (os.environ.get("IIKO_SERVER_LOGIN") or "").strip()
    password = os.environ.get("IIKO_SERVER_PASSWORD") or ""
    if not login or not password:
        raise RuntimeError("iikoServer credentials are not configured")
    return base_url, login, password


def _auth():
    base_url, login, password = _settings()
    password_hash = hashlib.sha1(password.encode("utf-8")).hexdigest()
    response = requests.get(
        f"{base_url}/api/auth",
        params={"login": login, "pass": password_hash},
        timeout=20,
    )
    response.raise_for_status()
    token = response.text.strip().strip('"')
    if not token or "<html" in token.lower():
        raise RuntimeError("iikoServer returned an invalid auth token")
    return base_url, token


def _logout(base_url, token):
    if not token:
        return
    try:
        requests.get(f"{base_url}/api/logout", params={"key": token}, timeout=6)
    except requests.RequestException:
        pass


def _month_bounds(period):
    start = datetime.strptime(period, "%Y-%m")
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.strftime("%Y-%m-%dT00:00:00.000"), end.strftime("%Y-%m-%dT00:00:00.000")


def _field_map(payload):
    if not isinstance(payload, dict):
        return {}
    candidates = []
    if isinstance(payload.get("columns"), dict):
        candidates.append(payload["columns"])
    candidates.append(payload)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        useful = {
            key: value
            for key, value in candidate.items()
            if isinstance(key, str)
            and isinstance(value, dict)
            and (
                "groupingAllowed" in value
                or "aggregationAllowed" in value
                or "filteringAllowed" in value
                or "type" in value
            )
        }
        if useful:
            return useful
    return {}


def _allowed(fields, name, capability):
    info = fields.get(name)
    return bool(info) and info.get(capability) is not False


def _pick(available, *names):
    for name in names:
        if name in available:
            return name
    return None


def _pick_like(available, includes, excludes=()):
    for name in sorted(available):
        low = name.lower()
        if all(part in low for part in includes) and not any(part in low for part in excludes):
            return name
    return None


def _num(value):
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _store_matches(scope_key, value):
    text = str(value or "").strip().lower()
    if not text:
        return False
    cfg = SCOPES[scope_key]
    if cfg["store_needles"] and not any(x in text for x in cfg["store_needles"]):
        return False
    if any(x in text for x in cfg["store_excludes"]):
        return False
    return True


def _marker(value):
    text = str(value or "").strip().lower()
    return bool(text) and any(marker in text for marker in INVENTORY_MARKERS)


def _date_filter(date_field, period):
    date_from, date_to = _month_bounds(period)
    return {
        date_field: {
            "filterType": "DateRange",
            "periodType": "CUSTOM",
            "from": date_from,
            "to": date_to,
            "includeLow": True,
            "includeHigh": False,
        }
    }


def _olap_post(base_url, token, body, timeout=90):
    response = requests.post(
        f"{base_url}/api/v2/reports/olap",
        params={"key": token},
        json=body,
        timeout=timeout,
    )
    if not response.ok:
        raise RuntimeError(f"TRANSACTIONS OLAP HTTP {response.status_code}: {response.text[:700]}")
    data = response.json()
    rows = data.get("data", data if isinstance(data, list) else [])
    return rows if isinstance(rows, list) else []


def _get_fields(base_url, token):
    response = requests.get(
        f"{base_url}/api/v2/reports/olap/columns",
        params={"key": token, "reportType": "TRANSACTIONS"},
        timeout=30,
    )
    response.raise_for_status()
    fields = _field_map(response.json())
    if not fields:
        raise RuntimeError("iikoServer не вернул список полей TRANSACTIONS OLAP")
    return fields


def _resolve(fields):
    available = set(fields)
    date_field = _pick(available, "DateTime.DateTyped", "DateSecondary.DateTyped") or _pick_like(available, ("date", "typed"))
    tx_field = _pick(available, "TransactionType.Code", "TransactionType", "TransactionType.Name") or _pick_like(available, ("transactiontype",))
    document_field = _pick(available, "Document", "Document.Number", "Document.Num") or _pick_like(available, ("document",), ("date",))
    product_field = _pick(available, "Product.Name", "Contr-Product.Name") or _pick_like(available, ("product", "name"))
    product_id_field = _pick(available, "Product.Id", "Contr-Product.Id") or _pick_like(available, ("product", "id"))
    unit_field = _pick(available, "Product.MeasureUnit", "Contr-Product.MeasureUnit") or _pick_like(available, ("product", "measure"))

    store_fields = []
    preferred_store = (
        "Store.Name",
        "Store",
        "Account.StoreOrAccount.Name",
        "Account.StoreOrAccount",
        "Contr-Account.StoreOrAccount.Name",
        "Contr-Account.StoreOrAccount",
    )
    for name in preferred_store:
        if name in available and _allowed(fields, name, "groupingAllowed") and name not in store_fields:
            store_fields.append(name)
    for name in sorted(available):
        if "store" in name.lower() and _allowed(fields, name, "groupingAllowed") and name not in store_fields:
            store_fields.append(name)
        if len(store_fields) >= 5:
            break

    account_fields = []
    preferred_account = (
        "Account.Name",
        "Account",
        "Contr-Account.Name",
        "Contr-Account",
        "Account.Code",
        "Contr-Account.Code",
    )
    for name in preferred_account:
        if name in available and _allowed(fields, name, "groupingAllowed") and name not in account_fields:
            account_fields.append(name)
    for name in sorted(available):
        low = name.lower()
        if "account" in low and "storeoraccount" not in low and _allowed(fields, name, "groupingAllowed") and name not in account_fields:
            account_fields.append(name)
        if len(account_fields) >= 6:
            break

    aggregate_candidates = (
        "Amount.In",
        "Amount.Out",
        "Amount.StoreInOutTyped",
        "Sum.Incoming",
        "Sum.Outgoing",
        "Product.AvgSum",
        "Contr-Amount",
    )
    aggregates = [x for x in aggregate_candidates if x in available and _allowed(fields, x, "aggregationAllowed")]

    missing = []
    if not date_field:
        missing.append("date")
    if not store_fields:
        missing.append("store")
    if not product_field:
        missing.append("product")
    if not aggregates:
        missing.append("amount/sum")
    if missing:
        raise RuntimeError("В TRANSACTIONS OLAP не найдены обязательные поля: " + ", ".join(missing))

    return {
        "date": date_field,
        "transaction": tx_field,
        "document": document_field,
        "product": product_field,
        "productId": product_id_field,
        "unit": unit_field,
        "stores": store_fields,
        "accounts": account_fields,
        "aggregates": aggregates,
    }


def _discover(base_url, token, period, fields, names, scope):
    group_fields = []
    for field in [names.get("transaction"), *names["stores"], *names["accounts"], names.get("document")]:
        if field and field not in group_fields and _allowed(fields, field, "groupingAllowed"):
            group_fields.append(field)

    body = {
        "reportType": "TRANSACTIONS",
        "buildSummary": False,
        "groupByRowFields": group_fields,
        "groupByColFields": [],
        "aggregateFields": [names["aggregates"][0]],
        "filters": _date_filter(names["date"], period),
    }
    rows = _olap_post(base_url, token, body, timeout=70)

    tx_values, store_values, account_values, document_values = [], [], [], []
    store_field_values = defaultdict(list)
    marker_docs = []
    scope_store_values = defaultdict(list)

    for row in rows:
        if not isinstance(row, dict):
            continue
        if names.get("transaction"):
            value = str(row.get(names["transaction"]) or "").strip()
            if value and value not in tx_values:
                tx_values.append(value)
        for field in names["stores"]:
            value = str(row.get(field) or "").strip()
            if value:
                if value not in store_values:
                    store_values.append(value)
                if value not in store_field_values[field]:
                    store_field_values[field].append(value)
                if _store_matches(scope, value) and value not in scope_store_values[field]:
                    scope_store_values[field].append(value)
        for field in names["accounts"]:
            value = str(row.get(field) or "").strip()
            if value and value not in account_values:
                account_values.append(value)
        if names.get("document"):
            value = str(row.get(names["document"]) or "").strip()
            if value and value not in document_values:
                document_values.append(value)
            if value and _marker(value) and value not in marker_docs:
                marker_docs.append(value)

    primary_store_field = None
    primary_store_values = []
    for field in names["stores"]:
        values = scope_store_values.get(field) or []
        if values:
            primary_store_field = field
            primary_store_values = values
            break

    return {
        "transactionValues": tx_values[:80],
        "storeValues": store_values[:80],
        "accountValues": account_values[:80],
        "documentValues": document_values[:80],
        "markerDocuments": marker_docs[:40],
        "discoveryRows": len(rows),
        "primaryStoreField": primary_store_field,
        "primaryStoreValues": primary_store_values,
    }


def _query_rows(base_url, token, period, fields, names, diagnostics):
    group_fields = []
    for field in [
        names["date"],
        names.get("transaction"),
        *names["stores"],
        *names["accounts"],
        names.get("document"),
        names["product"],
        names.get("productId"),
        names.get("unit"),
    ]:
        if field and field not in group_fields and _allowed(fields, field, "groupingAllowed"):
            group_fields.append(field)

    filters = _date_filter(names["date"], period)
    store_field = diagnostics.get("primaryStoreField")
    store_values = diagnostics.get("primaryStoreValues") or []
    if store_field and store_values and _allowed(fields, store_field, "filteringAllowed"):
        filters[store_field] = {"filterType": "IncludeValues", "values": store_values}

    body = {
        "reportType": "TRANSACTIONS",
        "buildSummary": False,
        "groupByRowFields": group_fields,
        "groupByColFields": [],
        "aggregateFields": names["aggregates"],
        "filters": filters,
    }
    try:
        return _olap_post(base_url, token, body, timeout=100)
    except RuntimeError:
        # Some iiko builds reject filtering by Store-like fields. Date-only fallback is safe.
        body["filters"] = _date_filter(names["date"], period)
        return _olap_post(base_url, token, body, timeout=100)


def _row_store(scope, row, fields):
    for field in fields:
        value = str(row.get(field) or "").strip()
        if value and _store_matches(scope, value):
            return value
    return None


def _looks_like_inventory(scope, row, names):
    # 1) Strongest signal: inventory surplus/shortage accounts or inventory transaction/document labels.
    for field in [names.get("transaction"), *names["accounts"], names.get("document")]:
        if field and _marker(row.get(field)):
            return True

    # Do NOT classify a row as an inventory merely because its document number
    # looks like Arai####. Other Arai stock/accounting documents use the same
    # numbering style; this was the reason the dashboard invented revision dates
    # such as 19/20 September that do not exist in the iikoChain inventory list.
    # A real posted inventory must be confirmed by its transaction/account marker.
    return False


def _build(scope, period, rows, names, diagnostics):
    revisions = defaultdict(lambda: {"shortage": 0.0, "surplus": 0.0, "stores": set(), "documents": set()})
    products = defaultdict(lambda: {"name": None, "unit": None, "shortage": 0.0, "surplus": 0.0, "shortageDates": set(), "surplusDates": set()})
    matched_rows = 0
    matched_stores = set()
    matched_documents = set()

    for row in rows:
        if not isinstance(row, dict):
            continue
        store = _row_store(scope, row, names["stores"])
        if not store or not _looks_like_inventory(scope, row, names):
            continue

        matched_rows += 1
        matched_stores.add(store)
        date_value = str(row.get(names["date"]) or "")[:10] or "Без даты"
        document = str(row.get(names.get("document")) or "").strip() if names.get("document") else ""
        if document:
            matched_documents.add(document)

        item = revisions[date_value]
        item["stores"].add(store)
        if document:
            item["documents"].add(document)

        product_name = str(row.get(names["product"]) or "Позиция без названия").strip()
        product_id = str(row.get(names.get("productId")) or "").strip() if names.get("productId") else ""
        key = product_id or product_name
        products[key]["name"] = product_name
        if names.get("unit"):
            unit = str(row.get(names["unit"]) or "").strip()
            if unit:
                products[key]["unit"] = unit

        amount_in = abs(_num(row.get("Amount.In")))
        amount_out = abs(_num(row.get("Amount.Out")))
        signed_amount = _num(row.get("Amount.StoreInOutTyped"))
        if not amount_in and not amount_out and signed_amount:
            if signed_amount > 0:
                amount_in = signed_amount
            else:
                amount_out = abs(signed_amount)

        avg_cost = abs(_num(row.get("Product.AvgSum")))
        sum_in = abs(_num(row.get("Sum.Incoming")))
        sum_out = abs(_num(row.get("Sum.Outgoing")))
        if not sum_in and amount_in and avg_cost:
            sum_in = amount_in * avg_cost
        if not sum_out and amount_out and avg_cost:
            sum_out = amount_out * avg_cost

        item["surplus"] += sum_in
        item["shortage"] += sum_out
        products[key]["surplus"] += sum_in
        products[key]["shortage"] += sum_out
        if sum_out > 0.005:
            products[key]["shortageDates"].add(date_value)
        if sum_in > 0.005:
            products[key]["surplusDates"].add(date_value)

    history = []
    for date_value, item in sorted(revisions.items(), reverse=True):
        shortage = round(item["shortage"], 2)
        surplus = round(item["surplus"], 2)
        history.append({
            "date": date_value,
            "shortage": shortage,
            "surplus": surplus,
            "net": round(surplus - shortage, 2),
            "stores": sorted(item["stores"]),
            "documents": sorted(item["documents"]),
        })

    product_rows = []
    for item in products.values():
        product_rows.append({
            "name": item["name"] or "Позиция без названия",
            "unit": item["unit"],
            "shortage": round(item["shortage"], 2),
            "surplus": round(item["surplus"], 2),
            "shortageRevisionCount": len(item["shortageDates"]),
            "surplusRevisionCount": len(item["surplusDates"]),
        })

    top_shortages = sorted((x for x in product_rows if x["shortage"] > 0), key=lambda x: x["shortage"], reverse=True)[:10]
    top_surpluses = sorted((x for x in product_rows if x["surplus"] > 0), key=lambda x: x["surplus"], reverse=True)[:10]
    recurring = sorted(
        (x for x in product_rows if x["shortageRevisionCount"] >= 2),
        key=lambda x: (x["shortageRevisionCount"], x["shortage"]),
        reverse=True,
    )[:10]

    total_shortage = round(sum(x["shortage"] for x in history), 2)
    total_surplus = round(sum(x["surplus"] for x in history), 2)
    diagnostics = dict(diagnostics)
    diagnostics["matchedDocuments"] = sorted(matched_documents)[:80]

    return {
        "success": True,
        "scope": scope,
        "scopeLabel": SCOPES[scope]["label"],
        "period": period,
        "source": "iikoServer TRANSACTIONS OLAP / inventory-account detection",
        "matchedRows": matched_rows,
        "stores": sorted(matched_stores),
        "summary": {
            "lastRevision": history[0]["date"] if history else None,
            "revisionsCount": len(history),
            "shortage": total_shortage,
            "surplus": total_surplus,
            "net": round(total_surplus - total_shortage, 2),
        },
        "history": history,
        "topShortages": top_shortages,
        "topSurpluses": top_surpluses,
        "recurringShortages": recurring,
        "discrepancyPercent": None,
        "diagnostics": diagnostics,
        "note": "Инвентаризации определяются по складу, документу и счетам недостач/излишков. Процент расхождения добавим после получения полного книжного остатка.",
    }


def install_revisions_data_v2(app):
    if getattr(app, "_doner_revisions_data_v2_installed", False):
        return
    app._doner_revisions_data_v2_installed = True

    @app.route("/revision-data", methods=["GET"], endpoint="revision_data_v2")
    def revision_data_v2():
        scope = (request.args.get("scope") or "arai").strip().lower()
        period = (request.args.get("period") or "").strip()
        if scope not in SCOPES:
            return jsonify({"success": False, "message": "Unknown revision scope"}), 400
        try:
            datetime.strptime(period, "%Y-%m")
        except ValueError:
            return jsonify({"success": False, "message": "Period must be YYYY-MM"}), 400

        base_url = token = None
        try:
            base_url, token = _auth()
            fields = _get_fields(base_url, token)
            names = _resolve(fields)
            diagnostics = _discover(base_url, token, period, fields, names, scope)
            rows = _query_rows(base_url, token, period, fields, names, diagnostics)
            result = _build(scope, period, rows, names, diagnostics)
            result["fieldMap"] = names
            return jsonify(result)
        except Exception as error:
            return jsonify({
                "success": False,
                "scope": scope,
                "period": period,
                "message": "Не удалось получить данные инвентаризации из iikoServer",
                "details": str(error),
            }), 502
        finally:
            if base_url and token:
                _logout(base_url, token)
