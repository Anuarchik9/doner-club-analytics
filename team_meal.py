import sales_channel


TEAM_MEAL_TOKENS = ("депозит", "deposit")


def _team_meal_text(row):
    return sales_channel._text_for_row(row)


def install_team_meal(app):
    if getattr(app, "_doner_team_meal_installed", False):
        return
    app._doner_team_meal_installed = True

    original_specific_channel = sales_channel._specific_channel
    original_row_totals = sales_channel._row_totals
    original_build_mix = sales_channel._build_mix
    original_filter_ui_script = sales_channel._filter_ui_script

    def specific_channel_with_team_meal(row):
        text = _team_meal_text(row)
        if text and any(token in text for token in TEAM_MEAL_TOKENS):
            return "team_meal"
        return original_specific_channel(row)

    def group_for_row_with_team_meal(row):
        channel = specific_channel_with_team_meal(row)
        if channel in {"excluded", "other", "team_meal"}:
            return channel
        return sales_channel.CHANNELS[channel]["group"]

    def row_totals_with_unknown_labels(rows):
        result = original_row_totals(rows)
        unknown = []
        seen = set()
        for row in rows:
            if specific_channel_with_team_meal(row) != "other":
                continue
            parts = []
            for field in sales_channel.CHANNEL_FIELDS:
                value = row.get(field)
                if value not in (None, ""):
                    text = str(value).strip()
                    if text and text not in parts:
                        parts.append(text)
            label = " / ".join(parts) if parts else "Без названия"
            key = label.lower()
            if key not in seen:
                seen.add(key)
                unknown.append(label)
            if len(unknown) >= 12:
                break
        result.setdefault("dimensionValues", {})["Unknown"] = unknown
        return result

    def build_mix_with_team_meal(point, date_from, date_to):
        result = original_build_mix(point, date_from, date_to)
        item = (result.get("channels") or {}).get("team_meal") or {}
        revenue = float(item.get("revenue", 0) or 0)
        checks = float(item.get("checks", 0) or 0)
        result["teamMeal"] = {
            "revenue": round(revenue, 2),
            "checks": round(checks, 3),
            "guests": round(float(item.get("guests", 0) or 0), 3),
            "averageCheck": round(revenue / checks, 2) if checks else 0,
            "label": "Питание команды",
        }
        return result

    def filter_ui_script_with_team_meal():
        script = original_filter_ui_script()
        script = script.replace(
            "const on=mix.online||{},off=mix.offline||{},other=mix.other||{},excluded=mix.excluded||{};",
            "const on=mix.online||{},off=mix.offline||{},other=mix.other||{},excluded=mix.excluded||{},teamMeal=mix.teamMeal||{};",
        )
        old = """if(Number(excluded.revenue||0)>0)note+=` Баллы/бонусы исключены: ${cash(excluded.revenue)}.`;\n    if(Number(other.revenue||0)>0)note+=` Не распределено: ${cash(other.revenue)}.`;"""
        new = """if(Number(excluded.revenue||0)>0)note+=` Баллы/бонусы исключены: ${cash(excluded.revenue)}.`;\n    if(Number(teamMeal.revenue||0)>0)note+=` Команда покушала на эту сумму: ${cash(teamMeal.revenue)}.`;\n    if(Number(other.revenue||0)>0){const unknown=(mix.dimensionValues?.Unknown||[]).slice(0,4);note+=` Не распределено${unknown.length?` (${unknown.join(', ')})`:''}: ${cash(other.revenue)}.`;}"""
        script = script.replace(old, new)
        return script

    sales_channel._specific_channel = specific_channel_with_team_meal
    sales_channel._group_for_row = group_for_row_with_team_meal
    sales_channel._row_totals = row_totals_with_unknown_labels
    sales_channel._build_mix = build_mix_with_team_meal
    sales_channel._filter_ui_script = filter_ui_script_with_team_meal
