"""Low-resource local wake phrase detection for SAFU ("Hey Safu").

No custom neural model or copyrighted voice sample is downloaded. PocketSphinx
ships its English acoustic model with the Python wheel; SAFU supplies a tiny
local pronunciation dictionary so the custom word "Safu" is recognised even
when it is absent from the default CMU dictionary.
"""
from __future__ import annotations

import importlib.util
import os
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable

WAKE_PHRASE = "hey safu"
SAMPLE_RATE = 16000
DEFAULT_THRESHOLD = 1e-18

# Pronunciations intentionally include two common English renderings of Safu.
# PocketSphinx dictionary syntax allows numbered alternate pronunciations.
_WAKE_DICT = """HEY HH EY
SAFU S AA F UW
SAFU(2) S AE F UW
"""


def _dict_path() -> Path:
    base = Path(tempfile.gettempdir()) / "safu_assistant"
    base.mkdir(parents=True, exist_ok=True)
    path = base / "wake_words.dict"
    try:
        if not path.exists() or path.read_text(encoding="utf-8") != _WAKE_DICT:
            path.write_text(_WAKE_DICT, encoding="utf-8")
    except Exception:
        pass
    return path


def is_installed() -> bool:
    try:
        return importlib.util.find_spec("pocketsphinx") is not None
    except Exception:
        return False


def _probe_decoder() -> tuple[bool, str]:
    """Construct the decoder once so 'ready' means actually usable, not just importable."""
    if not is_installed():
        return False, "PocketSphinx is not installed."
    try:
        from pocketsphinx import Decoder, get_model_path
        model_root = Path(get_model_path())
        hmm = model_root / "en-us"
        if not hmm.exists():
            # Some wheels return .../model/en-us already.
            hmm = model_root
        dct = _dict_path()
        try:
            dec = Decoder(
                hmm=str(hmm),
                dict=str(dct),
                keyphrase=WAKE_PHRASE,
                kws_threshold=float(DEFAULT_THRESHOLD),
                samprate=SAMPLE_RATE,
                logfn=os.devnull,
            )
        except TypeError:
            cfg = Decoder.default_config()
            cfg.set_string("-hmm", str(hmm))
            cfg.set_string("-dict", str(dct))
            cfg.set_string("-keyphrase", WAKE_PHRASE)
            cfg.set_float("-kws_threshold", float(DEFAULT_THRESHOLD))
            cfg.set_float("-samprate", float(SAMPLE_RATE))
            cfg.set_string("-logfn", os.devnull)
            dec = Decoder(cfg)
        del dec
        return True, "ready"
    except Exception as e:
        return False, str(e)


def is_ready() -> bool:
    ok, _ = _probe_decoder()
    return ok


def _compatible_spec() -> str | None:
    """Choose a release with a known prebuilt wheel for this CPython version."""
    major, minor = sys.version_info[:2]
    if major != 3:
        return None
    if 8 <= minor <= 12:
        return "pocketsphinx==5.0.4"
    if minor == 13:
        return "pocketsphinx==5.1.1"
    return None


def install_and_download(logger: Callable[[str], None] = print) -> tuple[bool, str]:
    """Install/repair local wake detection without ever compiling from source.

    The function name is kept for UI compatibility.  There is no separate wake
    model download.  If this Python version has no selected binary wheel, Safu
    continues with its guarded Gemini transcription wake fallback.
    """
    try:
        if not is_installed():
            spec = _compatible_spec()
            if not spec:
                return False, (
                    f"No supported prebuilt local wake wheel for Python "
                    f"{sys.version_info.major}.{sys.version_info.minor}. "
                    "Safu can still use cloud wake fallback."
                )
            logger(f"Wake word: installing {spec} as a prebuilt wheel…")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--only-binary=:all:", spec],
                capture_output=True, text=True, timeout=300,
            )
            if r.returncode != 0:
                tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
                return False, (
                    "Local wake wheel install failed, but Safu can use cloud fallback: "
                    + " | ".join(tail)[:300]
                )

        ok, why = _probe_decoder()
        if not ok:
            return False, f"Local wake engine could not start: {why}"
        logger("Wake word: local 'Hey Safu' engine is ready — no model download required.")
        return True, "Hey Safu local wake is ready."
    except Exception as e:
        return False, f"Local wake setup error: {e}. Cloud wake fallback remains available."



class WakeWordDetector:
    """Dedicated-thread PocketSphinx keyword spotter fed from the existing mic."""

    def __init__(self, on_detect: Callable[[], None],
                 threshold: float = DEFAULT_THRESHOLD,
                 logger: Callable[[str], None] = print):
        self._on_detect = on_detect
        self._threshold = threshold
        self._logger = logger
        self._queue: queue.Queue = queue.Queue(maxsize=10)
        self._thread: threading.Thread | None = None
        self._running = False
        self._decoder = None
        self._ready = False

    def _make_decoder(self):
        from pocketsphinx import Decoder, get_model_path
        model_root = Path(get_model_path())
        hmm = model_root / "en-us"
        if not hmm.exists():
            hmm = model_root
        dct = _dict_path()
        try:
            return Decoder(
                hmm=str(hmm), dict=str(dct), keyphrase=WAKE_PHRASE,
                kws_threshold=float(self._threshold), samprate=SAMPLE_RATE,
                logfn=os.devnull,
            )
        except TypeError:
            cfg = Decoder.default_config()
            cfg.set_string("-hmm", str(hmm))
            cfg.set_string("-dict", str(dct))
            cfg.set_string("-keyphrase", WAKE_PHRASE)
            cfg.set_float("-kws_threshold", float(self._threshold))
            cfg.set_float("-samprate", float(SAMPLE_RATE))
            cfg.set_string("-logfn", os.devnull)
            return Decoder(cfg)

    def start(self) -> bool:
        if self._running:
            return True
        try:
            self._decoder = self._make_decoder()
            self._decoder.start_utt()
        except Exception as e:
            self._logger(f"Wake word: could not start 'Hey Safu' — {e}")
            self._decoder = None
            return False
        self._running = True
        self._ready = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="SafuWakeWord")
        self._thread.start()
        self._logger("Wake word: listening locally for 'Hey Safu'.")
        return True

    def stop(self) -> None:
        self._running = False
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
        try:
            if self._decoder:
                self._decoder.end_utt()
        except Exception:
            pass
        self._decoder = None
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def feed(self, frame_int16) -> None:
        if not self._running:
            return
        try:
            arr = frame_int16[:, 0] if getattr(frame_int16, "ndim", 1) > 1 else frame_int16
            payload = arr.astype("int16", copy=False).tobytes()
            self._queue.put_nowait(payload)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(payload)
            except Exception:
                pass
        except Exception:
            pass

    def _loop(self) -> None:
        while self._running:
            try:
                payload = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
            if payload is None or not self._running:
                break
            try:
                self._decoder.process_raw(payload, False, False)
                hyp = self._decoder.hyp()
                if hyp and WAKE_PHRASE in (hyp.hypstr or "").lower():
                    self._decoder.end_utt()
                    self._drain()
                    try:
                        self._on_detect()
                    finally:
                        self._decoder.start_utt()
            except Exception as e:
                self._logger(f"Wake word: inference error — {e}")
                try:
                    self._decoder.end_utt(); self._decoder.start_utt()
                except Exception:
                    pass

    def _drain(self) -> None:
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
