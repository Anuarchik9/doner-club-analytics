import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests
from flask import jsonify, request

from revisions_data_v2 import (
    SCOPES,
    _allowed,
    _auth,
    _date_filter,
    _discover,
    _get_fields,
    _looks_like_inventory,
    _logout,
    _month_bounds,
    _arai_revision_kind,
    _scope_revision_kind,
    _olap_post,
    _resolve,
    _row_store,
    _store_matches,
)
from revisions_data_v5 import _build as _build_v5
from revisions_data_v6 import _enrich


BALANCE_PATH = "/api/v2/reports/balance/stores"
STORE_PATH = "/api/corporation/stores"

# The old iikoServer XML API exposes document exports by document type. Unlike
# TRANSACTIONS OLAP, this source retains the document status (NEW/PROCESSED) and
# therefore can mirror the iikoChain inventory register instead of guessing
# inventories from accounting movements.
INVENTORY_EXPORT_TYPES = (
    "incomingInventory",
    "inventory",
    "stockTaking",
    "inventoryDocument",
    "inventoryAct",
)


def _norm(value):
    text = str(value or "").lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return " ".join(text.split())


def _resolve_datetime_field(fields):
    for name in ("DateTime.Typed", "DateSecondary.DateTimeTyped", "DateTime"):
        if name in fields and _allowed(fields, name, "groupingAllowed"):
            return name
    for name in sorted(fields):
        low = name.lower()
        if "datetime" in low and "date" not in low.replace("datetime", "") and _allowed(fields, name, "groupingAllowed"):
            return name
    return None


def _query_rows_with_time(base_url, token, period, fields, names, diagnostics):
    date_time_field = names.get("dateTime")
    group_fields = []
    for field in [
        names["date"],
        date_time_field,
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
        return _olap_post(base_url, token, body, timeout=105)
    except RuntimeError:
        body["filters"] = _date_filter(names["date"], period)
        return _olap_post(base_url, token, body, timeout=105)


def _inventory_document_times(scope, rows, names):
    field = names.get("dateTime")
    result = {}
    if not field:
        return result

    for row in rows:
        if not isinstance(row, dict):
            continue
        store = _row_store(scope, row, names["stores"])
        if not store or not _looks_like_inventory(scope, row, names):
            continue
        document = str(row.get(names.get("document")) or "").strip() if names.get("document") else ""
        if not document:
            document = "Без номера"
        date_value = str(row.get(names["date"]) or "")[:10]
        stamp = str(row.get(field) or "").strip()
        if not date_value or not stamp:
            continue
        key = (date_value, document, store)
        previous = result.get(key)
        # The posting time should normally be identical on all rows of the same
        # inventory document. If it is not, keep the earliest posting timestamp.
        if previous is None or stamp < previous:
            result[key] = stamp
    return result


def _xml_tag(element):
    return str(element.tag or "").split("}")[-1].strip().lower()


def _xml_text(element, *names):
    wanted = {str(name).lower() for name in names}
    for child in list(element):
        if _xml_tag(child) in wanted:
            value = (child.text or "").strip()
            if value:
                return value
    return None


def _xml_desc_text(element, *names):
    wanted = {str(name).lower() for name in names}
    for child in element.iter():
        if child is element:
            continue
        if _xml_tag(child) in wanted:
            value = (child.text or "").strip()
            if value:
                return value
    return None


def _product_names_map(base_url, token):
    try:
        response = requests.get(
            f"{base_url}/api/v2/entities/products/list",
            params={"key": token, "includeDeleted": "false"},
            headers={"Accept": "application/json"},
            timeout=40,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload if isinstance(payload, list) else (
            payload.get("items") or payload.get("response") or []
        )
        result = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            product_id = str(
                item.get("id") or item.get("productId") or item.get("uuid") or ""
            ).strip()
            name = str(item.get("name") or item.get("fullName") or "").strip()
            if product_id and name:
                result[product_id] = name
        return result
    except Exception:
        return {}


def _inventory_export_items(document_node, product_names):
    names = []
    product_ids = []
    items_node = None
    for child in list(document_node):
        if _xml_tag(child) in ("items", "itemlist", "itemslist", "itemdtoes"):
            items_node = child
            break
    if items_node is None:
        return names, product_ids

    for item in list(items_node):
        if _xml_tag(item) not in ("item", "inventoryitem", "incominginventoryitemdto"):
            continue
        product_id = (
            _xml_text(item, "productId", "product")
            or _xml_desc_text(item, "productId", "id")
            or ""
        ).strip()
        product_name = (
            _xml_desc_text(item, "productName", "name")
            or product_names.get(product_id)
            or ""
        ).strip()
        if product_id:
            product_ids.append(product_id)
        if product_name and product_name not in names:
            names.append(product_name)
    return names, product_ids


def _parse_inventory_export(xml_text, product_names):
    root = ET.fromstring(xml_text)
    documents = []
    seen = set()
    for node in root.iter():
        number = _xml_text(node, "documentNumber", "number")
        date_value = _xml_text(node, "dateIncoming", "date")
        status = _xml_text(node, "status", "documentStatus")
        if not number or not date_value:
            continue
        # Avoid treating nested item/product nodes as document headers.
        key = (number, date_value)
        if key in seen:
            continue
        seen.add(key)
        store_id = (
            _xml_text(node, "storeId", "store")
            or _xml_desc_text(node, "storeId")
            or ""
        ).strip()
        store_code = (_xml_text(node, "storeCode") or "").strip()
        comment = (_xml_text(node, "comment") or "").strip()
        product_names_list, product_ids = _inventory_export_items(node, product_names)
        documents.append(
            {
                "document": number.strip(),
                "dateTime": date_value.strip(),
                "date": date_value.strip()[:10],
                "status": (status or "UNKNOWN").strip().upper(),
                "storeId": store_id,
                "storeCode": store_code,
                "comment": comment,
                "productNames": product_names_list,
                "productIds": product_ids,
            }
        )
    return documents


def _fetch_inventory_documents(base_url, token, period):
    start, next_month = _month_bounds(period)
    date_from = start[:10]
    end_exclusive = datetime.fromisoformat(next_month[:19])
    date_to = (end_exclusive - timedelta(days=1)).date().isoformat()
    product_names = _product_names_map(base_url, token)
    attempts = []

    for document_type in INVENTORY_EXPORT_TYPES:
        url = f"{base_url}/api/documents/export/{document_type}"
        for params in (
            {"key": token, "from": date_from, "to": date_to},
            {"key": token, "dateFrom": date_from, "dateTo": date_to},
        ):
            try:
                response = requests.get(url, params=params, timeout=45)
                attempts.append(
                    {
                        "type": document_type,
                        "params": "from/to" if "from" in params else "dateFrom/dateTo",
                        "status": response.status_code,
                    }
                )
                if not response.ok:
                    continue
                documents = _parse_inventory_export(response.text, product_names)
                if documents:
                    return documents, {
                        "available": True,
                        "type": document_type,
                        "documents": len(documents),
                        "attempts": attempts[-6:],
                    }
            except Exception as error:
                attempts.append(
                    {
                        "type": document_type,
                        "error": str(error)[:220],
                    }
                )
    return [], {
        "available": False,
        "attempts": attempts[-10:],
    }


def _scope_inventory_documents(scope, documents, rows, names, stores):
    store_by_id = {str(item.get("id") or ""): item for item in stores}
    row_products = defaultdict(set)
    document_field = names.get("document")
    product_field = names.get("product")
    if document_field and product_field:
        for row in rows:
            if not isinstance(row, dict):
                continue
            number = str(row.get(document_field) or "").strip()
            product = str(row.get(product_field) or "").strip()
            if number and product:
                row_products[number].add(product)

    required_kind = _scope_revision_kind(scope)
    result = []
    for raw in documents:
        item = dict(raw)
        store = store_by_id.get(str(item.get("storeId") or ""))
        store_name = (
            (store or {}).get("name")
            or item.get("storeCode")
            or item.get("storeId")
            or ""
        )
        item["store"] = store_name
        if not _store_matches(scope, store_name):
            continue

        product_names = list(item.get("productNames") or [])
        if not product_names:
            product_names = sorted(row_products.get(item.get("document")) or [])
            item["productNames"] = product_names

        detected_kind = _arai_revision_kind(product_names)
        item["revisionKind"] = detected_kind
        if required_kind and detected_kind != required_kind:
            continue

        item["processed"] = item.get("status") == "PROCESSED"
        item["pending"] = item.get("status") in ("NEW", "SAVE", "UNKNOWN")
        item["itemsPreview"] = ", ".join(product_names[:4])
        item["itemsCount"] = len(product_names)
        result.append(item)

    result.sort(
        key=lambda item: (
            str(item.get("dateTime") or ""),
            str(item.get("document") or ""),
        ),
        reverse=True,
    )
    return result


def _load_stores(base_url, token):
    response = requests.get(
        f"{base_url}{STORE_PATH}",
        params={"key": token},
        timeout=25,
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    stores = []
    seen = set()
    for element in root.iter():
        store_id = (element.findtext("id") or "").strip()
        name = (element.findtext("name") or "").strip()
        code = (element.findtext("code") or "").strip()
        if not store_id or not name or store_id in seen:
            continue
        seen.add(store_id)
        stores.append({"id": store_id, "name": name, "code": code})
    return stores


def _match_store(scope, label, stores):
    wanted = set(_norm(label).split())
    if not wanted:
        return None

    best = None
    best_score = -1.0
    for store in stores:
        # Keep Arai and Workshop strictly separated even when the corporation has
        # similarly named warehouses elsewhere.
        if not _store_matches(scope, store.get("name")):
            continue
        name_tokens = set(_norm(store.get("name")).split())
        code_tokens = set(_norm(store.get("code")).split())
        tokens = name_tokens | code_tokens
        if not tokens:
            continue
        overlap = len(wanted & tokens)
        union = len(wanted | tokens) or 1
        score = overlap / union
        norm_label = _norm(label)
        norm_name = _norm(store.get("name"))
        if norm_label and (norm_label in norm_name or norm_name in norm_label):
            score += 1.0
        # Exact token coverage is especially important for names such as
        # "АРАЙ общий" vs "Арай (АРАЙ общий)".
        if wanted.issubset(tokens):
            score += 1.0
        if score > best_score:
            best_score = score
            best = store
    return best if best_score >= 0.35 else None


def _parse_timestamp(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    cleaned = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
    ):
        try:
            return datetime.strptime(raw[:26], fmt)
        except ValueError:
            continue
    return None


def _balance_timestamp(document_time):
    parsed = _parse_timestamp(document_time)
    if not parsed:
        return None
    # The book quantity in iikoChain is the accounting balance immediately BEFORE
    # the inventory adjustment is posted. One second is enough to move to that state.
    before = parsed - timedelta(seconds=1)
    return before.strftime("%Y-%m-%dT%H:%M:%S")


def _fetch_balance(base_url, token, store_id, timestamp):
    response = requests.get(
        f"{base_url}{BALANCE_PATH}",
        params={"key": token, "timestamp": timestamp, "store": store_id},
        timeout=40,
    )
    if not response.ok:
        raise RuntimeError(f"balance/stores HTTP {response.status_code}: {response.text[:300]}")
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("balance/stores вернул неожиданный формат")

    net_sum = 0.0
    absolute_sum = 0.0
    rows = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        # Even with a server-side store filter, keep this guard for builds that
        # ignore optional filters.
        row_store = str(item.get("store") or "").strip()
        if row_store and row_store != store_id:
            continue
        try:
            value = float(item.get("sum") or 0)
        except (TypeError, ValueError):
            value = 0.0
        net_sum += value
        absolute_sum += abs(value)
        rows += 1

    # Normally net value is the accounting book value. If a legacy/backdated
    # dataset produces a zero net total, absolute value is a safer denominator
    # than returning an infinite percentage.
    basis = abs(net_sum) if abs(net_sum) > 0.01 else absolute_sum
    return {
        "bookValue": round(basis, 2),
        "bookValueNet": round(net_sum, 2),
        "bookValueAbsolute": round(absolute_sum, 2),
        "balanceRows": rows,
        "timestamp": timestamp,
    }


def _accuracy_status(value):
    if value is None:
        return None
    value = float(value)
    if value <= 1.0:
        return {"key": "ok", "label": "Норма"}
    if value <= 2.0:
        return {"key": "warn", "label": "Внимание"}
    return {"key": "critical", "label": "Критично"}


def _attach_book_values(base_url, token, scope, result, doc_times):
    stores = _load_stores(base_url, token)
    details = result.get("revisionDetails") or []
    tasks = {}
    errors = []
    store_matches = {}

    for revision in details:
        date_value = revision.get("date")
        for document in revision.get("documents") or []:
            label = str(document.get("store") or "").strip()
            store = _match_store(scope, label, stores)
            if not store:
                document["bookValueError"] = f"Не сопоставлен склад: {label}"
                errors.append(document["bookValueError"])
                continue
            store_matches[label] = {"id": store["id"], "name": store["name"]}
            doc_name = str(document.get("document") or "Без номера")
            raw_time = doc_times.get((date_value, doc_name, label))
            if not raw_time:
                # Fallback to a normalized store-name lookup in case OLAP and the
                # document detail spell the same warehouse slightly differently.
                target_norm = _norm(label)
                for (d, n, s), value in doc_times.items():
                    if d == date_value and n == doc_name and _norm(s) == target_norm:
                        raw_time = value
                        break
            timestamp = _balance_timestamp(raw_time)
            if not timestamp:
                document["bookValueError"] = "iiko не отдала точное время проводки ревизии"
                errors.append(f"{doc_name}: {document['bookValueError']}")
                continue
            document["documentTime"] = raw_time
            document["bookTimestamp"] = timestamp
            key = (store["id"], timestamp)
            document["_balanceKey"] = key
            tasks.setdefault(key, (store["id"], timestamp))

    balances = {}
    if tasks:
        with ThreadPoolExecutor(max_workers=min(4, len(tasks))) as executor:
            future_map = {
                executor.submit(_fetch_balance, base_url, token, store_id, timestamp): key
                for key, (store_id, timestamp) in tasks.items()
            }
            for future in as_completed(future_map):
                key = future_map[future]
                try:
                    balances[key] = future.result()
                except Exception as error:
                    balances[key] = {"error": str(error)}

    successful_docs = 0
    total_docs = 0
    for revision in details:
        for document in revision.get("documents") or []:
            total_docs += 1
            key = document.pop("_balanceKey", None)
            if not key:
                continue
            balance = balances.get(key) or {}
            if balance.get("error"):
                document["bookValueError"] = balance["error"]
                errors.append(f"{document.get('document')}: {balance['error']}")
                continue
            document.update(balance)
            book_value = float(document.get("bookValue") or 0)
            gross = float(document.get("gross") or 0)
            shortage = float(document.get("shortage") or 0)
            surplus = float(document.get("surplus") or 0)
            if book_value > 0.01:
                document["shortagePct"] = round(shortage / book_value * 100, 2)
                document["surplusPct"] = round(surplus / book_value * 100, 2)
                document["discrepancyPct"] = round(gross / book_value * 100, 2)
                document["accuracyStatus"] = _accuracy_status(document["discrepancyPct"])
                successful_docs += 1

    history_map = {item.get("date"): item for item in result.get("history") or []}
    for revision in details:
        date_value = revision.get("date")
        history_item = history_map.get(date_value)
        if not history_item:
            continue

        # A date may contain several inventory documents. Count the same physical
        # warehouse once in the denominator even if it has multiple documents.
        by_store = {}
        expected_stores = set()
        for document in revision.get("documents") or []:
            label = str(document.get("store") or "")
            expected_stores.add(label)
            if document.get("bookValue") is not None:
                by_store[label] = float(document.get("bookValue") or 0)

        history_item["bookBalanceCoverage"] = {
            "storesWithBalance": len(by_store),
            "storesExpected": len(expected_stores),
        }
        if expected_stores and len(by_store) == len(expected_stores):
            book_value = round(sum(by_store.values()), 2)
            history_item["bookValue"] = book_value
            if book_value > 0.01:
                shortage = float(history_item.get("shortage") or 0)
                surplus = float(history_item.get("surplus") or 0)
                gross = float(history_item.get("gross") or 0)
                history_item["shortagePct"] = round(shortage / book_value * 100, 2)
                history_item["surplusPct"] = round(surplus / book_value * 100, 2)
                history_item["discrepancyPct"] = round(gross / book_value * 100, 2)
                history_item["accuracyStatus"] = _accuracy_status(history_item["discrepancyPct"])

    usable_history = [x for x in (result.get("history") or []) if x.get("bookValue") is not None]
    summary = result.setdefault("summary", {})
    if usable_history:
        latest = usable_history[0]
        summary["latestBookValue"] = latest.get("bookValue")
        summary["latestShortagePct"] = latest.get("shortagePct")
        summary["latestSurplusPct"] = latest.get("surplusPct")
        summary["latestDiscrepancyPct"] = latest.get("discrepancyPct")
        summary["latestAccuracyStatus"] = latest.get("accuracyStatus")
        denominator = sum(float(item.get("bookValue") or 0) for item in usable_history)
        if denominator > 0.01:
            summary["periodDiscrepancyPct"] = round(
                sum(float(item.get("gross") or 0) for item in usable_history) / denominator * 100,
                2,
            )
    summary["bookBalanceDates"] = len(usable_history)
    summary["bookBalanceDocuments"] = successful_docs
    summary["bookBalanceAvailable"] = bool(usable_history)

    result["discrepancyPercent"] = summary.get("latestDiscrepancyPct")
    result["balanceDiagnostics"] = {
        "available": bool(usable_history),
        "dateTimeField": result.get("fieldMap", {}).get("dateTime"),
        "storesLoaded": len(stores),
        "storeMatches": store_matches,
        "documentsWithBookValue": successful_docs,
        "documentsTotal": total_docs,
        "errors": errors[:12],
        "calculation": "book balance immediately before inventory posting via /api/v2/reports/balance/stores",
        "temporaryThresholds": {"okMaxPct": 1.0, "warningMaxPct": 2.0},
    }
    result["accuracyNote"] = (
        "% расхождения = (недостача + излишки) / книжная стоимость склада непосредственно перед проводкой ревизии. "
        "Книжная стоимость берётся из iikoServer balance/stores на секунду раньше времени документа. "
        "Пороги статуса пока рабочие: до 1% — Норма, 1–2% — Внимание, выше 2% — Критично; позже их можно заменить нормативами Doner Club."
    )
    return result


def install_revisions_data_v7(app):
    if getattr(app, "_doner_revisions_data_v7_installed", False):
        return
    app._doner_revisions_data_v7_installed = True

    @app.route("/revision-data", methods=["GET"], endpoint="revision_data_v7")
    def revision_data_v7():
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
            names["dateTime"] = _resolve_datetime_field(fields)
            diagnostics = _discover(base_url, token, period, fields, names, scope)
            rows = _query_rows_with_time(base_url, token, period, fields, names, diagnostics)

            # Source of truth for the inventory register/statuses. OLAP is still
            # used for discrepancy amounts, but it is no longer allowed to invent
            # inventory documents from unrelated Arai accounting movements.
            inventory_documents, inventory_export = _fetch_inventory_documents(
                base_url, token, period
            )
            stores = _load_stores(base_url, token)
            scoped_documents = _scope_inventory_documents(
                scope, inventory_documents, rows, names, stores
            )

            if scoped_documents:
                processed_numbers = {
                    item.get("document")
                    for item in scoped_documents
                    if item.get("status") == "PROCESSED" and item.get("document")
                }
                if processed_numbers and names.get("document"):
                    rows = [
                        row for row in rows
                        if str(row.get(names["document"]) or "").strip()
                        in processed_numbers
                    ]

            result = _build_v5(scope, period, rows, names, diagnostics)
            result = _enrich(result)
            result["fieldMap"] = names
            result["inventoryDocuments"] = scoped_documents
            result["inventoryDocumentExport"] = inventory_export

            processed_documents = [
                item for item in scoped_documents
                if item.get("status") == "PROCESSED"
            ]
            pending_documents = [
                item for item in scoped_documents
                if item.get("status") != "PROCESSED"
            ]
            if processed_documents:
                processed_dates = sorted(
                    {item.get("date") for item in processed_documents if item.get("date")},
                    reverse=True,
                )
                summary = result.setdefault("summary", {})
                summary["lastRevision"] = processed_dates[0] if processed_dates else None
                summary["documentsCount"] = len(processed_documents)
                summary["revisionsCount"] = len(processed_dates)
                summary["pendingDocumentsCount"] = len(pending_documents)
                summary["sourceOfTruth"] = "iiko inventory document export"
                summary["documentState"] = "PROCESSED"

            doc_times = _inventory_document_times(scope, rows, names)
            try:
                result = _attach_book_values(base_url, token, scope, result, doc_times)
            except Exception as balance_error:
                # Book-value enrichment must never break the already working
                # inventory analytics. Return the revision data and expose the
                # balance error separately in the UI.
                result.setdefault("summary", {})["bookBalanceAvailable"] = False
                result["balanceDiagnostics"] = {
                    "available": False,
                    "dateTimeField": names.get("dateTime"),
                    "errors": [str(balance_error)],
                }
            return jsonify(result)
        except Exception as error:
            return jsonify(
                {
                    "success": False,
                    "scope": scope,
                    "period": period,
                    "message": "Не удалось получить данные инвентаризации из iikoServer",
                    "details": str(error),
                }
            ), 502
        finally:
            if base_url and token:
                _logout(base_url, token)
