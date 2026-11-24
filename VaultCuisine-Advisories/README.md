# VaultCuisine Gemini advisories

These public documents describe exact-model Google Gemini Developer API lifecycle, compatibility and pricing evidence used by VaultCuisine. See each versioned schema and the changelog.

- [Lifecycle catalogue](gemini-lifecycle.json) and [schema](GEMINI_LIFECYCLE_ADVISORY_SCHEMA.md)
- [Compatibility catalogue](gemini-compatibility.json) and [schema](GEMINI_COMPATIBILITY_ADVISORY_SCHEMA.md)
- [Pricing catalogue](gemini-pricing.json) and [schema](GEMINI_PRICING_ADVISORY_SCHEMA.md)
- [Changelog](CHANGELOG.md)

Use a direct HTTPS GET without redirects. The production lifecycle endpoint resides in the VaultCuisine-Advisories folder of the existing Rekluz Labs website repository. Compatibility and pricing retrieval require separate app allowlisting after publication verification.

GitHub receives ordinary connection metadata such as originating IP addresses. Requests carry no API keys, model identifiers, user identifiers, recipes, photos or prompts. HTTPS authenticates the GitHub host. Publisher access controls and review protect document contents. A compromised publisher can still serve false evidence. Individual model entitlement and usage charges remain unknown.
