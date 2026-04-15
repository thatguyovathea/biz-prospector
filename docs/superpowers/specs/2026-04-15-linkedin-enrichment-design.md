# LinkedIn Enrichment for Employee Title Analysis — Design Spec

## Goal

Use Apollo.io's existing People Search API (already integrated, free endpoint) to fetch employee rosters for each lead's company, analyze their job titles for signals of manual operations vs. tech maturity, and feed those signals into the scoring engine — replacing the two placeholder factors (`employee_count` and `business_age`) with real data.

## Why This Matters

The scoring engine currently has two factors that always return 0.0:
- `business_age` (weight 5) — needs founding date
- `employee_count` (weight 5) — needs headcount

That's 10% of the total score that produces no signal. More importantly, employee title analysis is a strong indicator of operational maturity — a company with "Data Entry Clerk" and "Filing Clerk" roles is far more likely to benefit from automation than one with "CRM Administrator" and "IT Director" roles.

## Data Source

**Apollo People Search API** (`POST /v1/mixed_people/search`) — already integrated in `src/enrichment/contacts.py`.

Key properties:
- **Free** — the People Search endpoint does not consume Apollo credits
- **Domain-filterable** — pass `q_organization_domains` to get employees at a specific company
- **Returns per-person**: `first_name`, `last_name`, `title`, `linkedin_url`, `organization` (with `estimated_num_employees`, `founded_year`, `industry`, `linkedin_url`)
- **Paginated** — 100 results per page, up to 50,000 results max
- **Rate limited** — 50 calls/minute (free plan), 200+/minute (paid)

We already call this endpoint in `search_apollo()` for contact enrichment but filter to `TARGET_TITLES[:8]` and only fetch 5 results. For title analysis, we make a second call **without title filters** to get a broader employee sample.

## Architecture

### New Module: `src/enrichment/linkedin.py`

Single-responsibility module for employee title analysis. Does three things:
1. Fetch employees from Apollo (broader search than contact enrichment)
2. Classify titles as manual-process indicators vs. tech-maturity indicators
3. Extract company metadata (employee count, founding year) from the organization object

### Data Flow

```
Async Processor (_enrich_single)
  └─ After contact enrichment completes:
     └─ If apollo_key exists AND lead has domain:
        └─ Call fetch_company_employees(domain, apollo_key)
           └─ Returns: list of employee titles + company metadata
        └─ Call analyze_employee_titles(titles, manual_keywords, tech_keywords)
           └─ Returns: manual_role_count, tech_role_count, title_signals_score
        └─ Apply results to lead fields
```

This runs as a separate step after contact enrichment, not inside it. Contact enrichment finds the best decision-maker; LinkedIn enrichment analyzes the company's workforce.

### No Fallback Endpoint Needed

The original design considered an Apollo Organization Enrichment endpoint (`/organizations/enrich`) as a fallback. After research, the Organization Enrichment endpoint does NOT return employee titles — only company-level metadata (employee count, revenue, etc.). Since the People Search is free and returns both employee titles AND organization metadata, there's no need for a separate endpoint. If People Search returns no results for a domain, we simply have no title data — same as having no reviews or no job postings. The scoring factor returns 0.0 (no signal).

## Data Model Changes (`src/models.py`)

Add these fields to the `Lead` class:

```python
# LinkedIn / Employee title analysis (populated in enrichment)
linkedin_url: str = ""                         # Best contact's LinkedIn profile URL
company_linkedin_url: str = ""                 # Company LinkedIn page URL
employee_count: Optional[int] = None           # Headcount from Apollo org data
founded_year: Optional[int] = None             # Founding year from Apollo org data
employee_titles: list[str] = Field(default_factory=list)  # All employee titles found
manual_role_count: int = 0                     # Count of manual-process role titles
tech_role_count: int = 0                       # Count of tech-leadership role titles
```

The `linkedin_url` field also captures the contact's LinkedIn URL that Apollo/Hunter already return but we currently discard.

## Title Classification

### Manual Process Keywords

Titles containing these terms signal the company relies on manual operations:

```python
MANUAL_ROLE_KEYWORDS = [
    "data entry",
    "filing",
    "receptionist",
    "bookkeeper",
    "administrative assistant",
    "office clerk",
    "records clerk",
    "dispatcher",
    "scheduling coordinator",
    "front desk",
    "payroll clerk",
    "accounts receivable",
    "accounts payable",
]
```

### Tech Maturity Keywords

Titles containing these terms signal the company has invested in technology:

```python
TECH_ROLE_KEYWORDS = [
    "it manager",
    "it director",
    "chief technology",
    "cto",
    "crm",
    "systems administrator",
    "database administrator",
    "software engineer",
    "developer",
    "devops",
    "data analyst",
    "digital marketing",
    "web developer",
    "information technology",
]
```

### Classification Logic

```python
def analyze_employee_titles(
    titles: list[str],
    manual_keywords: list[str],
    tech_keywords: list[str],
) -> dict:
    manual_count = 0
    tech_count = 0
    for title in titles:
        title_lower = title.lower()
        if any(kw in title_lower for kw in manual_keywords):
            manual_count += 1
        if any(kw in title_lower for kw in tech_keywords):
            tech_count += 1
    return {
        "manual_role_count": manual_count,
        "tech_role_count": tech_count,
    }
```

A title can match both lists (e.g., "IT Data Entry Specialist") — this is fine and won't skew results significantly.

### Enrichment Application

```python
def enrich_lead_with_titles(
    lead: Lead,
    employees: dict,
    manual_keywords: list[str],
    tech_keywords: list[str],
) -> Lead:
    """Apply employee title analysis and company metadata to a lead."""
    titles = employees.get("titles", [])
    lead.employee_titles = titles
    lead.employee_count = employees.get("employee_count")
    lead.founded_year = employees.get("founded_year")
    lead.company_linkedin_url = employees.get("company_linkedin_url", "")

    analysis = analyze_employee_titles(titles, manual_keywords, tech_keywords)
    lead.manual_role_count = analysis["manual_role_count"]
    lead.tech_role_count = analysis["tech_role_count"]
    return lead
```

The `fetch_company_employees()` function returns a dict:

```python
{
    "titles": ["Owner", "Office Manager", "Data Entry Clerk", ...],
    "employee_count": 45,
    "founded_year": 2008,
    "company_linkedin_url": "https://linkedin.com/company/example",
}
```

## Scoring Changes (`src/scoring/score.py`)

### Replace `employee_count` with `employee_title_signals`

The placeholder `employee_count` factor (weight 5) becomes a meaningful title analysis factor:

```python
# --- Employee title signals (manual roles vs tech roles) ---
if lead.employee_titles:  # Have title data
    if lead.tech_role_count > 0:
        # Tech roles present — less likely to need our services
        title_score = 0.0
    elif lead.manual_role_count > 0:
        # Manual roles, no tech roles — strong signal
        title_score = _normalize(lead.manual_role_count, 0, 5)
    else:
        # Employees found but no manual or tech roles — neutral
        title_score = 0.3
else:
    title_score = 0.0  # No data, no signal
breakdown["employee_title_signals"] = title_score
raw_score += title_score * w.get("employee_title_signals", 0)
```

**Scoring logic:**
- No employee data → 0.0 (no signal, same as today)
- Tech roles found → 0.0 (company already has tech investment, poor prospect)
- Manual roles found, no tech roles → 0.0 to 1.0 based on count (normalized over 0–5 range; more manual roles = stronger signal)
- Employees found but no manual/tech roles → 0.3 (mild positive — small company without tech staff is still a prospect)

### Replace `business_age` with real data

The placeholder `business_age` factor (weight 5) gets populated:

```python
# --- Business age ---
if lead.founded_year:
    company_age = datetime.now().year - lead.founded_year
    # Older established businesses (10+ years) are better prospects
    # Young companies (<3 years) may not have budget
    age_score = _normalize(company_age, 3, 20)
else:
    age_score = 0.0  # No data
breakdown["business_age"] = age_score
raw_score += age_score * w.get("business_age", 0)
```

**Scoring logic:**
- No founding year → 0.0 (no signal)
- Under 3 years → 0.0 (too young, less likely to have budget for modernization)
- 3–20 years → linear 0.0 to 1.0 (sweet spot: established but may still use legacy processes)
- Over 20 years → 1.0 (strong signal — long-established businesses are most likely to have entrenched manual processes)

### Weight Rename

In `DEFAULT_WEIGHTS`, `config/settings.example.yaml`, and all 8 vertical configs:
- `employee_count` → `employee_title_signals` (same default weight of 5)
- `business_age` stays the same name (weight 5)

## Config Changes

### `config/settings.example.yaml`

Add keyword lists under the `scoring` section:

```yaml
scoring:
  weights:
    # ... existing weights ...
    employee_title_signals: 5    # renamed from employee_count
    business_age: 5

  # ... existing keyword lists ...

  manual_role_keywords:
    - "data entry"
    - "filing"
    - "receptionist"
    - "bookkeeper"
    - "administrative assistant"
    - "office clerk"
    - "records clerk"
    - "dispatcher"
    - "scheduling coordinator"
    - "front desk"
    - "payroll clerk"
    - "accounts receivable"
    - "accounts payable"

  tech_role_keywords:
    - "it manager"
    - "it director"
    - "chief technology"
    - "cto"
    - "crm"
    - "systems administrator"
    - "database administrator"
    - "software engineer"
    - "developer"
    - "devops"
    - "data analyst"
    - "digital marketing"
    - "web developer"
    - "information technology"
```

### Vertical Configs

All 8 vertical configs (`config/verticals/*.yaml`) have `employee_count: 5` renamed to `employee_title_signals: 5`. No weight value changes needed — the default of 5 is appropriate for all verticals since title analysis is a universal signal.

## Async Processor Changes (`src/enrichment/async_processor.py`)

Add a new enrichment step after contact enrichment:

```python
# Employee title analysis (uses Apollo People Search — free endpoint)
if apollo_key and lead.website:
    try:
        limiter = get_limiter("apollo")
        await limiter.async_wait()
        from src.enrichment.linkedin import (
            fetch_company_employees,
            analyze_employee_titles,
            enrich_lead_with_titles,
        )
        domain = _extract_domain(lead.website)
        if domain:
            employees = await loop.run_in_executor(
                None, fetch_company_employees, domain, apollo_key
            )
            enrich_lead_with_titles(lead, employees, manual_kw_roles, tech_kw_roles)
    except Exception:
        pass
```

The `manual_kw_roles` and `tech_kw_roles` are loaded from settings at the top of `enrich_leads_async()`, alongside the existing `manual_kw` and `complaint_kw`:

```python
manual_kw_roles = settings.get("scoring", {}).get("manual_role_keywords", [])
tech_kw_roles = settings.get("scoring", {}).get("tech_role_keywords", [])
```

These are passed into `_enrich_single()` as additional parameters.

## Contact Enrichment Side Effect

In `src/enrichment/contacts.py`, the existing `search_apollo()` and `_pick_best_contact()` flow is modified to also capture:
- `linkedin_url` from the selected contact → `lead.linkedin_url`

This is a one-line addition to `enrich_lead_contacts()` where it applies the best contact to the lead. No new API call needed.

## Error Handling

Follows existing patterns:
- All exceptions in the LinkedIn enrichment step are caught and swallowed (same as reviews, job postings, contacts)
- If Apollo returns no employees for a domain, the lead's title fields stay at defaults (empty list, 0 counts)
- If Apollo is down or rate limited, enrichment continues without title data
- Scoring gracefully handles missing data (returns 0.0 for both factors)

## Testing

Tests follow the existing mocking patterns (respx for HTTP, unittest.mock for functions):

1. **`tests/enrichment/test_linkedin.py`** — Unit tests for the new module:
   - `fetch_company_employees()` returns parsed employee titles + company metadata
   - `fetch_company_employees()` with empty response returns empty list
   - `fetch_company_employees()` HTTP error returns empty list
   - `analyze_employee_titles()` counts manual roles correctly
   - `analyze_employee_titles()` counts tech roles correctly
   - `analyze_employee_titles()` with no matching titles returns 0/0
   - `enrich_lead_with_titles()` applies all fields to lead

2. **`tests/scoring/test_score.py`** — Additional scoring tests:
   - `employee_title_signals` factor: manual roles present, no tech → positive score
   - `employee_title_signals` factor: tech roles present → 0.0
   - `employee_title_signals` factor: no title data → 0.0
   - `business_age` factor: founded 15 years ago → normalized score
   - `business_age` factor: founded 1 year ago → 0.0
   - `business_age` factor: no founded_year → 0.0

3. **`tests/enrichment/test_async_processor.py`** — Integration:
   - Employee title enrichment runs after contact enrichment
   - Employee title enrichment exception is swallowed

4. **`tests/enrichment/test_contacts.py`** — Verify linkedin_url capture:
   - Apollo result's linkedin_url is stored on lead

5. **Existing tests updated:**
   - Scoring tests referencing `employee_count` weight updated to `employee_title_signals`
   - Config tests for verticals updated for renamed weight

## Files Changed

| File | Action | Purpose |
|------|--------|---------|
| `src/models.py` | Modify | Add 7 new Lead fields |
| `src/enrichment/linkedin.py` | Create | Employee fetching, title analysis, lead enrichment |
| `src/enrichment/contacts.py` | Modify | Capture linkedin_url on best contact |
| `src/enrichment/async_processor.py` | Modify | Add title analysis step after contact enrichment |
| `src/scoring/score.py` | Modify | Replace 2 placeholder factors with real logic |
| `config/settings.example.yaml` | Modify | Add role keyword lists, rename weight |
| `config/verticals/hvac.yaml` | Modify | Rename employee_count → employee_title_signals |
| `config/verticals/dental.yaml` | Modify | Same rename |
| `config/verticals/legal.yaml` | Modify | Same rename |
| `config/verticals/property_management.yaml` | Modify | Same rename |
| `config/verticals/construction.yaml` | Modify | Same rename |
| `config/verticals/insurance.yaml` | Modify | Same rename |
| `config/verticals/accounting.yaml` | Modify | Same rename |
| `config/verticals/auto_repair.yaml` | Modify | Same rename |
| `tests/enrichment/test_linkedin.py` | Create | Unit tests for new module |
| `tests/scoring/test_score.py` | Modify | Tests for new scoring factors |
| `tests/enrichment/test_async_processor.py` | Modify | Integration test for title enrichment |
| `tests/enrichment/test_contacts.py` | Modify | Test linkedin_url capture |
| `tests/test_config.py` | Modify | Update vertical config weight name assertion |
| `FEATURES.md` | Modify | Add LinkedIn enrichment feature |
| `CHANGELOG.md` | Modify | Add entry under [Unreleased] |
