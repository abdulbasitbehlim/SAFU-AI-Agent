"""SAFU 0.0.1 offline preflight / integrity self-check.

Default mode verifies the package itself without requiring network, microphone,
Gemini credentials, or a running GUI. Missing runtime dependencies are warnings
because run_safu.bat/setup.py can install them. Use ``--strict`` after setup to
make missing core dependencies fail the check.
"""
from __future__ import annotations

import ast
import compileall
import importlib.util
import json
import platform
import builtins
import symtable
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STRICT = "--strict" in sys.argv
_failures = 0
_warnings = 0


def _line(kind: str, label: str, detail: str = "") -> None:
    print(f"[{kind}] {label}" + (f" — {detail}" if detail else ""))


def check(label: str, value: bool, detail: str = "") -> bool:
    global _failures
    if value:
        _line("OK", label, detail)
    else:
        _failures += 1
        _line("FAIL", label, detail)
    return value


def warn(label: str, detail: str = "") -> None:
    global _warnings
    _warnings += 1
    _line("WARN", label, detail)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _verify_image(path: Path, expected: str | None = None) -> tuple[bool, str]:
    if not path.is_file() or path.stat().st_size < 100:
        return False, "missing or empty"
    try:
        from PIL import Image
        with Image.open(path) as im:
            fmt, size = im.format, im.size
            im.verify()
        if expected and fmt != expected:
            return False, f"expected {expected}, got {fmt}"
        return True, f"{fmt} {size[0]}x{size[1]}"
    except ImportError:
        # Pillow itself is a runtime dependency; a signature check is enough for
        # package verification before setup.
        head = path.read_bytes()[:8]
        if path.suffix.lower() == ".png" and head == b"\x89PNG\r\n\x1a\n":
            return True, "PNG signature valid (Pillow not installed)"
        if path.suffix.lower() == ".ico" and head[:4] == b"\x00\x00\x01\x00":
            return True, "ICO signature valid (Pillow not installed)"
        return False, "could not verify image signature"
    except Exception as e:
        return False, str(e)


def _branding_clean() -> tuple[bool, str]:
    needles = ("jarvis", "faithmakes", "fatihmakes", "mark 53")
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name in {"LICENSE", "verify_safu.py"} or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() in {".png", ".ico", ".jpg", ".jpeg", ".webp", ".zip", ".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        if any(n in text for n in needles):
            hits.append(str(path.relative_to(ROOT)))
    return not hits, ("clean outside LICENSE" if not hits else ", ".join(hits[:8]))


def _no_shipped_secrets() -> tuple[bool, str]:
    """Detect common credential shapes accidentally bundled in text files."""
    import re
    patterns = (
        re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
        re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        re.compile(r"ghp_[A-Za-z0-9]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
    )
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() in {".png", ".ico", ".jpg", ".jpeg", ".webp", ".zip", ".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if any(rx.search(text) for rx in patterns):
            hits.append(str(path.relative_to(ROOT)))
    return not hits, ("no common credential patterns found" if not hits else ", ".join(hits[:8]))


def _no_shell_true() -> tuple[bool, str]:
    hits: list[str] = []
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        hits.append(f"{path.relative_to(ROOT)}:{getattr(node, 'lineno', '?')}")
    return not hits, ("none found" if not hits else ", ".join(hits[:8]))



def _qt_callback_scan() -> tuple[bool, str]:
    """Catch stale Qt signal/timer callbacks before the GUI is launched.

    This specifically guards against errors such as
    ``timer.timeout.connect(self._step)`` when ``_step`` was removed during a
    refactor.  It scans private ``self._...`` callbacks connected through Qt
    signals or QTimer.singleShot and confirms the method exists on that class.
    """
    hits: list[str] = []
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception as e:
            hits.append(f"{path.relative_to(ROOT)}: parse error: {e}")
            continue
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            methods = {
                n.name for n in cls.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            for node in ast.walk(cls):
                if not isinstance(node, ast.Call):
                    continue
                callback_args = []
                if isinstance(node.func, ast.Attribute) and node.func.attr == "connect":
                    callback_args = node.args
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "singleShot":
                    callback_args = node.args[1:]
                else:
                    continue
                for arg in callback_args:
                    if (
                        isinstance(arg, ast.Attribute)
                        and isinstance(arg.value, ast.Name)
                        and arg.value.id == "self"
                        and arg.attr.startswith("_")
                        and arg.attr not in methods
                    ):
                        hits.append(
                            f"{path.relative_to(ROOT)}:{getattr(arg, 'lineno', '?')} "
                            f"{cls.name}.{arg.attr}"
                        )
    return not hits, ("all private Qt callbacks resolve" if not hits else "; ".join(hits[:8]))


def _undefined_global_scan() -> tuple[bool, str]:
    """Lightweight static NameError guard for every shipped Python module."""
    # Names below are provided implicitly by the Python runtime/compiler.
    # ``__conditional_annotations__`` is a CPython 3.14+ compiler-internal
    # symbol used to implement conditional annotations (PEP 749-era behavior).
    # It can appear in symtable output without being a user-defined global, so
    # treating it as unresolved is a false positive.
    runtime_names = {
        "__file__", "__name__", "__package__", "__spec__", "__loader__",
        "__cached__", "__builtins__", "__conditional_annotations__",
    }
    builtin_names = set(dir(builtins))
    hits: list[str] = []
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            table = symtable.symtable(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as e:
            hits.append(f"{path.relative_to(ROOT)}: {e}")
            continue
        module_defs = {
            s.get_name() for s in table.get_symbols()
            if s.is_assigned() or s.is_imported() or s.is_namespace()
        }
        allowed = module_defs | builtin_names | runtime_names
        missing: set[str] = set()

        def walk(tbl) -> None:
            for symbol in tbl.get_symbols():
                if (symbol.is_referenced() and symbol.is_global()
                        and symbol.get_name() not in allowed):
                    missing.add(symbol.get_name())
            for child in tbl.get_children():
                walk(child)

        walk(table)
        if missing:
            hits.append(f"{path.relative_to(ROOT)}: {', '.join(sorted(missing))}")
    return not hits, ("no unresolved global names found" if not hits else "; ".join(hits[:8]))


def _test_ui_constructor() -> tuple[bool | None, str]:
    """Actually construct the main Qt window when PyQt6 is installed.

    This is deliberately part of strict post-install verification because plain
    compilation cannot catch missing QObject callbacks or widget-construction
    errors.  The window is never shown.
    """
    if not _module_available("PyQt6"):
        return None, "PyQt6 not installed in this environment"
    try:
        # Headless Linux CI needs the offscreen platform; Windows/macOS can use
        # their normal Qt platform plugin while still keeping the window hidden.
        import os
        if platform.system() == "Linux" and not os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        import ui
        app = QApplication.instance() or QApplication(["safu-verify"])
        win = ui.MainWindow(str(ROOT / "config" / "safu_avatar.png"))
        app.processEvents()
        # Stop known repeating timers before disposal so the smoke test exits
        # immediately and cannot leave background GUI work running.
        for obj in (
            getattr(win, "_clock_tmr", None),
            getattr(win, "_metric_tmr", None),
            getattr(getattr(win, "hud", None), "_tmr", None),
        ):
            try:
                obj.stop()
            except Exception:
                pass
        win.close()
        win.deleteLater()
        app.processEvents()
        return True, "MainWindow constructed and disposed without exception"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def _test_config_setters() -> tuple[bool, str]:
    try:
        import memory.config_manager as c
        old_dir, old_file = c.CONFIG_DIR, c.CONFIG_FILE
        with tempfile.TemporaryDirectory(prefix="safu_cfg_") as td:
            td = Path(td)
            try:
                c.CONFIG_DIR, c.CONFIG_FILE = td, td / "api_keys.json"
                c._write_raw({"assistant_name": "SAFU", "gemini_api_key": ""})
                c.save_dashboard_enabled(True)
                c.save_wake_word_enabled(True)
                c.save_brief_enabled(False)
                c.save_voice("Leda")
                c.save_input_device("Test Mic")
                c.save_output_device("Test Speaker")
                c.save_assistant_config("SAFU", "Basit")
                data = json.loads(c.CONFIG_FILE.read_text(encoding="utf-8"))
                needed = (
                    data.get("remote_dashboard_enabled") is True
                    and data.get("wake_word_enabled") is True
                    and data.get("morning_brief_enabled") is False
                    and data.get("voice_name") == "Leda"
                    and data.get("input_device") == "Test Mic"
                    and data.get("output_device") == "Test Speaker"
                    and data.get("assistant_name") == "SAFU"
                )
                return needed, "read/modify/write settings preserved"
            finally:
                c.CONFIG_DIR, c.CONFIG_FILE = old_dir, old_file
    except Exception as e:
        return False, str(e)


def _test_file_controller() -> tuple[bool, str]:
    try:
        import actions.file_controller as f
        # Place the smoke directory under the user's home, which is intentionally
        # inside the controller's trusted root on every platform.
        base = Path(tempfile.mkdtemp(prefix="safu_file_test_", dir=Path.home()))
        try:
            f.create_file(str(base), "alpha.txt", "hello")
            if f.read_file(str(base), "alpha.txt") != "hello":
                return False, "read after create failed"
            f.write_file(str(base), "alpha.txt", " world", append=True)
            if f.read_file(str(base), "alpha.txt") != "hello world":
                return False, "append failed"
            f.create_folder(str(base), "sub")
            f.copy_file(str(base), "alpha.txt", str(base / "sub"))
            f.rename_file(str(base / "sub"), "alpha.txt", "beta.txt")
            f.move_file(str(base / "sub"), "beta.txt", str(base))
            found = f.find_files(name="beta", extension="txt", path=str(base))
            if "beta.txt" not in found or not (base / "beta.txt").is_file():
                return False, "copy/rename/move/find flow failed"
            return True, "create/read/write/copy/rename/move/find"
        finally:
            shutil.rmtree(base, ignore_errors=True)
    except Exception as e:
        return False, str(e)


def _test_action_registry() -> tuple[bool, str]:
    try:
        from core.action_loader import discover_actions
        logs: list[str] = []
        reserved = {"system_status", "screen_process", "close_camera", "save_memory", "manage_monitor", "shutdown_safu"}
        reg = discover_actions(ROOT / "actions", reserved_names=reserved, logger=logs.append)
        rejects = [r for r in reg._all_records if not r.valid and r.error]
        if rejects:
            return False, "; ".join(f"{r.file}: {r.error}" for r in rejects[:4])
        return len(reg.names()) >= 19, f"{len(reg.names())} actions loaded, no collisions/rejections"
    except Exception as e:
        return False, str(e)



def _test_desktop_and_document_creation() -> tuple[bool, str]:
    try:
        from core.user_folders import user_folder
        import actions.file_controller as f
        import actions.document_creator as d
        desk = user_folder("desktop")
        if not isinstance(desk, Path) or not desk.is_absolute():
            return False, f"invalid desktop path: {desk}"
        base = Path(tempfile.mkdtemp(prefix="safu_doc_test_", dir=Path.home()))
        try:
            out = d.document_creator({"location": str(base), "filename": "created_by_safu.txt", "content": "hello"})
            target = base / "created_by_safu.txt"
            if not target.is_file() or target.read_text(encoding="utf-8") != "hello":
                return False, f"document creator did not create expected file: {out}"
            # Collision safety: second create must not overwrite the first file.
            d.document_creator({"location": str(base), "filename": "created_by_safu.txt", "content": "second"})
            dup = base / "created_by_safu (1).txt"
            if not dup.is_file() or target.read_text(encoding="utf-8") != "hello":
                return False, "duplicate-safe create failed"
            return True, f"desktop resolves to {desk}; create + duplicate-safe behavior passed"
        finally:
            shutil.rmtree(base, ignore_errors=True)
    except Exception as e:
        return False, str(e)


def _test_multimodel_package() -> tuple[bool, str]:
    try:
        from memory.config_manager import get_brain_settings
        from core import model_router
        cfg = get_brain_settings()
        providers = {"gemini", "openai", "anthropic", "ollama", "openai_compatible"}
        router_text = (ROOT / "core" / "model_router.py").read_text(encoding="utf-8", errors="ignore")
        ui_text = (ROOT / "ui.py").read_text(encoding="utf-8", errors="ignore")
        good = all(x in router_text for x in providers) and "class ModelBrainOverlay" in ui_text and cfg.get("provider")
        return bool(good), f"preferred={cfg.get('provider')}; router + Model Brain UI present"
    except Exception as e:
        return False, str(e)

def main() -> int:
    global _failures
    print("SAFU 0.0.1 verification")
    print(f"Python {platform.python_version()} ({platform.architecture()[0]}) | {platform.system()}")
    print("Mode: " + ("STRICT post-install" if STRICT else "offline package preflight"))
    print()

    check("Python version", sys.version_info >= (3, 11), "requires 3.11+")
    check("Python sources compile", compileall.compile_dir(ROOT, quiet=1))

    for rel, fmt in (("config/safu_avatar.png", "PNG"), ("config/safu_icon.png", "PNG"), ("config/safu.ico", "ICO")):
        good, detail = _verify_image(ROOT / rel, fmt)
        check(f"Asset {rel}", good, detail)

    # Public repositories intentionally do not ship the user's real
    # config/api_keys.json. Validate the private file when present (installed
    # runtime), otherwise validate the safe example template (fresh clone/CI).
    cfg_path = ROOT / "config" / "api_keys.json"
    cfg_source = cfg_path if cfg_path.exists() else ROOT / "config" / "api_keys.example.json"
    try:
        cfg = json.loads(cfg_source.read_text(encoding="utf-8"))
        check("Configuration JSON", isinstance(cfg, dict), f"valid object ({cfg_source.name})")
        check("Assistant identity", cfg.get("assistant_name") == "SAFU", str(cfg.get("assistant_name")))
        check("Remote dashboard default", cfg.get("remote_dashboard_enabled") is False, "off by default")
        check("Bundled API key", not bool((cfg.get("gemini_api_key") or "").strip()), "no plaintext key shipped")
        check("Input language mode", str(cfg.get("input_language", cfg.get("speech_language", ""))).lower() == "auto", "multilingual auto-detect")
        check("Reply language", str(cfg.get("response_language", "")).lower() in {"en-us", "en", "english"}, "English output")
        check("English-only output flag", bool(cfg.get("english_only_output", cfg.get("english_only"))), "enabled")
        check("Instant reply mode", cfg.get("instant_reply_mode") is True, "enabled by default")
        try:
            _vad_ms = int(cfg.get("vad_silence_ms", 9999))
        except Exception:
            _vad_ms = 9999
        check("Low-latency VAD", 100 <= _vad_ms <= 250, f"silence window {_vad_ms} ms")
        check("Proactive audio latency gate", cfg.get("proactive_audio") is False, "off in instant mode")
    except Exception as e:
        check("Configuration JSON", False, str(e))

    clean, detail = _no_shipped_secrets()
    check("Credential pattern scan", clean, detail)

    clean, detail = _branding_clean()
    check("Legacy branding scan", clean, detail)
    safe, detail = _no_shell_true()
    check("shell=True scan", safe, detail)
    safe, detail = _undefined_global_scan()
    check("Undefined-global scan", safe, detail)
    # Regression guard for CPython 3.14+ where symtable may surface the
    # compiler-generated ``__conditional_annotations__`` name.
    verifier_text = Path(__file__).read_text(encoding="utf-8", errors="ignore")
    check("Python 3.14 annotation scanner compatibility",
          '"__conditional_annotations__"' in verifier_text,
          "compiler-internal annotation symbol allowlisted")
    safe, detail = _qt_callback_scan()
    check("Qt callback integrity", safe, detail)

    main_text = (ROOT / "main.py").read_text(encoding="utf-8", errors="ignore")
    prompt_text = (ROOT / "core" / "prompt.txt").read_text(encoding="utf-8", errors="ignore")
    lang_ok = (
        "INPUT IS MULTILINGUAL" in main_text
        and "OUTPUT IS ENGLISH ONLY" in main_text
        and "Understand spoken and typed user input in ANY language" in prompt_text
        and "Every SAFU spoken response" in prompt_text
        and "ENGLISH ONLY" in prompt_text
        and "assume the user intended to communicate with you in English" not in prompt_text
    )
    check("Multilingual-input / English-output policy", lang_ok, "auto-detect input; replies stay English")
    check("Startup os import", "import os" in main_text[:300], "prevents os.environ NameError")
    check("Live model ID", "gemini-2.5-flash-native-audio-preview-12-2025" in main_text)
    check("Live API endpoint", '"api_version": "v1beta"' in main_text, "required by 2.5 proactive audio")
    check("PCM input MIME", "audio/pcm;rate=16000" in main_text, "16-bit PCM @ 16 kHz")
    check("Fast mic chunks", "CHUNK_SIZE          = 640" in main_text, "40 ms capture blocks")
    check("Live VAD override", "realtime_input_config" in main_text and "silence_duration_ms" in main_text, "fast end-of-speech configured")
    wake_text = (ROOT / "core" / "wake_word.py").read_text(encoding="utf-8", errors="ignore")
    check("Hey Safu pronunciation", "SAFU S AA F UW" in wake_text and "hey safu" in wake_text.lower(), "F-sound wake dictionary")
    req_text = (ROOT / "requirements-lite.txt").read_text(encoding="utf-8", errors="ignore")
    check("Current google-genai floor", "google-genai>=2.23.0,<3" in req_text, "Live VAD-capable SDK floor")

    good, detail = _test_config_setters()
    check("Config setter smoke test", good, detail)
    good, detail = _test_file_controller()
    check("Local-file smoke test", good, detail)
    good, detail = _test_action_registry()
    check("Action registry smoke test", good, detail)
    good, detail = _test_desktop_and_document_creation()
    check("Desktop/document creation smoke test", good, detail)
    good, detail = _test_multimodel_package()
    check("Multi-model brain package", good, detail)
    check("Automation/file routing policy",
          "document_creator" in prompt_text and "agent_task" in prompt_text and "model_delegate" in prompt_text,
          "file creation, multi-step workflows and model delegation are explicitly routed")

    ui_ok, ui_detail = _test_ui_constructor()
    if ui_ok is True:
        check("Qt MainWindow construction", True, ui_detail)
    elif ui_ok is False:
        check("Qt MainWindow construction", False, ui_detail)
    elif STRICT:
        check("Qt MainWindow construction", False, ui_detail)
    else:
        warn("Qt MainWindow construction", ui_detail + "; strict mode tests this after setup")

    try:
        import setup as s
        from core import wake_word as w
        spec_a, spec_b = s._wake_spec(), w._compatible_spec()
        check("Wake-wheel selection", spec_a == spec_b, str(spec_a or "cloud fallback"))
        setup_text = (ROOT / "setup.py").read_text(encoding="utf-8", errors="ignore")
        check("Wake install is binary-only", "--only-binary=:all:" in setup_text, "prevents source-build fallback")
        if w.is_ready():
            _line("OK", "Local Hey Safu engine", "PocketSphinx decoder ready")
        else:
            warn("Local Hey Safu engine", "not installed/ready here; setup.py installs a binary wheel when supported")
    except Exception as e:
        check("Wake module", False, str(e))

    core = ["PyQt6", "sounddevice", "numpy", "google.genai", "psutil", "mss", "PIL"]
    for mod in core:
        present = _module_available(mod)
        if present:
            _line("OK", f"Runtime dependency {mod}")
        elif STRICT:
            check(f"Runtime dependency {mod}", False, "run python setup.py")
        else:
            warn(f"Runtime dependency {mod}", "not installed in this environment; run python setup.py")

    print()
    if _failures:
        print(f"SAFU 0.0.1 verification FAILED: {_failures} failure(s), {_warnings} warning(s).")
        return 1
    print(f"SAFU 0.0.1 package verification PASSED with {_warnings} warning(s).")
    if not STRICT:
        print("After setup on Windows, run: python verify_safu.py --strict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
