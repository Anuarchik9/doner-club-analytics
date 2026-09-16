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


def _direction(row, names):
    """Use iiko shortage/surplus accounts when available.

    Inventory postings are double-entry accounting rows. Treating every Incoming
    amount as a surplus and every Outgoing amount as a shortage can count the two
    sides of the same posting twice. Account names are the strongest signal in
    this database, so classify the row first and only then take its monetary value.
    """
    values = []
    for field in [*names.get("accounts", []), names.get("transaction"), names.get("document")]:
        if field:
            value = str(row.get(field) or "").strip().lower()
            if value:
                values.append(value)
    text = " | ".join(values)
    shortage = "недостач" in text or "shortage" in text
    surplus = "излишк" in text or "surplus" in text
    if shortage and not surplus:
        return "shortage"
    if surplus and not shortage:
        return "surplus"
    return None


def _money_parts(row):
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
    return sum_in, sum_out


def _classified_value(row, names):
    sum_in, sum_out = _money_parts(row)
    direction = _direction(row, names)

    # On an explicitly identified inventory account use one side of the posting,
    # not both. max() protects from builds that expose the same posting value in
    # both Incoming and Outgoing aggregate columns.
    if direction == "shortage":
        return 0.0, max(sum_in, sum_out)
    if direction == "surplus":
        return max(sum_in, sum_out), 0.0

    # Fallback for builds where account labels are unavailable: use the net stock
    # movement instead of counting both sides of a double-entry row.
    if sum_in > sum_out:
        return sum_in - sum_out, 0.0
    if sum_out > sum_in:
        return 0.0, sum_out - sum_in
    return 0.0, 0.0


def _build(scope, period, rows, names, diagnostics):
    revisions = defaultdict(
        lambda: {"shortage": 0.0, "surplus": 0.0, "stores": set(), "documents": set()}
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
        # Keep document discovery even if a zero-cost inventory item has no value.
        matched_rows += 1
        matched_stores.add(store)

        date_value = str(row.get(names["date"]) or "")[:10] or "Без даты"
        document = str(row.get(names.get("document")) or "").strip() if names.get("document") else ""
        if document:
            matched_documents.add(document)

        revision = revisions[date_value]
        revision["stores"].add(store)
        if document:
            revision["documents"].add(document)
        revision["surplus"] += surplus_value
        revision["shortage"] += shortage_value

        product_name = str(row.get(names["product"]) or "Позиция без названия").strip()
        product_id = str(row.get(names.get("productId")) or "").strip() if names.get("productId") else ""
        key = product_id or product_name
        item = products[key]
        item["name"] = product_name
        if names.get("unit"):
            unit = str(row.get(names["unit"]) or "").strip()
            if unit:
                item["unit"] = unit
        item["surplus"] += surplus_value
        item["shortage"] += shortage_value
        if shortage_value > 0.005:
            item["shortageDates"].add(date_value)
        if surplus_value > 0.005:
            item["surplusDates"].add(date_value)

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
        "topShortages": top_shortages,
        "topSurpluses": top_surpluses,
        "recurringShortages": recurring,
        "discrepancyPercent": None,
        "diagnostics": diagnostics,
        "note": "Недостача и излишки классифицируются по бухгалтерским счетам инвентаризации; если подписи счетов недоступны, используется чистое движение, чтобы не удваивать одну проводку.",
    }


def install_revisions_data_v3(app):
    if getattr(app, "_doner_revisions_data_v3_installed", False):
        return
    app._doner_revisions_data_v3_installed = True

    @app.route("/revision-data", methods=["GET"], endpoint="revision_data_v3")
    def revision_data_v3():
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
