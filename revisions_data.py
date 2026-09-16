import hashlib
import os
from collections import defaultdict
from datetime import datetime

import requests
from flask import jsonify, request


SCOPES = {
    "arai": {
        "label": "Арай",
        "store_needles": ("арай",),
        "store_excludes": ("цех",),
    },
    "workshop": {
        "label": "Цех",
        "store_needles": ("цех",),
        "store_excludes": (),
    },
}

INVENTORY_MARKERS = (
    "invtr",
    "inventory",
    "invent",
    "reconciliation",
    "инвентар",
    "ревиз",
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
            key: value for key, value in candidate.items()
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


def _allowed(field_map, name, capability):
    info = field_map.get(name)
    if not info:
        return False
    return info.get(capability) is not False


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


def _store_matches(scope_key, store):
    config = SCOPES[scope_key]
    text = str(store or "").strip().lower()
    if not text:
        return False
    if config["store_needles"] and not any(needle in text for needle in config["store_needles"]):
        return False
    if any(needle in text for needle in config["store_excludes"]):
        return False
    return True


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


def _inventory_label(value):
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


def _olap_post(base_url, token, body, timeout=75):
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


def _get_transaction_fields(base_url, token):
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


def _resolve_fields(fields):
    available = set(fields)

    date_field = _pick(
        available,
        "DateTime.DateTyped",
        "DateSecondary.DateTyped",
    ) or _pick_like(available, ("date", "typed"))

    tx_field = _pick(
        available,
        "TransactionType.Code",
        "TransactionType",
        "TransactionType.Name",
    ) or _pick_like(available, ("transactiontype",))

    store_candidates = []
    for name in (
        "Store",
        "Store.Name",
        "Account.StoreOrAccount",
        "Account.StoreOrAccount.Name",
        "Store.Id",
    ):
        if name in available and _allowed(fields, name, "groupingAllowed") and name not in store_candidates:
            store_candidates.append(name)
    for name in sorted(available):
        low = name.lower()
        if "store" in low and _allowed(fields, name, "groupingAllowed") and name not in store_candidates:
            store_candidates.append(name)
        if len(store_candidates) >= 3:
            break

    document_field = _pick(
        available,
        "Document",
        "Document.Number",
        "Document.Num",
    ) or _pick_like(available, ("document",), ("date",))

    product_field = _pick(
        available,
        "Product.Name",
        "Contr-Product.Name",
    ) or _pick_like(available, ("product", "name"))

    product_id_field = _pick(
        available,
        "Product.Id",
        "Contr-Product.Id",
    ) or _pick_like(available, ("product", "id"))

    unit_field = _pick(
        available,
        "Product.MeasureUnit",
        "Contr-Product.MeasureUnit",
    ) or _pick_like(available, ("product", "measure"))

    aggregate_candidates = (
        "Amount.In",
        "Amount.Out",
        "Amount.StoreInOutTyped",
        "Sum.Incoming",
        "Sum.Outgoing",
        "Product.AvgSum",
        "Contr-Amount",
    )
    aggregate_fields = [
        name for name in aggregate_candidates
        if name in available and _allowed(fields, name, "aggregationAllowed")
    ]

    missing = []
    if not date_field:
        missing.append("date")
    if not tx_field:
        missing.append("transaction type")
    if not store_candidates:
        missing.append("store")
    if not product_field:
        missing.append("product")
    if not aggregate_fields:
        missing.append("amount/sum")
    if missing:
        raise RuntimeError("В TRANSACTIONS OLAP не найдены обязательные поля: " + ", ".join(missing))

    return {
        "date": date_field,
        "transaction": tx_field,
        "stores": store_candidates,
        "document": document_field,
        "product": product_field,
        "productId": product_id_field,
        "unit": unit_field,
        "aggregates": aggregate_fields,
    }


def _discover_inventory_values(base_url, token, period, fields, names):
    group_fields = []
    for field in [names["transaction"], *names["stores"], names.get("document")]:
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
    rows = _olap_post(base_url, token, body, timeout=60)

    tx_values = []
    all_tx_values = []
    all_store_values = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        tx = str(row.get(names["transaction"]) or "").strip()
        if tx and tx not in all_tx_values:
            all_tx_values.append(tx)
        if tx and _inventory_label(tx) and tx not in tx_values:
            tx_values.append(tx)
        for store_field in names["stores"]:
            store = str(row.get(store_field) or "").strip()
            if store and store not in all_store_values:
                all_store_values.append(store)

    return {
        "inventoryTransactionValues": tx_values,
        "transactionValues": all_tx_values[:80],
        "storeValues": all_store_values[:80],
        "discoveryRows": len(rows),
    }


def _query_inventory_transactions(base_url, token, period, fields, names, inventory_values):
    group_fields = []
    for field in [
        names["date"],
        names["transaction"],
        *names["stores"],
        names.get("document"),
        names["product"],
        names.get("productId"),
        names.get("unit"),
    ]:
        if field and field not in group_fields and _allowed(fields, field, "groupingAllowed"):
            group_fields.append(field)

    filters = _date_filter(names["date"], period)
    if inventory_values and _allowed(fields, names["transaction"], "filteringAllowed"):
        filters[names["transaction"]] = {
            "filterType": "IncludeValues",
            "values": inventory_values,
        }

    body = {
        "reportType": "TRANSACTIONS",
        "buildSummary": False,
        "groupByRowFields": group_fields,
        "groupByColFields": [],
        "aggregateFields": names["aggregates"],
        "filters": filters,
    }

    try:
        rows = _olap_post(base_url, token, body, timeout=90)
    except RuntimeError:
        if names["transaction"] in filters:
            body["filters"] = _date_filter(names["date"], period)
            rows = _olap_post(base_url, token, body, timeout=90)
        else:
            raise
    return rows


def _row_inventory(row, tx_field, inventory_values):
    value = str(row.get(tx_field) or "").strip()
    if inventory_values:
        return value in inventory_values
    return _inventory_label(value)


def _row_store(scope_key, row, store_fields):
    values = []
    for field in store_fields:
        value = str(row.get(field) or "").strip()
        if value:
            values.append(value)
    for value in values:
        if _store_matches(scope_key, value):
            return value
    return None


def _build_result(scope_key, period, rows, names, diagnostics):
    tx_field = names["transaction"]
    date_field = names["date"]
    document_field = names.get("document")
    product_field = names["product"]
    product_id_field = names.get("productId")
    unit_field = names.get("unit")
    inventory_values = diagnostics.get("inventoryTransactionValues") or []

    revisions = defaultdict(lambda: {"shortage": 0.0, "surplus": 0.0, "stores": set(), "documents": set()})
    products = defaultdict(lambda: {"shortage": 0.0, "surplus": 0.0, "shortageRevisions": set(), "surplusRevisions": set(), "unit": None})
    matched_rows = 0
    matched_stores = set()

    for row in rows:
        if not isinstance(row, dict) or not _row_inventory(row, tx_field, inventory_values):
            continue
        store = _row_store(scope_key, row, names["stores"])
        if not store:
            continue

        matched_rows += 1
        matched_stores.add(store)
        date_value = str(row.get(date_field) or "")[:10] or "Без даты"
        document = str(row.get(document_field) or "").strip() if document_field else ""
        revision_key = date_value
        if document:
            revisions[revision_key]["documents"].add(document)
        revisions[revision_key]["stores"].add(store)

        product = str(row.get(product_field) or "Позиция без названия").strip()
        product_id = str(row.get(product_id_field) or "").strip() if product_id_field else ""
        product_key = product_id or product
        unit = str(row.get(unit_field) or "").strip() if unit_field else ""
        if unit:
            products[product_key]["unit"] = unit
        products[product_key]["name"] = product

        amount_in = abs(_num(row.get("Amount.In")))
        amount_out = abs(_num(row.get("Amount.Out")))
        signed_amount = _num(row.get("Amount.StoreInOutTyped"))
        if amount_in == 0 and amount_out == 0 and signed_amount:
            if signed_amount > 0:
                amount_in = signed_amount
            else:
                amount_out = abs(signed_amount)

        avg_cost = abs(_num(row.get("Product.AvgSum")))
        sum_in = abs(_num(row.get("Sum.Incoming")))
        sum_out = abs(_num(row.get("Sum.Outgoing")))
        if sum_in == 0 and amount_in and avg_cost:
            sum_in = amount_in * avg_cost
        if sum_out == 0 and amount_out and avg_cost:
            sum_out = amount_out * avg_cost

        revisions[revision_key]["surplus"] += sum_in
        revisions[revision_key]["shortage"] += sum_out
        products[product_key]["surplus"] += sum_in
        products[product_key]["shortage"] += sum_out
        if sum_out > 0.005:
            products[product_key]["shortageRevisions"].add(revision_key)
        if sum_in > 0.005:
            products[product_key]["surplusRevisions"].add(revision_key)

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
            "name": item.get("name") or "Позиция без названия",
            "unit": item.get("unit"),
            "shortage": round(item["shortage"], 2),
            "surplus": round(item["surplus"], 2),
            "shortageRevisionCount": len(item["shortageRevisions"]),
            "surplusRevisionCount": len(item["surplusRevisions"]),
        })

    top_shortages = sorted(
        (x for x in product_rows if x["shortage"] > 0),
        key=lambda x: x["shortage"],
        reverse=True,
    )[:10]
    top_surpluses = sorted(
        (x for x in product_rows if x["surplus"] > 0),
        key=lambda x: x["surplus"],
        reverse=True,
    )[:10]
    recurring = sorted(
        (x for x in product_rows if x["shortageRevisionCount"] >= 2),
        key=lambda x: (x["shortageRevisionCount"], x["shortage"]),
        reverse=True,
    )[:10]

    total_shortage = round(sum(item["shortage"] for item in history), 2)
    total_surplus = round(sum(item["surplus"] for item in history), 2)
    return {
        "success": True,
        "scope": scope_key,
        "scopeLabel": SCOPES[scope_key]["label"],
        "period": period,
        "source": "iikoServer TRANSACTIONS OLAP / inventory reconciliation",
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
        "note": "Процент расхождения пока не считается: для него нужен полный книжный остаток на момент каждой инвентаризации.",
    }


def install_revisions_data(app):
    if getattr(app, "_doner_revisions_data_installed", False):
        return
    app._doner_revisions_data_installed = True

    @app.route("/revision-data", methods=["GET"], endpoint="revision_data")
    def revision_data():
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
            fields = _get_transaction_fields(base_url, token)
            names = _resolve_fields(fields)
            diagnostics = _discover_inventory_values(base_url, token, period, fields, names)
            rows = _query_inventory_transactions(
                base_url,
                token,
                period,
                fields,
                names,
                diagnostics.get("inventoryTransactionValues") or [],
            )
            result = _build_result(scope, period, rows, names, diagnostics)
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
