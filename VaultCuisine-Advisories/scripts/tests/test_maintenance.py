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
from extract import api_notices, capabilities, detail_capabilities, lifecycle, prices, roster
from check_paths import check
from notify import issue_plan, notify
from sources import approved, fetch
from update import run, propose_pricing
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

    def test_exact_model_capabilities(self):
        detail = (FIX / "model-detail.md").read_text(encoding="utf-8")
        self.assertEqual(detail_capabilities(detail, "gemini-4-hydrogen"),
                         {"TEXT_INPUT": "SUPPORTED", "IMAGE_INPUT": "SUPPORTED", "TEXT_OUTPUT": "SUPPORTED"})
        self.assertEqual(detail_capabilities(detail, "gemini-4-neon"), {})

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

    def test_api_breaking_and_dedupe(self):
        notices = api_notices(DOCS["changelog"])
        self.assertEqual(len(notices), 1)
        first = issue_plan({"api": notices})
        self.assertEqual(first, issue_plan({"api": notices}))
        self.assertEqual(len({title for title, _ in first}), 1)

    def test_existing_api_issue_is_not_recreated(self):
        notices = {"api": api_notices(DOCS["changelog"]), "review": [], "failures": []}
        title, body = issue_plan(notices)[0]
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            path = Path(directory) / "notices.json"
            path.write_text(json.dumps(notices), encoding="utf-8")
            with patch("notify.api", return_value=[{"title": title, "body": body, "state": "closed", "url": "https://api.github.com/repos/rekluzlabs/rekluzlabs.github.io/issues/1"}]) as mocked:
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

    def test_new_documented_free_tier_can_be_proposed(self):
        old = copy.deepcopy(self.docs["PRICING"])
        old["records"] = [r for r in old["records"] if r["modelId"] == "gemini-4-hydrogen"]
        new_section = DOCS["pricing"].replace("gemini-4-new", "gemini-4-test").replace("not available on the Free tier", "available on the Free tier").replace("* Not available", "* Free of charge")
        observed = prices(new_section)
        proposed, review, changes = propose_pricing(old, observed, {"gemini-4-test", "gemini-4-hydrogen"}, {"gemini-4-test"}, "2026-11-27")
        self.assertIn("gemini-4-test", changes)
        self.assertEqual(next(r for r in proposed["records"] if r["modelId"] == "gemini-4-test")["tier"], "FREE")
        self.assertEqual(len(old["records"]), 1)


class RunTests(unittest.TestCase):
    def test_dry_run_preserves_existing_and_reports(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            out = Path(directory) / "out"
            before = [(ROOT / f"gemini-{kind}.json").read_bytes() for kind in ("lifecycle", "compatibility", "pricing")]
            result = run(ROOT, out, DOCS, today=NOW)
            self.assertTrue((out / "report.md").exists())
            self.assertEqual(before, [(ROOT / f"gemini-{kind}.json").read_bytes() for kind in ("lifecycle", "compatibility", "pricing")])
            self.assertIn("unexpectedly incomplete", "\n".join(result["review"]))

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
