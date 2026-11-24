# Gemini pricing advisory format

## Document envelope

| Field | Required value |
| --- | --- |
| schemaVersion | Integer 1 |
| revision | Positive integer up to 2,147,483,647 |
| publishedAt | ISO-8601 instant, at most 40 characters, at or before retrieval |
| provider | google |
| api | gemini-developer/v1beta |
| kind | PRICING |
| records | 1 to 256 records with unique exact identifiers |

The decoded UTF-8 response is limited to 128 KiB. Unknown fields and enum values are rejected. Each row requires **modelId**, an exact case-sensitive bare API identifier of up to 128 characters, **verifiedOn**, an ISO calendar date from 2023 through the UTC publication date, and **evidence**, one to six distinct official Google HTTPS documentation URLs of up to 256 characters each. URLs may contain a section fragment. Credentials, explicit ports and query strings are forbidden.

## Revisions and freshness

Publish cumulative revisions with nondecreasing publication and evidence dates. A lower revision or any mutation of an equal revision is rejected. Keep every prior exact ID, including withdrawal records. A material change with the same verification date requires **correction** set to true. A withdrawal sets **correction** and **withdrawn** to true and supplies new dated evidence without any domain fields. Reinstating a withdrawn record requires an explicit correction. Both flags default to false.

Records are evaluated against their own evidence date. Recently downloading a document cannot renew its evidence. Records are fresh through 90 UTC calendar days from verification. The last validated remote document survives download and validation errors. Bundled evidence supplies offline fallback. Precedence against bundled evidence is described below.

## Pricing fields

A non-withdrawn record requires **tier** (FREE, PAID_ONLY, RESTRICTED_FREE, UNKNOWN) and **restrictions**, a string of up to 320 characters without control or formatting characters. RESTRICTED_FREE requires nonblank documented restrictions. Include the exact model's official Gemini Developer API pricing URL and any official source establishing an access restriction.

Fresh, newer exact-ID evidence replaces the bundled tier. A same-day conflict with bundled pricing displays Pricing unknown unless an explicit correction resolves it. An applicable withdrawal or expiry of newer evidence leaves the tier unknown. An unlisted model can use valid bundled evidence. Public tiers describe Google documentation. Account access, usage and charges remain unverified.

Material paid-only evidence requires review before affected generation. Evidence dates and source order alone do not change the acknowledgement. Paid-only selection keeps its confirmation.
