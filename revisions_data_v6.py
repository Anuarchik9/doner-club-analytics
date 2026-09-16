from datetime import datetime
from collections import defaultdict

from flask import jsonify, request

from revisions_data_v2 import (
    SCOPES,
    _auth,
    _logout,
    _get_fields,
    _resolve,
    _discover,
    _query_rows,
)
from revisions_data_v5 import _build as _build_v5


def _streaks(revision_dates, shortage_dates):
    shortage_dates = set(shortage_dates)
    current = 0
    for date_value in revision_dates:
        if date_value in shortage_dates:
            current += 1
        else:
            break

    best = 0
    run = 0
    for date_value in revision_dates:
        if date_value in shortage_dates:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return current, best


def _enrich(result):
    history = result.get("history") or []
    revision_dates = [item.get("date") for item in history if item.get("date")]

    per_product = defaultdict(
        lambda: {
            "name": None,
            "unit": None,
            "shortage": 0.0,
            "surplus": 0.0,
            "byDate": defaultdict(lambda: {"shortage": 0.0, "surplus": 0.0}),
        }
    )

    for revision in result.get("revisionDetails") or []:
        date_value = revision.get("date")
        if not date_value:
            continue
        for document in revision.get("documents") or []:
            for line in document.get("products") or []:
                name = str(line.get("name") or "Позиция без названия").strip()
                unit = str(line.get("unit") or "").strip()
                item = per_product[name]
                item["name"] = name
                if unit:
                    item["unit"] = unit
                shortage = float(line.get("shortage") or 0)
                surplus = float(line.get("surplus") or 0)
                item["shortage"] += shortage
                item["surplus"] += surplus
                item["byDate"][date_value]["shortage"] += shortage
                item["byDate"][date_value]["surplus"] += surplus

    product_trends = []
    for item in per_product.values():
        shortage_dates = [
            date_value
            for date_value in revision_dates
            if item["byDate"][date_value]["shortage"] > 0.005
        ]
        current_streak, max_streak = _streaks(revision_dates, shortage_dates)
        latest_shortage = (
            item["byDate"][revision_dates[0]]["shortage"] if revision_dates else 0.0
        )
        previous_shortage = (
            item["byDate"][revision_dates[1]]["shortage"] if len(revision_dates) > 1 else 0.0
        )
        shortage_trend_pct = None
        if previous_shortage > 0.005:
            shortage_trend_pct = round(
                (latest_shortage - previous_shortage) / previous_shortage * 100, 1
            )

        product_trends.append(
            {
                "name": item["name"],
                "unit": item["unit"],
                "shortage": round(item["shortage"], 2),
                "surplus": round(item["surplus"], 2),
                "shortageRevisionCount": len(shortage_dates),
                "shortageDates": shortage_dates,
                "currentShortageStreak": current_streak,
                "maxShortageStreak": max_streak,
                "latestShortage": round(latest_shortage, 2),
                "previousShortage": round(previous_shortage, 2),
                "shortageTrendPct": shortage_trend_pct,
            }
        )

    system_problems = sorted(
        (
            item
            for item in product_trends
            if item["shortageRevisionCount"] >= 2
        ),
        key=lambda item: (
            item["currentShortageStreak"],
            item["maxShortageStreak"],
            item["shortageRevisionCount"],
            item["shortage"],
        ),
        reverse=True,
    )[:10]

    latest_problem = sorted(
        (item for item in product_trends if item["latestShortage"] > 0.005),
        key=lambda item: item["latestShortage"],
        reverse=True,
    )

    result["productTrends"] = product_trends
    result["systemProblems"] = system_problems
    result["latestTopShortage"] = latest_problem[0] if latest_problem else None

    if history:
        result.setdefault("summary", {})["latestShortage"] = round(
            float(history[0].get("shortage") or 0), 2
        )
        result["summary"]["latestSurplus"] = round(
            float(history[0].get("surplus") or 0), 2
        )
        result["summary"]["latestNet"] = round(
            float(history[0].get("net") or 0), 2
        )
        result["summary"]["latestShortageChangePct"] = history[0].get(
            "shortageChangePct"
        )

    result["trendNote"] = (
        "Подряд считается по последовательности проведённых ревизий выбранного направления, "
        "а не по календарным дням."
    )
    return result


def install_revisions_data_v6(app):
    if getattr(app, "_doner_revisions_data_v6_installed", False):
        return
    app._doner_revisions_data_v6_installed = True

    @app.route("/revision-data", methods=["GET"], endpoint="revision_data_v6")
    def revision_data_v6():
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
            result = _build_v5(scope, period, rows, names, diagnostics)
            result = _enrich(result)
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
