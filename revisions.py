import json
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import timedelta

import requests
from flask import jsonify, session

import app as core


CACHE_TTL_SECONDS = 10 * 60
_cache = {}
_lock = threading.Lock()

_REVISION_TERMS = (
    "inventory", "invent", "stocktaking", "stock_taking", "stock taking",
    "reconciliation", "инвентар", "ревиз", "пересчет", "пересчёт",
)

_DOCUMENT_PROBES = (
    "inventory",
    "inventoryDocument",
    "inventoryReconciliation",
    "stocktaking",
    "stockTaking",
)


def _cache_get(key):
    with _lock:
        item = _cache.get(key)
        if not item or item["expires_at"] <= time.time():
            if item:
                _cache.pop(key, None)
            return None
        return item["value"]


def _cache_set(key, value):
    with _lock:
        _cache[key] = {"value": value, "expires_at": time.time() + CACHE_TTL_SECONDS}
        if len(_cache) > 40:
            for old in sorted(_cache, key=lambda k: _cache[k]["expires_at"])[:10]:
                _cache.pop(old, None)


def _matches_revision(value):
    text = str(value or "").strip().lower()
    return any(term in text for term in _REVISION_TERMS)


def _xml_to_obj(node):
    children = list(node)
    if not children:
        return (node.text or "").strip()
    result = {}
    for child in children:
        key = child.tag.split("}")[-1]
        value = _xml_to_obj(child)
        if key in result:
            if not isinstance(result[key], list):
                result[key] = [result[key]]
            result[key].append(value)
        else:
            result[key] = value
    return result


def _decode_response(response):
    text = response.text or ""
    content_type = (response.headers.get("Content-Type") or "").lower()
    if "json" in content_type or text.lstrip().startswith(("{", "[")):
        try:
            return response.json()
        except Exception:
            pass
    if text.lstrip().startswith("<"):
        try:
            root = ET.fromstring(text)
            return {root.tag.split("}")[-1]: _xml_to_obj(root)}
        except Exception:
            pass
    return text[:8000]


def _candidate_strings(value, path="root", output=None):
    if output is None:
        output = []
    if len(output) >= 80:
        return output
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if _matches_revision(key):
                output.append({"path": child_path, "value": str(key)})
            _candidate_strings(item, child_path, output)
    elif isinstance(value, list):
        for idx, item in enumerate(value[:300]):
            _candidate_strings(item, f"{path}[{idx}]", output)
    elif isinstance(value, (str, int, float)) and _matches_revision(value):
        output.append({"path": path, "value": str(value)[:300]})
    return output


def _extract_type_names(payload):
    values = []

    def walk(value):
        if isinstance(value, dict):
            # iiko versions differ: entity type can be returned as name/type/id/code.
            for key in ("name", "type", "entityType", "code", "id"):
                candidate = value.get(key)
                if isinstance(candidate, str) and _matches_revision(candidate):
                    values.append(candidate.strip())
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str) and _matches_revision(value):
            # Plain lists of entity type names are also supported.
            simple = value.strip()
            if re.fullmatch(r"[A-Za-zА-Яа-я0-9_.-]{2,100}", simple):
                values.append(simple)

    walk(payload)
    result = []
    seen = set()
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result[:25]


def _record_list(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("items", "documents", "data", "rows", "result", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    if len(payload) == 1:
        only = next(iter(payload.values()))
        if isinstance(only, list):
            return only
        if isinstance(only, dict):
            return _record_list(only)
    return []


def _find_first(record, names):
    wanted = {x.lower() for x in names}
    queue = [record]
    while queue:
        value = queue.pop(0)
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower() in wanted and item not in (None, "", [], {}):
                    return item
                if isinstance(item, (dict, list)):
                    queue.append(item)
        elif isinstance(value, list):
            queue.extend(value[:50])
    return None


def _safe_document_sample(record):
    if not isinstance(record, dict):
        return {"raw": str(record)[:300]}
    return {
        "id": _find_first(record, ("id", "documentId", "uuid")),
        "date": _find_first(record, ("date", "documentDate", "createdAt", "dateIncoming", "timestamp")),
        "number": _find_first(record, ("number", "documentNumber", "num")),
        "status": _find_first(record, ("status", "state", "documentStatus")),
        "responsible": _find_first(record, ("responsible", "responsibleName", "employeeName", "userName", "author")),
        "store": _find_first(record, ("storeName", "warehouseName", "departmentName", "store", "warehouse")),
        "name": _find_first(record, ("name", "title", "documentType")),
    }


def _get(base_url, token, path, params=None, timeout=18):
    query = {"key": token}
    if params:
        query.update(params)
    return requests.get(f"{base_url}{path}", params=query, timeout=timeout)


def _discover_revision_source(point, weeks):
    today = core.datetime.now(core.LOCAL_TZ).date()
    start = today - timedelta(days=max(14, min(weeks, 26) * 7))
    key = ((point or "").strip().lower(), start.isoformat(), today.isoformat())
    cached = _cache_get(key)
    if cached is not None:
        result = dict(cached)
        result["cache"] = {"hit": True, "ttlSeconds": CACHE_TTL_SECONDS}
        return result

    base_url = None
    token = None
    diagnostics = []
    candidates = []
    found = None
    entity_types = []
    presets_matches = []

    try:
        base_url, token = core.iiko_server_auth()

        # 1. Ask iikoServer which generic entity types this installation exposes.
        try:
            response = _get(base_url, token, "/api/v2/entities/list")
            payload = _decode_response(response)
            diagnostics.append({"probe": "entity-types", "status": response.status_code})
            if response.ok:
                entity_types = _extract_type_names(payload)
                candidates.extend(_candidate_strings(payload))
        except Exception as error:
            diagnostics.append({"probe": "entity-types", "error": str(error)[:250]})

        # 2. Inspect saved report presets; some installations expose inventory reports here.
        try:
            response = _get(base_url, token, "/api/v2/reports/olap/presets")
            payload = _decode_response(response)
            diagnostics.append({"probe": "olap-presets", "status": response.status_code})
            if response.ok:
                presets_matches = _candidate_strings(payload)
                candidates.extend(presets_matches)
        except Exception as error:
            diagnostics.append({"probe": "olap-presets", "error": str(error)[:250]})

        # 3. If a revision-like entity type exists, retrieve it. This is the safest path
        # because the type name is reported by the user's own iikoServer.
        for entity_type in entity_types:
            try:
                response = _get(base_url, token, f"/api/v2/entities/{entity_type}")
                diagnostics.append({"probe": f"entity:{entity_type}", "status": response.status_code})
                if not response.ok:
                    continue
                payload = _decode_response(response)
                records = _record_list(payload)
                if records or _candidate_strings(payload):
                    found = {
                        "kind": "entity",
                        "name": entity_type,
                        "endpoint": f"/api/v2/entities/{entity_type}",
                        "recordCount": len(records),
                        "documents": [_safe_document_sample(x) for x in records[:8]],
                    }
                    break
            except Exception as error:
                diagnostics.append({"probe": f"entity:{entity_type}", "error": str(error)[:250]})

        # 4. Older iikoServer generations expose warehouse documents through export endpoints.
        # We probe a short allow-list and only use an endpoint if this exact server confirms it.
        if not found:
            params = {
                "from": start.strftime("%d.%m.%Y"),
                "to": today.strftime("%d.%m.%Y"),
            }
            for document_type in _DOCUMENT_PROBES:
                path = f"/api/documents/export/{document_type}"
                try:
                    response = _get(base_url, token, path, params=params)
                    diagnostics.append({"probe": f"document:{document_type}", "status": response.status_code})
                    if not response.ok:
                        continue
                    payload = _decode_response(response)
                    records = _record_list(payload)
                    if records:
                        found = {
                            "kind": "document-export",
                            "name": document_type,
                            "endpoint": path,
                            "recordCount": len(records),
                            "documents": [_safe_document_sample(x) for x in records[:8]],
                        }
                        break
                except Exception as error:
                    diagnostics.append({"probe": f"document:{document_type}", "error": str(error)[:250]})

        status = "source_found" if found else ("candidate_found" if candidates else "not_found")
        result = {
            "success": True,
            "status": status,
            "point": point,
            "period": {"from": start.isoformat(), "to": today.isoformat(), "weeks": weeks},
            "source": found,
            "candidateEntityTypes": entity_types,
            "candidateMatches": candidates[:20],
            "presetMatches": presets_matches[:10],
            "diagnostics": diagnostics,
            "nextStep": (
                "normalize_inventory_fields" if found
                else "identify_inventory_document_endpoint"
            ),
            "cache": {"hit": False, "ttlSeconds": CACHE_TTL_SECONDS},
        }
        _cache_set(key, result)
        return result
    finally:
        if base_url and token:
            core.iiko_server_logout(base_url, token)


def install_revisions(app):
    if getattr(app, "_doner_revisions_installed", False):
        return
    app._doner_revisions_installed = True

    @app.before_request
    def _protect_revision_api():
        if core.request.path.startswith("/revision-") and not session.get("dc_authenticated"):
            return jsonify({
                "success": False,
                "code": "AUTH_REQUIRED",
                "message": "Authentication required",
                "login": "/login",
            }), 401
        return None

    @app.route("/revision-discovery")
    def revision_discovery():
        try:
            point = (core.request.args.get("point") or "Arai").strip()
            weeks = int(core.request.args.get("weeks") or 8)
            weeks = max(2, min(weeks, 26))
            return jsonify(_discover_revision_source(point, weeks))
        except requests.HTTPError as error:
            response = error.response
            return jsonify({
                "success": False,
                "code": "REVISION_IIKO_HTTP_ERROR",
                "statusCode": response.status_code if response is not None else None,
                "message": "iikoServer revision discovery request failed",
                "details": response.text[:900] if response is not None else str(error),
            }), 502
        except Exception as error:
            return jsonify({
                "success": False,
                "code": "REVISION_DISCOVERY_ERROR",
                "message": str(error),
            }), 500

    @app.after_request
    def _inject_revisions(response):
        if (
            core.request.path.endswith("dashboard-v2.html")
            and response.status_code == 200
            and response.mimetype == "text/html"
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/revisions.js?v=20260916-1"></script>'
                if tag not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
