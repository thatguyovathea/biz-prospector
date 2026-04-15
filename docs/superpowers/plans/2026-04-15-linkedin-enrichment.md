# LinkedIn Enrichment for Employee Title Analysis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use Apollo's free People Search API to fetch employee rosters for each lead's company, analyze job titles for manual-process vs. tech-maturity signals, and replace two placeholder scoring factors with real data.

**Architecture:** New `src/enrichment/linkedin.py` module fetches employees via Apollo People Search (already integrated, free), classifies titles using configurable keyword lists, and feeds results into scoring. The async processor calls this after contact enrichment. Two scoring placeholders (`employee_count` → `employee_title_signals`, `business_age`) get real implementations.

**Tech Stack:** Python, httpx (HTTP client), respx (test mocking), pytest, Apollo.io People Search API

---

### Task 1: Add LinkedIn/employee fields to Lead model

**Files:**
- Modify: `src/models.py:56-59`
- Modify: `tests/conftest.py:43-46`

- [ ] **Step 1: Write a failing test that uses the new fields**

Add to `tests/enrichment/test_linkedin.py` (create new file):

```python
"""Tests for LinkedIn employee title analysis."""

from tests.conftest import make_lead


class TestLeadLinkedInFields:
    def test_default_values(self):
        lead = make_lead()
        assert lead.linkedin_url == ""
        assert lead.company_linkedin_url == ""
        assert lead.employee_count is None
        assert lead.founded_year is None
        assert lead.employee_titles == []
        assert lead.manual_role_count == 0
        assert lead.tech_role_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/enrichment/test_linkedin.py::TestLeadLinkedInFields -v`
Expected: FAIL — `Lead` has no field `linkedin_url`

- [ ] **Step 3: Add the fields to Lead model**

In `src/models.py`, after line 59 (the `contact_title` field), add:

```python
    # LinkedIn / Employee title analysis (populated in enrichment)
    linkedin_url: str = ""
    company_linkedin_url: str = ""
    employee_count: Optional[int] = None
    founded_year: Optional[int] = None
    employee_titles: list[str] = Field(default_factory=list)
    manual_role_count: int = 0
    tech_role_count: int = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/enrichment/test_linkedin.py::TestLeadLinkedInFields -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/enrichment/test_linkedin.py
git commit -m "feat: add LinkedIn/employee title fields to Lead model"
```

---

### Task 2: Implement fetch_company_employees

**Files:**
- Create: `src/enrichment/linkedin.py`
- Modify: `tests/enrichment/test_linkedin.py`

- [ ] **Step 1: Write failing tests for fetch_company_employees**

Append to `tests/enrichment/test_linkedin.py`:

```python
import httpx
import respx

from src.enrichment.linkedin import fetch_company_employees


class TestFetchCompanyEmployees:
    @respx.mock
    def test_returns_titles_and_metadata(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={
                "people": [
                    {
                        "title": "Owner",
                        "linkedin_url": "https://linkedin.com/in/owner",
                        "organization": {
                            "estimated_num_employees": 45,
                            "founded_year": 2008,
                            "linkedin_url": "https://linkedin.com/company/acme",
                        },
                    },
                    {
                        "title": "Data Entry Clerk",
                        "linkedin_url": "",
                        "organization": {
                            "estimated_num_employees": 45,
                            "founded_year": 2008,
                            "linkedin_url": "https://linkedin.com/company/acme",
                        },
                    },
                    {
                        "title": "Office Manager",
                        "linkedin_url": "",
                        "organization": {},
                    },
                ],
            })
        )
        result = fetch_company_employees("acmehvac.com", "fake-key")
        assert result["titles"] == ["Owner", "Data Entry Clerk", "Office Manager"]
        assert result["employee_count"] == 45
        assert result["founded_year"] == 2008
        assert result["company_linkedin_url"] == "https://linkedin.com/company/acme"

    @respx.mock
    def test_empty_response(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={"people": []})
        )
        result = fetch_company_employees("nobody.com", "fake-key")
        assert result["titles"] == []
        assert result["employee_count"] is None
        assert result["founded_year"] is None
        assert result["company_linkedin_url"] == ""

    @respx.mock
    def test_http_error_returns_empty(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(500)
        )
        result = fetch_company_employees("error.com", "fake-key")
        assert result["titles"] == []
        assert result["employee_count"] is None

    @respx.mock
    def test_timeout_returns_empty(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        result = fetch_company_employees("slow.com", "fake-key")
        assert result["titles"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/enrichment/test_linkedin.py::TestFetchCompanyEmployees -v`
Expected: FAIL — `cannot import name 'fetch_company_employees'`

- [ ] **Step 3: Implement fetch_company_employees**

Create `src/enrichment/linkedin.py`:

```python
"""LinkedIn enrichment module.

Fetches employee rosters from Apollo People Search API and analyzes
job titles for manual-process vs. tech-maturity signals.
"""

from __future__ import annotations

import httpx
from rich.console import Console

console = Console()


def fetch_company_employees(
    domain: str,
    api_key: str,
    max_results: int = 25,
) -> dict:
    """Fetch employees at a company via Apollo People Search.

    Uses the free People Search endpoint (no credits consumed).
    Returns dict with: titles (list[str]), employee_count, founded_year,
    company_linkedin_url.
    """
    empty = {
        "titles": [],
        "employee_count": None,
        "founded_year": None,
        "company_linkedin_url": "",
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                "https://api.apollo.io/v1/mixed_people/search",
                json={
                    "api_key": api_key,
                    "q_organization_domains": domain,
                    "per_page": max_results,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        console.print(f"    [yellow]Employee fetch failed: {e}[/]")
        return empty

    people = data.get("people", [])
    if not people:
        return empty

    titles = [p.get("title", "") for p in people if p.get("title")]

    # Extract company metadata from first person with organization data
    employee_count = None
    founded_year = None
    company_linkedin_url = ""
    for person in people:
        org = person.get("organization", {})
        if org.get("estimated_num_employees") is not None:
            employee_count = org["estimated_num_employees"]
        if org.get("founded_year") is not None:
            founded_year = org["founded_year"]
        if org.get("linkedin_url"):
            company_linkedin_url = org["linkedin_url"]
        if employee_count is not None and founded_year is not None:
            break

    return {
        "titles": titles,
        "employee_count": employee_count,
        "founded_year": founded_year,
        "company_linkedin_url": company_linkedin_url,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/enrichment/test_linkedin.py::TestFetchCompanyEmployees -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/enrichment/linkedin.py tests/enrichment/test_linkedin.py
git commit -m "feat: add fetch_company_employees via Apollo People Search"
```

---

### Task 3: Implement analyze_employee_titles

**Files:**
- Modify: `src/enrichment/linkedin.py`
- Modify: `tests/enrichment/test_linkedin.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/enrichment/test_linkedin.py`:

```python
from src.enrichment.linkedin import analyze_employee_titles


class TestAnalyzeEmployeeTitles:
    def test_counts_manual_roles(self):
        titles = ["Owner", "Data Entry Clerk", "Receptionist", "Sales Manager"]
        result = analyze_employee_titles(
            titles,
            manual_keywords=["data entry", "receptionist"],
            tech_keywords=["it manager", "developer"],
        )
        assert result["manual_role_count"] == 2
        assert result["tech_role_count"] == 0

    def test_counts_tech_roles(self):
        titles = ["Owner", "IT Manager", "Software Developer", "CRM Administrator"]
        result = analyze_employee_titles(
            titles,
            manual_keywords=["data entry", "receptionist"],
            tech_keywords=["it manager", "developer", "crm"],
        )
        assert result["manual_role_count"] == 0
        assert result["tech_role_count"] == 3

    def test_mixed_roles(self):
        titles = ["Data Entry Clerk", "IT Manager", "Office Manager"]
        result = analyze_employee_titles(
            titles,
            manual_keywords=["data entry"],
            tech_keywords=["it manager"],
        )
        assert result["manual_role_count"] == 1
        assert result["tech_role_count"] == 1

    def test_no_matching_titles(self):
        titles = ["Owner", "Sales Manager", "Accountant"]
        result = analyze_employee_titles(
            titles,
            manual_keywords=["data entry"],
            tech_keywords=["it manager"],
        )
        assert result["manual_role_count"] == 0
        assert result["tech_role_count"] == 0

    def test_empty_titles(self):
        result = analyze_employee_titles(
            [],
            manual_keywords=["data entry"],
            tech_keywords=["it manager"],
        )
        assert result["manual_role_count"] == 0
        assert result["tech_role_count"] == 0

    def test_case_insensitive(self):
        titles = ["DATA ENTRY SPECIALIST", "IT MANAGER"]
        result = analyze_employee_titles(
            titles,
            manual_keywords=["data entry"],
            tech_keywords=["it manager"],
        )
        assert result["manual_role_count"] == 1
        assert result["tech_role_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/enrichment/test_linkedin.py::TestAnalyzeEmployeeTitles -v`
Expected: FAIL — `cannot import name 'analyze_employee_titles'`

- [ ] **Step 3: Implement analyze_employee_titles**

Append to `src/enrichment/linkedin.py`:

```python
def analyze_employee_titles(
    titles: list[str],
    manual_keywords: list[str],
    tech_keywords: list[str],
) -> dict:
    """Classify employee titles as manual-process or tech-maturity signals.

    Returns dict with: manual_role_count, tech_role_count.
    """
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/enrichment/test_linkedin.py::TestAnalyzeEmployeeTitles -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/enrichment/linkedin.py tests/enrichment/test_linkedin.py
git commit -m "feat: add analyze_employee_titles for manual/tech role classification"
```

---

### Task 4: Implement enrich_lead_with_titles

**Files:**
- Modify: `src/enrichment/linkedin.py`
- Modify: `tests/enrichment/test_linkedin.py`

- [ ] **Step 1: Write failing test**

Append to `tests/enrichment/test_linkedin.py`:

```python
from src.enrichment.linkedin import enrich_lead_with_titles


class TestEnrichLeadWithTitles:
    def test_applies_all_fields(self):
        lead = make_lead()
        employees = {
            "titles": ["Owner", "Data Entry Clerk", "IT Manager"],
            "employee_count": 45,
            "founded_year": 2008,
            "company_linkedin_url": "https://linkedin.com/company/acme",
        }
        enrich_lead_with_titles(
            lead, employees,
            manual_keywords=["data entry"],
            tech_keywords=["it manager"],
        )
        assert lead.employee_titles == ["Owner", "Data Entry Clerk", "IT Manager"]
        assert lead.employee_count == 45
        assert lead.founded_year == 2008
        assert lead.company_linkedin_url == "https://linkedin.com/company/acme"
        assert lead.manual_role_count == 1
        assert lead.tech_role_count == 1

    def test_empty_employees(self):
        lead = make_lead()
        employees = {
            "titles": [],
            "employee_count": None,
            "founded_year": None,
            "company_linkedin_url": "",
        }
        enrich_lead_with_titles(
            lead, employees,
            manual_keywords=["data entry"],
            tech_keywords=["it manager"],
        )
        assert lead.employee_titles == []
        assert lead.employee_count is None
        assert lead.founded_year is None
        assert lead.manual_role_count == 0
        assert lead.tech_role_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/enrichment/test_linkedin.py::TestEnrichLeadWithTitles -v`
Expected: FAIL — `cannot import name 'enrich_lead_with_titles'`

- [ ] **Step 3: Implement enrich_lead_with_titles**

Append to `src/enrichment/linkedin.py`:

```python
from src.models import Lead


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

Note: Move the `from src.models import Lead` import to the top of the file (alongside the existing imports).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/enrichment/test_linkedin.py -v`
Expected: PASS (all 13 tests in the file)

- [ ] **Step 5: Commit**

```bash
git add src/enrichment/linkedin.py tests/enrichment/test_linkedin.py
git commit -m "feat: add enrich_lead_with_titles to apply analysis to leads"
```

---

### Task 5: Replace scoring placeholders with real logic

**Files:**
- Modify: `src/scoring/score.py:19-29,103-107`
- Modify: `tests/scoring/test_score.py`
- Modify: `tests/conftest.py:88-89`

- [ ] **Step 1: Write failing tests for the new scoring factors**

Append to `tests/scoring/test_score.py`:

```python
class TestEmployeeTitleSignalsFactor:
    def test_manual_roles_no_tech(self):
        lead = make_lead(employee_titles=["Owner", "Data Entry Clerk", "Receptionist"],
                         manual_role_count=2, tech_role_count=0)
        score_lead(lead)
        assert lead.score_breakdown["employee_title_signals"] > 0

    def test_tech_roles_present(self):
        lead = make_lead(employee_titles=["Owner", "IT Manager"],
                         manual_role_count=0, tech_role_count=1)
        score_lead(lead)
        assert lead.score_breakdown["employee_title_signals"] == 0.0

    def test_no_title_data(self):
        lead = make_lead(employee_titles=[], manual_role_count=0, tech_role_count=0)
        score_lead(lead)
        assert lead.score_breakdown["employee_title_signals"] == 0.0

    def test_employees_but_no_manual_or_tech(self):
        lead = make_lead(employee_titles=["Owner", "Sales Manager"],
                         manual_role_count=0, tech_role_count=0)
        score_lead(lead)
        assert lead.score_breakdown["employee_title_signals"] == pytest.approx(0.3, abs=0.01)

    def test_many_manual_roles_high_score(self):
        lead = make_lead(employee_titles=["A", "B", "C", "D", "E", "F"],
                         manual_role_count=5, tech_role_count=0)
        score_lead(lead)
        assert lead.score_breakdown["employee_title_signals"] == 1.0


class TestBusinessAgeFactor:
    def test_founded_15_years_ago(self):
        lead = make_lead(founded_year=2011)
        score_lead(lead)
        score = lead.score_breakdown["business_age"]
        assert 0.5 < score < 1.0

    def test_founded_1_year_ago(self):
        lead = make_lead(founded_year=2025)
        score_lead(lead)
        assert lead.score_breakdown["business_age"] == 0.0

    def test_founded_30_years_ago(self):
        lead = make_lead(founded_year=1996)
        score_lead(lead)
        assert lead.score_breakdown["business_age"] == 1.0

    def test_no_founded_year(self):
        lead = make_lead(founded_year=None)
        score_lead(lead)
        assert lead.score_breakdown["business_age"] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/scoring/test_score.py::TestEmployeeTitleSignalsFactor -v`
Expected: FAIL — `employee_title_signals` key not in breakdown

Run: `python -m pytest tests/scoring/test_score.py::TestBusinessAgeFactor::test_founded_15_years_ago -v`
Expected: FAIL — `business_age` is still 0.0 (placeholder)

- [ ] **Step 3: Update DEFAULT_WEIGHTS in score.py**

In `src/scoring/score.py`, replace lines 20-29:

```python
DEFAULT_WEIGHTS = {
    "website_outdated": 20,
    "no_crm_detected": 15,
    "no_scheduling_tool": 10,
    "no_chat_widget": 5,
    "manual_job_postings": 25,
    "negative_reviews_ops": 15,
    "business_age": 5,
    "employee_count": 5,
}
```

With:

```python
DEFAULT_WEIGHTS = {
    "website_outdated": 20,
    "no_crm_detected": 15,
    "no_scheduling_tool": 10,
    "no_chat_widget": 5,
    "manual_job_postings": 25,
    "negative_reviews_ops": 15,
    "business_age": 5,
    "employee_title_signals": 5,
}
```

- [ ] **Step 4: Replace the two placeholder scoring blocks**

In `src/scoring/score.py`, replace lines 103-107:

```python
    # --- Business age (placeholder — would need external data) ---
    breakdown["business_age"] = 0.0  # TODO: enrich with founding date

    # --- Employee count (placeholder) ---
    breakdown["employee_count"] = 0.0  # TODO: enrich with headcount
```

With:

```python
    # --- Business age ---
    if lead.founded_year:
        company_age = datetime.now().year - lead.founded_year
        age_score = _normalize(company_age, 3, 20)
    else:
        age_score = 0.0
    breakdown["business_age"] = age_score
    raw_score += age_score * w.get("business_age", 0)

    # --- Employee title signals (manual roles vs tech roles) ---
    if lead.employee_titles:
        if lead.tech_role_count > 0:
            title_score = 0.0
        elif lead.manual_role_count > 0:
            title_score = _normalize(lead.manual_role_count, 0, 5)
        else:
            title_score = 0.3
    else:
        title_score = 0.0
    breakdown["employee_title_signals"] = title_score
    raw_score += title_score * w.get("employee_title_signals", 0)
```

- [ ] **Step 5: Update conftest.py sample_settings weight name**

In `tests/conftest.py`, replace line 89:

```python
                "employee_count": 5,
```

With:

```python
                "employee_title_signals": 5,
```

- [ ] **Step 6: Update existing test that checks breakdown keys**

In `tests/scoring/test_score.py`, in the `TestCompositeScoring` class, find `test_breakdown_has_all_factors` and replace:

```python
        expected_keys = {
            "website_outdated", "no_crm_detected", "no_scheduling_tool",
            "no_chat_widget", "manual_job_postings", "negative_reviews_ops",
            "business_age", "employee_count",
        }
```

With:

```python
        expected_keys = {
            "website_outdated", "no_crm_detected", "no_scheduling_tool",
            "no_chat_widget", "manual_job_postings", "negative_reviews_ops",
            "business_age", "employee_title_signals",
        }
```

- [ ] **Step 7: Run all scoring tests**

Run: `python -m pytest tests/scoring/test_score.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/scoring/score.py tests/scoring/test_score.py tests/conftest.py
git commit -m "feat: replace scoring placeholders with employee title signals and business age"
```

---

### Task 6: Capture linkedin_url in contact enrichment

**Files:**
- Modify: `src/enrichment/contacts.py:210-213`
- Modify: `tests/enrichment/test_contacts.py`

- [ ] **Step 1: Write failing test**

Append to `tests/enrichment/test_contacts.py`:

```python
class TestLinkedInUrlCapture:
    @respx.mock
    def test_captures_linkedin_url_from_apollo(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={
                "people": [{
                    "first_name": "Bob",
                    "last_name": "Owner",
                    "email": "bob@acme.com",
                    "title": "Owner",
                    "linkedin_url": "https://linkedin.com/in/bobowner",
                    "phone_number": "",
                }]
            })
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake-key")
        assert lead.linkedin_url == "https://linkedin.com/in/bobowner"

    @respx.mock
    def test_captures_linkedin_url_from_hunter(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={"people": []})
        )
        respx.get("https://api.hunter.io/v2/domain-search").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "emails": [{
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "value": "jane@acme.com",
                        "position": "CEO",
                        "linkedin": "https://linkedin.com/in/janedoe",
                    }]
                }
            })
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake", hunter_key="fake")
        assert lead.linkedin_url == "https://linkedin.com/in/janedoe"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/enrichment/test_contacts.py::TestLinkedInUrlCapture -v`
Expected: FAIL — `lead.linkedin_url` is still `""`

- [ ] **Step 3: Add linkedin_url capture to enrich_lead_contacts**

In `src/enrichment/contacts.py`, in the `enrich_lead_contacts` function, after line 213 (`lead.contact_title = best.get("title", "")`), add:

```python
        lead.linkedin_url = best.get("linkedin_url", "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/enrichment/test_contacts.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/enrichment/contacts.py tests/enrichment/test_contacts.py
git commit -m "feat: capture contact linkedin_url during enrichment"
```

---

### Task 7: Wire LinkedIn enrichment into async processor

**Files:**
- Modify: `src/enrichment/async_processor.py:1-5,35-41,84-96,99-111`
- Modify: `tests/enrichment/test_async_processor.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/enrichment/test_async_processor.py`:

```python
class TestLinkedInEnrichment:
    @pytest.mark.asyncio
    async def test_title_enrichment_runs(self, mock_settings):
        leads = [make_lead(id="li1", website="https://acme.com")]
        mock_fetch = MagicMock(return_value={
            "titles": ["Owner", "Data Entry Clerk"],
            "employee_count": 10,
            "founded_year": 2010,
            "company_linkedin_url": "",
        })

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"), \
             patch("src.enrichment.async_processor.fetch_company_employees", mock_fetch), \
             patch("src.enrichment.async_processor.enrich_lead_with_titles") as mock_enrich:
            results = await enrich_leads_async(leads, max_concurrent=2)

        mock_fetch.assert_called_once()
        mock_enrich.assert_called_once()

    @pytest.mark.asyncio
    async def test_title_enrichment_exception_swallowed(self, mock_settings):
        leads = [make_lead(id="li_err", website="https://error.com")]

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"), \
             patch("src.enrichment.async_processor.fetch_company_employees", side_effect=Exception("Apollo down")):
            results = await enrich_leads_async(leads, max_concurrent=2)

        assert len(results) == 1
        assert results[0].enriched_at is not None

    @pytest.mark.asyncio
    async def test_skips_title_enrichment_without_website(self, mock_settings):
        leads = [make_lead(id="noweb", website="")]
        mock_fetch = MagicMock()

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"), \
             patch("src.enrichment.async_processor.fetch_company_employees", mock_fetch):
            results = await enrich_leads_async(leads, max_concurrent=2)

        mock_fetch.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/enrichment/test_async_processor.py::TestLinkedInEnrichment -v`
Expected: FAIL — `fetch_company_employees` not imported in async_processor

- [ ] **Step 3: Update async_processor.py imports**

In `src/enrichment/async_processor.py`, add after line 19 (`from src.enrichment.contacts import enrich_lead_contacts`):

```python
from src.enrichment.contacts import enrich_lead_contacts, _extract_domain
from src.enrichment.linkedin import fetch_company_employees, enrich_lead_with_titles
```

And remove the original line 19 since we replaced it with the expanded import.

- [ ] **Step 4: Update _enrich_single function signature**

In `src/enrichment/async_processor.py`, replace the `_enrich_single` function signature (lines 35-41):

```python
async def _enrich_single(
    lead: Lead,
    settings: dict,
    semaphore: asyncio.Semaphore,
    complaint_kw: list[str],
    manual_kw: list[str],
) -> Lead:
```

With:

```python
async def _enrich_single(
    lead: Lead,
    settings: dict,
    semaphore: asyncio.Semaphore,
    complaint_kw: list[str],
    manual_kw: list[str],
    manual_role_kw: list[str],
    tech_role_kw: list[str],
) -> Lead:
```

- [ ] **Step 5: Add LinkedIn enrichment step after contact enrichment**

In `src/enrichment/async_processor.py`, after the contact enrichment block (after line 93, the `except Exception: pass` for contacts), add:

```python
        # Employee title analysis (uses Apollo People Search — free endpoint)
        apollo_key = settings.get("apis", {}).get("apollo_key", "")
        if apollo_key and lead.website:
            try:
                limiter = get_limiter("apollo")
                await limiter.async_wait()
                domain = _extract_domain(lead.website)
                if domain:
                    employees = await loop.run_in_executor(
                        None, fetch_company_employees, domain, apollo_key
                    )
                    enrich_lead_with_titles(lead, employees, manual_role_kw, tech_role_kw)
            except Exception:
                pass
```

Note: The `apollo_key` variable is already defined above from the contact enrichment block. To avoid redefinition, remove the duplicate and reuse the existing one. The simplest approach: the `apollo_key` from line 85 is still in scope, so just use it directly in the new block without re-declaring it.

- [ ] **Step 6: Update enrich_leads_async to load and pass new keyword lists**

In `src/enrichment/async_processor.py`, in the `enrich_leads_async` function, after line 111 (`manual_kw = settings.get(...)`) add:

```python
    manual_role_kw = settings.get("scoring", {}).get("manual_role_keywords", [])
    tech_role_kw = settings.get("scoring", {}).get("tech_role_keywords", [])
```

And update the `_enrich_single` call in the tasks list comprehension (around line 120) from:

```python
    tasks = [
        _enrich_single(lead, settings, semaphore, complaint_kw, manual_kw)
        for lead in leads
    ]
```

To:

```python
    tasks = [
        _enrich_single(lead, settings, semaphore, complaint_kw, manual_kw,
                        manual_role_kw, tech_role_kw)
        for lead in leads
    ]
```

- [ ] **Step 7: Run all async processor tests**

Run: `python -m pytest tests/enrichment/test_async_processor.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/enrichment/async_processor.py tests/enrichment/test_async_processor.py
git commit -m "feat: wire LinkedIn title enrichment into async processor"
```

---

### Task 8: Update config and documentation

**Files:**
- Modify: `config/settings.example.yaml:42`
- Modify: `FEATURES.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update settings.example.yaml**

In `config/settings.example.yaml`, replace line 42:

```yaml
    employee_count: 5          # Sweet spot: 10-200 employees
```

With:

```yaml
    employee_title_signals: 5  # Manual vs tech roles in employee titles
```

Then append after the `ops_complaint_keywords` section (after line 69), add:

```yaml

  # Employee title keywords that signal manual processes
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

  # Employee title keywords that signal tech maturity
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

- [ ] **Step 2: Update FEATURES.md**

In `FEATURES.md`, add a new entry under the `## Enrichment` section:

```markdown
- **Employee title analysis** — Apollo People Search fetches employee rosters, classifies titles as manual-process or tech-maturity signals, feeds into scoring
```

- [ ] **Step 3: Update CHANGELOG.md**

In `CHANGELOG.md`, add under the `## [Unreleased]` → `### Added` section:

```markdown
- Employee title analysis via Apollo People Search (free endpoint) for scoring
- Business age scoring from Apollo organization data (founded year)
- LinkedIn URL capture for contacts
```

- [ ] **Step 4: Commit**

```bash
git add config/settings.example.yaml FEATURES.md CHANGELOG.md
git commit -m "docs: update config, features, and changelog for LinkedIn enrichment"
```

---

### Task 9: Run full test suite and verify coverage

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest --cov=src --cov-branch -q`
Expected: All tests pass, coverage >= 99%.

- [ ] **Step 2: Check for any missed coverage**

Run: `python -m pytest --cov=src --cov-branch --cov-report=term-missing -q 2>&1 | grep -E "FAIL|linkedin|score"`
Expected: `src/enrichment/linkedin.py` at 100% or close. `src/scoring/score.py` at 99%+.

- [ ] **Step 3: Run validation scripts**

Run: `bash scripts/validate.sh`
Expected: All checks PASS.

Run: `bash scripts/check-phase-gate.sh`
Expected: Phase gate PASSED.

- [ ] **Step 4: Commit if any fixes were needed**

If any tests failed or coverage dropped, fix and commit. Otherwise, no commit needed.
