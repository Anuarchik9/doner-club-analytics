import re
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


def _olap(base_url, token, group_fields, aggregate_fields, filters, timeout=90):
    body = {
        "reportType": "TRANSACTIONS",
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
        timeout=timeout,
    )
    if not response.ok:
        raise RuntimeError(f"TRANSACTIONS OLAP HTTP {response.status_code}: {response.text[:500]}")
    payload = response.json()
    rows = payload.get("data", payload if isinstance(payload, list) else [])
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
        raise RuntimeError("iikoServer did not return TRANSACTIONS OLAP columns")
    return fields


def _purchase_marker(row, inspect_fields):
    text = " | ".join(_norm(row.get(field)).lower() for field in inspect_fields if row.get(field))
    return any(token in text for token in PURCHASE_TOKENS)


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

        supplier_fields = _field_candidates(fields, SUPPLIER_TOKENS)
        # Contr-* fields are useful on older iiko builds even when they are not
        # explicitly named Supplier/Counteragent.
        fallback_counterparty = [
            name for name in (
                "Contr-Account.Name", "Contr-Account", "Contr-Account.Code",
                "Account.Name", "Account", "Account.Code",
            )
            if name in fields and _allowed(fields, name, "groupingAllowed")
        ]
        counterparty_fields = []
        for name in supplier_fields + fallback_counterparty:
            if name not in counterparty_fields:
                counterparty_fields.append(name)

        product_field = _pick(fields, ("Product.Name", "Contr-Product.Name"))
        unit_field = _pick(fields, ("Product.MeasureUnit", "Contr-Product.MeasureUnit"))

        aggregate_fields = [
            name for name in ("Amount.In", "Sum.Incoming", "Product.AvgSum", "Amount.StoreInOutTyped")
            if name in fields and _allowed(fields, name, "aggregationAllowed")
        ]
        if not aggregate_fields:
            raise RuntimeError("No incoming amount/cost aggregates found in TRANSACTIONS")

        discovery_groups = []
        for name in [date_field, tx_field, document_field, *counterparty_fields[:6]]:
            if name and name not in discovery_groups and _allowed(fields, name, "groupingAllowed"):
                discovery_groups.append(name)

        rows = _olap(
            base_url, token,
            discovery_groups,
            aggregate_fields,
            _date_filter(date_field, date_from, date_to),
            timeout=105,
        )

        tx_values = []
        supplier_values = {}
        marker_rows = 0
        positive_incoming_rows = 0
        inspect_fields = [field for field in [tx_field, document_field, *counterparty_fields] if field]

        for row in rows:
            if tx_field:
                value = _norm(row.get(tx_field))
                if value and value not in tx_values and len(tx_values) < 120:
                    tx_values.append(value)
            for field in counterparty_fields:
                value = _norm(row.get(field))
                if value:
                    bucket = supplier_values.setdefault(field, [])
                    if value not in bucket and len(bucket) < 80:
                        bucket.append(value)
            if _purchase_marker(row, inspect_fields):
                marker_rows += 1
            if _num(row.get("Amount.In")) > 0 or _num(row.get("Sum.Incoming")) > 0:
                positive_incoming_rows += 1

        price_evidence = []
        if product_field:
            detail_groups = []
            for name in [date_field, tx_field, document_field, *counterparty_fields[:3], product_field, unit_field]:
                if name and name not in detail_groups and _allowed(fields, name, "groupingAllowed"):
                    detail_groups.append(name)

            detail_from = (today - timedelta(days=min(days, 60))).isoformat()
            detail_rows = _olap(
                base_url, token,
                detail_groups,
                aggregate_fields,
                _date_filter(date_field, detail_from, date_to),
                timeout=105,
            )
            for row in detail_rows:
                amount = abs(_num(row.get("Amount.In")))
                incoming_sum = abs(_num(row.get("Sum.Incoming")))
                avg_sum = abs(_num(row.get("Product.AvgSum")))
                if amount <= 0 and incoming_sum <= 0:
                    continue
                unit_price = incoming_sum / amount if amount and incoming_sum else avg_sum
                if unit_price <= 0:
                    continue
                supplier = ""
                supplier_field = None
                for field in counterparty_fields:
                    value = _norm(row.get(field))
                    if value:
                        supplier = value
                        supplier_field = field
                        break
                price_evidence.append({
                    "date": _norm(row.get(date_field))[:10],
                    "document": _norm(row.get(document_field)) if document_field else "",
                    "supplier": supplier,
                    "supplierField": supplier_field,
                    "product": _norm(row.get(product_field)),
                    "unit": _norm(row.get(unit_field)) if unit_field else "",
                    "quantity": round(amount, 4),
                    "sum": round(incoming_sum, 2),
                    "unitPrice": round(unit_price, 4),
                    "transaction": _norm(row.get(tx_field)) if tx_field else "",
                })
                if len(price_evidence) >= 40:
                    break

        likely_supplier_fields = [
            field for field in supplier_fields
            if supplier_values.get(field)
        ]
        fallback_with_values = [
            field for field in fallback_counterparty
            if supplier_values.get(field)
        ]

        return {
            "success": True,
            "period": {"from": date_from, "to": date_to, "days": days},
            "fieldSupport": {
                "date": date_field,
                "transaction": tx_field,
                "document": document_field,
                "product": product_field,
                "unit": unit_field,
                "supplierNamedFields": likely_supplier_fields,
                "counterpartyFallbackFields": fallback_with_values,
                "incomingAggregates": aggregate_fields,
            },
            "evidence": {
                "discoveryRows": len(rows),
                "purchaseMarkerRows": marker_rows,
                "positiveIncomingRows": positive_incoming_rows,
                "supplierValues": {
                    field: values[:25] for field, values in supplier_values.items() if values
                },
                "transactionValues": tx_values[:50],
                "priceRowsFound": len(price_evidence),
                "priceSamples": price_evidence[:12],
            },
            "capability": {
                "canBuildSupplierList": bool(likely_supplier_fields or fallback_with_values),
                "canBuildPurchasePriceHistory": bool(price_evidence),
                "canBuildProductSupplierMatrix": bool(price_evidence and (likely_supplier_fields or fallback_with_values)),
            },
            "note": (
                "Diagnostics only. Counterparty/account fields are treated as candidates until "
                "their values are confirmed as real suppliers."
            ),
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


def install_procurement_diagnostics(app):
    if getattr(app, "_doner_procurement_diagnostics_installed", False):
        return
    app._doner_procurement_diagnostics_installed = True

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
