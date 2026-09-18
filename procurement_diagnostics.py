import os
import re
import time
import xml.etree.ElementTree as ET
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


def _local_tag(tag):
    return str(tag or "").split("}")[-1].split(":")[-1]


def _leaf_entries(node):
    result = []
    def walk(current, path):
        tag = _local_tag(current.tag)
        next_path = path + [tag]
        children = list(current)
        text = (current.text or "").strip()
        if not children and text:
            result.append((".".join(next_path), tag, text))
            return
        for child in children:
            walk(child, next_path)
    walk(node, [])
    return result


def _pick_leaf(entries, exact=(), contains=(), exclude=()):
    exact_set = {str(x).casefold() for x in exact}
    contains_set = tuple(str(x).casefold() for x in contains)
    exclude_set = tuple(str(x).casefold() for x in exclude)
    best = None
    best_score = -10**9
    for path, tag, value in entries:
        low_tag = tag.casefold()
        low_path = path.casefold()
        if exclude_set and any(token in low_path for token in exclude_set):
            continue
        score = 0
        if low_tag in exact_set:
            score += 100
        if contains_set and all(token in low_path for token in contains_set):
            score += 30
        if score <= 0:
            continue
        score -= len(path) * 0.01
        if score > best_score:
            best_score = score
            best = value
    return best


def _contractor_catalog(base_url, token):
    response = requests.get(
        f"{base_url}/api/v2/entities/contractors",
        params={"key": token},
        timeout=35,
    )
    response.raise_for_status()
    content_type = (response.headers.get("content-type") or "").lower()
    contractors = []

    def add_record(record):
        if not isinstance(record, dict):
            return
        cid = _norm(record.get("id") or record.get("uuid") or record.get("supplierId"))
        name = _norm(record.get("name") or record.get("fullName") or record.get("shortName"))
        ctype = _norm(record.get("type") or record.get("counteragentType"))
        if cid and name:
            contractors.append({"id": cid, "name": name, "type": ctype})

    if "json" in content_type:
        payload = response.json()
        def walk(value):
            if isinstance(value, dict):
                add_record(value)
                for child in value.values():
                    if isinstance(child, (dict, list)):
                        walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(payload)
    else:
        try:
            root = ET.fromstring(response.content)
            for node in root.iter():
                entries = _leaf_entries(node)
                cid = _pick_leaf(entries, exact=("id", "uuid"))
                name = _pick_leaf(entries, exact=("name", "fullName", "shortName"))
                ctype = _pick_leaf(entries, exact=("type", "counteragentType"))
                if cid and name:
                    contractors.append({"id": _norm(cid), "name": _norm(name), "type": _norm(ctype)})
        except ET.ParseError:
            pass

    unique = {}
    for item in contractors:
        unique[item["id"]] = item
    return list(unique.values())



IIKOWEB_BASE_URL = "https://public-api.iikoweb.ru"


def _iikoweb_token():
    api_key = (os.environ.get("IIKO_API_KEY") or "").strip()
    app_id = (os.environ.get("IIKO_APP_ID") or "").strip()
    client_secret = (os.environ.get("IIKO_CLIENT_SECRET") or "").strip()
    if not api_key:
        raise RuntimeError("IIKO_API_KEY is not configured")
    payload = {"api_key": api_key}
    if app_id:
        payload["app_id"] = app_id
    if client_secret:
        payload["client_secret"] = client_secret
    response = requests.post(
        f"{IIKOWEB_BASE_URL}/auth",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    token = _norm(data.get("token"))
    if not token:
        raise RuntimeError("iiko Public Web API returned an empty token")
    return token


def _iikoweb_post(token, path, payload, timeout=70):
    response = requests.post(
        f"{IIKOWEB_BASE_URL}/{path.lstrip('/')}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def _ci_get(mapping, *names):
    if not isinstance(mapping, dict):
        return None
    wanted = {str(name).casefold() for name in names}
    for key, value in mapping.items():
        if str(key).casefold() in wanted:
            return value
    return None


def _iter_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)):
                yield from _iter_dicts(child)


def _nested_text(value, *names):
    if isinstance(value, dict):
        direct = _ci_get(value, *names)
        if direct not in (None, "") and not isinstance(direct, (dict, list)):
            return _norm(direct)
        for child in value.values():
            if isinstance(child, dict):
                nested = _nested_text(child, *names)
                if nested:
                    return nested
    return ""


def _json_product_info(item, products_map):
    product = _ci_get(item, "product", "item", "nomenclature")
    product_id = _norm(
        _ci_get(item, "productId", "itemId", "nomenclatureId")
        or (_ci_get(product, "id", "productId") if isinstance(product, dict) else "")
    )
    product_name = _norm(
        _ci_get(item, "productName", "itemName", "nomenclatureName")
        or (_ci_get(product, "name", "productName") if isinstance(product, dict) else "")
    )
    if not product_name and product_id:
        product_name = _norm((products_map.get(product_id) or {}).get("name"))
    return product_id, product_name


def _json_unit_name(item):
    unit = _ci_get(item, "measureUnit", "unit", "mainUnit", "unitName")
    if isinstance(unit, dict):
        return _norm(_ci_get(unit, "name", "shortName", "code"))
    if unit not in (None, ""):
        return _norm(unit)
    return ""


def _json_supplier_info(document, fallback_name="", fallback_id=""):
    supplier = _ci_get(document, "supplier", "counteragent", "contractor", "provider")
    supplier_id = _norm(
        _ci_get(document, "supplierId", "counteragentId", "contractorId", "providerId")
        or (_ci_get(supplier, "id", "supplierId") if isinstance(supplier, dict) else "")
        or fallback_id
    )
    supplier_name = _norm(
        _ci_get(document, "supplierName", "counteragentName", "contractorName", "providerName")
        or (_ci_get(supplier, "name", "fullName", "shortName") if isinstance(supplier, dict) else "")
        or fallback_name
    )
    return supplier_id, supplier_name


def _document_item_list(document):
    if not isinstance(document, dict):
        return []
    preferred = (
        "items", "lines", "rows", "documentItems", "invoiceItems",
        "positions", "products", "records",
    )
    for name in preferred:
        value = _ci_get(document, name)
        if isinstance(value, list) and any(isinstance(x, dict) for x in value):
            return [x for x in value if isinstance(x, dict)]
    for value in document.values():
        if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
            if any(
                _ci_get(x, "productId", "product", "productName", "itemId", "amount", "quantity") is not None
                for x in value[:5]
            ):
                return value
    return []


def _parse_iikoweb_invoice_payload(payload, fallback_supplier_name="", fallback_supplier_id=""):
    try:
        products_map = core.get_products_map()
    except Exception:
        products_map = {}

    rows = []
    documents_seen = 0
    used_nodes = set()

    for document in _iter_dicts(payload):
        items = _document_item_list(document)
        if not items:
            continue
        marker = id(document)
        if marker in used_nodes:
            continue
        used_nodes.add(marker)

        parsed_items = []
        for item in items:
            product_id, product_name = _json_product_info(item, products_map)
            quantity = abs(_num(_ci_get(item, "amount", "quantity", "qty", "count", "actualAmount", "productAmount")))
            unit_price = abs(_num(_ci_get(item, "price", "unitPrice", "priceWithoutVat", "costPrice", "purchasePrice")))
            line_sum = abs(_num(_ci_get(item, "sum", "total", "productSum", "totalSum", "cost", "amountSum")))
            if unit_price <= 0 and quantity > 0 and line_sum > 0:
                unit_price = line_sum / quantity
            if line_sum <= 0 and quantity > 0 and unit_price > 0:
                line_sum = quantity * unit_price
            if not product_name or quantity <= 0 or unit_price <= 0:
                continue
            parsed_items.append({
                "productId": product_id,
                "product": product_name,
                "unit": _json_unit_name(item),
                "quantity": quantity,
                "sum": line_sum,
                "unitPrice": unit_price,
            })
        if not parsed_items:
            continue

        documents_seen += 1
        supplier_id, supplier_name = _json_supplier_info(
            document,
            fallback_supplier_name,
            fallback_supplier_id,
        )
        date_value = _normalize_invoice_date(
            _ci_get(
                document,
                "dateIncoming", "documentDate", "invoiceDate", "deliveryDate",
                "date", "dateTime", "createdAt", "creationDate",
            )
        )
        document_number = _norm(
            _ci_get(document, "documentNumber", "number", "invoiceNumber", "num", "documentNo")
        )
        document_id = _norm(_ci_get(document, "id", "documentId", "invoiceId"))

        for item in parsed_items:
            rows.append({
                "date": date_value,
                "document": document_number or document_id,
                "supplierId": supplier_id,
                "supplier": supplier_name,
                **item,
            })

    # Some API builds return a flat list of line records rather than document objects.
    if not rows:
        for item in _iter_dicts(payload):
            product_id, product_name = _json_product_info(item, products_map)
            quantity = abs(_num(_ci_get(item, "amount", "quantity", "qty", "count", "actualAmount", "productAmount")))
            unit_price = abs(_num(_ci_get(item, "price", "unitPrice", "priceWithoutVat", "costPrice", "purchasePrice")))
            line_sum = abs(_num(_ci_get(item, "sum", "total", "productSum", "totalSum", "cost", "amountSum")))
            if unit_price <= 0 and quantity > 0 and line_sum > 0:
                unit_price = line_sum / quantity
            if line_sum <= 0 and quantity > 0 and unit_price > 0:
                line_sum = quantity * unit_price
            if not product_name or quantity <= 0 or unit_price <= 0:
                continue
            supplier_id, supplier_name = _json_supplier_info(item, fallback_supplier_name, fallback_supplier_id)
            rows.append({
                "date": _normalize_invoice_date(
                    _ci_get(item, "dateIncoming", "documentDate", "invoiceDate", "deliveryDate", "date", "dateTime")
                ),
                "document": _norm(_ci_get(item, "documentNumber", "number", "invoiceNumber", "documentId", "id")),
                "supplierId": supplier_id,
                "supplier": supplier_name,
                "productId": product_id,
                "product": product_name,
                "unit": _json_unit_name(item),
                "quantity": quantity,
                "sum": line_sum,
                "unitPrice": unit_price,
            })

    return rows, {
        "documents": documents_seen,
        "rows": len(rows),
        "responseType": type(payload).__name__,
    }


def _iikoweb_counteragents(token, department_id):
    payload = {
        "departmentId": department_id,
        "type": ["supplier"],
        "limit": 2000,
        "offset": 0,
    }
    data = _iikoweb_post(token, "document-processing/counteragents", payload, timeout=45)
    result = []
    for record in _iter_dicts(data):
        cid = _norm(_ci_get(record, "id", "supplierId", "counteragentId", "contractorId"))
        name = _norm(_ci_get(record, "name", "fullName", "shortName", "supplierName"))
        if cid and name:
            result.append({"id": cid, "name": name})
    unique = {}
    for item in result:
        unique[item["id"]] = item
    return list(unique.values())


def _iikoweb_supplier_history_rows(supplier_name, supplier_id, date_from, date_to):
    token = _iikoweb_token()
    departments = core.get_departments()
    if not departments:
        raise RuntimeError("iiko did not return departments for invoice export")

    aliases_by_department = {}
    alias_meta = []
    counteragent_errors = []

    for department in departments:
        department_id = _norm(department.get("organizationId"))
        if not department_id:
            continue
        candidates = {}
        if supplier_id:
            candidates[supplier_id] = {"id": supplier_id, "name": supplier_name}
        try:
            for item in _iikoweb_counteragents(token, department_id):
                if _supplier_alias_match(item.get("name"), supplier_name):
                    candidates[item["id"]] = item
        except Exception as error:
            counteragent_errors.append({
                "departmentId": department_id,
                "department": department.get("name") or department.get("code"),
                "error": str(error)[:300],
            })
        aliases_by_department[department_id] = list(candidates.values())
        for item in candidates.values():
            alias_meta.append({
                "departmentId": department_id,
                "department": department.get("name") or department.get("code"),
                "id": item.get("id"),
                "name": item.get("name"),
            })

    all_rows = []
    export_meta = []
    errors = []
    seen = set()

    for department in departments:
        department_id = _norm(department.get("organizationId"))
        if not department_id:
            continue
        aliases = aliases_by_department.get(department_id) or []
        if not aliases and supplier_id:
            aliases = [{"id": supplier_id, "name": supplier_name}]
        for alias in aliases:
            alias_id = _norm(alias.get("id"))
            if not alias_id:
                continue
            for chunk_from, chunk_to in _date_chunks(date_from, date_to, 90):
                body = {
                    "departmentId": department_id,
                    "dateFrom": chunk_from,
                    "dateTo": chunk_to,
                    "supplierId": alias_id,
                }
                try:
                    payload = _iikoweb_post(
                        token,
                        "document-processing/incoming-invoice/export",
                        body,
                        timeout=75,
                    )
                    rows, meta = _parse_iikoweb_invoice_payload(
                        payload,
                        fallback_supplier_name=supplier_name or alias.get("name") or "",
                        fallback_supplier_id=supplier_id or alias_id,
                    )
                    export_meta.append({
                        "departmentId": department_id,
                        "department": department.get("name") or department.get("code"),
                        "supplierId": alias_id,
                        "supplierName": alias.get("name"),
                        "from": chunk_from,
                        "to": chunk_to,
                        **meta,
                    })
                    for row in rows:
                        row_name = _norm(row.get("supplier"))
                        row_id = _norm(row.get("supplierId"))
                        if row_name and not _supplier_alias_match(row_name, supplier_name):
                            if supplier_id and row_id != supplier_id and row_id != alias_id:
                                continue
                        row["supplier"] = supplier_name or row_name or alias.get("name") or ""
                        row["supplierId"] = supplier_id or row_id or alias_id
                        key = (
                            row.get("date"),
                            row.get("document"),
                            row.get("productId") or row.get("product"),
                            round(_num(row.get("quantity")), 6),
                            round(_num(row.get("sum")), 2),
                            round(_num(row.get("unitPrice")), 4),
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        all_rows.append(row)
                except Exception as error:
                    errors.append({
                        "departmentId": department_id,
                        "department": department.get("name") or department.get("code"),
                        "supplierId": alias_id,
                        "from": chunk_from,
                        "to": chunk_to,
                        "error": str(error)[:500],
                    })

    return all_rows, {
        "aliases": alias_meta,
        "exports": export_meta,
        "errors": errors[:20],
        "counteragentErrors": counteragent_errors[:20],
        "departmentsChecked": len([d for d in departments if d.get("organizationId")]),
    }


def _incoming_invoice_xml(base_url, token, date_from, date_to, supplier_id=None):
    params = {"key": token, "from": date_from, "to": date_to}
    if supplier_id:
        params["supplierId"] = supplier_id
    response = requests.get(
        f"{base_url}/api/documents/export/incomingInvoice",
        params=params,
        timeout=70,
    )
    response.raise_for_status()
    return response.content


def _invoice_item_candidates(root):
    candidates = []
    for node in root.iter():
        entries = _leaf_entries(node)
        lows = [path.casefold() for path, _tag, _value in entries]
        tags = [tag.casefold() for _path, tag, _value in entries]
        has_product = any("product" in path or tag in {"product", "productid", "productname"} for path, tag in zip(lows, tags))
        has_qty = any(
            tag in {"amount", "quantity", "qty", "count", "actualamount", "productamount"}
            or path.endswith(".amount")
            or path.endswith(".quantity")
            for path, tag in zip(lows, tags)
        )
        has_price = any(
            tag in {"price", "sum", "total", "cost", "productsum", "unitprice", "pricewithoutvat"}
            or "price" in tag
            or tag.endswith("sum")
            for tag in tags
        )
        tag_name = _local_tag(node.tag).casefold()
        if has_product and has_qty and has_price and (
            "item" in tag_name or "line" in tag_name or "record" in tag_name or len(list(node)) <= 12
        ):
            candidates.append(node)

    if not candidates:
        return []

    parent = {child: node for node in root.iter() for child in node}
    candidate_set = set(candidates)
    minimal = []
    for node in candidates:
        descendant_candidate = False
        for child in node.iter():
            if child is not node and child in candidate_set:
                descendant_candidate = True
                break
        if not descendant_candidate:
            minimal.append(node)
    return minimal


def _ancestor_invoice_info(node, parent):
    current = node
    best = {"date": "", "document": "", "supplierId": "", "supplierName": ""}
    for _ in range(8):
        current = parent.get(current)
        if current is None:
            break
        entries = _leaf_entries(current)
        if not best["date"]:
            best["date"] = _pick_leaf(
                entries,
                exact=(
                    "dateIncoming", "documentDate", "invoiceDate", "deliveryDate",
                    "date", "dateTime", "createdAt",
                ),
                exclude=("item.", "items.", "line.", "lines."),
            ) or ""
        if not best["document"]:
            best["document"] = _pick_leaf(
                entries,
                exact=("documentNumber", "number", "invoiceNumber", "document", "num"),
                exclude=("item.", "items.", "line.", "lines."),
            ) or ""
        if not best["supplierId"]:
            best["supplierId"] = _pick_leaf(
                entries,
                exact=("supplierId", "counteragentId", "contractorId", "providerId"),
            ) or ""
        if not best["supplierName"]:
            best["supplierName"] = _pick_leaf(
                entries,
                exact=("supplierName", "counteragentName", "contractorName", "providerName"),
            ) or ""
        if best["date"] and best["document"]:
            break
    return best


def _normalize_invoice_date(value):
    text = _norm(value)
    if not text:
        return ""
    match = re.search(r"(20\d{2})[-.](\d{2})[-.](\d{2})", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    match = re.search(r"(\d{2})[.](\d{2})[.](20\d{2})", text)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    return text[:10]


def _parse_incoming_invoice_rows(xml_bytes, fallback_supplier_name="", fallback_supplier_id=""):
    if not xml_bytes:
        return [], {"root": "", "itemCandidates": 0}
    root = ET.fromstring(xml_bytes)
    parent = {child: node for node in root.iter() for child in node}
    rows = []
    candidates = _invoice_item_candidates(root)

    for item in candidates:
        entries = _leaf_entries(item)
        product_name = (
            _pick_leaf(entries, exact=("productName", "itemName", "name"), contains=("product",))
            or _pick_leaf(entries, exact=("productName", "itemName"))
        )
        product_id = _pick_leaf(entries, exact=("productId", "itemId"), contains=("product",)) or ""
        unit = (
            _pick_leaf(entries, exact=("measureUnit", "unitName", "unit", "mainUnit"), contains=("unit",))
            or _pick_leaf(entries, exact=("measureUnit", "unitName", "unit"))
            or ""
        )
        quantity = _num(
            _pick_leaf(entries, exact=("amount", "quantity", "qty", "actualAmount", "productAmount"))
        )
        line_sum = _num(
            _pick_leaf(entries, exact=("sum", "total", "productSum", "cost", "totalSum"))
        )
        unit_price = _num(
            _pick_leaf(entries, exact=("price", "unitPrice", "priceWithoutVat", "costPrice"))
        )
        if unit_price <= 0 and quantity and line_sum:
            unit_price = line_sum / quantity
        if line_sum <= 0 and quantity and unit_price:
            line_sum = quantity * unit_price
        if not product_name:
            # Some iiko builds put the product name in a nested <product><name> field.
            for path, tag, value in entries:
                if tag.casefold() == "name" and "product" in path.casefold():
                    product_name = value
                    break
        if not product_name or quantity <= 0 or unit_price <= 0:
            continue

        info = _ancestor_invoice_info(item, parent)
        date_value = _normalize_invoice_date(info.get("date"))
        document = _norm(info.get("document"))
        supplier_id = _norm(info.get("supplierId") or fallback_supplier_id)
        supplier_name = _norm(info.get("supplierName") or fallback_supplier_name)
        rows.append({
            "date": date_value,
            "document": document,
            "supplierId": supplier_id,
            "supplier": supplier_name,
            "productId": _norm(product_id),
            "product": _norm(product_name),
            "unit": _norm(unit),
            "quantity": round(quantity, 6),
            "sum": round(line_sum, 2),
            "unitPrice": round(unit_price, 4),
        })

    meta = {
        "root": _local_tag(root.tag),
        "itemCandidates": len(candidates),
        "rows": len(rows),
    }
    return rows, meta


def _supplier_from_invoice_rows(rows, supplier_name, supplier_id):
    documents = set()
    products = {}
    total_spend = 0.0
    total_quantity = 0.0
    last_delivery = ""

    for row in rows:
        date_value = _norm(row.get("date"))
        product_name = _norm(row.get("product"))
        quantity = abs(_num(row.get("quantity")))
        line_sum = abs(_num(row.get("sum")))
        unit_price = abs(_num(row.get("unitPrice")))
        if not date_value or not product_name or quantity <= 0 or unit_price <= 0:
            continue
        document = _norm(row.get("document"))
        unit = _norm(row.get("unit"))
        total_spend += line_sum
        total_quantity += quantity
        if document:
            documents.add(f"{date_value}|{document}")
        if date_value > last_delivery:
            last_delivery = date_value

        product = products.setdefault(product_name, {
            "name": product_name,
            "unit": unit,
            "totalSpend": 0.0,
            "totalQuantity": 0.0,
            "history": {},
        })
        product["totalSpend"] += line_sum
        product["totalQuantity"] += quantity
        if unit and not product["unit"]:
            product["unit"] = unit
        day = product["history"].setdefault(date_value, {
            "sum": 0.0,
            "quantity": 0.0,
            "prices": [],
            "documents": set(),
        })
        day["sum"] += line_sum
        day["quantity"] += quantity
        day["prices"].append(unit_price)
        if document:
            day["documents"].add(document)

    result_products = []
    for product in products.values():
        history = []
        for date_value, values in sorted(product["history"].items()):
            price = (
                values["sum"] / values["quantity"]
                if values["quantity"] and values["sum"]
                else sum(values["prices"]) / len(values["prices"])
            )
            history.append({
                "date": date_value,
                "price": round(price, 2),
                "quantity": round(values["quantity"], 4),
                "sum": round(values["sum"], 2),
                "documents": sorted(values["documents"]),
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
        prices = [point["price"] for point in history]
        result_products.append({
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

    result_products.sort(key=lambda item: (-item["totalSpend"], item["name"].lower()))
    if not result_products:
        return None
    return {
        "id": supplier_id,
        "name": supplier_name,
        "type": "SUPPLIER",
        "totalSpend": round(total_spend, 2),
        "totalQuantity": round(total_quantity, 4),
        "deliveries": len(documents),
        "lastDelivery": last_delivery,
        "productsCount": len(result_products),
        "products": result_products,
    }


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



def _build_supplier_history_olap(supplier_name, days=30, supplier_id=""):
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



def build_supplier_history(supplier_name, days=30, supplier_id=""):
    """Load supplier history from actual incoming-invoice documents first.

    TRANSACTIONS OLAP is kept only as a compatibility fallback because it can
    expose a short accounting window even when older incoming invoices exist.
    """
    supplier_name = _norm(supplier_name)
    supplier_id = _norm(supplier_id)
    if not supplier_id and not _valid_supplier_name(supplier_name):
        raise ValueError("supplier is required")

    days = max(30, min(int(days or 30), 730))
    today = datetime.now(core.LOCAL_TZ).date()
    date_from = (today - timedelta(days=days)).isoformat()
    date_to = today.isoformat()

    base_url = token = None
    invoice_error = ""
    invoice_meta = []
    try:
        base_url, token = core.iiko_server_auth()

        aliases = []
        try:
            contractors = _contractor_catalog(base_url, token)
            aliases = [
                item for item in contractors
                if (supplier_id and item.get("id") == supplier_id)
                or _supplier_alias_match(item.get("name"), supplier_name)
            ]
        except Exception as error:
            invoice_error = f"contractors: {error}"

        alias_map = {}
        for item in aliases:
            key = item.get("id") or _supplier_name_key(item.get("name"))
            if key:
                alias_map[key] = item
        if supplier_id:
            alias_map.setdefault(
                supplier_id,
                {"id": supplier_id, "name": supplier_name, "type": "SUPPLIER"},
            )
        elif supplier_name and not alias_map:
            # No supplier ID means we cannot safely filter the invoice endpoint
            # by contractor. In that rare case the OLAP fallback below is safer.
            aliases = []
        aliases = list(alias_map.values())

        all_rows = []
        seen = set()
        if aliases:
            for alias in aliases:
                alias_id = _norm(alias.get("id"))
                alias_name = _norm(alias.get("name") or supplier_name)
                if not alias_id:
                    continue
                for chunk_from, chunk_to in _date_chunks(date_from, date_to, 90):
                    try:
                        xml_bytes = _incoming_invoice_xml(
                            base_url,
                            token,
                            chunk_from,
                            chunk_to,
                            supplier_id=alias_id,
                        )
                        rows, meta = _parse_incoming_invoice_rows(
                            xml_bytes,
                            fallback_supplier_name=supplier_name or alias_name,
                            fallback_supplier_id=alias_id,
                        )
                        invoice_meta.append({
                            "supplierId": alias_id,
                            "supplierName": alias_name,
                            "from": chunk_from,
                            "to": chunk_to,
                            **meta,
                        })
                        for row in rows:
                            row["supplier"] = supplier_name or alias_name
                            row["supplierId"] = supplier_id or alias_id
                            key = (
                                row.get("date"),
                                row.get("document"),
                                row.get("productId") or row.get("product"),
                                round(_num(row.get("quantity")), 6),
                                round(_num(row.get("sum")), 2),
                                round(_num(row.get("unitPrice")), 4),
                            )
                            if key in seen:
                                continue
                            seen.add(key)
                            all_rows.append(row)
                    except Exception as error:
                        invoice_error = str(error)

        supplier = _supplier_from_invoice_rows(
            all_rows,
            supplier_name,
            supplier_id or (aliases[0].get("id") if aliases else ""),
        )
        if supplier:
            all_dates = [
                point.get("date")
                for product in supplier.get("products") or []
                for point in product.get("history") or []
                if point.get("date")
            ]
            return {
                "success": True,
                "period": {"from": date_from, "to": date_to, "days": days},
                "supplier": supplier,
                "serverFiltered": True,
                "historyMeta": {
                    "source": "incomingInvoice",
                    "sourceLabel": "Приходные накладные iiko",
                    "oldestDate": min(all_dates) if all_dates else "",
                    "newestDate": max(all_dates) if all_dates else "",
                    "points": len(all_dates),
                    "aliases": aliases,
                    "aliasCount": len(aliases),
                    "invoiceChunks": len(invoice_meta),
                    "invoiceRows": len(all_rows),
                    "invoiceMeta": invoice_meta[:20],
                },
            }
    except Exception as error:
        invoice_error = str(error)
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)

    fallback = _build_supplier_history_olap(supplier_name, days, supplier_id)
    meta = fallback.setdefault("historyMeta", {})
    meta["source"] = "transactionsOlapFallback"
    meta["sourceLabel"] = "TRANSACTIONS OLAP (резервный источник)"
    meta["incomingInvoiceError"] = invoice_error
    meta["incomingInvoiceMeta"] = invoice_meta[:10]
    return fallback

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
