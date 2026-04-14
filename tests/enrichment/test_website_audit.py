"""Tests for website auditor — pattern matching for CRM, chat, scheduling, tech stack."""

from unittest.mock import patch

import httpx
import pytest
import respx

from src.enrichment.website_audit import (
    AuditResult,
    _check_patterns,
    _check_mobile_responsive,
    _detect_tech_from_html,
    _find_outdated_signals,
    audit_website,
    enrich_lead_with_audit,
    CRM_PATTERNS,
    CHAT_PATTERNS,
    SCHEDULING_PATTERNS,
)
from bs4 import BeautifulSoup
from tests.conftest import make_lead, build_html


class TestCRMDetection:
    @pytest.mark.parametrize("crm_name,pattern_fragment", [
        ("hubspot", "hubspot"),
        ("salesforce", "salesforce"),
        ("pipedrive", "pipedrive"),
        ("zoho", "zoho"),
        ("freshsales", "freshsales"),
        ("keap", "keap.com"),
        ("infusionsoft", "infusionsoft"),
        ("activecampaign", "activecampaign"),
    ])
    def test_detects_crm(self, crm_name, pattern_fragment):
        html = build_html(has_crm=crm_name)
        assert _check_patterns(html, CRM_PATTERNS) is True

    def test_no_crm_in_plain_html(self):
        html = build_html()
        assert _check_patterns(html, CRM_PATTERNS) is False


class TestChatDetection:
    @pytest.mark.parametrize("chat_name", [
        "intercom", "drift", "crisp", "tawk", "livechat",
        "zendesk", "freshchat", "tidio", "chatwoot",
    ])
    def test_detects_chat(self, chat_name):
        html = build_html(has_chat=chat_name)
        assert _check_patterns(html, CHAT_PATTERNS) is True

    def test_no_chat_in_plain_html(self):
        html = build_html()
        assert _check_patterns(html, CHAT_PATTERNS) is False


class TestSchedulingDetection:
    @pytest.mark.parametrize("sched_name", [
        "calendly", "acuity", "cal.com", "square_appointments",
        "booksy", "vagaro", "setmore",
    ])
    def test_detects_scheduling(self, sched_name):
        html = build_html(has_scheduling=sched_name)
        assert _check_patterns(html, SCHEDULING_PATTERNS) is True

    def test_no_scheduling_in_plain_html(self):
        html = build_html()
        assert _check_patterns(html, SCHEDULING_PATTERNS) is False


class TestTechStackDetection:
    @pytest.mark.parametrize("tech", [
        "wordpress", "wix", "squarespace", "shopify", "webflow",
        "google_analytics", "google_tag_manager", "facebook_pixel",
        "bootstrap", "tailwind", "react", "angular", "vue",
    ])
    def test_detects_tech(self, tech):
        html = build_html(techs=[tech])
        soup = BeautifulSoup(html, "html.parser")
        detected = _detect_tech_from_html(html, soup)
        assert tech in detected

    def test_plain_html_no_tech(self):
        html = build_html()
        soup = BeautifulSoup(html, "html.parser")
        detected = _detect_tech_from_html(html, soup)
        assert detected == []

    def test_multiple_techs(self):
        html = build_html(techs=["wordpress", "google_analytics", "bootstrap"])
        soup = BeautifulSoup(html, "html.parser")
        detected = _detect_tech_from_html(html, soup)
        assert "wordpress" in detected
        assert "google_analytics" in detected
        assert "bootstrap" in detected


class TestOutdatedSignals:
    def test_legacy_jquery(self):
        html = build_html(outdated=["legacy_jquery"])
        found = _find_outdated_signals(html)
        assert "legacy_jquery" in found

    def test_old_wordpress(self):
        html = build_html(outdated=["old_wordpress"])
        found = _find_outdated_signals(html)
        assert "old_wordpress" in found

    def test_framesets(self):
        html = build_html(outdated=["frameset"])
        found = _find_outdated_signals(html)
        assert "framesets" in found

    def test_marquee_and_blink(self):
        html = build_html(outdated=["marquee", "blink"])
        found = _find_outdated_signals(html)
        assert "marquee" in found
        assert "blink" in found

    def test_flash(self):
        html = build_html(outdated=["flash"])
        found = _find_outdated_signals(html)
        assert "flash_swf" in found

    def test_no_outdated_signals(self):
        html = build_html()
        found = _find_outdated_signals(html)
        assert found == []

    def test_jquery_3x_not_flagged(self):
        html = '<script src="jquery.min.js?ver=3.6.0"></script>'
        found = _find_outdated_signals(html)
        assert "legacy_jquery" not in found


class TestMobileResponsive:
    def test_responsive_with_viewport(self):
        html = build_html(has_viewport=True)
        soup = BeautifulSoup(html, "html.parser")
        assert _check_mobile_responsive(soup) is True

    def test_not_responsive_without_viewport(self):
        html = build_html(has_viewport=False)
        soup = BeautifulSoup(html, "html.parser")
        assert _check_mobile_responsive(soup) is False


class TestAuditWebsite:
    @respx.mock
    def test_full_audit(self):
        html = build_html(
            has_crm="hubspot",
            has_chat="intercom",
            has_scheduling="calendly",
            techs=["wordpress", "google_analytics"],
            has_viewport=True,
        )
        respx.get("https://acmehvac.com").mock(
            return_value=httpx.Response(200, text=html)
        )
        result = audit_website("https://acmehvac.com")
        assert result.reachable is True
        assert result.has_ssl is True
        assert result.has_crm is True
        assert result.has_chat is True
        assert result.has_scheduling is True
        assert result.is_mobile_responsive is True
        assert "wordpress" in result.detected_tech
        assert "google_analytics" in result.detected_tech

    @respx.mock
    def test_bare_website(self):
        html = build_html(has_viewport=False)
        respx.get("https://baresite.com").mock(
            return_value=httpx.Response(200, text=html)
        )
        result = audit_website("https://baresite.com")
        assert result.reachable is True
        assert result.has_crm is False
        assert result.has_chat is False
        assert result.has_scheduling is False
        assert result.is_mobile_responsive is False

    @respx.mock
    def test_timeout_handling(self):
        respx.get("https://slow.com").mock(side_effect=httpx.TimeoutException("timed out"))
        result = audit_website("https://slow.com")
        assert result.reachable is False
        assert result.error == "timeout"

    @respx.mock
    def test_http_error_handling(self):
        respx.get("https://broken.com").mock(
            return_value=httpx.Response(404)
        )
        result = audit_website("https://broken.com")
        assert result.reachable is False
        assert "http_404" in result.error

    def test_empty_url(self):
        result = audit_website("")
        assert result.error == "no_url"

    @respx.mock
    def test_normalizes_url(self):
        html = build_html()
        respx.get("https://example.com").mock(
            return_value=httpx.Response(200, text=html)
        )
        result = audit_website("example.com")
        assert result.reachable is True


class TestEnrichLeadWithAudit:
    def test_applies_audit_to_lead(self):
        lead = make_lead()
        audit = AuditResult(
            url="https://acmehvac.com",
            reachable=True,
            has_ssl=True,
            has_crm=True,
            has_chat=False,
            has_scheduling=True,
            is_mobile_responsive=True,
            detected_tech=["wordpress", "react"],
        )
        enrich_lead_with_audit(lead, audit)
        assert lead.has_crm is True
        assert lead.has_chat_widget is False
        assert lead.has_scheduling is True
        assert lead.has_ssl is True
        assert lead.is_mobile_responsive is True
        assert lead.tech_stack == ["wordpress", "react"]
