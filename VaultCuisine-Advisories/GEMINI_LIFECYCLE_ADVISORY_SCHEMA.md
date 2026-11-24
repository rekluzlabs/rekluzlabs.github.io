# Gemini lifecycle advisory format and publication

The production-format file is [gemini-lifecycle.json](gemini-lifecycle.json). Its only audience is the Gemini Developer API v1beta experience in VaultCuisine.

## Schema version 1

| Field | Required value |
| --- | --- |
| schemaVersion | Integer 1 |
| revision | Monotonically increasing positive integer, at most 2,147,483,647 |
| publishedAt | ISO-8601 instant, at most 40 characters and at or before retrieval time |
| provider | google |
| api | gemini-developer/v1beta |
| records | 1–256 unique records keyed by exact bare model identifier |
| modelId | Exact case-sensitive API identifier, with no models/ prefix |
| verifiedOn | ISO calendar date YYYY-MM-DD, between 2023 and the UTC publication date |
| facts | Nonempty list of distinct supported fact names |
| evidence | 1–6 unique HTTPS documentation URLs on ai.google.dev or aistudio.google.com, up to 256 characters each |
| shutdownOn | Optional ISO calendar date for a shutdown fact |
| redirectOn | Optional ISO calendar date for a redirection fact |
| redirectTargets | Up to 8 distinct exact target IDs, required for a redirection fact |
| replacements | Up to 8 distinct exact Google-suggested model IDs |
| restriction | EXISTING_ACTIVE_API_USERS when ACCESS_RESTRICTED is present |
| correction | Boolean, defaults to false. Set to true for an explicit, cited correction or withdrawal |

IDs are limited by VaultCuisine's existing Gemini model identifier validator. Replacements and redirect targets cannot point to the affected ID. The entire decoded response is capped at 128 KiB. The app generates concise display copy from structured fields. Unknown fields, enums, and schema versions are rejected.

Facts are NO_SHUTDOWN_ANNOUNCED, DEPRECATED, EARLIEST_SHUTDOWN, SCHEDULED_SHUTDOWN, SHUT_DOWN, REDIRECTION_ANNOUNCED, REDIRECTION_ACTIVE, ACCESS_RESTRICTED, and WITHDRAWN. Shutdown and routing each permit one fact. They can coexist with other facts. A future date cannot support a confirmed historical shutdown or an explicit active redirect. Missing dates convey that the date is unknown. Omission of an entire model provides no evidence for that model. NO_SHUTDOWN_ANNOUNCED takes a dated, explicit Google statement. WITHDRAWN must be the only fact and requires a correction. Keep the withdrawal record in later revisions.

## Precedence and freshness

The feed is cumulative. Preserve prior rows or supply cited corrections. A lower revision or mutation of an equal revision is rejected. For a model with both bundled and cached evidence, prefer the later verification date. On the same date, prefer equivalent remote evidence or an explicit remote correction. A same-day material disagreement without a correction displays the bundled evidence with a conflict flag and cannot block generation. An omitted remote row always leaves the bundle available. Stale shutdown evidence remains visible but stops blocking requests. Evidence becomes stale after 90 UTC calendar days or when the device clock precedes verification. Retrieval dates are separate and do not renew Google verification.

## Publication and correction

Publish this document as **gemini-lifecycle.json** in the **VaultCuisine-Advisories** directory of the Rekluz Labs website repository's main branch. Revision 2 is the starting point. Validate every replacement against the shipped format and retain prior evidence or cite an explicit correction or withdrawal.

VaultCuisine uses a direct HTTPS GET to the exact GitHub raw URL. It rejects redirects and caches accepted data privately. GitHub receives ordinary connection metadata, including the originating IP address. HTTPS authenticates the host. A compromised publisher can serve false evidence, so restrict write access and review changes.
