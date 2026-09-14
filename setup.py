"""SAFU setup — resilient Windows/Anaconda installer.

The everyday assistant is installed first.  The local "Hey Safu" detector is
optional and is installed separately with an exact PocketSphinx wheel version
that matches the current CPython version.  This prevents pip from falling back
to a compiler-heavy source build on Windows.
"""
from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

OS = platform.system()
FULL = "--full" in sys.argv
ROOT = Path(__file__).resolve().parent


def _run(label: str, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n▶ {label}")
    return subprocess.run(args, check=check, cwd=ROOT)


def _wake_spec() -> str | None:
    """Return a PocketSphinx release with a published wheel for this runtime.

    PocketSphinx 5.1.1 does not publish a CPython 3.12 Windows wheel, while
    5.0.4 does.  Pinning avoids pip selecting 5.1.1 and trying to compile it.
    """
    major, minor = sys.version_info[:2]
    if major != 3:
        return None
    if 8 <= minor <= 12:
        return "pocketsphinx==5.0.4"
    if minor == 13:
        return "pocketsphinx==5.1.1"
    # No known supported wheel in this build for 3.14+; use Safu's guarded
    # Gemini transcription wake fallback instead of attempting a source build.
    return None


def _install_local_wake() -> tuple[bool, str]:
    spec = _wake_spec()
    if not spec:
        return False, (
            f"No safe prebuilt PocketSphinx wheel selected for Python "
            f"{sys.version_info.major}.{sys.version_info.minor}. "
            "Safu will use its cloud wake fallback."
        )

    print(f"\n▶ Installing local Hey Safu engine ({spec}, binary wheel only)…")
    cmd = [sys.executable, "-m", "pip", "install", "--only-binary=:all:", spec]
    r = subprocess.run(cmd)
    if r.returncode == 0:
        return True, f"Local Hey Safu engine installed: {spec}"
    return False, (
        f"Could not install {spec} as a prebuilt wheel. "
        "The rest of Safu is installed and can run; wake will use cloud fallback."
    )


def main() -> None:
    mode = "FULL" if FULL else "STANDARD"
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"⚙  SAFU 0.0.1 setup — {mode} mode — OS: {OS or 'unknown'} — Python {py}")

    if sys.version_info < (3, 11):
        raise SystemExit(
            "SAFU requires Python 3.11 or newer. Preferred for fully local wake: 64-bit Python 3.11-3.13; Python 3.14+ uses cloud wake fallback."
        )

    req = ROOT / ("requirements.txt" if FULL else "requirements-lite.txt")
    if not req.exists():
        raise SystemExit(f"Requirements file is missing: {req}")
    _run(f"Installing {req.name}…", [sys.executable, "-m", "pip", "install", "-r", str(req)])

    wake_ok, wake_msg = _install_local_wake()
    print(("✅ " if wake_ok else "⚠  ") + wake_msg)

    if FULL:
        _run("Installing Chromium for optional browser automation…",
             [sys.executable, "-m", "playwright", "install", "chromium"])

    if OS == "Windows" and FULL:
        try:
            import win32com.client  # noqa: F401
        except ImportError:
            postinstall = Path(sys.executable).parent / "Scripts" / "pywin32_postinstall.py"
            print(f'If Windows integration fails, run: "{sys.executable}" "{postinstall}" -install')

    print("\n✅ Safu core setup complete.")
    print("   Launch: python main.py")
    if wake_ok:
        print("   Hey Safu: LOCAL/OFFLINE wake engine ready.")
    else:
        print("   Hey Safu: cloud transcription fallback will be used when connected.")
    if not FULL:
        print("   Need camera/browser/remote-dashboard extras later? Run: python setup.py --full")


if __name__ == "__main__":
    main()
