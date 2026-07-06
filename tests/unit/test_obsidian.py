
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


# --- Path-traversal containment (PLAN 2.3) -------------------------------


@pytest.fixture
def secret_outside_vault(vault, tmp_path):
    """Write a file in the tmp_path parent so `..` traversal has a real target."""
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("top secret")
    return secret


def test_read_rejects_dotdot_traversal(vault, secret_outside_vault):
    with pytest.raises(ValueError):
        vault.read("../secret.txt")


def test_read_rejects_deep_dotdot_traversal(vault):
    with pytest.raises(ValueError):
        vault.read("../../etc/passwd")


def test_read_rejects_absolute_path(vault):
    with pytest.raises(ValueError):
        vault.read("/etc/passwd")


def test_write_rejects_dotdot_traversal(vault, tmp_path):
    with pytest.raises(ValueError):
        vault.write("../escaped.md", "should not be written")
    assert not (tmp_path.parent / "escaped.md").exists()


def test_write_rejects_absolute_path(vault):
    with pytest.raises(ValueError):
        vault.write("/tmp/agent-ls-escape.md", "should not be written")


def test_write_rejects_nested_dotdot_escape(vault, tmp_path):
    # A path that dips into the vault then climbs back out must still be blocked.
    with pytest.raises(ValueError):
        vault.write("teams/../../escaped.md", "should not be written")
    assert not (tmp_path.parent / "escaped.md").exists()


def test_exists_rejects_traversal(vault):
    with pytest.raises(ValueError):
        vault.exists("../secret.txt")


def test_list_docs_rejects_traversal(vault):
    with pytest.raises(ValueError):
        vault.list_docs("..")


def test_read_with_frontmatter_rejects_traversal(vault):
    with pytest.raises(ValueError):
        vault.read_with_frontmatter("../secret.txt")


def test_write_with_template_rejects_traversal(vault):
    from agent_ls.integrations.obsidian.templates import DocTemplate

    with pytest.raises(ValueError):
        vault.write_with_template("../escaped.md", DocTemplate.DAILY_LOG, {})


def test_inner_dotdot_that_stays_inside_is_allowed(vault):
    # `teams/platform/../platform/setup.md` normalizes back inside the vault.
    content = vault.read("teams/platform/../platform/setup.md")
    assert "Platform Setup" in content
