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
- `extract.py` reads exact `Model code` fields and explicit `Endpoint` cells in Google's model tables. A successful HTTP response is reported separately from a sufficiently complete roster. Empty or sharply reduced extraction blocks new-model pricing and compatibility changes. Pricing uses exact section IDs and Standard input/output rows. Batch, Flex and Priority rows cannot establish Standard free access. Free tier means Google documents a tier, not that a particular account can use it without charges. Conflicting free and billed statements are retained as known caveats when an unchanged published row already records the tier; new conflicts remain review items.
- A new general-purpose model already known to the compatibility catalogue may receive a clearly documented new `FREE` pricing row. Existing tier changes, new paid-only claims, access restrictions and uncertain prices remain review items. Existing rows are never removed or silently renewed.
- The deprecation table can add an exact new `NO_SHUTDOWN_ANNOUNCED` row only for an already established general-purpose model also in a complete roster. Repeated identical table rows merge, and embedded notes remain attached to their row. Table dates are earliest possible dates unless an explicit separate announcement confirms shutdown; active and announced redirection are distinguished. Previously recorded facts and dates do not create recurring review items. Omission from a page does not remove a record.
- Exact model details can supply candidate text input, text output and image input evidence. A candidate is not published without explicit GenerateContent applicability on that exact page. It cannot assert JSON MIME type, response schema or request configuration from generic model prose. New model rows are not added merely because they appear in a table.
- The changelog and migration guide flag mandatory changes to the Model List, GenerateContent, authentication, schemas and relevant endpoints. Optional Interactions capabilities are not breaking notices. The monitor does not change Android endpoints or request formats.

`validate.py` independently mirrors the schema 1 envelope, exact identifiers, official evidence URLs, duplicate checks, allowed enums, revision monotonicity, cumulative records and basic correction rules. This mirror is a conservative preflight; final production validation must use the Android decoders before a manual correction or schema change is published. A document-format change is a human task.

## Workflow operation

The staged workflow is at `docs/publication/.github/workflows/vaultcuisine-advisory-update.yml`. It runs at 05:17 UTC daily once `VC_ADVISORY_SCHEDULE_ENABLED=true` and can always be started manually. The monitor job has `contents: read` and `issues: write`; its report and proposed files are attached to the run for 14 days. Review the job summary and artifact before enabling publication. If repository Issues are disabled or issue creation is blocked, the notification step fails and the workflow run shows the failure.

The separate publication job is skipped unless both `VC_ADVISORY_PUBLISH=true` and `VC_LIVE_SYNC_VERIFIED=true` are set in repository **Settings → Secrets and variables → Actions → Variables**. It re-fetches and validates official sources; it does not trust an artifact from another job. Its `contents: write` permission applies only to that job. It rejects changes outside the three named JSON files, and commits only when a JSON file changed. Disable publication instantly by deleting or setting `VC_ADVISORY_PUBLISH=false`; monitoring continues. Disable the schedule with `VC_ADVISORY_SCHEDULE_ENABLED=false` and retain manual runs.

The issue notifier uses `GITHUB_TOKEN` and the repository Issues API. Retrieval failures, coverage blockers and new actionable findings use stable issue titles. Unchanged known caveats appear only in the downloadable diagnostic file. The notifier updates only its own open issues, never closes or reopens an existing issue automatically, and does not recreate an API announcement when the title already exists. Subscribe to repository Issues using **Watch → Custom → Issues**. Set **Settings → Notifications → Actions** for failed workflow runs; GitHub's notification menus may vary. The workflow pins official Node.js 24 checkout and artifact actions by full commit SHA.

## Recovery and rollback

Fetch or validation failures leave prior JSON unchanged. An interrupted job cannot publish partial JSON if it stops before the commit; a Git push is atomic. Git history retains published revisions. To restore earlier evidence, copy the earlier records into a *new* document with a revision above the current one, a current publication time and explicit `correction` or `WITHDRAWN` fields where required. Validate it with the Python mirror and Android production decoder, review the diff, and commit only the affected advisory. Never reset the branch to an old JSON revision: VaultCuisine rejects rollback revisions.

The monitor does not infer individual account entitlement, future charges, retirement from absence, capability from names or API migration requirements from model changes. It leaves unsupported or changed documentation structures for human review. Google or GitHub outages remain visible as failed runs or review issues.
