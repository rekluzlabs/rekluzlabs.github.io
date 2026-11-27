"""Independent conservative mirror of the Android v1 validators; Android remains authoritative."""
import copy
import datetime as dt
import json
import re
import unicodedata
from urllib.parse import urlsplit

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
FACTS = set("NO_SHUTDOWN_ANNOUNCED DEPRECATED EARLIEST_SHUTDOWN SCHEDULED_SHUTDOWN SHUT_DOWN REDIRECTION_ANNOUNCED REDIRECTION_ACTIVE ACCESS_RESTRICTED WITHDRAWN".split())
CAPS = set("GENERATE_CONTENT TEXT_INPUT TEXT_OUTPUT IMAGE_INPUT JSON_MIME_TYPE RESPONSE_SCHEMA PLAIN_TEXT_MIME_TYPE MAX_OUTPUT_TOKENS".split())
COMMON = {"modelId", "verifiedOn", "evidence", "correction"}
ENVELOPE = {"schemaVersion", "revision", "publishedAt", "provider", "api", "records"}


def date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("invalid date")
    return dt.date.fromisoformat(value)


def evidence(url):
    p = urlsplit(url)
    return (len(url) <= 256 and p.scheme == "https" and p.hostname in {"ai.google.dev", "aistudio.google.com"}
            and not p.username and p.port is None and not p.query and
            p.path.startswith(("/docs/", "/gemini-api/docs/", "/api/", "/api-reference/")))


def validate(document, kind, previous=None, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    raw = json.dumps(document, ensure_ascii=False).encode("utf-8")
    if len(raw) > 128 * 1024 or not isinstance(document, dict):
        raise ValueError("invalid size or envelope")
    keys = ENVELOPE | ({"kind"} if kind != "LIFECYCLE" else set())
    if set(document) != keys or document["schemaVersion"] != 1 or type(document["revision"]) is not int or not 1 <= document["revision"] <= 2_147_483_647 or document["provider"] != "google" or document["api"] != "gemini-developer/v1beta" or (kind != "LIFECYCLE" and document["kind"] != kind):
        raise ValueError("unsupported envelope")
    published = dt.datetime.fromisoformat(document["publishedAt"].replace("Z", "+00:00"))
    if published.tzinfo is None or published > now or len(document["publishedAt"]) > 40:
        raise ValueError("publication time")
    rows = document["records"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 256:
        raise ValueError("empty or oversized catalogue")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not COMMON - {"correction"} <= row.keys() or not ID.fullmatch(row["modelId"]):
            raise ValueError("invalid model row")
        model = row["modelId"]
        if model in seen:
            raise ValueError("duplicate model")
        seen.add(model)
        checked = date(row["verifiedOn"])
        if not 2023 <= checked.year or checked > published.date():
            raise ValueError("verification date")
        ev = row["evidence"]
        if not isinstance(ev, list) or not 1 <= len(ev) <= 6 or len(ev) != len(set(ev)) or not all(isinstance(u, str) and evidence(u) for u in ev):
            raise ValueError("invalid evidence")
        if kind == "PRICING":
            allowed = COMMON | {"tier", "restrictions", "withdrawn"}
            if row.get("withdrawn"):
                if not row.get("correction") or "tier" in row or "restrictions" in row:
                    raise ValueError("invalid withdrawal")
            elif row.get("tier") not in {"FREE", "PAID_ONLY", "RESTRICTED_FREE", "UNKNOWN"} or not isinstance(row.get("restrictions"), str) or len(row["restrictions"]) > 320 or any(unicodedata.category(ch) in {"Cc", "Cf"} for ch in row["restrictions"]) or (row["tier"] == "RESTRICTED_FREE" and not row["restrictions"].strip()):
                raise ValueError("invalid pricing")
        elif kind == "COMPATIBILITY":
            allowed = COMMON | {"purpose", "release", "releaseDate", "capabilities", "withdrawn"}
            if row.get("withdrawn"):
                if not row.get("correction") or any(k in row for k in ("purpose", "release", "capabilities")):
                    raise ValueError("invalid withdrawal")
            elif row.get("purpose") not in {"GENERAL_PURPOSE", "SPECIALIST", "UNKNOWN"} or row.get("release") not in {"STABLE", "PREVIEW", "UNKNOWN"} or not isinstance(row.get("capabilities"), list):
                raise ValueError("invalid compatibility")
            if "releaseDate" in row and date(row["releaseDate"]) > checked:
                raise ValueError("release after verification")
            names = [v.get("capability") for v in row.get("capabilities", [])]
            if len(names) != len(set(names)) or any(n not in CAPS for n in names) or any(v.get("support") not in {"SUPPORTED", "UNSUPPORTED", "UNKNOWN"} or set(v) != {"capability", "support"} for v in row.get("capabilities", [])):
                raise ValueError("invalid capabilities")
        else:
            allowed = COMMON | {"facts", "shutdownOn", "redirectOn", "redirectTargets", "replacements", "restriction"}
            facts = row.get("facts")
            if not isinstance(facts, list) or not facts or len(facts) != len(set(facts)) or not set(facts) <= FACTS:
                raise ValueError("invalid facts")
            shutdown = set(facts) & {"EARLIEST_SHUTDOWN", "SCHEDULED_SHUTDOWN", "SHUT_DOWN"}
            redirect = set(facts) & {"REDIRECTION_ANNOUNCED", "REDIRECTION_ACTIVE"}
            if len(shutdown) > 1 or len(redirect) > 1 or ("shutdownOn" in row and (not shutdown or not date(row["shutdownOn"]))) or ("redirectOn" in row and (not redirect or not date(row["redirectOn"]))) or ("NO_SHUTDOWN_ANNOUNCED" in facts and shutdown) or ("WITHDRAWN" in facts and (facts != ["WITHDRAWN"] or not row.get("correction"))):
                raise ValueError("invalid lifecycle facts")
            if "SHUT_DOWN" in facts and "shutdownOn" in row and date(row["shutdownOn"]) > checked:
                raise ValueError("future confirmed shutdown")
            if "REDIRECTION_ACTIVE" in facts and "redirectOn" in row and date(row["redirectOn"]) > checked:
                raise ValueError("future active redirect")
            for field in ("redirectTargets", "replacements"):
                values = row.get(field, [])
                if not isinstance(values, list) or len(values) > 8 or len(values) != len(set(values)) or any(not ID.fullmatch(v) or v == model for v in values):
                    raise ValueError("invalid model targets")
            if bool(redirect) != bool(row.get("redirectTargets")) or ("ACCESS_RESTRICTED" in facts) != (row.get("restriction") == "EXISTING_ACTIVE_API_USERS"):
                raise ValueError("invalid lifecycle metadata")
        if not set(row) <= allowed or ("correction" in row and type(row["correction"]) is not bool) or ("withdrawn" in row and type(row["withdrawn"]) is not bool):
            raise ValueError("unsupported row field")
    if previous:
        if document["revision"] <= previous["revision"] or published < dt.datetime.fromisoformat(previous["publishedAt"].replace("Z", "+00:00")):
            raise ValueError("revision rollback")
        current = {r["modelId"]: r for r in rows}
        for old in previous["records"]:
            new = current.get(old["modelId"])
            if not new or date(new["verifiedOn"]) < date(old["verifiedOn"]):
                raise ValueError("missing or older prior evidence")
            a, b = copy.deepcopy(old), copy.deepcopy(new)
            for v in (a, b):
                for key in ("verifiedOn", "evidence", "correction"):
                    v.pop(key, None)
            if a != b and not new.get("correction") and new["verifiedOn"] == old["verifiedOn"]:
                raise ValueError("same-date material change")
    return True
