from __future__ import annotations


DARK_THEME: dict[str, str] = {
    "$primary": "#4a9eff",
    "$secondary": "#6c757d",
    "$surface": "#1e1e2e",
    "$text": "#cdd6f4",
    "$text-muted": "#6c7086",
    "$success": "#a6e3a1",
    "$error": "#f38ba8",
    "$warning": "#f9e2af",
}

LIGHT_THEME: dict[str, str] = {
    "$primary": "#1e66f5",
    "$secondary": "#6c6f85",
    "$surface": "#eff1f5",
    "$text": "#4c4f69",
    "$text-muted": "#9ca0b0",
    "$success": "#40a02b",
    "$error": "#d20f39",
    "$warning": "#df8e1d",
}

_THEMES: dict[str, dict[str, str]] = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
}


def get_theme_css(theme_name: str) -> str:
    """Return a CSS string with variable definitions for the given theme.

    Args:
        theme_name: Either "dark" or "light".

    Returns:
        A string of Textual CSS variable declarations.

    Raises:
        ValueError: If theme_name is not recognized.
    """
    if theme_name not in _THEMES:
        available = ", ".join(sorted(_THEMES))
        raise ValueError(
            f"Unknown theme '{theme_name}'. Available themes: {available}"
        )

    theme = _THEMES[theme_name]
    lines: list[str] = []
    for var, value in theme.items():
        lines.append(f"{var}: {value};")

    return "\n".join(lines)
