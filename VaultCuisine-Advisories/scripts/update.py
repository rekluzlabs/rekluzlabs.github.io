"""Daily advisory monitor. Production writes require two explicit operator gates."""
import argparse
import copy
import datetime as dt
import json
import os
import time
from pathlib import Path

from extract import api_notices, detail_capabilities, generate_content_applicable, lifecycle, lifecycle_notices, migration_risks, prices, roster
from sources import URLS, fetch
from validate import validate

FILES = {"LIFECYCLE": "gemini-lifecycle.json", "COMPATIBILITY": "gemini-compatibility.json", "PRICING": "gemini-pricing.json"}


def material(row):
    value = {k: v for k, v in row.items() if k not in {"verifiedOn", "evidence"}}
    for key in ("facts", "redirectTargets", "replacements"):
        if key in value:
            value[key] = sorted(value[key])
    if "capabilities" in value:
        value["capabilities"] = sorted(value["capabilities"], key=lambda entry: entry["capability"])
    return value


def same_semantics(before, after):
    """Ordering, publication time, source URLs and check dates are not facts."""
    return ({r["modelId"]: material(r) for r in before["records"]} ==
            {r["modelId"]: material(r) for r in after["records"]})


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


def pricing_conflicts(pricing, lifecycle):
    """A free label must not contradict established restricted access."""
    life = {row["modelId"]: row for row in lifecycle["records"]}
    return [f"{row['modelId']}: FREE pricing conflicts with lifecycle ACCESS_RESTRICTED"
            for row in pricing["records"] if row.get("tier") == "FREE" and
            "ACCESS_RESTRICTED" in life.get(row["modelId"], {}).get("facts", [])]


def propose_pricing(current, observed, model_ids, eligible_ids, today, lifecycle=None):
    proposed = copy.deepcopy(current)
    review, changes = [], []
    known = {r["modelId"]: r for r in proposed["records"]}
    life = {r["modelId"]: r for r in lifecycle["records"]} if lifecycle else {}
    if not observed or not model_ids or len(observed) < max(1, len(known) // 2):
        return proposed, ["Pricing extraction incomplete; retained last valid document."], []
    for model in sorted((model_ids & eligible_ids) | set(known)):
        evidence = observed.get(model)
        old = known.get(model)
        if evidence is None:
            # Absence is not a pricing change or a reason to erase old evidence.
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
                status = life.get(model, {})
                restricted = "ACCESS_RESTRICTED" in status.get("facts", [])
                tier = "RESTRICTED_FREE" if restricted else "FREE"
                restrictions = evidence.caveat
                urls = [f"https://aistudio.google.com/docs/pricing#{model}"]
                if restricted:
                    if status.get("restriction") != "EXISTING_ACTIVE_API_USERS":
                        review.append(f"{model}: unsupported lifecycle access restriction requires review")
                        continue
                    restrictions += " API access is limited to existing active users."
                    urls += status["evidence"]
                    if "REDIRECTION_ANNOUNCED" in status.get("facts", []):
                        if not status.get("redirectOn") or not status.get("redirectTargets"):
                            review.append(f"{model}: incomplete announced redirection requires review")
                            continue
                        restrictions += (f" Requests redirect on {status['redirectOn']} to "
                                         f"{', '.join(status['redirectTargets'])} and will be billed at replacement rates.")
                    if len(restrictions) > 320 or len(set(urls)) > 6:
                        review.append(f"{model}: restricted pricing evidence exceeds schema limits")
                        continue
                row = {"modelId": model, "verifiedOn": today,
                       "evidence": list(dict.fromkeys(urls)),
                       "tier": tier, "restrictions": restrictions}
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
            report.append(f"- {name}: retrieved from {URLS[name]}")
        except (KeyError, OSError, UnicodeError, ValueError) as error:
            failures.append(f"{name}: {type(error).__name__}: {error}")
    report += ["", "## Retrieval failures", ""] + ([f"- {v}" for v in failures] if failures else ["- None"]) + [""]
    found_models = roster(sources.get("models", ""))
    pricing = prices(sources.get("pricing", ""))
    life = lifecycle(sources.get("deprecations", ""))
    notices = api_notices(sources.get("changelog", "")) + migration_risks(sources.get("migration", ""))
    proposed = copy.deepcopy(current)
    review, known_findings, coverage = [], [], []
    known_compat = {r["modelId"]: r for r in current["COMPATIBILITY"]["records"]}
    eligible = {model for model, row in known_compat.items() if row.get("purpose") == "GENERAL_PURPOSE"}
    known_life = {r["modelId"]: r for r in current["LIFECYCLE"]["records"]}
    prior_roster = {model for model in known_compat if model.startswith("gemini-")}
    roster_ok = ("models" in sources and len(found_models) >= max(8, len(prior_roster) // 2)
                 and len(found_models & prior_roster) >= max(4, len(prior_roster) // 2))
    pricing_ok = "pricing" in sources and len(pricing) >= max(1, len(current["PRICING"]["records"]) // 2)
    life_ok = "deprecations" in sources and len(life) >= max(1, len(known_life) // 2)
    if not roster_ok:
        coverage.append("Model roster semantic extraction incomplete; compatibility and new-model pricing retained.")
    if not pricing_ok:
        coverage.append("Exact Standard pricing extraction incomplete; pricing retained.")
    if not life_ok:
        coverage.append("Lifecycle table extraction incomplete; lifecycle retained.")
    if roster_ok and pricing_ok:
        proposed["PRICING"], items, _ = propose_pricing(current["PRICING"], pricing, found_models, eligible, today.date().isoformat(), current["LIFECYCLE"])
        for item in items:
            model = item.split(":", 1)[0]
            old = next((r for r in current["PRICING"]["records"] if r["modelId"] == model), None)
            evidence = pricing.get(model)
            if old and evidence and (old.get("tier") == evidence.tier and not evidence.confident or
                    old.get("tier") == "RESTRICTED_FREE" and evidence.tier == "FREE" and
                    "limiting access to the 2.5" in sources.get("models", "").lower()):
                known_findings.append(item)
            else:
                review.append(item)
    priced_ids = {r["modelId"] for r in current["PRICING"]["records"]}
    unpriced_general = eligible - priced_ids
    lifecycle_filtered = {model for model in unpriced_general if model in known_life and
        set(known_life[model]["facts"]) & {"DEPRECATED", "REDIRECTION_ACTIVE", "REDIRECTION_ANNOUNCED", "SHUT_DOWN"}}
    if unpriced_general - lifecycle_filtered:
        coverage.append("General-purpose models lack exact pricing: " + ", ".join(sorted(unpriced_general - lifecycle_filtered)))
    if life_ok:
        for model, item in sorted(life.items()):
            old = known_life.get(model)
            if old is None:
                if model not in eligible or not roster_ok or model not in found_models:
                    continue  # Specialist and unverified models never enter this selector.
                if item.get("facts") == ["NO_SHUTDOWN_ANNOUNCED"]:
                    proposed["LIFECYCLE"]["records"].append({"modelId": model, "verifiedOn": today.date().isoformat(),
                        "facts": ["NO_SHUTDOWN_ANNOUNCED"], "evidence": ["https://aistudio.google.com/docs/deprecations"]})
                else:
                    review.append(f"Lifecycle {model}: {item.get('review', 'new documented change requires review')}")
                continue
            if item.get("facts") == ["NO_SHUTDOWN_ANNOUNCED"]:
                if "NO_SHUTDOWN_ANNOUNCED" not in old["facts"]:
                    review.append(f"Lifecycle {model}: documented no-shutdown status differs from established facts")
                continue
            if "review" in item:
                if item.get("kind") == "ACTIVE_REDIRECTION" and "REDIRECTION_ACTIVE" in old["facts"] and set(item["targets"]) == set(old.get("redirectTargets", [])):
                    continue
                try:
                    day = dt.datetime.strptime(item.get("date", ""), "%B %d, %Y").date().isoformat()
                except ValueError:
                    day = None
                if item.get("kind") == "ANNOUNCED_REDIRECTION" and "REDIRECTION_ANNOUNCED" in old["facts"] and day == old.get("redirectOn") and set(item["targets"]) == set(old.get("redirectTargets", [])):
                    continue
                if item.get("kind") == "EARLIEST_SHUTDOWN" and day == old.get("shutdownOn"):
                    continue
                review.append(f"Lifecycle {model}: {item['review']}")
        proposed["LIFECYCLE"]["records"].sort(key=lambda row: row["modelId"])
    review.extend(lifecycle_notices(sources.get("changelog", ""), known_life, eligible, today.date()))
    compatibility_candidates = 0
    if roster_ok:
        for model in sorted(found_models & eligible):
            row = next(r for r in proposed["COMPATIBILITY"]["records"] if r["modelId"] == model)
            if row.get("withdrawn"):
                continue
            key = f"detail:{model}"
            try:
                if documents is None:
                    time.sleep(0.3)
                detail = documents.get(key) if documents is not None else fetch(f"https://aistudio.google.com/docs/models/{model}.md")[0]
                found = detail_capabilities(detail or "", model)
            except (OSError, UnicodeError, ValueError, KeyError):
                continue  # A detail-page failure never modifies an existing row.
            if not found:
                continue
            compatibility_candidates += 1
            # Input/output on a model page does not establish GenerateContent
            # applicability. Interactions-only claims must remain unknown.
            if not generate_content_applicable(detail):
                continue
            prior = {v["capability"]: v["support"] for v in row["capabilities"]}
            conflicts = [cap for cap, support in found.items() if prior.get(cap) not in (None, "UNKNOWN", support)]
            if conflicts:
                review.append(f"Compatibility {model}: conflicting exact capability evidence: {', '.join(conflicts)}")
                continue
            changed_caps = [cap for cap, support in found.items() if prior.get(cap) != support]
            if changed_caps:
                if row["verifiedOn"] >= today.date().isoformat():
                    review.append(f"Compatibility {model}: same-day material change requires correction review")
                    continue
                url = f"https://aistudio.google.com/docs/models/{model}"
                if url not in row["evidence"] and len(row["evidence"]) >= 6:
                    review.append(f"Compatibility {model}: evidence URL limit requires review")
                    continue
                prior.update(found)
                row["capabilities"] = [{"capability": cap, "support": prior[cap]} for cap in sorted(prior)]
                row["verifiedOn"] = today.date().isoformat()
                row["evidence"] = list(dict.fromkeys([*row["evidence"], url]))
    report += ["## Source retrieval", "", f"- Successful: {len(sources)}/5", f"- Failed: {len(failures)}", ""]
    report += ["## Semantic extraction and coverage", "", f"- Exact roster IDs: {len(found_models)} ({'complete' if roster_ok else 'blocked'})",
        f"- Exact pricing sections: {len(pricing)} ({'complete' if pricing_ok else 'blocked'})",
        f"- Existing general-purpose roster: {len(eligible)}; priced: {len(eligible & priced_ids)}; lifecycle-filtered without pricing: {len(lifecycle_filtered)}",
        f"- Lifecycle table models: {len(life)} ({'complete' if life_ok else 'blocked'})",
        f"- Exact capability candidates: {compatibility_candidates}; API-family evidence required", ""]
    report += ["## Coverage blockers", ""] + ([f"- {v}" for v in coverage] if coverage else ["- None"]) + [""]
    report += ["## Previously known findings", "", f"- {len(known_findings)} unchanged pricing caveats or access restrictions (details in notices.json)", ""]
    report += ["## New actionable review", ""] + ([f"- {v}" for v in review[:20]] if review else ["- None"])
    if len(review) > 20:
        report.append(f"- {len(review) - 20} additional findings in notices.json")
    report.append("")
    report += ["## Potential API changes", ""]
    report += [f"- {n['date']}: {n['summary']} — {n.get('source', URLS['changelog'])}" for n in notices] or ["- None detected"]
    report += ["", "## Publication decision", ""]
    changes = []
    for kind in FILES:
        if same_semantics(proposed[kind], current[kind]):
            proposed[kind] = copy.deepcopy(current[kind])
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
        report.append(f"- {kind}: validated proposal; revision {current[kind]['revision']} -> {proposed[kind]['revision']}")
        report.extend(f"  - {line}" for line in semantic_changes(current[kind], proposed[kind]))
    validation_findings = [item for item in review if "proposed document rejected" in item]
    cross_conflicts = pricing_conflicts(proposed["PRICING"], proposed["LIFECYCLE"])
    review.extend(cross_conflicts)
    if cross_conflicts:
        report += ["", "## Cross-catalogue conflicts", ""] + [f"- {item}" for item in cross_conflicts]
    if validation_findings:
        report += ["", "## Validation findings", ""] + [f"- {item}" for item in validation_findings]
    report += ["", "## Publication blockers", ""]
    report.append("- Automatic publication is disabled for this dry run." if not publish else "- Publication gates were explicitly enabled for this run.")
    if failures or coverage:
        report.append(f"- Source/coverage blockers: {len(failures) + len(coverage)} (see above and notices.json).")
    if review:
        report.append(f"- New actionable findings: {len(review)} require developer review.")
    if not failures and not coverage and not review:
        report.append("- No extraction or review blockers detected.")
    if publish and (failures or coverage or review):
        raise ValueError("publication blocked by source, coverage, or review findings: " +
                         "; ".join([*failures, *coverage, *review]))
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (output / "notices.json").write_text(json.dumps({"review": review, "known": known_findings,
        "coverage": coverage, "failures": failures, "api": notices}, indent=2) + "\n", encoding="utf-8")
    for kind in changes:
        name = FILES[kind]
        payload = json.dumps(proposed[kind], ensure_ascii=False, indent=2) + "\n"
        (output / name).write_text(payload, encoding="utf-8")
    if publish:
        for kind in changes:
            name = FILES[kind]
            (root / name).write_bytes((output / name).read_bytes())
    return {"failures": failures, "review": review, "known": known_findings,
            "coverage": coverage, "changes": changes, "api": notices}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    result = run(args.root, args.output, None, args.publish)
    print(json.dumps({k: len(v) for k, v in result.items()}, sort_keys=True))
