# BuiltWith API Integration — Design Spec

## Goal
Integrate the BuiltWith Domain API (v22) to augment the existing HTML-based tech detection with comprehensive, API-backed technology data. This gives more accurate tech stack information for scoring and outreach personalization.

## Architecture

### New module: `src/enrichment/builtwith.py`
Single-purpose module that handles all BuiltWith API interaction:
- `fetch_builtwith(domain, api_key)` → calls BuiltWith API, returns parsed tech list
- `parse_builtwith_response(data)` → extracts technology names/categories from raw API response
- `merge_tech_stacks(html_tech, builtwith_tech)` → deduplicates and combines both sources

### Integration points
1. **`src/enrichment/website_audit.py`**: `audit_website()` gains optional `builtwith_key` param. If provided, calls BuiltWith after HTML detection and merges results.
2. **`src/enrichment/async_processor.py`**: Passes `builtwith_key` from settings to `audit_website()`.
3. **`AuditResult` dataclass**: New `builtwith_tech` field to store API-sourced tech separately from HTML-detected tech.

### Graceful degradation
- If `builtwith_key` is empty/missing in settings → skip BuiltWith, use HTML-only (current behavior)
- If BuiltWith API call fails (timeout, error, rate limit) → log warning, continue with HTML-only results
- No hard dependency on BuiltWith — pipeline always works without it

## BuiltWith API Details

**Endpoint:** `GET https://api.builtwith.com/v22/api.json`
**Params:** `KEY={api_key}&LOOKUP={domain}&HIDETEXT=yes&HIDEDL=yes&NOPII=yes&NOATTR=yes`
  - `HIDETEXT=yes` — omit descriptions/links (saves bandwidth)
  - `HIDEDL=yes` — omit detection date ranges
  - `NOPII=yes` — no personal info
  - `NOATTR=yes` — no attribute data

**Response structure:**
```json
{
  "Results": [{
    "Result": {
      "Paths": [{
        "Technologies": [
          {"Name": "WordPress 6.4", "Tag": "cms", "Categories": ["CMS"]},
          {"Name": "jQuery 3.7", "Tag": "javascript-framework", "Categories": ["JavaScript Framework"]},
          {"Name": "HubSpot", "Tag": "marketing-automation", "Categories": ["Marketing Automation", "CRM"]}
        ]
      }]
    }
  }]
}
```

**Key technology fields we use:**
- `Name` — full tech name (e.g., "WordPress 6.4")
- `Tag` — category slug (e.g., "cms", "analytics", "hosting")
- `Categories` — human-readable category list

## Tech Stack Merging Strategy

1. Normalize all tech names to lowercase slugs (e.g., "WordPress 6.4" → "wordpress")
2. HTML detection results are kept as-is (fast, free)
3. BuiltWith results are added, deduped against HTML results
4. Final `lead.tech_stack` contains unique, normalized tech names from both sources
5. `AuditResult.builtwith_tech` stores raw BuiltWith tech names for reference

## Rate Limiting
Already configured in `src/rate_limit.py`: `builtwith: 20 calls/min`. Uses existing `get_limiter("builtwith")` + `retry_with_rate_limit` decorator.

## Error Handling
- HTTP 401/403 → log "invalid API key", skip
- HTTP 429 → handled by retry_with_rate_limit (exponential backoff)
- HTTP 5xx → retry up to 3 times
- Timeout → retry, then skip
- Malformed JSON → log warning, skip

## Testing Strategy
- Mock BuiltWith API responses with `respx`
- Test parse_builtwith_response with various response shapes
- Test merge_tech_stacks deduplication
- Test graceful degradation (no key, API error, timeout)
- Test integration with audit_website
