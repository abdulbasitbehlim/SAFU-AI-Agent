"""Fail if private SAFU runtime data or common credential shapes are publishable."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = {
    "config/api_keys.json",
    "memory/long_term.json",
}
SECRET_PATTERNS = {
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "OpenAI-style key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "Anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Private key": re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
}
BINARY_SUFFIXES = {".png", ".ico", ".jpg", ".jpeg", ".webp", ".pyc", ".zip"}


def tracked_files() -> list[str]:
    try:
        out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
        return [line.strip() for line in out.splitlines() if line.strip()]
    except Exception:
        return [str(p.relative_to(ROOT)).replace("\\", "/") for p in ROOT.rglob("*") if p.is_file()]


def main() -> int:
    files = tracked_files()
    problems: list[str] = []
    for rel in sorted(FORBIDDEN):
        if rel in files:
            problems.append(f"forbidden tracked file: {rel}")

    for rel in files:
        path = ROOT / rel
        if not path.is_file() or path.suffix.lower() in BINARY_SUFFIXES or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, rx in SECRET_PATTERNS.items():
            if rx.search(text):
                # The security/verifier source intentionally contains regex examples.
                if rel in {"SECURITY.md", "verify_safu.py", "scripts/check_public_repo.py"}:
                    continue
                problems.append(f"{label} pattern in {rel}")

    if problems:
        print("PUBLIC REPO CHECK FAILED")
        for p in problems:
            print(" -", p)
        return 1
    print(f"PUBLIC REPO CHECK PASSED ({len(files)} tracked/publishable files checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
