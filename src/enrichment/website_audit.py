"""Website auditor module.

Checks each lead's website for signals of outdated tech:
- Missing CRM tracking scripts
- No chat widget
- No scheduling/booking tool
- No SSL
- Poor mobile responsiveness
- Outdated tech stack via BuiltWith
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup
from rich.console import Console

from src.models import Lead

console = Console()

# Known script patterns for detection
CRM_PATTERNS = [
    r"hubspot", r"salesforce", r"pipedrive", r"zoho", r"freshsales",
    r"activecampaign", r"keap\.com", r"infusionsoft", r"copper\.com",
    r"close\.com", r"nutshell",
]

CHAT_PATTERNS = [
    r"intercom", r"drift", r"crisp", r"tawk\.to", r"livechat",
    r"zendesk", r"freshchat", r"tidio", r"olark", r"chatwoot",
    r"hubspot.*conversations",
]

SCHEDULING_PATTERNS = [
    r"calendly", r"acuity", r"cal\.com", r"square.*appointments",
    r"booksy", r"vagaro", r"setmore", r"appointy", r"simplybook",
    r"zocdoc", r"schedulicity",
]

OUTDATED_SIGNALS = [
    r"jquery\.min\.js\?ver=[12]\.",  # jQuery 1.x or 2.x
    r"wp-content.*flavor=starter",    # Very old WordPress themes
    r"<meta name=\"generator\" content=\"wordpress [1-4]\.",  # WP < 5
    r"<frameset",                     # Framesets
    r"<marquee",                      # Marquee tags
    r"<blink",                        # Blink tags
    r"swfobject",                     # Flash
    r"\.swf",                         # Flash files
]


@dataclass
class AuditResult:
    """Result of auditing a single website."""

    url: str
    reachable: bool = False
    has_ssl: bool = False
    has_crm: bool = False
    has_chat: bool = False
    has_scheduling: bool = False
    is_mobile_responsive: bool = False
    outdated_signals_found: list[str] | None = None
    detected_tech: list[str] | None = None
    page_speed_score: int | None = None
    error: str | None = None


def _check_patterns(html: str, patterns: list[str]) -> bool:
    """Check if any regex pattern matches in the HTML."""
    html_lower = html.lower()
    return any(re.search(p, html_lower) for p in patterns)


def _find_outdated_signals(html: str) -> list[str]:
    """Return list of outdated tech signals found."""
    found = []
    html_lower = html.lower()
    labels = [
        "legacy_jquery", "old_wp_theme", "old_wordpress",
        "framesets", "marquee", "blink", "flash_swfobject", "flash_swf",
    ]
    for pattern, label in zip(OUTDATED_SIGNALS, labels):
        if re.search(pattern, html_lower):
            found.append(label)
    return found


def _check_mobile_responsive(soup: BeautifulSoup) -> bool:
    """Check for viewport meta tag (basic mobile responsiveness indicator)."""
    viewport = soup.find("meta", attrs={"name": "viewport"})
    return viewport is not None


def _detect_tech_from_html(html: str, soup: BeautifulSoup) -> list[str]:
    """Detect technologies from HTML source (lightweight, no API needed)."""
    tech = []
    html_lower = html.lower()

    checks = {
        "wordpress": [r"wp-content", r"wp-includes"],
        "wix": [r"wix\.com", r"_wix"],
        "squarespace": [r"squarespace\.com", r"static\.squarespace"],
        "shopify": [r"shopify", r"cdn\.shopify"],
        "webflow": [r"webflow"],
        "google_analytics": [r"google-analytics\.com", r"gtag"],
        "google_tag_manager": [r"googletagmanager\.com"],
        "facebook_pixel": [r"fbevents\.js", r"facebook\.com/tr"],
        "bootstrap": [r"bootstrap\.min"],
        "tailwind": [r"tailwindcss", r"tailwind"],
        "react": [r"react\.production", r"__react"],
        "angular": [r"angular", r"ng-version"],
        "vue": [r"vue\.min\.js", r"vue\.runtime"],
    }

    for tech_name, patterns in checks.items():
        if any(re.search(p, html_lower) for p in patterns):
            tech.append(tech_name)

    return tech


def audit_website(url: str, timeout: int = 15) -> AuditResult:
    """Audit a single website for modernization signals."""
    if not url:
        return AuditResult(url=url, error="no_url")

    # Normalize URL
    if not url.startswith("http"):
        url = f"https://{url}"

    result = AuditResult(url=url)

    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BizProspector/1.0)"},
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()

            result.reachable = True
            result.has_ssl = resp.url.scheme == "https"

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            result.has_crm = _check_patterns(html, CRM_PATTERNS)
            result.has_chat = _check_patterns(html, CHAT_PATTERNS)
            result.has_scheduling = _check_patterns(html, SCHEDULING_PATTERNS)
            result.is_mobile_responsive = _check_mobile_responsive(soup)
            result.outdated_signals_found = _find_outdated_signals(html)
            result.detected_tech = _detect_tech_from_html(html, soup)

    except httpx.TimeoutException:
        result.error = "timeout"
    except httpx.HTTPStatusError as e:
        result.error = f"http_{e.response.status_code}"
    except Exception as e:
        result.error = str(e)[:200]

    return result


def enrich_lead_with_audit(lead: Lead, audit: AuditResult) -> Lead:
    """Apply audit results to a Lead object."""
    lead.has_crm = audit.has_crm
    lead.has_chat_widget = audit.has_chat
    lead.has_scheduling = audit.has_scheduling
    lead.has_ssl = audit.has_ssl
    lead.is_mobile_responsive = audit.is_mobile_responsive
    lead.tech_stack = audit.detected_tech or []
    return lead
