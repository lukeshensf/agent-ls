
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


class TestPathTraversalContainment:
    """`relative_path` reaches the vault from LLM/Slack-derived text and is never
    validated upstream. Any input that resolves outside the vault root must be
    rejected with ValueError, not silently read/written outside the vault.
    """

    def test_read_rejects_dotdot_traversal(self, vault):
        with pytest.raises(ValueError):
            vault.read("../../etc/passwd")

    def test_read_rejects_absolute_path(self, vault):
        # `Path(root) / "/etc/passwd"` == `Path("/etc/passwd")` — absolute inputs
        # replace the root entirely, so they must be caught by the containment check.
        with pytest.raises(ValueError):
            vault.read("/etc/passwd")

    def test_write_rejects_dotdot_traversal(self, vault, tmp_path):
        outside = tmp_path.parent / "escaped.md"
        with pytest.raises(ValueError):
            vault.write("../escaped.md", "pwned")
        assert not outside.exists()

    def test_write_rejects_absolute_path(self, vault, tmp_path):
        target = tmp_path.parent / "abs-escape.md"
        with pytest.raises(ValueError):
            vault.write(str(target), "pwned")
        assert not target.exists()

    def test_exists_rejects_traversal(self, vault):
        with pytest.raises(ValueError):
            vault.exists("../../etc/passwd")

    def test_list_docs_rejects_traversal(self, vault):
        with pytest.raises(ValueError):
            vault.list_docs("../..")

    def test_nested_dotdot_that_stays_inside_is_allowed(self, vault):
        # `teams/platform/../platform/setup.md` normalizes back inside the vault,
        # so it must NOT be rejected — the guard checks the resolved location.
        content = vault.read("teams/platform/../platform/setup.md")
        assert "Platform Setup" in content

    def test_read_with_frontmatter_rejects_traversal(self, vault):
        with pytest.raises(ValueError):
            vault.read_with_frontmatter("../../etc/passwd")
