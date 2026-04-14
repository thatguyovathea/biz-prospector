"""Tests for YAML config loading."""

from unittest.mock import patch

import pytest
import yaml

from src.config import load_settings, load_vertical, get_api_key


class TestLoadSettings:
    def test_loads_yaml(self, tmp_path):
        settings = {"apis": {"serpapi_key": "test-key"}, "pipeline": {"batch_size": 50}}
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml.dump(settings))
        with patch("src.config.CONFIG_DIR", tmp_path):
            result = load_settings()
        assert result["apis"]["serpapi_key"] == "test-key"
        assert result["pipeline"]["batch_size"] == 50

    def test_raises_on_missing_file(self, tmp_path):
        with patch("src.config.CONFIG_DIR", tmp_path):
            with pytest.raises(FileNotFoundError, match="Config not found"):
                load_settings()


class TestLoadVertical:
    def test_loads_vertical_yaml(self, tmp_path):
        verticals_dir = tmp_path / "verticals"
        verticals_dir.mkdir()
        config = {"name": "hvac", "weights": {"no_scheduling_tool": 20}}
        (verticals_dir / "hvac.yaml").write_text(yaml.dump(config))
        with patch("src.config.CONFIG_DIR", tmp_path):
            result = load_vertical("hvac")
        assert result["name"] == "hvac"
        assert result["weights"]["no_scheduling_tool"] == 20

    def test_returns_empty_for_missing(self, tmp_path):
        verticals_dir = tmp_path / "verticals"
        verticals_dir.mkdir()
        with patch("src.config.CONFIG_DIR", tmp_path):
            result = load_vertical("nonexistent")
        assert result == {}


class TestGetApiKey:
    def test_retrieves_key(self):
        settings = {"apis": {"serpapi_key": "my-key-123"}}
        assert get_api_key(settings, "serpapi_key") == "my-key-123"

    def test_raises_on_missing_key(self):
        settings = {"apis": {}}
        with pytest.raises(ValueError, match="API key 'serpapi_key' not set"):
            get_api_key(settings, "serpapi_key")

    def test_raises_on_empty_key(self):
        settings = {"apis": {"serpapi_key": ""}}
        with pytest.raises(ValueError, match="API key 'serpapi_key' not set"):
            get_api_key(settings, "serpapi_key")

    def test_raises_on_no_apis_section(self):
        settings = {}
        with pytest.raises(ValueError):
            get_api_key(settings, "serpapi_key")
