# Gemini compatibility advisory format

## Document envelope

| Field | Required value |
| --- | --- |
| schemaVersion | Integer 1 |
| revision | Positive integer up to 2,147,483,647 |
| publishedAt | ISO-8601 instant, at most 40 characters, at or before retrieval |
| provider | google |
| api | gemini-developer/v1beta |
| kind | COMPATIBILITY |
| records | 1 to 256 records with unique exact identifiers |

The decoded UTF-8 response is limited to 128 KiB. Unknown fields and enum values are rejected. Each row requires **modelId**, an exact case-sensitive bare API identifier of up to 128 characters, **verifiedOn**, an ISO calendar date from 2023 through the UTC publication date, and **evidence**, one to six distinct official Google HTTPS documentation URLs of up to 256 characters each. URLs may contain a section fragment. Credentials, explicit ports and query strings are forbidden.

## Revisions and freshness

Publish cumulative revisions with nondecreasing publication and evidence dates. A lower revision or any mutation of an equal revision is rejected. Keep every prior exact ID, including withdrawal records. A material change with the same verification date requires **correction** set to true. A withdrawal sets **correction** and **withdrawn** to true and supplies new dated evidence without any domain fields. Reinstating a withdrawn record requires an explicit correction. Both flags default to false.

Records are evaluated against their own evidence date. Recently downloading a document cannot renew its evidence. Records are fresh through 90 UTC calendar days from verification. The last validated remote document survives download and validation errors. Bundled evidence supplies offline fallback. Precedence against bundled evidence is described below.

## Compatibility fields

A non-withdrawn record includes **purpose** (GENERAL_PURPOSE, SPECIALIST, UNKNOWN), **release** (STABLE, PREVIEW, UNKNOWN), and **capabilities**, a list with at most one row per capability. The optional **releaseDate** is an ISO calendar date between 2023 and the verification date.

Each capability row has **capability** and **support**. Supported capability names are GENERATE_CONTENT, TEXT_INPUT, TEXT_OUTPUT, IMAGE_INPUT, JSON_MIME_TYPE, RESPONSE_SCHEMA, PLAIN_TEXT_MIME_TYPE and MAX_OUTPUT_TOKENS. Support is SUPPORTED, UNSUPPORTED or UNKNOWN. An omitted capability can use matching bundled evidence. An explicit UNKNOWN replaces applicable bundled evidence. The advertised output limit remains part of the authenticated Google model catalogue.

Fresh, newer exact-ID evidence replaces the applicable bundled fields. Same-day contradictory capability claims remain unknown through the app classifier unless an explicit correction resolves the disagreement. When a same-day purpose conflict involves a bundled specialist, the specialist exclusion remains in force. Otherwise disputed purpose and release are unknown. The seven-feature classifier still evaluates required capabilities, advertised methods and token limits. Evidence cannot grant generation authorization.
