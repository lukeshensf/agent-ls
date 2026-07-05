"""Unit tests for mypy configuration."""

import subprocess
import tomllib
from pathlib import Path


def test_mypy_config_exists():
    """Test that mypy configuration exists in pyproject.toml."""
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml not found"

    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    assert "tool" in config, "No [tool] section in pyproject.toml"
    assert "mypy" in config["tool"], "No [tool.mypy] section in pyproject.toml"


def test_mypy_strict_optional_enabled():
    """Test that strict_optional is enabled for better type checking."""
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"

    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    mypy_config = config["tool"]["mypy"]
    assert mypy_config.get("strict_optional") is True, "strict_optional should be True"


def test_mypy_warn_redundant_casts_enabled():
    """Test that warn_redundant_casts is enabled."""
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"

    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    mypy_config = config["tool"]["mypy"]
    assert mypy_config.get("warn_redundant_casts") is True


def test_mypy_warn_unused_ignores_enabled():
    """Test that warn_unused_ignores is enabled."""
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"

    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    mypy_config = config["tool"]["mypy"]
    assert mypy_config.get("warn_unused_ignores") is True


def test_types_pyyaml_installed():
    """Test that types-PyYAML is in dev dependencies."""
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"

    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    dev_deps = config["dependency-groups"]["dev"]

    # Check if types-PyYAML is in the list
    has_types_pyyaml = any("types-PyYAML" in dep or "types-pyyaml" in dep for dep in dev_deps)
    assert has_types_pyyaml, "types-PyYAML not found in dev dependencies"


def test_mypy_error_count_reduced():
    """Test that mypy error count is reduced from baseline (28 errors)."""
    result = subprocess.run(
        ["uv", "run", "mypy", "src/"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    # Count errors from output
    output_lines = result.stdout.strip().split("\n")
    last_line = output_lines[-1] if output_lines else ""

    # Parse error count from "Found X errors in Y files"
    if "Found" in last_line and "error" in last_line:
        error_count = int(last_line.split()[1])
        # Should be fewer than baseline 28 errors
        assert error_count < 28, f"Expected fewer than 28 errors, got {error_count}"
    elif "Success" in last_line:
        # Zero errors is even better!
        pass
    else:
        # If mypy output format changes, fail explicitly
        assert False, f"Could not parse mypy output: {last_line}"
