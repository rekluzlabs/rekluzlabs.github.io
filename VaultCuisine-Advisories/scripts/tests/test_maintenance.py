import copy
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1]
ROOT = SCRIPT.parent
sys.path.insert(0, str(SCRIPT))
from extract import api_notices, capabilities, detail_capabilities, generate_content_applicable, lifecycle, lifecycle_notices, prices, roster
from check_paths import check
from notify import issue_plan, notify
from sources import approved, fetch
from update import run, propose_pricing, pricing_conflicts, same_semantics
from validate import validate

FIX = Path(__file__).parent / "fixtures"
DOCS = {name: (FIX / f"{name}.md").read_text(encoding="utf-8") for name in ("models", "pricing", "deprecations", "changelog")}
DOCS["migration"] = "# Migration\n" + "GenerateContent remains available. " * 10
NOW = dt.datetime(2026, 11, 27, 12, tzinfo=dt.timezone.utc)
TEMP_ROOT = Path(os.environ.get("RUNNER_TEMP", "D:/codex-cache/work/vaultcuisine-stage8d4" if os.name == "nt" else "/tmp"))
TEMP_ROOT.mkdir(parents=True, exist_ok=True)


class ExtractionTests(unittest.TestCase):
    def test_new_model_discovery(self):
        self.assertIn("gemini-4-new", roster(DOCS["models"]))
        self.assertNotIn("gemini-4-new", capabilities(DOCS["models"]).get("gemini-4-new", {}).get("capabilities", []))

    def test_current_model_table_endpoints_and_coverage(self):
        sample = (FIX / "current-models.md").read_text(encoding="utf-8")
        self.assertEqual(roster(sample), {"gemini-4-neon", "gemini-4-hydrogen", "gemini-3.6-flash"})
        self.assertNotIn("gemini-4-incidental", roster(sample))

    def test_exact_model_capabilities(self):
        detail = (FIX / "model-detail.md").read_text(encoding="utf-8")
        self.assertEqual(detail_capabilities(detail, "gemini-4-hydrogen"),
                         {"TEXT_INPUT": "SUPPORTED", "IMAGE_INPUT": "SUPPORTED", "TEXT_OUTPUT": "SUPPORTED"})
        self.assertEqual(detail_capabilities(detail, "gemini-4-neon"), {})

    def test_capability_candidate_requires_affirmative_generate_content_api(self):
        self.assertFalse(generate_content_applicable("See the GenerateContent migration guide."))
        self.assertFalse(generate_content_applicable("GenerateContent API is not supported."))
        self.assertTrue(generate_content_applicable("Supported APIs: generateContent, models.list"))

    def test_free_paid_and_batch_separation(self):
        result = prices(DOCS["pricing"])
        self.assertEqual(result["gemini-4-hydrogen"].tier, "FREE")
        self.assertEqual(result["gemini-4-new"].tier, "PAID_ONLY")

    def test_free_removed_and_conflict(self):
        changed = DOCS["pricing"].replace("* Free of charge", "* Not available")
        self.assertEqual(prices(changed)["gemini-4-hydrogen"].tier, "PAID_ONLY")
        conflict = DOCS["pricing"].replace("`gemini-4-hydrogen`", "`gemini-4-hydrogen`\nEvery token is counted and billed.")
        self.assertFalse(prices(conflict)["gemini-4-hydrogen"].confident)

    def test_restricted_unknown_layout(self):
        restricted = DOCS["pricing"].replace("`gemini-4-hydrogen`", "`gemini-4-hydrogen`\nLimited to existing active API users.")
        self.assertEqual(prices(restricted)["gemini-4-hydrogen"].tier, "RESTRICTED_FREE")
        self.assertEqual(prices("## Gemini 4 New {% id=\"gemini-4-new\" %}\nNo table" )["gemini-4-new"].tier, "UNKNOWN")
        self.assertEqual(prices("<html>layout changed</html>"), {})

    def test_lifecycle_earliest_and_replacement_review(self):
        found = lifecycle(DOCS["deprecations"])
        self.assertEqual(found["gemini-4-hydrogen"]["facts"], ["NO_SHUTDOWN_ANNOUNCED"])
        self.assertIn("earliest", found["gemini-4-new"]["review"])
        self.assertIn("gemini-4-hydrogen", found["gemini-4-new"]["review"])

    def test_current_lifecycle_table_notes_and_repeated_rows(self):
        found = lifecycle((FIX / "current-deprecations.md").read_text(encoding="utf-8"))
        for model in ("gemini-4-neon", "gemini-4-hydrogen", "gemini-4-carbon", "gemini-4-argon"):
            self.assertEqual(found[model], {"facts": ["NO_SHUTDOWN_ANNOUNCED"]})
        self.assertEqual(found["gemini-2.5-flash"]["kind"], "ANNOUNCED_REDIRECTION")
        self.assertIn("December 1, 2026", found["gemini-2.5-flash"]["review"])
        self.assertIn("automatically route", found["gemini-2.5-flash"]["review"])
        self.assertEqual(found["gemini-3.8-live"], {"facts": ["NO_SHUTDOWN_ANNOUNCED"]})

    def test_api_breaking_and_dedupe(self):
        notices = api_notices(DOCS["changelog"])
        self.assertEqual(len(notices), 1)
        first = issue_plan({"api": notices})
        self.assertEqual(first, issue_plan({"api": notices}))
        self.assertEqual(len({title for title, _ in first}), 1)

    def test_optional_interactions_tool_retrieval_is_not_breaking(self):
        sample = (FIX / "current-changelog.md").read_text(encoding="utf-8")
        self.assertEqual(api_notices(sample), [])

    def test_previously_verified_lifecycle_announcement_is_quiet(self):
        note = "# Release notes\n## November 19, 2026\n* `gemini-2.5-flash` deprecated and redirects to `gemini-3.5-flash-lite`.\n"
        known = {"gemini-2.5-flash": {"verifiedOn": "2026-11-23"}}
        self.assertEqual(lifecycle_notices(note, known, {"gemini-2.5-flash"}, NOW.date()), [])

    def test_existing_api_issue_is_not_recreated(self):
        notices = {"api": api_notices(DOCS["changelog"]), "review": [], "failures": []}
        title, body = issue_plan(notices)[0]
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            path = Path(directory) / "notices.json"
            path.write_text(json.dumps(notices), encoding="utf-8")
            with patch("notify.api", return_value=[{"title": title, "body": body, "state": "closed", "url": "https://api.github.com/repos/rekluzlabs/rekluzlabs.github.io/issues/1"}]) as mocked:
                notify(path, "synthetic-token")
                self.assertEqual(mocked.call_count, 1)

    def test_existing_user_issue_is_not_closed_or_edited(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            path = Path(directory) / "notices.json"
            path.write_text(json.dumps({"failures": [], "review": [], "coverage": [], "api": []}), encoding="utf-8")
            old = {"title": "VaultCuisine advisory failures require attention", "body": "User notes",
                   "state": "open", "user": {"login": "repository-owner"}, "url": "https://api.github.com/issues/1"}
            with patch("notify.api", return_value=[old]) as mocked:
                notify(path, "synthetic-token")
                self.assertEqual(mocked.call_count, 1)

    def test_unchanged_bot_review_issue_has_no_repeat_update(self):
        notices = {"failures": [], "coverage": [], "review": ["New exact material correction"], "api": []}
        title, body = issue_plan(notices)[0]
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            path = Path(directory) / "notices.json"
            path.write_text(json.dumps(notices), encoding="utf-8")
            old = {"title": title, "body": body, "state": "open",
                   "user": {"login": "github-actions[bot]"}, "url": "https://api.github.com/issues/1"}
            with patch("notify.api", return_value=[old]) as mocked:
                notify(path, "synthetic-token")
                self.assertEqual(mocked.call_count, 1)

    def test_approved_sources(self):
        self.assertTrue(approved("https://aistudio.google.com/docs/pricing.md"))
        self.assertFalse(approved("http://aistudio.google.com/docs/pricing.md"))
        self.assertFalse(approved("https://evil.example/docs/pricing.md"))
        self.assertFalse(approved("https://aistudio.google.com.evil.example/docs/pricing.md"))

    def test_source_timeout(self):
        class TimedOut:
            def open(self, request, timeout):
                self.assert_timeout(timeout)
                raise TimeoutError("synthetic timeout")
            def assert_timeout(self, timeout):
                if timeout != 12:
                    raise AssertionError("unbounded timeout")
        with patch("sources.build_opener", return_value=TimedOut()):
            with self.assertRaises(TimeoutError):
                fetch("https://aistudio.google.com/docs/pricing.md")


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.docs = {kind: json.loads((ROOT / f"gemini-{kind.lower()}.json").read_text(encoding="utf-8")) for kind in ("LIFECYCLE", "COMPATIBILITY", "PRICING")}

    def test_current_production_documents(self):
        for kind, doc in self.docs.items():
            self.assertTrue(validate(doc, kind, now=NOW))

    def test_old_revision_and_missing_record(self):
        old = self.docs["PRICING"]
        changed = copy.deepcopy(old)
        with self.assertRaises(ValueError):
            validate(changed, "PRICING", previous=old, now=NOW)
        changed["revision"] += 1
        changed["records"].pop()
        with self.assertRaises(ValueError):
            validate(changed, "PRICING", previous=old, now=NOW)

    def test_invalid_schema_and_duplicate(self):
        doc = copy.deepcopy(self.docs["PRICING"])
        doc["schemaVersion"] = 2
        with self.assertRaises(ValueError):
            validate(doc, "PRICING", now=NOW)

    def test_revised_lifecycle_date_requires_fresh_evidence(self):
        old = self.docs["LIFECYCLE"]
        changed = copy.deepcopy(old)
        changed["revision"] += 1
        row = next(r for r in changed["records"] if "shutdownOn" in r)
        row["shutdownOn"] = "2027-01-01"
        with self.assertRaises(ValueError):
            validate(changed, "LIFECYCLE", previous=old, now=NOW)

    def test_unsupported_capability_rejected(self):
        doc = copy.deepcopy(self.docs["COMPATIBILITY"])
        doc["records"][0]["capabilities"].append({"capability": "REMOTE_COMMAND", "support": "SUPPORTED"})
        with self.assertRaises(ValueError):
            validate(doc, "COMPATIBILITY", now=NOW)
        doc["schemaVersion"] = 1
        doc["records"].append(copy.deepcopy(doc["records"][0]))
        with self.assertRaises(ValueError):
            validate(doc, "PRICING", now=NOW)

    def test_correction_and_revised_date_rules(self):
        old = self.docs["PRICING"]
        next_doc = copy.deepcopy(old)
        next_doc["revision"] += 1
        next_doc["records"][0]["tier"] = "UNKNOWN"
        with self.assertRaises(ValueError):
            validate(next_doc, "PRICING", previous=old, now=NOW)
        next_doc["records"][0]["correction"] = True
        self.assertTrue(validate(next_doc, "PRICING", previous=old, now=NOW))

    def test_no_unnecessary_pricing_revision(self):
        old = self.docs["PRICING"]
        proposed, _, changes = propose_pricing(old, prices(DOCS["pricing"]), {"gemini-4-hydrogen"}, {"gemini-4-hydrogen"}, "2026-11-27")
        self.assertEqual(proposed, old)
        self.assertFalse(changes)

    def test_record_order_and_metadata_do_not_change_semantics(self):
        old = self.docs["COMPATIBILITY"]
        proposed = copy.deepcopy(old)
        proposed["records"].reverse()
        proposed["revision"] += 1
        proposed["publishedAt"] = "2026-11-27T12:00:00Z"
        self.assertTrue(same_semantics(old, proposed))
        proposed["records"][0]["purpose"] = "UNKNOWN"
        self.assertFalse(same_semantics(old, proposed))

    def test_four_exact_gemini_four_lifecycle_additions_validate(self):
        old = self.docs["LIFECYCLE"]
        changed = copy.deepcopy(old)
        extracted = lifecycle((FIX / "current-deprecations.md").read_text(encoding="utf-8"))
        for model in ("gemini-4-neon", "gemini-4-hydrogen", "gemini-4-carbon", "gemini-4-argon"):
            self.assertNotIn(model, {row["modelId"] for row in old["records"]})
            changed["records"].append({"modelId": model, "verifiedOn": "2026-11-27",
                "evidence": ["https://aistudio.google.com/docs/deprecations"], "facts": extracted[model]["facts"]})
        changed["revision"] = old["revision"] + 1
        changed["publishedAt"] = "2026-11-27T12:00:00Z"
        self.assertTrue(validate(changed, "LIFECYCLE", previous=old, now=NOW))

    def test_new_documented_free_tier_can_be_proposed(self):
        old = copy.deepcopy(self.docs["PRICING"])
        old["records"] = [r for r in old["records"] if r["modelId"] == "gemini-4-hydrogen"]
        new_section = DOCS["pricing"].replace("gemini-4-new", "gemini-4-test").replace("not available on the Free tier", "available on the Free tier").replace("* Not available", "* Free of charge")
        observed = prices(new_section)
        proposed, review, changes = propose_pricing(old, observed, {"gemini-4-test", "gemini-4-hydrogen"}, {"gemini-4-test"}, "2026-11-27")
        self.assertIn("gemini-4-test", changes)
        self.assertEqual(next(r for r in proposed["records"] if r["modelId"] == "gemini-4-test")["tier"], "FREE")
        self.assertEqual(len(old["records"]), 1)

    def test_second_dry_run_documents_validate_and_preserve_prior_evidence(self):
        for kind in ("LIFECYCLE", "PRICING"):
            candidate = json.loads((FIX / f"second-dry-run-gemini-{kind.lower()}.json").read_text(encoding="utf-8"))
            self.assertTrue(validate(candidate, kind, previous=self.docs[kind],
                                     now=dt.datetime(2026, 11, 27, 19, tzinfo=dt.timezone.utc)))
        lifecycle_doc = json.loads((FIX / "second-dry-run-gemini-lifecycle.json").read_text(encoding="utf-8"))
        pricing_doc = json.loads((FIX / "second-dry-run-gemini-pricing.json").read_text(encoding="utf-8"))
        self.assertEqual(set(pricing_conflicts(pricing_doc, lifecycle_doc)), {
            "gemini-2.5-flash: FREE pricing conflicts with lifecycle ACCESS_RESTRICTED",
            "gemini-2.5-pro: FREE pricing conflicts with lifecycle ACCESS_RESTRICTED"})

    def test_restricted_free_proposal_preserves_access_and_redirection_warning(self):
        lifecycle_doc = self.docs["LIFECYCLE"]
        observed = prices((FIX / "current-pricing-2.5.md").read_text(encoding="utf-8"))
        current = copy.deepcopy(self.docs["PRICING"])
        current["records"] = [row for row in current["records"] if row["modelId"] == "gemini-2.5-flash-lite"]
        proposed, review, changes = propose_pricing(current, observed,
            {"gemini-2.5-flash", "gemini-2.5-pro"}, {"gemini-2.5-flash", "gemini-2.5-pro"},
            "2026-11-27", lifecycle_doc)
        self.assertEqual(set(changes), {"gemini-2.5-flash", "gemini-2.5-pro"})
        self.assertFalse(review)
        self.assertFalse(pricing_conflicts(proposed, lifecycle_doc))
        for model in changes:
            row = next(r for r in proposed["records"] if r["modelId"] == model)
            self.assertEqual(row["tier"], "RESTRICTED_FREE")
            self.assertIn("existing active users", row["restrictions"])
            self.assertIn("2026-12-01", row["restrictions"])
            self.assertIn("billed at replacement rates", row["restrictions"])
            self.assertEqual(len(row["evidence"]), 2)


class RunTests(unittest.TestCase):
    def test_publish_with_coverage_blocker_never_writes_even_with_gates(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            root = Path(directory) / "VaultCuisine-Advisories"
            (root / "scripts").mkdir(parents=True)
            (root / "scripts" / "update.py").write_text("fixture", encoding="utf-8")
            for kind in ("lifecycle", "compatibility", "pricing"):
                (root / f"gemini-{kind}.json").write_bytes((ROOT / f"gemini-{kind}.json").read_bytes())
            prior = {kind: (root / f"gemini-{kind}.json").read_bytes()
                     for kind in ("lifecycle", "compatibility", "pricing")}
            with patch.dict(os.environ, {"VC_ADVISORY_PUBLISH": "true", "VC_LIVE_SYNC_VERIFIED": "true"}):
                with self.assertRaisesRegex(ValueError, "publication blocked"):
                    run(root, Path(directory) / "out", DOCS, publish=True, today=NOW)
            self.assertEqual(prior, {kind: (root / f"gemini-{kind}.json").read_bytes()
                                     for kind in prior})
    def test_dry_run_preserves_existing_and_reports(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            out = Path(directory) / "out"
            before = [(ROOT / f"gemini-{kind}.json").read_bytes() for kind in ("lifecycle", "compatibility", "pricing")]
            result = run(ROOT, out, DOCS, today=NOW)
            self.assertTrue((out / "report.md").exists())
            self.assertEqual(before, [(ROOT / f"gemini-{kind}.json").read_bytes() for kind in ("lifecycle", "compatibility", "pricing")])
            self.assertIn("semantic extraction incomplete", "\n".join(result["coverage"]))
            self.assertNotIn("COMPATIBILITY", result["changes"])

    def test_empty_roster_blocks_new_model_proposals(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            bad = dict(DOCS)
            bad["models"] = "# Models\n" + ("No explicit model endpoint is listed here.\n" * 10)
            result = run(ROOT, Path(directory), bad, today=NOW)
            self.assertTrue(result["coverage"])
            self.assertNotIn("COMPATIBILITY", result["changes"])
            self.assertNotIn("PRICING", result["changes"])
            report = (Path(directory) / "report.md").read_text(encoding="utf-8")
            self.assertIn("- models: retrieved from", report)
            self.assertIn("Exact roster IDs: 0 (blocked)", report)

    def test_complete_unchanged_roster_does_not_churn_compatibility(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            docs = dict(DOCS)
            current = json.loads((ROOT / "gemini-compatibility.json").read_text(encoding="utf-8"))
            docs["models"] = "# Models\n## Current exact codes\n" + "\n".join(
                f"*   *Model code* **{row['modelId']}**" for row in current["records"] if row["modelId"].startswith("gemini-"))
            result = run(ROOT, Path(directory), docs, today=NOW)
            self.assertNotIn("COMPATIBILITY", result["changes"])
            self.assertFalse((Path(directory) / "gemini-compatibility.json").exists())

    def test_partial_and_empty_sources_preserve(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            bad = dict(DOCS)
            bad["pricing"] = "bad"
            result = run(ROOT, Path(directory), bad, today=NOW)
            self.assertIn("pricing", result["failures"][0])
            self.assertNotIn("PRICING", result["changes"])

    def test_publish_requires_both_gates(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            with self.assertRaises(ValueError):
                run(ROOT, Path(directory), DOCS, publish=True, today=NOW)

    def test_root_path_restriction(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            with self.assertRaises(ValueError):
                run(Path(directory), Path(directory) / "out", DOCS, today=NOW)

    def test_publication_restricted_to_advisory_files(self):
        self.assertTrue(check(["VaultCuisine-Advisories/gemini-pricing.json"]))
        with self.assertRaises(ValueError):
            check(["index.html"])


if __name__ == "__main__":
    unittest.main()
