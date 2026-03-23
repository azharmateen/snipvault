"""Clipboard integration: copy snippet to clipboard, paste mode."""

import sys
from typing import Optional


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True on success."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        # Fallback: try pbcopy on macOS, xclip on Linux
        return _fallback_copy(text)


def _fallback_copy(text: str) -> bool:
    """Platform-specific clipboard fallback."""
    import subprocess
    import platform

    system = platform.system()
    try:
        if system == "Darwin":
            proc = subprocess.Popen(
                ["pbcopy"], stdin=subprocess.PIPE, text=True
            )
            proc.communicate(input=text)
            return proc.returncode == 0
        elif system == "Linux":
            # Try xclip first, then xsel
            for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
                try:
                    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
                    proc.communicate(input=text)
                    if proc.returncode == 0:
                        return True
                except FileNotFoundError:
                    continue
        elif system == "Windows":
            proc = subprocess.Popen(
                ["clip"], stdin=subprocess.PIPE, text=True
            )
            proc.communicate(input=text)
            return proc.returncode == 0
    except Exception:
        pass
    return False


def paste_to_stdout(text: str) -> None:
    """Output raw content to stdout without any decoration (for piping)."""
    sys.stdout.write(text)
    sys.stdout.flush()


def format_snippet_for_copy(
    snippet: dict, include_metadata: bool = False
) -> str:
    """Format a snippet for clipboard copy.

    Args:
        snippet: Snippet dict with content, title, language, etc.
        include_metadata: If True, include title/language/tags header.

    Returns:
        Formatted string ready for clipboard.
    """
    if not include_metadata:
        return snippet["content"]

    lines = []
    lines.append(f"# {snippet['title']}")
    if snippet.get("language"):
        lines.append(f"# Language: {snippet['language']}")
    if snippet.get("tags"):
        lines.append(f"# Tags: {', '.join(snippet['tags'])}")
    lines.append("")
    lines.append(snippet["content"])
    return "\n".join(lines)
