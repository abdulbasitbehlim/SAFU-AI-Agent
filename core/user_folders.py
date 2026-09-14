"""Resolve real per-user folders reliably, including Windows OneDrive redirects."""
from __future__ import annotations

import os
import platform
from pathlib import Path

_SYSTEM = platform.system()

_REGISTRY_VALUES = {
    "desktop": "Desktop",
    "documents": "Personal",
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "pictures": "My Pictures",
    "music": "My Music",
    "videos": "My Video",
}


def _windows_registry_folder(kind: str) -> Path | None:
    if _SYSTEM != "Windows":
        return None
    value_name = _REGISTRY_VALUES.get(kind.lower())
    if not value_name:
        return None
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            raw, _ = winreg.QueryValueEx(key, value_name)
        if isinstance(raw, str) and raw.strip():
            expanded = os.path.expandvars(raw.strip())
            p = Path(expanded).expanduser()
            if p.exists() or p.parent.exists():
                return p
    except Exception:
        pass
    return None


def user_folder(kind: str) -> Path:
    """Return the user's real Desktop/Documents/etc. path.

    Windows: honors Explorer/OneDrive redirection from User Shell Folders.
    Linux: honors common XDG environment overrides when present.
    macOS: uses the conventional home folders.
    """
    k = (kind or "").strip().lower()
    if k == "home":
        return Path.home()

    win = _windows_registry_folder(k)
    if win is not None:
        return win

    if _SYSTEM == "Linux":
        env_key = {
            "desktop": "XDG_DESKTOP_DIR",
            "documents": "XDG_DOCUMENTS_DIR",
            "downloads": "XDG_DOWNLOAD_DIR",
            "pictures": "XDG_PICTURES_DIR",
            "music": "XDG_MUSIC_DIR",
            "videos": "XDG_VIDEOS_DIR",
        }.get(k)
        if env_key:
            raw = os.environ.get(env_key, "").strip().strip('"')
            if raw:
                raw = raw.replace("$HOME", str(Path.home()))
                return Path(os.path.expandvars(raw)).expanduser()

    if _SYSTEM == "Windows":
        # OneDrive fallback for machines where registry access is restricted.
        for env_name in ("OneDriveCommercial", "OneDriveConsumer", "OneDrive"):
            root = os.environ.get(env_name, "").strip()
            if root:
                candidate = Path(root) / kind.capitalize()
                if candidate.exists():
                    return candidate

    name = {
        "desktop": "Desktop",
        "documents": "Documents",
        "downloads": "Downloads",
        "pictures": "Pictures",
        "music": "Music",
        "videos": "Videos",
    }.get(k, kind.capitalize())
    return Path.home() / name


def desktop() -> Path:
    return user_folder("desktop")
