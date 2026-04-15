"""Tests for BuiltWith API integration."""

import httpx
import pytest
import respx

from src.enrichment.builtwith import (
    BUILTWITH_API_URL,
    _normalize_tech_name,
    fetch_builtwith,
    merge_tech_stacks,
    parse_builtwith_response,
)


# --- Sample API responses ---

SAMPLE_BUILTWITH_RESPONSE = {
    "Results": [{
        "Result": {
            "Paths": [{
                "Technologies": [
                    {
                        "Name": "WordPress 6.4",
                        "Tag": "cms",
                        "Categories": ["CMS"],
                    },
                    {
                        "Name": "jQuery 3.7.1",
                        "Tag": "javascript-framework",
                        "Categories": ["JavaScript Framework"],
                    },
                    {
                        "Name": "HubSpot",
                        "Tag": "marketing-automation",
                        "Categories": ["Marketing Automation", "CRM"],
                    },
                    {
                        "Name": "Google Analytics",
                        "Tag": "analytics",
                        "Categories": ["Analytics"],
                    },
                    {
                        "Name": "Nginx",
                        "Tag": "web-server",
                        "Categories": ["Web Server"],
                    },
                ]
            }]
        }
    }]
}

EMPTY_RESPONSE = {"Results": []}

MULTI_PATH_RESPONSE = {
    "Results": [{
        "Result": {
            "Paths": [
                {
                    "Technologies": [
                        {"Name": "WordPress 6.4", "Tag": "cms", "Categories": ["CMS"]},
                    ]
                },
                {
                    "Technologies": [
                        {"Name": "Cloudflare", "Tag": "cdn", "Categories": ["CDN"]},
                    ]
                },
            ]
        }
    }]
}


class TestNormalizeTechName:
    def test_strips_version(self):
        assert _normalize_tech_name("WordPress 6.4") == "wordpress"

    def test_strips_complex_version(self):
        assert _normalize_tech_name("jQuery 3.7.1") == "jquery"

    def test_spaces_to_underscores(self):
        assert _normalize_tech_name("Google Analytics") == "google_analytics"

    def test_already_lowercase(self):
        assert _normalize_tech_name("nginx") == "nginx"

    def test_special_chars_removed(self):
        assert _normalize_tech_name("ASP.NET") == "asp_net"

    def test_empty_string(self):
        assert _normalize_tech_name("") == ""

    def test_version_only(self):
        # Version-only strings don't occur in real BuiltWith data,
        # but the regex only strips trailing versions after a name
        assert _normalize_tech_name("3.7.1") == "3_7_1"

    def test_trailing_spaces(self):
        assert _normalize_tech_name("  WordPress 6.4  ") == "wordpress"


class TestParseBuiltWithResponse:
    def test_parses_technologies(self):
        techs = parse_builtwith_response(SAMPLE_BUILTWITH_RESPONSE)
        assert len(techs) == 5
        names = [t["normalized"] for t in techs]
        assert "wordpress" in names
        assert "jquery" in names
        assert "hubspot" in names
        assert "google_analytics" in names
        assert "nginx" in names

    def test_preserves_original_name(self):
        techs = parse_builtwith_response(SAMPLE_BUILTWITH_RESPONSE)
        wp = next(t for t in techs if t["normalized"] == "wordpress")
        assert wp["name"] == "WordPress 6.4"

    def test_preserves_tag(self):
        techs = parse_builtwith_response(SAMPLE_BUILTWITH_RESPONSE)
        wp = next(t for t in techs if t["normalized"] == "wordpress")
        assert wp["tag"] == "cms"

    def test_preserves_categories(self):
        techs = parse_builtwith_response(SAMPLE_BUILTWITH_RESPONSE)
        hs = next(t for t in techs if t["normalized"] == "hubspot")
        assert "Marketing Automation" in hs["categories"]
        assert "CRM" in hs["categories"]

    def test_empty_results(self):
        assert parse_builtwith_response(EMPTY_RESPONSE) == []

    def test_empty_dict(self):
        assert parse_builtwith_response({}) == []

    def test_multi_path_response(self):
        techs = parse_builtwith_response(MULTI_PATH_RESPONSE)
        names = [t["normalized"] for t in techs]
        assert "wordpress" in names
        assert "cloudflare" in names

    def test_skips_empty_name(self):
        data = {
            "Results": [{
                "Result": {
                    "Paths": [{
                        "Technologies": [
                            {"Name": "", "Tag": "unknown", "Categories": []},
                            {"Name": "Valid Tech", "Tag": "cms", "Categories": []},
                        ]
                    }]
                }
            }]
        }
        techs = parse_builtwith_response(data)
        assert len(techs) == 1
        assert techs[0]["normalized"] == "valid_tech"


class TestMergeTechStacks:
    def test_merges_unique(self):
        html = ["wordpress", "google_analytics"]
        bw = [
            {"normalized": "nginx", "name": "Nginx"},
            {"normalized": "cloudflare", "name": "Cloudflare"},
        ]
        result = merge_tech_stacks(html, bw)
        assert set(result) == {"wordpress", "google_analytics", "nginx", "cloudflare"}

    def test_deduplicates(self):
        html = ["wordpress", "google_analytics"]
        bw = [
            {"normalized": "wordpress", "name": "WordPress 6.4"},
            {"normalized": "nginx", "name": "Nginx"},
        ]
        result = merge_tech_stacks(html, bw)
        assert result.count("wordpress") == 1

    def test_sorted(self):
        html = ["zeta", "alpha"]
        bw = [{"normalized": "mid", "name": "Mid"}]
        result = merge_tech_stacks(html, bw)
        assert result == ["alpha", "mid", "zeta"]

    def test_empty_builtwith(self):
        html = ["wordpress"]
        result = merge_tech_stacks(html, [])
        assert result == ["wordpress"]

    def test_empty_html(self):
        bw = [{"normalized": "nginx", "name": "Nginx"}]
        result = merge_tech_stacks([], bw)
        assert result == ["nginx"]

    def test_both_empty(self):
        assert merge_tech_stacks([], []) == []

    def test_skips_empty_normalized(self):
        html = ["wordpress"]
        bw = [{"normalized": "", "name": ""}]
        result = merge_tech_stacks(html, bw)
        assert result == ["wordpress"]


class TestFetchBuiltWith:
    @respx.mock
    def test_successful_fetch(self):
        respx.get(BUILTWITH_API_URL).mock(
            return_value=httpx.Response(200, json=SAMPLE_BUILTWITH_RESPONSE)
        )
        techs = fetch_builtwith("example.com", "fake-key")
        assert len(techs) == 5
        names = [t["normalized"] for t in techs]
        assert "wordpress" in names

    @respx.mock
    def test_strips_protocol(self):
        route = respx.get(BUILTWITH_API_URL).mock(
            return_value=httpx.Response(200, json=SAMPLE_BUILTWITH_RESPONSE)
        )
        fetch_builtwith("https://example.com/", "fake-key")
        assert route.called
        request = route.calls[0].request
        assert "example.com" in str(request.url)

    @respx.mock
    def test_returns_empty_on_401(self):
        respx.get(BUILTWITH_API_URL).mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )
        result = fetch_builtwith("example.com", "bad-key")
        assert result == []

    @respx.mock
    def test_returns_empty_on_403(self):
        respx.get(BUILTWITH_API_URL).mock(
            return_value=httpx.Response(403, json={"error": "forbidden"})
        )
        result = fetch_builtwith("example.com", "bad-key")
        assert result == []

    def test_returns_empty_without_key(self):
        result = fetch_builtwith("example.com", "")
        assert result == []

    def test_returns_empty_without_domain(self):
        result = fetch_builtwith("", "fake-key")
        assert result == []

    @respx.mock
    def test_returns_empty_on_timeout(self):
        respx.get(BUILTWITH_API_URL).mock(side_effect=httpx.TimeoutException("timeout"))
        result = fetch_builtwith("example.com", "fake-key")
        assert result == []

    @respx.mock
    def test_retries_on_500(self):
        route = respx.get(BUILTWITH_API_URL).mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(500),
                httpx.Response(200, json=SAMPLE_BUILTWITH_RESPONSE),
            ]
        )
        techs = fetch_builtwith("example.com", "fake-key")
        assert len(techs) == 5
        assert route.call_count == 3

    @respx.mock
    def test_retries_on_429(self):
        route = respx.get(BUILTWITH_API_URL).mock(
            side_effect=[
                httpx.Response(429),
                httpx.Response(200, json=SAMPLE_BUILTWITH_RESPONSE),
            ]
        )
        techs = fetch_builtwith("example.com", "fake-key")
        assert len(techs) == 5

    @respx.mock
    def test_empty_response(self):
        respx.get(BUILTWITH_API_URL).mock(
            return_value=httpx.Response(200, json=EMPTY_RESPONSE)
        )
        result = fetch_builtwith("example.com", "fake-key")
        assert result == []

    @respx.mock
    def test_generic_exception_returns_empty(self):
        respx.get(BUILTWITH_API_URL).mock(
            side_effect=ValueError("unexpected parsing error")
        )
        result = fetch_builtwith("example.com", "fake-key")
        assert result == []

    @respx.mock
    def test_malformed_json_returns_empty(self):
        respx.get(BUILTWITH_API_URL).mock(
            return_value=httpx.Response(200, text="not json at all")
        )
        result = fetch_builtwith("example.com", "fake-key")
        assert result == []
