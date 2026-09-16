from collections import defaultdict
from datetime import datetime

from flask import jsonify, request

from revisions_data_v2 import (
    SCOPES,
    _auth,
    _logout,
    _get_fields,
    _resolve,
    _discover,
    _query_rows,
    _row_store,
    _looks_like_inventory,
    _num,
)
from revisions_data_v3 import _classified_value, _direction


def _quantity_delta(row, names):
    amount_in = abs(_num(row.get("Amount.In")))
    amount_out = abs(_num(row.get("Amount.Out")))
    signed = _num(row.get("Amount.StoreInOutTyped"))
    raw = signed if signed else (amount_in - amount_out)
    direction = _direction(row, names)
    basis = abs(raw) or amount_in or amount_out
    if direction == "shortage":
        return -abs(basis)
    if direction == "surplus":
        return abs(basis)
    return raw


def _unit_cost(row):
    return abs(_num(row.get("Product.AvgSum")))


def _build(scope, period, rows, names, diagnostics):
    revisions = defaultdict(
        lambda: {
            "shortage": 0.0,
            "surplus": 0.0,
            "stores": set(),
            "documents": set(),
        }
    )
    products = defaultdict(
        lambda: {
            "name": None,
            "unit": None,
            "shortage": 0.0,
            "surplus": 0.0,
            "shortageDates": set(),
            "surplusDates": set(),
        }
    )
    documents = defaultdict(
        lambda: {
            "date": None,
            "document": None,
            "store": None,
            "shortage": 0.0,
            "surplus": 0.0,
            "products": defaultdict(
                lambda: {
                    "name": None,
                    "unit": None,
                    "quantityDelta": 0.0,
                    "unitCost": 0.0,
                    "shortage": 0.0,
                    "surplus": 0.0,
                    "rows": 0,
                }
            ),
        }
    )

    matched_rows = 0
    matched_stores = set()
    matched_documents = set()

    for row in rows:
        if not isinstance(row, dict):
            continue
        store = _row_store(scope, row, names["stores"])
        if not store or not _looks_like_inventory(scope, row, names):
            continue

        surplus_value, shortage_value = _classified_value(row, names)
        quantity_delta = _quantity_delta(row, names)
        unit_cost = _unit_cost(row)

        matched_rows += 1
        matched_stores.add(store)

        date_value = str(row.get(names["date"]) or "")[:10] or "Без даты"
        document = str(row.get(names.get("document")) or "").strip() if names.get("document") else ""
        document_label = document or "Без номера"
        if document:
            matched_documents.add(document)

        revision = revisions[date_value]
        revision["stores"].add(store)
        revision["documents"].add(document_label)
        revision["surplus"] += surplus_value
        revision["shortage"] += shortage_value

        product_name = str(row.get(names["product"]) or "Позиция без названия").strip()
        product_id = str(row.get(names.get("productId")) or "").strip() if names.get("productId") else ""
        product_key = product_id or product_name
        unit = ""
        if names.get("unit"):
            unit = str(row.get(names["unit"]) or "").strip()

        item = products[product_key]
        item["name"] = product_name
        if unit:
            item["unit"] = unit
        item["surplus"] += surplus_value
        item["shortage"] += shortage_value
        if shortage_value > 0.005:
            item["shortageDates"].add(date_value)
        if surplus_value > 0.005:
            item["surplusDates"].add(date_value)

        doc_key = (date_value, document_label, store)
        doc = documents[doc_key]
        doc["date"] = date_value
        doc["document"] = document_label
        doc["store"] = store
        doc["shortage"] += shortage_value
        doc["surplus"] += surplus_value

        line = doc["products"][product_key]
        line["name"] = product_name
        if unit:
            line["unit"] = unit
        line["quantityDelta"] += quantity_delta
        if unit_cost:
            line["unitCost"] = unit_cost
        line["shortage"] += shortage_value
        line["surplus"] += surplus_value
        line["rows"] += 1

    history = []
    for date_value, item in sorted(revisions.items(), reverse=True):
        shortage = round(item["shortage"], 2)
        surplus = round(item["surplus"], 2)
        history.append(
            {
                "date": date_value,
                "shortage": shortage,
                "surplus": surplus,
                "gross": round(shortage + surplus, 2),
                "net": round(surplus - shortage, 2),
                "stores": sorted(item["stores"]),
                "documents": sorted(item["documents"]),
            }
        )

    # Change versus the previous revision date. History is newest -> oldest.
    for index, item in enumerate(history):
        previous = history[index + 1] if index + 1 < len(history) else None
        if previous and previous["shortage"]:
            item["shortageChangePct"] = round(
                (item["shortage"] - previous["shortage"]) / previous["shortage"] * 100,
                1,
            )
        else:
            item["shortageChangePct"] = None

    product_rows = []
    for item in products.values():
        shortage = round(item["shortage"], 2)
        surplus = round(item["surplus"], 2)
        product_rows.append(
            {
                "name": item["name"] or "Позиция без названия",
                "unit": item["unit"],
                "shortage": shortage,
                "surplus": surplus,
                "net": round(surplus - shortage, 2),
                "shortageRevisionCount": len(item["shortageDates"]),
                "surplusRevisionCount": len(item["surplusDates"]),
            }
        )

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

    details_by_date = defaultdict(list)
    for doc in documents.values():
        detail_products = []
        for line in doc["products"].values():
            shortage = round(line["shortage"], 2)
            surplus = round(line["surplus"], 2)
            detail_products.append(
                {
                    "name": line["name"] or "Позиция без названия",
                    "unit": line["unit"],
                    "quantityDelta": round(line["quantityDelta"], 3),
                    "unitCost": round(line["unitCost"], 2),
                    "shortage": shortage,
                    "surplus": surplus,
                    "net": round(surplus - shortage, 2),
                    "sourceRows": line["rows"],
                }
            )
        detail_products.sort(key=lambda x: max(x["shortage"], x["surplus"]), reverse=True)
        shortage = round(doc["shortage"], 2)
        surplus = round(doc["surplus"], 2)
        lines_shortage = round(sum(x["shortage"] for x in detail_products), 2)
        lines_surplus = round(sum(x["surplus"] for x in detail_products), 2)
        details_by_date[doc["date"]].append(
            {
                "document": doc["document"],
                "store": doc["store"],
                "shortage": shortage,
                "surplus": surplus,
                "gross": round(shortage + surplus, 2),
                "net": round(surplus - shortage, 2),
                "lineControlDifference": round(
                    abs(shortage - lines_shortage) + abs(surplus - lines_surplus), 2
                ),
                "products": detail_products,
            }
        )

    revision_details = []
    for date_value in sorted(details_by_date.keys(), reverse=True):
        docs = sorted(
            details_by_date[date_value],
            key=lambda x: x["gross"],
            reverse=True,
        )
        revision_details.append({"date": date_value, "documents": docs})

    total_shortage = round(sum(x["shortage"] for x in history), 2)
    total_surplus = round(sum(x["surplus"] for x in history), 2)
    revisions_count = len(history)
    gross_variance = round(total_shortage + total_surplus, 2)
    top5_shortage = sum(x["shortage"] for x in top_shortages[:5])
    top5_surplus = sum(x["surplus"] for x in top_surpluses[:5])

    diagnostics = dict(diagnostics)
    diagnostics["matchedDocuments"] = sorted(matched_documents)[:80]
    diagnostics["calculationMode"] = "inventory account direction + net movement fallback"

    return {
        "success": True,
        "scope": scope,
        "scopeLabel": SCOPES[scope]["label"],
        "period": period,
        "source": "iikoServer TRANSACTIONS OLAP / inventory-account direction",
        "matchedRows": matched_rows,
        "stores": sorted(matched_stores),
        "summary": {
            "lastRevision": history[0]["date"] if history else None,
            "revisionsCount": revisions_count,
            "documentsCount": len(matched_documents),
            "shortage": total_shortage,
            "surplus": total_surplus,
            "grossVariance": gross_variance,
            "net": round(total_surplus - total_shortage, 2),
            "avgShortagePerRevision": round(total_shortage / revisions_count, 2) if revisions_count else 0,
            "avgSurplusPerRevision": round(total_surplus / revisions_count, 2) if revisions_count else 0,
            "top5ShortageShare": round(top5_shortage / total_shortage * 100, 1) if total_shortage else 0,
            "top5SurplusShare": round(top5_surplus / total_surplus * 100, 1) if total_surplus else 0,
        },
        "history": history,
        "revisionDetails": revision_details,
        "topShortages": top_shortages,
        "topSurpluses": top_surpluses,
        "recurringShortages": recurring,
        "discrepancyPercent": None,
        "diagnostics": diagnostics,
        "validation": {
            "lineControl": "Сумма документа сверяется с суммой его строк OLAP",
            "desktopDocumentTotalAvailable": False,
            "note": "Независимый итог окна инвентаризации iikoChain этим OLAP не отдаётся; поэтому контроль 0 ₸ подтверждает внутреннюю согласованность строк, но не является независимой сверкой с экраном iikoChain.",
        },
        "note": "Недостача и излишки классифицируются по бухгалтерским счетам инвентаризации; если подписи счетов недоступны, используется чистое движение, чтобы не удваивать одну проводку.",
    }


def install_revisions_data_v4(app):
    if getattr(app, "_doner_revisions_data_v4_installed", False):
        return
    app._doner_revisions_data_v4_installed = True

    @app.route("/revision-data", methods=["GET"], endpoint="revision_data_v4")
    def revision_data_v4():
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
