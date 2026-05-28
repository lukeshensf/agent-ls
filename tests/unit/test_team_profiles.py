from unittest.mock import MagicMock

import pytest

from agent_ls.integrations.obsidian.team_profiles import TeamProfileLoader


@pytest.fixture
def mock_vault():
    vault = MagicMock()
    return vault


class TestTeamProfileLoader:
    def test_load_profile_success(self, mock_vault):
        profile_content = """---
description: Backend payments team
required_tools:
  - java
  - bazel
  - docker
optional_tools:
  - intellij
channels:
  - payments-eng
  - payments-oncall
setup_steps:
  - description: Install Java 21
    command: brew install openjdk@21
  - description: Install Bazel
    command: brew install bazel
  - description: Clone payments repo
    command: git clone git@github.com:company/payments.git
---

# Payments Team Setup

Follow these steps to get started.
"""
        mock_vault.exists.return_value = True
        mock_vault.read.return_value = profile_content

        loader = TeamProfileLoader(vault=mock_vault)
        profile = loader.load_profile("payments")

        assert profile is not None
        assert profile.name == "payments"
        assert profile.description == "Backend payments team"
        assert "java" in profile.required_tools
        assert "bazel" in profile.required_tools
        assert "intellij" in profile.optional_tools
        assert "payments-eng" in profile.channels
        assert len(profile.setup_steps) == 3
        assert profile.setup_steps[0].command == "brew install openjdk@21"

    def test_load_profile_not_found(self, mock_vault):
        mock_vault.exists.return_value = False

        loader = TeamProfileLoader(vault=mock_vault)
        profile = loader.load_profile("nonexistent")

        assert profile is None

    def test_load_profile_no_frontmatter(self, mock_vault):
        mock_vault.exists.return_value = True
        mock_vault.read.return_value = "# Just a readme\n\nNo frontmatter here"

        loader = TeamProfileLoader(vault=mock_vault)
        profile = loader.load_profile("eng")

        assert profile is not None
        assert profile.name == "eng"
        assert profile.setup_steps == []

    def test_list_profiles(self, mock_vault):
        mock_vault.list_docs.return_value = [
            "teams/payments/profile.md",
            "teams/payments/setup.md",
            "teams/infra/profile.md",
        ]

        loader = TeamProfileLoader(vault=mock_vault)
        profiles = loader.list_profiles()

        assert "payments" in profiles
        assert "infra" in profiles

    def test_list_profiles_empty(self, mock_vault):
        mock_vault.list_docs.return_value = []

        loader = TeamProfileLoader(vault=mock_vault)
        profiles = loader.list_profiles()

        assert profiles == []
