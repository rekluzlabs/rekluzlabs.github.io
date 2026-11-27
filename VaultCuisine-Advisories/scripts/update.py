"""Daily advisory monitor. Production writes require two explicit operator gates."""
import argparse
import copy
import datetime as dt
import json
import os
import time
from pathlib import Path

from extract import api_notices, capabilities, detail_capabilities, lifecycle, lifecycle_notices, migration_risks, prices, roster
from sources import URLS, fetch
from validate import validate

FILES = {"LIFECYCLE": "gemini-lifecycle.json", "COMPATIBILITY": "gemini-compatibility.json", "PRICING": "gemini-pricing.json"}


def material(row):
    return {k: v for k, v in row.items() if k not in {"verifiedOn", "evidence", "correction"}}


def semantic_changes(before, after):
    old = {r["modelId"]: r for r in before["records"]}
    new = {r["modelId"]: r for r in after["records"]}
    result = []
    for model in sorted(set(old) | set(new)):
        if model not in old:
            result.append(f"added {model}: {material(new[model])}")
        elif model not in new:
            result.append(f"removed {model}: BLOCKED")
        elif material(old[model]) != material(new[model]):
            result.append(f"changed {model}: {material(old[model])} -> {material(new[model])}")
    return result


def propose_pricing(current, observed, model_ids, eligible_ids, today):
    proposed = copy.deepcopy(current)
    review, changes = [], []
    known = {r["modelId"]: r for r in proposed["records"]}
    if not observed or not model_ids or len(observed) < max(1, len(known) // 2):
        return proposed, ["Pricing extraction incomplete; retained last valid document."], []
    for model in sorted(model_ids | set(known)):
        evidence = observed.get(model)
        old = known.get(model)
        if evidence is None:
            review.append(f"{model}: no exact Standard pricing evidence")
            continue
        if not evidence.confident:
            review.append(f"{model}: ambiguous or conflicting pricing ({evidence.caveat})")
            continue
        if old and old.get("tier") == evidence.tier:
            continue  # Do not renew verification dates on unchanged material.
        # Material financial changes, including first-time paid-only claims, require review.
        if old and old.get("tier") != evidence.tier:
            review.append(f"{model}: classification {old.get('tier')} -> {evidence.tier} requires review")
            continue
        if not old:
            if model in eligible_ids and evidence.tier == "FREE":
                row = {"modelId": model, "verifiedOn": today,
                       "evidence": [f"https://aistudio.google.com/docs/pricing#{model}"],
                       "tier": evidence.tier, "restrictions": evidence.caveat}
                proposed["records"].append(row)
                changes.append(model)
            else:
                review.append(f"{model}: new exact pricing {evidence.tier} requires model and entitlement review")
    if changes:
        proposed["records"].sort(key=lambda row: row["modelId"])
    return proposed, review, changes


def run(root, output, documents, publish=False, today=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    if root.name != "VaultCuisine-Advisories" or not (root / "scripts" / "update.py").is_file():
        raise ValueError("advisory root must be the publication package")
    if publish and (os.getenv("VC_ADVISORY_PUBLISH") != "true" or os.getenv("VC_LIVE_SYNC_VERIFIED") != "true"):
        raise ValueError("publication gates are not enabled")
    today = today or dt.datetime.now(dt.timezone.utc)
    current = {kind: json.loads((root / name).read_text(encoding="utf-8")) for kind, name in FILES.items()}
    for kind, doc in current.items():
        validate(doc, kind, now=today)
    report = ["# VaultCuisine advisory maintenance dry run", "", f"Checked at: {today.isoformat()}", ""]
    failures = []
    sources = {}
    for name in URLS:
        try:
            sources[name] = documents[name] if documents is not None else fetch(URLS[name])[0]
            if not isinstance(sources[name], str) or len(sources[name]) < 100:
                raise ValueError("empty or incomplete source")
            report.append(f"- {name}: retrieved and parsed from {URLS[name]}")
        except (KeyError, OSError, UnicodeError, ValueError) as error:
            failures.append(f"{name}: {type(error).__name__}: {error}")
    report += ["", "## Extraction failures", ""] + ([f"- {v}" for v in failures] if failures else ["- None"]) + [""]
    found_models = roster(sources.get("models", ""))
    pricing = prices(sources.get("pricing", ""))
    life = lifecycle(sources.get("deprecations", ""))
    compat = capabilities(sources.get("models", ""))
    notices = api_notices(sources.get("changelog", "")) + migration_risks(sources.get("migration", ""))
    proposed = copy.deepcopy(current)
    review = []
    if found_models and pricing:
        eligible = {r["modelId"] for r in current["COMPATIBILITY"]["records"] if r.get("purpose") == "GENERAL_PURPOSE"}
        proposed["PRICING"], items, _ = propose_pricing(current["PRICING"], pricing, found_models, eligible, today.date().isoformat())
        review.extend(items)
    else:
        review.append("Pricing or model roster extraction empty; pricing retained.")
    known_life = {r["modelId"] for r in current["LIFECYCLE"]["records"]}
    if len(life) < max(1, len(known_life) // 2):
        review.append("Lifecycle extraction unexpectedly incomplete; lifecycle retained.")
    else:
        for model, item in sorted(life.items()):
            if model not in known_life and item.get("facts") == ["NO_SHUTDOWN_ANNOUNCED"] and model in found_models:
                proposed["LIFECYCLE"]["records"].append({"modelId": model, "verifiedOn": today.date().isoformat(),
                    "facts": ["NO_SHUTDOWN_ANNOUNCED"], "evidence": ["https://aistudio.google.com/docs/deprecations"]})
            elif model not in known_life or "review" in item:
                review.append(f"Lifecycle {model}: {item.get('review', 'new documented model; inspect deprecation table')}")
    review.extend(lifecycle_notices(sources.get("changelog", "")))
    proposed["LIFECYCLE"]["records"].sort(key=lambda row: row["modelId"])
    known_compat = {r["modelId"] for r in current["COMPATIBILITY"]["records"]}
    if len(found_models) < max(1, len([x for x in known_compat if x.startswith("gemini-")]) // 2):
        review.append("Model roster unexpectedly incomplete; compatibility retained.")
        found_models = set()
    for model in sorted(found_models - known_compat):
        if model in compat:
            proposed["COMPATIBILITY"]["records"].append({"modelId": model, "verifiedOn": today.date().isoformat(),
                "evidence": ["https://aistudio.google.com/docs/models"], "purpose": "UNKNOWN", "release": "UNKNOWN",
                "capabilities": []})
        review.append(f"Compatibility {model}: newly listed; exact API and feature evidence required; remains UNKNOWN")
    proposed["COMPATIBILITY"]["records"].sort(key=lambda row: row["modelId"])
    if len(found_models) > 60:
        review.append("Model roster exceeds the bounded per-model documentation budget; compatibility unchanged.")
        proposed["COMPATIBILITY"] = copy.deepcopy(current["COMPATIBILITY"])
    elif found_models:
        for row in proposed["COMPATIBILITY"]["records"]:
            model = row["modelId"]
            if model not in found_models or row.get("withdrawn"):
                continue
            key = f"detail:{model}"
            try:
                if documents is None:
                    time.sleep(0.3)
                detail = documents.get(key) if documents is not None else fetch(f"https://aistudio.google.com/docs/models/{model}")[0]
                if not detail:
                    continue
                found = detail_capabilities(detail, model)
            except (OSError, UnicodeError, ValueError) as error:
                review.append(f"Compatibility {model}: model detail unavailable ({type(error).__name__})")
                continue
            if not found:
                review.append(f"Compatibility {model}: no exact input/output evidence in model detail")
                continue
            prior = {v["capability"]: v["support"] for v in row["capabilities"]}
            conflicts = [cap for cap, support in found.items() if prior.get(cap) not in (None, "UNKNOWN", support)]
            if conflicts:
                review.append(f"Compatibility {model}: conflicting explicit capability evidence: {', '.join(conflicts)}")
                continue
            changed_caps = [cap for cap, support in found.items() if prior.get(cap) != support]
            if changed_caps:
                if row["verifiedOn"] >= today.date().isoformat():
                    review.append(f"Compatibility {model}: same-day material change needs explicit correction review")
                    continue
                url = f"https://aistudio.google.com/docs/models/{model}"
                if url not in row["evidence"] and len(row["evidence"]) >= 6:
                    review.append(f"Compatibility {model}: evidence URL limit needs review")
                    continue
                prior.update(found)
                row["capabilities"] = [{"capability": cap, "support": prior[cap]} for cap in sorted(prior)]
                row["verifiedOn"] = today.date().isoformat()
                row["evidence"] = list(dict.fromkeys([*row["evidence"], url]))
    report += ["## Coverage", "", f"- Explicit model codes: {len(found_models)}", f"- Exact pricing sections: {len(pricing)}", f"- Lifecycle rows: {len(life)}", f"- Compatibility candidates: {len(compat)}", ""]
    report += ["## Human review", ""] + ([f"- {v}" for v in review] if review else ["- None"]) + [""]
    report += ["## Potential API changes", ""]
    report += [f"- {n['date']}: {n['summary']} — {n.get('source', URLS['changelog'])}" for n in notices] or ["- None detected"]
    report += ["", "## Publication decision", ""]
    changes = []
    for kind in FILES:
        if proposed[kind] == current[kind]:
            report.append(f"- {kind}: no safe semantic change; no revision or commit")
            continue
        proposed[kind]["revision"] += 1
        proposed[kind]["publishedAt"] = today.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        try:
            validate(proposed[kind], kind, previous=current[kind], now=today)
        except ValueError as error:
            review.append(f"{kind}: proposed document rejected ({error}); retained last valid document")
            proposed[kind] = copy.deepcopy(current[kind])
            report.append(f"- {kind}: validation failed; no proposal published")
            continue
        changes.append(kind)
        report.append(f"- {kind}: validated proposal")
        report.extend(f"  - {line}" for line in semantic_changes(current[kind], proposed[kind]))
    validation_findings = [item for item in review if "proposed document rejected" in item]
    if validation_findings:
        report += ["", "## Validation findings", ""] + [f"- {item}" for item in validation_findings]
    if failures or review:
        report.append("- Human review required for listed findings; existing files preserved.")
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (output / "notices.json").write_text(json.dumps({"review": review, "failures": failures, "api": notices}, indent=2) + "\n", encoding="utf-8")
    for kind in changes:
        name = FILES[kind]
        payload = json.dumps(proposed[kind], ensure_ascii=False, indent=2) + "\n"
        (output / name).write_text(payload, encoding="utf-8")
        if publish:
            (root / name).write_text(payload, encoding="utf-8")
    return {"failures": failures, "review": review, "changes": changes, "api": notices}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    result = run(args.root, args.output, None, args.publish)
    print(json.dumps({k: len(v) for k, v in result.items()}, sort_keys=True))
