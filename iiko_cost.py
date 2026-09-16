import threading
import time

import requests


CACHE_TTL_SECONDS = 6 * 60 * 60
_cache = {"field": None, "label": None, "expires_at": 0.0}
_lock = threading.Lock()


def _columns(base_url, token):
    response = requests.get(
        f"{base_url}/api/v2/reports/olap/columns",
        params={"key": token, "reportType": "SALES"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _entries(payload):
    if isinstance(payload, dict):
        # Normal iikoServer shape: {"Field.Id": {"name": "...", ...}, ...}
        direct = []
        for key, value in payload.items():
            if isinstance(value, dict) and any(
                k in value for k in ("name", "aggregationAllowed", "groupingAllowed", "filteringAllowed")
            ):
                direct.append((str(key), value))
        if direct:
            return direct
        for value in payload.values():
            result = _entries(value)
            if result:
                return result
    elif isinstance(payload, list):
        result = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            field = item.get("id") or item.get("field") or item.get("fieldName") or item.get("key")
            if field:
                result.append((str(field), item))
        if result:
            return result
    return []


def discover_cost_field(base_url, token, force=False):
    now = time.time()
    if not force and _cache.get("field") and _cache.get("expires_at", 0) > now:
        return _cache["field"], _cache.get("label")

    with _lock:
        if not force and _cache.get("field") and _cache.get("expires_at", 0) > time.time():
            return _cache["field"], _cache.get("label")

        payload = _columns(base_url, token)
        entries = _entries(payload)
        by_id = {field: meta for field, meta in entries}

        # Known names seen across iiko versions. Prefer the actual column list from this server.
        candidates = (
            "ProductCostBase.ProductCost",
            "DishCostSum",
            "DishCost",
            "ProductCost",
            "CostSum",
            "Cost",
        )
        chosen = None
        for field in candidates:
            meta = by_id.get(field)
            if meta and meta.get("aggregationAllowed", True):
                chosen = (field, str(meta.get("name") or field))
                break

        if not chosen:
            scored = []
            for field, meta in entries:
                if meta.get("aggregationAllowed") is False:
                    continue
                label = str(meta.get("name") or "")
                text = f"{field} {label}".lower()
                if "себестоим" not in text and "cost" not in text:
                    continue
                # We need total cost, not percentage or unit cost.
                score = 0
                if label.strip().lower() in {"себестоимость", "себестоимость, р.", "cost"}:
                    score += 100
                if "productcostbase.productcost" in field.lower():
                    score += 90
                if "процент" in text or "%" in text or "percent" in text or "pct" in text:
                    score -= 80
                if "единиц" in text or "unit" in text:
                    score -= 60
                if "сум" in text or "sum" in text or "total" in text:
                    score += 15
                scored.append((score, field, label or field))
            if scored:
                scored.sort(reverse=True)
                _, field, label = scored[0]
                chosen = (field, label)

        if not chosen:
            raise RuntimeError("iikoServer SALES OLAP does not expose an aggregate cost field")

        _cache["field"], _cache["label"] = chosen
        _cache["expires_at"] = time.time() + CACHE_TTL_SECONDS
        return chosen


def cost_value(row, field):
    try:
        return float(row.get(field) or 0)
    except (TypeError, ValueError):
        return 0.0
