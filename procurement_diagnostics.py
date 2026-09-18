import re
import time
from datetime import datetime, timedelta

import requests

import app as core
from flask import jsonify, request
from revisions_data_v2 import _allowed, _field_map


SUPPLIER_TOKENS = (
    "supplier", "vendor", "provider", "counteragent", "contractor", "contragent",
    "постав", "контрагент",
)
PURCHASE_TOKENS = (
    "supplier", "purchase", "incoming", "receipt", "invoice", "arrival",
    "постав", "закуп", "приход", "наклад", "поступ",
)


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def _num(value):
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _pick(fields, names, capability="groupingAllowed"):
    for name in names:
        if name in fields and _allowed(fields, name, capability):
            return name
    return None


def _field_candidates(fields, tokens, capability="groupingAllowed"):
    result = []
    for name in sorted(fields):
        low = name.lower()
        if any(token in low for token in tokens) and _allowed(fields, name, capability):
            result.append(name)
    return result


def _date_filter(field, date_from, date_to):
    return {
        field: {
            "filterType": "DateRange",
            "periodType": "CUSTOM",
            "from": date_from,
            "to": date_to,
            "includeLow": True,
            "includeHigh": True,
        }
    }


def _olap(base_url, token, group_fields, aggregate_fields, filters, timeout=90, retries=1):
    body = {
        "reportType": "TRANSACTIONS",
        "buildSummary": False,
        "groupByRowFields": group_fields,
        "groupByColFields": [],
        "aggregateFields": aggregate_fields,
        "filters": filters,
    }
    last_error = None
    for attempt in range(max(1, retries + 1)):
        try:
            response = requests.post(
                f"{base_url}/api/v2/reports/olap",
                params={"key": token},
                json=body,
                timeout=timeout,
            )
            if not response.ok:
                message = f"TRANSACTIONS OLAP HTTP {response.status_code}: {response.text[:500]}"
                if response.status_code in {502, 503, 504} and attempt < retries:
                    last_error = RuntimeError(message)
                    time.sleep(0.7 * (attempt + 1))
                    continue
                raise RuntimeError(message)
            payload = response.json()
            rows = payload.get("data", payload if isinstance(payload, list) else [])
            return rows if isinstance(rows, list) else []
        except (requests.Timeout, requests.ConnectionError) as error:
            last_error = error
            if attempt >= retries:
                raise
            time.sleep(0.7 * (attempt + 1))
    if last_error:
        raise last_error
    return []


def _date_chunks(date_from, date_to, chunk_days=90):
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    finish = datetime.strptime(date_to, "%Y-%m-%d").date()
    while start <= finish:
        end = min(finish, start + timedelta(days=max(1, chunk_days) - 1))
        yield start.isoformat(), end.isoformat()
        start = end + timedelta(days=1)


def _query_rows_chunked(
    base_url,
    token,
    group_fields,
    aggregate_fields,
    date_field,
    date_from,
    date_to,
    extra_filters=None,
    chunk_days=90,
    timeout=55,
):
    rows = []
    for chunk_from, chunk_to in _date_chunks(date_from, date_to, chunk_days):
        filters = _date_filter(date_field, chunk_from, chunk_to)
        if extra_filters:
            filters.update(extra_filters)
        rows.extend(
            _olap(
                base_url,
                token,
                group_fields,
                aggregate_fields,
                filters,
                timeout=timeout,
                retries=1,
            )
        )
    return rows


def _get_transaction_fields(base_url, token):
    response = requests.get(
        f"{base_url}/api/v2/reports/olap/columns",
        params={"key": token, "reportType": "TRANSACTIONS"},
        timeout=30,
    )
    response.raise_for_status()
    fields = _field_map(response.json())
    if not fields:
        raise RuntimeError("iikoServer did not return TRANSACTIONS OLAP columns")
    return fields


def _purchase_marker(row, inspect_fields):
    text = " | ".join(_norm(row.get(field)).lower() for field in inspect_fields if row.get(field))
    return any(token in text for token in PURCHASE_TOKENS)


def _supplier_name_field(fields):
    preferred = (
        "Counteragent.Name",
        "Supplier.Name",
        "Provider.Name",
        "Vendor.Name",
        "Contractor.Name",
        "Contr-Counteragent.Name",
        "Counteragent",
        "Supplier",
    )
    direct = _pick(fields, preferred)
    if direct:
        return direct
    candidates = []
    for name in sorted(fields):
        low = name.lower()
        if (
            any(token in low for token in ("counteragent", "supplier", "vendor", "provider", "contractor", "contragent"))
            and "name" in low
            and "type" not in low
            and "id" not in low
            and _allowed(fields, name, "groupingAllowed")
        ):
            score = 0
            if "counteragent" in low:
                score += 5
            if low.endswith(".name"):
                score += 3
            if "account" in low:
                score -= 2
            candidates.append((score, name))
    return sorted(candidates, reverse=True)[0][1] if candidates else None


def _supplier_type_field(fields):
    return _pick(fields, (
        "Account.CounteragentType",
        "Counteragent.Type",
        "CounteragentType",
        "Supplier.Type",
    ))


def _supplier_id_field(fields):
    return _pick(fields, (
        "Counteragent.Id",
        "Supplier.Id",
        "Provider.Id",
        "Vendor.Id",
        "Contractor.Id",
        "Contr-Counteragent.Id",
    ))


def _supplier_type_ok(value):
    text = _norm(value).upper()
    if not text:
        return True
    return text in {"SUPPLIER", "INTERNAL_SUPPLIER"} or "SUPPLIER" in text


def _valid_supplier_name(value):
    text = _norm(value)
    if not text:
        return False
    upper = text.upper()
    if upper in {"NONE", "SUPPLIER", "INTERNAL_SUPPLIER", "EMPLOYEE", "UNKNOWN", "NULL"}:
        return False
    if re.fullmatch(r"[0-9a-fA-F-]{24,}", text):
        return False
    return True


def _supplier_name_key(value):
    text = _norm(value).casefold().replace("ё", "е")
    text = re.sub(r"\b(тоо|ооо|ип|too|llp|ltd|inc|ao|ао)\b", " ", text, flags=re.IGNORECASE)
    return re.sub(r"[^0-9a-zа-я]+", "", text, flags=re.IGNORECASE)


def _supplier_alias_match(candidate, target):
    left = _supplier_name_key(candidate)
    right = _supplier_name_key(target)
    if not left or not right:
        return False
    if left == right:
        return True
    if min(len(left), len(right)) >= 5 and (left in right or right in left):
        return True
    return False


def _supplier_rollup(rows, date_field, document_field, product_field, unit_field, supplier_name_field, supplier_type_field, supplier_id_field=None):
    suppliers = {}
    for row in rows:
        supplier_type = _norm(row.get(supplier_type_field)) if supplier_type_field else ""
        supplier_name = _norm(row.get(supplier_name_field)) if supplier_name_field else ""
        supplier_id = _norm(row.get(supplier_id_field)) if supplier_id_field else ""
        if not _supplier_type_ok(supplier_type) or not _valid_supplier_name(supplier_name):
            continue

        amount = abs(_num(row.get("Amount.In")))
        incoming_sum = abs(_num(row.get("Sum.Incoming")))
        avg_sum = abs(_num(row.get("Product.AvgSum")))
        if amount <= 0 and incoming_sum <= 0:
            continue
        unit_price = incoming_sum / amount if amount and incoming_sum else avg_sum
        if unit_price <= 0:
            continue

        date_value = _norm(row.get(date_field))[:10]
        product_name = _norm(row.get(product_field)) if product_field else ""
        if not date_value or not product_name:
            continue
        unit = _norm(row.get(unit_field)) if unit_field else ""
        document = _norm(row.get(document_field)) if document_field else ""

        supplier_key = supplier_id or supplier_name.casefold()
        supplier = suppliers.setdefault(supplier_key, {
            "id": supplier_id,
            "name": supplier_name,
            "type": supplier_type or "SUPPLIER",
            "totalSpend": 0.0,
            "totalQuantity": 0.0,
            "documents": set(),
            "lastDelivery": "",
            "products": {},
        })
        if supplier_name and (not supplier.get("name") or len(supplier_name) > len(supplier.get("name") or "")):
            supplier["name"] = supplier_name
        if supplier_id and not supplier.get("id"):
            supplier["id"] = supplier_id
        supplier["totalSpend"] += incoming_sum
        supplier["totalQuantity"] += amount
        if document:
            supplier["documents"].add(f"{date_value}|{document}")
        if date_value > supplier["lastDelivery"]:
            supplier["lastDelivery"] = date_value

        product = supplier["products"].setdefault(product_name, {
            "name": product_name,
            "unit": unit,
            "totalSpend": 0.0,
            "totalQuantity": 0.0,
            "history": {},
        })
        product["totalSpend"] += incoming_sum
        product["totalQuantity"] += amount
        if unit and not product["unit"]:
            product["unit"] = unit
        day = product["history"].setdefault(date_value, {"sum": 0.0, "quantity": 0.0, "fallback": [], "documents": set()})
        day["sum"] += incoming_sum
        day["quantity"] += amount
        if document:
            day["documents"].add(document)
        if unit_price:
            day["fallback"].append(unit_price)

    result = []
    for supplier in suppliers.values():
        products = []
        for product in supplier["products"].values():
            history = []
            for date_value, values in sorted(product["history"].items()):
                price = values["sum"] / values["quantity"] if values["quantity"] and values["sum"] else (
                    sum(values["fallback"]) / len(values["fallback"]) if values["fallback"] else 0
                )
                if price <= 0:
                    continue
                history.append({
                    "date": date_value,
                    "price": round(price, 2),
                    "quantity": round(values["quantity"], 4),
                    "sum": round(values["sum"], 2),
                    "documents": sorted(values.get("documents") or []),
                })
            if not history:
                continue
            current = history[-1]
            previous = history[-2] if len(history) > 1 else None
            change = None
            change_pct = None
            if previous and previous["price"]:
                change = round(current["price"] - previous["price"], 2)
                change_pct = round(change / previous["price"] * 100, 2)
            prices = [x["price"] for x in history]
            products.append({
                "name": product["name"],
                "unit": product["unit"],
                "totalSpend": round(product["totalSpend"], 2),
                "totalQuantity": round(product["totalQuantity"], 4),
                "currentPrice": current["price"],
                "previousPrice": previous["price"] if previous else None,
                "change": change,
                "changePct": change_pct,
                "lastDate": current["date"],
                "minPrice": min(prices),
                "maxPrice": max(prices),
                "history": history,
            })
        products.sort(key=lambda item: (-item["totalSpend"], item["name"].lower()))
        if not products:
            continue
        result.append({
            "name": supplier["name"],
            "type": supplier["type"],
            "totalSpend": round(supplier["totalSpend"], 2),
            "totalQuantity": round(supplier["totalQuantity"], 4),
            "deliveries": len(supplier["documents"]),
            "lastDelivery": supplier["lastDelivery"],
            "productsCount": len(products),
            "products": products,
        })
    result.sort(key=lambda item: (-item["totalSpend"], item["name"].lower()))
    return result


def build_procurement_diagnostics(days=180):
    days = max(30, min(int(days or 180), 730))
    today = datetime.now(core.LOCAL_TZ).date()
    date_from = (today - timedelta(days=days)).isoformat()
    date_to = today.isoformat()

    base_url = token = None
    try:
        base_url, token = core.iiko_server_auth()
        fields = _get_transaction_fields(base_url, token)

        date_field = _pick(fields, (
            "DateTime.DateTyped",
            "DateSecondary.DateTyped",
            "DateTime.Typed",
            "DateSecondary.DateTimeTyped",
        ))
        if not date_field:
            date_field = next(
                (name for name in sorted(fields)
                 if "date" in name.lower() and "typed" in name.lower() and _allowed(fields, name, "groupingAllowed")),
                None,
            )
        if not date_field:
            raise RuntimeError("No usable transaction date field found")

        tx_field = _pick(fields, ("TransactionType.Code", "TransactionType", "TransactionType.Name"))
        document_field = _pick(fields, ("Document", "Document.Number", "Document.Num"))
        supplier_name_field = _supplier_name_field(fields)
        supplier_type_field = _supplier_type_field(fields)
        supplier_id_field = _supplier_id_field(fields)
        product_field = _pick(fields, ("Product.Name", "Contr-Product.Name"))
        unit_field = _pick(fields, ("Product.MeasureUnit", "Contr-Product.MeasureUnit"))

        if not supplier_name_field or not product_field:
            raise RuntimeError("iikoServer does not expose supplier/product fields required for procurement analytics")

        aggregate_fields = [
            name for name in ("Amount.In", "Sum.Incoming", "Product.AvgSum", "Amount.StoreInOutTyped")
            if name in fields and _allowed(fields, name, "aggregationAllowed")
        ]
        if not aggregate_fields:
            raise RuntimeError("No incoming amount/cost aggregates found in TRANSACTIONS")

        detail_groups = []
        for name in [
            date_field,
            tx_field,
            document_field,
            supplier_name_field,
            supplier_type_field,
            supplier_id_field,
            product_field,
            unit_field,
        ]:
            if name and name not in detail_groups and _allowed(fields, name, "groupingAllowed"):
                detail_groups.append(name)

        detail_rows = _query_rows_chunked(
            base_url,
            token,
            detail_groups,
            aggregate_fields,
            date_field,
            date_from,
            date_to,
            chunk_days=60 if days > 90 else 90,
            timeout=55,
        )

        supplier_rollup = _supplier_rollup(
            detail_rows,
            date_field,
            document_field,
            product_field,
            unit_field,
            supplier_name_field,
            supplier_type_field,
            supplier_id_field,
        )

        tx_values = []
        supplier_names = []
        supplier_types = []
        positive_incoming_rows = 0
        marker_rows = 0
        price_evidence = []

        inspect_fields = [field for field in (tx_field, document_field, supplier_name_field, supplier_type_field) if field]
        for row in detail_rows:
            if tx_field:
                value = _norm(row.get(tx_field))
                if value and value not in tx_values and len(tx_values) < 80:
                    tx_values.append(value)

            name = _norm(row.get(supplier_name_field))
            if name and name not in supplier_names and len(supplier_names) < 80:
                supplier_names.append(name)
            if supplier_type_field:
                stype = _norm(row.get(supplier_type_field))
                if stype and stype not in supplier_types:
                    supplier_types.append(stype)

            if _purchase_marker(row, inspect_fields):
                marker_rows += 1

            amount = abs(_num(row.get("Amount.In")))
            incoming_sum = abs(_num(row.get("Sum.Incoming")))
            avg_sum = abs(_num(row.get("Product.AvgSum")))
            if amount > 0 or incoming_sum > 0:
                positive_incoming_rows += 1

            unit_price = incoming_sum / amount if amount and incoming_sum else avg_sum
            if unit_price > 0 and len(price_evidence) < 12:
                supplier_type = _norm(row.get(supplier_type_field)) if supplier_type_field else ""
                if not supplier_type_field or _supplier_type_ok(supplier_type):
                    price_evidence.append({
                        "date": _norm(row.get(date_field))[:10],
                        "document": _norm(row.get(document_field)) if document_field else "",
                        "supplier": name,
                        "supplierType": supplier_type,
                        "supplierField": supplier_name_field,
                        "product": _norm(row.get(product_field)),
                        "unit": _norm(row.get(unit_field)) if unit_field else "",
                        "quantity": round(amount, 4),
                        "sum": round(incoming_sum, 2),
                        "unitPrice": round(unit_price, 4),
                        "transaction": _norm(row.get(tx_field)) if tx_field else "",
                    })

        supplier_values = {supplier_name_field: supplier_names}
        if supplier_type_field:
            supplier_values[supplier_type_field] = supplier_types

        return {
            "success": True,
            "period": {"from": date_from, "to": date_to, "days": days},
            "fieldSupport": {
                "date": date_field,
                "transaction": tx_field,
                "document": document_field,
                "product": product_field,
                "unit": unit_field,
                "supplierNamedFields": [supplier_name_field],
                "supplierNameField": supplier_name_field,
                "supplierTypeField": supplier_type_field,
                "supplierIdField": supplier_id_field,
                "counterpartyFallbackFields": [],
                "incomingAggregates": aggregate_fields,
            },
            "evidence": {
                "discoveryRows": len(detail_rows),
                "purchaseMarkerRows": marker_rows,
                "positiveIncomingRows": positive_incoming_rows,
                "supplierValues": supplier_values,
                "transactionValues": tx_values[:50],
                "priceRowsFound": len(price_evidence),
                "priceSamples": price_evidence,
                "suppliers": supplier_rollup,
                "suppliersCount": len(supplier_rollup),
            },
            "capability": {
                "canBuildSupplierList": bool(supplier_rollup),
                "canBuildPurchasePriceHistory": any(
                    len(product.get("history") or []) > 1
                    for supplier in supplier_rollup
                    for product in supplier.get("products") or []
                ),
                "canBuildProductSupplierMatrix": bool(supplier_rollup),
            },
            "note": "Read-only procurement analytics built from incoming iiko transaction rows.",
        }
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def diagnostics_text(result):
    support = result.get("fieldSupport") or {}
    evidence = result.get("evidence") or {}
    capability = result.get("capability") or {}
    lines = [
        "🔎 <b>ПРОВЕРКА ЗАКУПОК / ПОСТАВЩИКОВ</b>",
        f"Период: <b>{result['period']['from']} — {result['period']['to']}</b>",
        "",
        f"Поставщики: <b>{'есть данные' if capability.get('canBuildSupplierList') else 'явных данных пока не найдено'}</b>",
        f"История закупочных цен: <b>{'можно строить' if capability.get('canBuildPurchasePriceHistory') else 'пока не подтверждена'}</b>",
        f"Матрица товар → поставщик: <b>{'можно строить' if capability.get('canBuildProductSupplierMatrix') else 'пока не подтверждена'}</b>",
        "",
        f"Строк TRANSACTIONS: {evidence.get('discoveryRows', 0)}",
        f"Строк с приходом: {evidence.get('positiveIncomingRows', 0)}",
        f"Ценовых примеров найдено: {evidence.get('priceRowsFound', 0)}",
    ]
    supplier_fields = support.get("supplierNamedFields") or []
    fallback_fields = support.get("counterpartyFallbackFields") or []
    if supplier_fields:
        lines.append("Поля поставщика: " + ", ".join(supplier_fields[:5]))
    elif fallback_fields:
        lines.append("Поля-кандидаты контрагента: " + ", ".join(fallback_fields[:5]))

    samples = evidence.get("priceSamples") or []
    if samples:
        lines += ["", "<b>Примеры закупочных строк</b>"]
        for item in samples[:5]:
            supplier = item.get("supplier") or "контрагент не определён"
            product = item.get("product") or "товар"
            unit = item.get("unit") or "ед."
            lines.append(
                f"• {product} · {item.get('unitPrice', 0):,.2f} ₸/{unit} · {supplier} · {item.get('date') or 'без даты'}"
                .replace(",", " ")
            )
    return "\n".join(lines)



def build_supplier_history(supplier_name, days=30, supplier_id=""):
    supplier_name = _norm(supplier_name)
    supplier_id = _norm(supplier_id)
    if not supplier_id and not _valid_supplier_name(supplier_name):
        raise ValueError("supplier is required")

    days = max(30, min(int(days or 30), 730))
    today = datetime.now(core.LOCAL_TZ).date()
    date_from = (today - timedelta(days=days)).isoformat()
    date_to = today.isoformat()

    base_url = token = None
    try:
        base_url, token = core.iiko_server_auth()
        fields = _get_transaction_fields(base_url, token)

        date_candidates = []
        for name in (
            "DateSecondary.DateTyped",
            "DateTime.DateTyped",
            "DateSecondary.DateTimeTyped",
            "DateTime.Typed",
        ):
            if name in fields and _allowed(fields, name, "groupingAllowed") and name not in date_candidates:
                date_candidates.append(name)
        for name in sorted(fields):
            if (
                "date" in name.lower()
                and "typed" in name.lower()
                and _allowed(fields, name, "groupingAllowed")
                and name not in date_candidates
            ):
                date_candidates.append(name)
        if not date_candidates:
            raise RuntimeError("No usable transaction date field found")

        supplier_name_field = _supplier_name_field(fields)
        supplier_type_field = _supplier_type_field(fields)
        supplier_id_field = _supplier_id_field(fields)
        document_field = _pick(fields, ("Document", "Document.Number", "Document.Num"))
        product_field = _pick(fields, ("Product.Name", "Contr-Product.Name"))
        unit_field = _pick(fields, ("Product.MeasureUnit", "Contr-Product.MeasureUnit"))

        if not supplier_name_field or not product_field:
            raise RuntimeError("iikoServer does not expose enough supplier purchase fields")

        aggregate_fields = [
            name for name in ("Amount.In", "Sum.Incoming", "Product.AvgSum", "Amount.StoreInOutTyped")
            if name in fields and _allowed(fields, name, "aggregationAllowed")
        ]
        if not aggregate_fields:
            raise RuntimeError("No incoming amount/cost aggregates found in TRANSACTIONS")

        requested_start = datetime.strptime(date_from, "%Y-%m-%d").date()

        def discover_aliases(date_field):
            groups = []
            for name in [supplier_name_field, supplier_type_field, supplier_id_field]:
                if name and name not in groups and _allowed(fields, name, "groupingAllowed"):
                    groups.append(name)
            discovery_aggregate = next(
                (name for name in ("Amount.In", "Sum.Incoming", "Product.AvgSum") if name in aggregate_fields),
                aggregate_fields[0],
            )
            try:
                rows = _query_rows_chunked(
                    base_url,
                    token,
                    groups,
                    [discovery_aggregate],
                    date_field,
                    date_from,
                    date_to,
                    extra_filters=None,
                    chunk_days=180,
                    timeout=40,
                )
            except (RuntimeError, requests.Timeout, requests.ConnectionError):
                rows = _query_rows_chunked(
                    base_url,
                    token,
                    groups,
                    [discovery_aggregate],
                    date_field,
                    date_from,
                    date_to,
                    extra_filters=None,
                    chunk_days=90,
                    timeout=40,
                )

            aliases = {}
            for row in rows:
                name = _norm(row.get(supplier_name_field))
                stype = _norm(row.get(supplier_type_field)) if supplier_type_field else ""
                sid = _norm(row.get(supplier_id_field)) if supplier_id_field else ""
                if not _supplier_type_ok(stype) or not _valid_supplier_name(name):
                    continue
                if (supplier_id and sid == supplier_id) or _supplier_alias_match(name, supplier_name):
                    key = sid or name.casefold()
                    aliases[key] = {"id": sid, "name": name, "type": stype}
            if supplier_id or supplier_name:
                key = supplier_id or supplier_name.casefold()
                aliases.setdefault(key, {"id": supplier_id, "name": supplier_name, "type": ""})
            return list(aliases.values())

        def query_for_date_field(date_field):
            aliases = discover_aliases(date_field)
            alias_ids = sorted({x["id"] for x in aliases if x.get("id")})
            alias_names = sorted({x["name"] for x in aliases if x.get("name")})

            group_fields = []
            for name in [
                date_field,
                document_field,
                supplier_name_field,
                supplier_type_field,
                supplier_id_field,
                product_field,
                unit_field,
            ]:
                if name and name not in group_fields and _allowed(fields, name, "groupingAllowed"):
                    group_fields.append(name)

            extra_filter = None
            filter_mode = "none"
            if alias_ids and supplier_id_field and _allowed(fields, supplier_id_field, "filteringAllowed"):
                extra_filter = {
                    supplier_id_field: {
                        "filterType": "IncludeValues",
                        "values": alias_ids,
                    }
                }
                filter_mode = "ids"
            elif alias_names and _allowed(fields, supplier_name_field, "filteringAllowed"):
                extra_filter = {
                    supplier_name_field: {
                        "filterType": "IncludeValues",
                        "values": alias_names,
                    }
                }
                filter_mode = "names"

            server_filtered = bool(extra_filter)
            try:
                rows = _query_rows_chunked(
                    base_url,
                    token,
                    group_fields,
                    aggregate_fields,
                    date_field,
                    date_from,
                    date_to,
                    extra_filters=extra_filter,
                    chunk_days=90,
                    timeout=45,
                )
            except (RuntimeError, requests.Timeout, requests.ConnectionError):
                server_filtered = False
                filter_mode = "python"
                rows = _query_rows_chunked(
                    base_url,
                    token,
                    group_fields,
                    aggregate_fields,
                    date_field,
                    date_from,
                    date_to,
                    extra_filters=None,
                    chunk_days=45,
                    timeout=45,
                )

            alias_id_set = set(alias_ids)
            alias_name_keys = {_supplier_name_key(name) for name in alias_names if name}
            selected_rows = []
            for row in rows:
                sid = _norm(row.get(supplier_id_field)) if supplier_id_field else ""
                name = _norm(row.get(supplier_name_field))
                if (
                    (sid and sid in alias_id_set)
                    or (_supplier_name_key(name) in alias_name_keys)
                    or _supplier_alias_match(name, supplier_name)
                ):
                    copy = dict(row)
                    # Normalize all historical duplicate counteragent cards into
                    # one supplier so old and new cards share one price history.
                    if supplier_id_field:
                        copy[supplier_id_field] = supplier_id or ("merged:" + _supplier_name_key(supplier_name))
                    copy[supplier_name_field] = supplier_name or name
                    selected_rows.append(copy)

            suppliers = _supplier_rollup(
                selected_rows,
                date_field,
                document_field,
                product_field,
                unit_field,
                supplier_name_field,
                supplier_type_field,
                supplier_id_field,
            )
            supplier = suppliers[0] if suppliers else None
            if not supplier:
                return {
                    "dateField": date_field,
                    "supplier": None,
                    "serverFiltered": server_filtered,
                    "filterMode": filter_mode,
                    "points": 0,
                    "oldest": "",
                    "newest": "",
                    "deliveries": 0,
                    "aliases": aliases,
                }

            all_dates = [
                point.get("date")
                for product in supplier.get("products") or []
                for point in product.get("history") or []
                if point.get("date")
            ]
            return {
                "dateField": date_field,
                "supplier": supplier,
                "serverFiltered": server_filtered,
                "filterMode": filter_mode,
                "points": len(all_dates),
                "oldest": min(all_dates) if all_dates else "",
                "newest": max(all_dates) if all_dates else "",
                "deliveries": int(supplier.get("deliveries") or 0),
                "aliases": aliases,
            }

        attempts = []
        best = None
        for date_field in date_candidates[:2]:
            try:
                result = query_for_date_field(date_field)
                attempts.append({
                    "dateField": date_field,
                    "points": result["points"],
                    "deliveries": result["deliveries"],
                    "oldest": result["oldest"],
                    "newest": result["newest"],
                    "aliases": result["aliases"],
                    "filterMode": result["filterMode"],
                })
                if (
                    best is None
                    or result["deliveries"] > best["deliveries"]
                    or (
                        result["deliveries"] == best["deliveries"]
                        and result["points"] > best["points"]
                    )
                    or (
                        result["deliveries"] == best["deliveries"]
                        and result["points"] == best["points"]
                        and result["oldest"]
                        and (not best["oldest"] or result["oldest"] < best["oldest"])
                    )
                ):
                    best = result

                if result["oldest"]:
                    oldest_date = datetime.strptime(result["oldest"], "%Y-%m-%d").date()
                    if oldest_date <= requested_start + timedelta(days=14):
                        break
            except (RuntimeError, requests.Timeout, requests.ConnectionError):
                continue

        if best is None:
            raise RuntimeError("iikoServer did not return supplier history for the selected period")

        supplier = best["supplier"]
        aliases = best.get("aliases") or []
        return {
            "success": True,
            "period": {"from": date_from, "to": date_to, "days": days},
            "supplier": supplier,
            "serverFiltered": best["serverFiltered"],
            "historyMeta": {
                "oldestDate": best["oldest"],
                "newestDate": best["newest"],
                "points": best["points"],
                "dateField": best["dateField"],
                "attempts": attempts,
                "aliases": aliases,
                "aliasCount": len(aliases),
            },
        }
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def install_procurement_diagnostics(app):
    if getattr(app, "_doner_procurement_diagnostics_installed", False):
        return
    app._doner_procurement_diagnostics_installed = True

    @app.route("/procurement-supplier-history", methods=["GET"], endpoint="procurement_supplier_history_api")
    def procurement_supplier_history_api():
        try:
            supplier = request.args.get("supplier") or ""
            supplier_id = request.args.get("supplierId") or ""
            days = int(request.args.get("days") or 30)
            return jsonify(build_supplier_history(supplier, days, supplier_id))
        except ValueError as error:
            return jsonify({"success": False, "message": str(error)}), 400
        except requests.Timeout:
            return jsonify({
                "success": False,
                "message": "iikoServer did not answer in time. Retry in a few seconds.",
            }), 504
        except Exception as error:
            return jsonify({
                "success": False,
                "message": "Не удалось загрузить историю выбранного поставщика",
                "details": str(error),
            }), 502

    @app.route("/procurement-diagnostics", methods=["GET"], endpoint="procurement_diagnostics_api")
    def procurement_diagnostics_api():
        try:
            days = int(request.args.get("days") or 180)
            return jsonify(build_procurement_diagnostics(days))
        except ValueError:
            return jsonify({"success": False, "message": "days must be an integer"}), 400
        except requests.Timeout:
            return jsonify({
                "success": False,
                "message": "iikoServer did not answer in time. Retry in a few seconds.",
            }), 504
        except Exception as error:
            return jsonify({
                "success": False,
                "message": "Не удалось проверить данные поставщиков и закупок в iiko",
                "details": str(error),
            }), 502
