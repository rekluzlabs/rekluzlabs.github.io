# VaultCuisine advisory maintenance

This package uses Python's standard library. It makes credential-free HTTPS requests only to Google AI Studio documentation. It never calls the Gemini API. The Android application and its formats remain authoritative.

## Local dry run

From the website repository root, run:

```sh
python3 -B -m unittest discover -s VaultCuisine-Advisories/scripts/tests -v
python3 -B VaultCuisine-Advisories/scripts/update.py --output /tmp/vc-advisory-report
```

Read `/tmp/vc-advisory-report/report.md`, `notices.json`, and any proposed `gemini-*.json`. The script never changes published files without `--publish` and both environment variables `VC_ADVISORY_PUBLISH=true` and `VC_LIVE_SYNC_VERIFIED=true`. The workflow starts with both variables absent and with `VC_ADVISORY_SCHEDULE_ENABLED` absent. Do not set the publication variables until Stage 8D.3A live synchronization and a representative GitHub dry run have been reviewed.

## Extraction rules

- `sources.py` allows only HTTPS `ai.google.dev` and `aistudio.google.com` documentation paths, with three approved redirects, 12-second timeouts and a 2 MB response cap. The canonical current pages are the Google AI Studio models, pricing, deprecations, changelog and migration guide pages. No JavaScript or downloaded code is executed.
- `extract.py` reads exact `Model code` fields, exact pricing section IDs and Standard input/output rows. Batch, Flex and Priority rows cannot establish Standard free access. Free tier means Google documents a tier, not that a particular account can use it without charges. Conflicting free and billed statements remain review items.
- A new general-purpose model already known to the compatibility catalogue may receive a clearly documented new `FREE` pricing row. Existing tier changes, new paid-only claims, access restrictions and uncertain prices remain review items. Existing rows are never removed or silently renewed.
- The deprecation table can add an exact new `NO_SHUTDOWN_ANNOUNCED` row. Dates on that table are treated as earliest possible dates; changed dates, redirections, retirements and corrections require review. Omission from a page does not remove a record.
- An exact model detail can add explicit text input, text output and image input support. It cannot assert GenerateContent, JSON MIME type, response schema or request configuration from that evidence alone. New model rows remain `UNKNOWN` until stronger exact-model and API-family evidence exists.
- The changelog and migration guide produce API review notices. The monitor does not change Android endpoints or request formats.

`validate.py` independently mirrors the schema 1 envelope, exact identifiers, official evidence URLs, duplicate checks, allowed enums, revision monotonicity, cumulative records and basic correction rules. This mirror is a conservative preflight; final production validation must use the Android decoders before a manual correction or schema change is published. A document-format change is a human task.

## Workflow operation

The staged workflow is at `docs/publication/.github/workflows/vaultcuisine-advisory-update.yml`. It runs at 05:17 UTC daily once `VC_ADVISORY_SCHEDULE_ENABLED=true` and can always be started manually. The monitor job has `contents: read` and `issues: write`; its report and proposed files are attached to the run for 14 days. Review the job summary and artifact before enabling publication. If repository Issues are disabled or issue creation is blocked, the notification step fails and the workflow run shows the failure.

The separate publication job is skipped unless both `VC_ADVISORY_PUBLISH=true` and `VC_LIVE_SYNC_VERIFIED=true` are set in repository **Settings → Secrets and variables → Actions → Variables**. It re-fetches and validates official sources; it does not trust an artifact from another job. Its `contents: write` permission applies only to that job. It rejects changes outside the three named JSON files, and commits only when a JSON file changed. Disable publication instantly by deleting or setting `VC_ADVISORY_PUBLISH=false`; monitoring continues. Disable the schedule with `VC_ADVISORY_SCHEDULE_ENABLED=false` and retain manual runs.

The issue notifier uses `GITHUB_TOKEN` and the repository Issues API. Review and extraction findings update a stable open issue. API announcements use a digest in the issue title and are not recreated when the same title exists, including a closed issue. Subscribe to repository Issues using **Watch → Custom → Issues**. Set **Settings → Notifications → Actions** for failed workflow runs; GitHub's notification menus may vary.

## Recovery and rollback

Fetch or validation failures leave prior JSON unchanged. An interrupted job cannot publish partial JSON if it stops before the commit; a Git push is atomic. Git history retains published revisions. To restore earlier evidence, copy the earlier records into a *new* document with a revision above the current one, a current publication time and explicit `correction` or `WITHDRAWN` fields where required. Validate it with the Python mirror and Android production decoder, review the diff, and commit only the affected advisory. Never reset the branch to an old JSON revision: VaultCuisine rejects rollback revisions.

The monitor does not infer individual account entitlement, future charges, retirement from absence, capability from names or API migration requirements from model changes. It leaves unsupported or changed documentation structures for human review. Google or GitHub outages remain visible as failed runs or review issues.
