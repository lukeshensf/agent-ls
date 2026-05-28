import tempfile
from pathlib import Path

import pytest

from agent_ls.integrations.obsidian.vault import ObsidianVault


@pytest.fixture
def vault(tmp_path):
    (tmp_path / "test.md").write_text("# Test\nHello world")
    (tmp_path / "teams" / "platform").mkdir(parents=True)
    (tmp_path / "teams" / "platform" / "setup.md").write_text("# Platform Setup\nStep 1...")
    return ObsidianVault(str(tmp_path))


def test_read(vault):
    content = vault.read("test.md")
    assert "Hello world" in content


def test_read_not_found(vault):
    with pytest.raises(FileNotFoundError):
        vault.read("nonexistent.md")


def test_write(vault):
    vault.write("new-doc.md", "# New\nContent here")
    assert vault.exists("new-doc.md")
    assert "Content here" in vault.read("new-doc.md")


def test_write_nested(vault):
    vault.write("deep/nested/doc.md", "Nested content")
    assert vault.exists("deep/nested/doc.md")


def test_list_docs(vault):
    docs = vault.list_docs("teams/platform")
    assert "teams/platform/setup.md" in docs


def test_list_docs_empty(vault):
    docs = vault.list_docs("nonexistent")
    assert docs == []


def test_exists(vault):
    assert vault.exists("test.md")
    assert not vault.exists("nope.md")
