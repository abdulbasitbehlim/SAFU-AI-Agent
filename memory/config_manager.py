import base64
import json
import os
import platform
import sys
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR    = get_base_dir()
CONFIG_DIR  = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"

def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    return CONFIG_FILE.exists()

def _read_raw() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"❌ Failed to load api_keys.json: {e}")
        return {}

def _write_raw(data: dict) -> None:
    ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")

def _dpapi_encrypt(secret: str) -> str | None:
    if platform.system() != "Windows" or not secret:
        return None
    try:
        import win32crypt
        blob = win32crypt.CryptProtectData(
            secret.encode("utf-8"), "SAFU encrypted secret", None, None, None, 0
        )
        if isinstance(blob, tuple):
            blob = blob[-1]
        return base64.b64encode(blob).decode("ascii")
    except Exception as e:
        print(f"[Config] DPAPI encryption unavailable: {e}")
        return None

def _dpapi_decrypt(encoded: str) -> str | None:
    if platform.system() != "Windows" or not encoded:
        return None
    try:
        import win32crypt
        blob = base64.b64decode(encoded.encode("ascii"))
        out = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
        clear = out[-1] if isinstance(out, tuple) else out
        return bytes(clear).decode("utf-8")
    except Exception as e:
        print(f"[Config] DPAPI decryption failed: {e}")
        return None

def save_api_keys(gemini_api_key: str) -> None:
    """Persist the Gemini key. On Windows it is encrypted with user-scoped DPAPI."""
    data = _read_raw()
    key = (gemini_api_key or "").strip()
    enc = _dpapi_encrypt(key)
    if enc:
        data.pop("gemini_api_key", None)
        data["gemini_api_key_dpapi"] = enc
    else:
        # Portable fallback for macOS/Linux or systems without pywin32.
        data["gemini_api_key"] = key
        data.pop("gemini_api_key_dpapi", None)
    _write_raw(data)

def load_api_keys() -> dict:
    """Return config with a transient decrypted `gemini_api_key` when available."""
    data = _read_raw()
    enc = data.get("gemini_api_key_dpapi", "")
    if enc and not data.get("gemini_api_key"):
        key = _dpapi_decrypt(enc)
        if key:
            data["gemini_api_key"] = key
    # Migrate legacy plaintext secrets to DPAPI automatically on Windows.
    plain = (data.get("gemini_api_key") or "").strip()
    if plain and platform.system() == "Windows" and not enc:
        encrypted = _dpapi_encrypt(plain)
        if encrypted:
            raw = _read_raw()
            raw.pop("gemini_api_key", None)
            raw["gemini_api_key_dpapi"] = encrypted
            _write_raw(raw)
    return data

def get_gemini_key() -> str | None:
    key = load_api_keys().get("gemini_api_key")
    return key.strip() if isinstance(key, str) and key.strip() else None

def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)


def get_assistant_name() -> str:
    """Return the configured assistant name, or 'SAFU' if not set."""
    return load_api_keys().get("assistant_name", "SAFU") or "SAFU"


def get_user_name() -> str:
    """Return the configured user name for addressing."""
    return load_api_keys().get("user_name", "")


def save_assistant_config(assistant_name: str, user_name: str) -> None:
    """Persist assistant name and user name to config."""
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["assistant_name"] = assistant_name.strip() or "SAFU"
    data["user_name"] = user_name.strip()
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


# ── Assistant voice ──────────────────────────────────────────────────────────
# Gemini Live prebuilt voices. Names are proper nouns — identical in every
# language, so this list is safe to show verbatim in any locale.
AVAILABLE_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]
# Leda is documented as "Youthful" and is the default Safu voice.  It is an
# original Google prebuilt voice, not an imitation of an anime actor/character.
DEFAULT_VOICE    = "Leda"


def get_voice() -> str:
    """Return the configured Live voice, falling back to the default if unset
    or if the stored value is not a voice we recognise."""
    v = load_api_keys().get("voice_name", DEFAULT_VOICE) or DEFAULT_VOICE
    return v if v in AVAILABLE_VOICES else DEFAULT_VOICE


def save_voice(voice_name: str) -> None:
    """Persist the chosen Live voice. Unknown names collapse to the default so a
    bad value can never reach the API and break the session."""
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    v = (voice_name or "").strip()
    data["voice_name"] = v if v in AVAILABLE_VOICES else DEFAULT_VOICE
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def get_wake_word_enabled() -> bool:
    """Whether local wake-word gating is on (assistant sleeps until 'Hey Safu')."""
    return load_api_keys().get("wake_word_enabled", False)


def save_wake_word_enabled(enabled: bool) -> None:
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["wake_word_enabled"] = bool(enabled)
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def get_brief_enabled() -> bool:
    return load_api_keys().get("morning_brief_enabled", True)


def save_brief_enabled(enabled: bool) -> None:
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["morning_brief_enabled"] = enabled
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


# ── Audio devices ────────────────────────────────────────────────────────────
# Stored as device NAMES, not sounddevice indices. Indices shift every time a
# USB device is plugged in or removed, so a saved index silently starts pointing
# at a different microphone. The empty string means "system default", which is
# both the factory setting and what an unresolvable saved device falls back to —
# so unplugging a headset degrades to the built-in speakers instead of crashing.

def _patch_config(**fields) -> None:
    """Read-modify-write one or more keys in api_keys.json.

    Every setter in this file open-coded this. Collapsing it here means a new
    setting is one line, and there is one place where a corrupt config file is
    handled instead of nine."""
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update(fields)
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def get_input_device() -> str:
    """Microphone device name, or '' for the system default."""
    return (load_api_keys().get("input_device", "") or "").strip()


def save_input_device(name: str) -> None:
    _patch_config(input_device=(name or "").strip())


def get_output_device() -> str:
    """Speaker device name, or '' for the system default."""
    return (load_api_keys().get("output_device", "") or "").strip()


def save_output_device(name: str) -> None:
    _patch_config(output_device=(name or "").strip())


def get_plugin_enabled(plugin_name: str) -> bool:
    """Plugins are enabled by default the moment they're discovered (opt-out model)."""
    return load_api_keys().get("plugins_enabled", {}).get(plugin_name, True)


# ── Per-plugin settings ("tokens" / connection details) ───────────────────────
# Generic store so a plugin can declare its own config fields (PLUGIN_SETTINGS)
# and the settings UI renders + persists them WITHOUT any core edit — keeping the
# drop-in model intact. Values live under plugin_config[<namespace>][<key>].
# A namespace defaults to the plugin name, but a suite of plugins (e.g. the
# printer control/watchdog/autoeject trio) can share ONE namespace.
def get_plugin_config(namespace: str) -> dict:
    """All stored values for a namespace (empty dict if none set yet)."""
    cfg = load_api_keys().get("plugin_config")
    val = cfg.get(namespace) if isinstance(cfg, dict) else None
    return dict(val) if isinstance(val, dict) else {}


def get_plugin_setting(namespace: str, key: str, default=None):
    """A single value from a namespace, or `default` if unset."""
    return get_plugin_config(namespace).get(key, default)


def save_plugin_config(namespace: str, values: dict) -> None:
    """Merge `values` into a namespace's stored config (read-modify-write, like
    every other helper here). Only the provided keys are touched."""
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    pc = data.get("plugin_config")
    if not isinstance(pc, dict):
        pc = {}
    cur = pc.get(namespace)
    if not isinstance(cur, dict):
        cur = {}
    cur.update(values)
    pc[namespace] = cur
    data["plugin_config"] = pc
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def save_plugin_enabled(plugin_name: str, enabled: bool) -> None:
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    plugins_cfg = data.get("plugins_enabled")
    if not isinstance(plugins_cfg, dict):
        plugins_cfg = {}
    plugins_cfg[plugin_name] = enabled
    data["plugins_enabled"] = plugins_cfg
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")

def get_dashboard_enabled() -> bool:
    """Remote phone dashboard is opt-in to reduce background RAM/network exposure."""
    return bool(load_api_keys().get("remote_dashboard_enabled", False))

def save_dashboard_enabled(enabled: bool) -> None:
    """Persist remote-dashboard state without touching the encrypted API key."""
    _patch_config(remote_dashboard_enabled=bool(enabled))

# ── Multi-model brain settings ───────────────────────────────────────────────
# SAFU's realtime voice remains Gemini Live, but heavy reasoning/coding/drafting
# can be delegated to another provider. Cloud provider secrets are DPAPI-encrypted
# on Windows just like the Gemini key. Local endpoints do not need a secret.

def _save_secret_field(field: str, value: str) -> None:
    data = _read_raw()
    value = (value or "").strip()
    enc = _dpapi_encrypt(value)
    dp_field = field + "_dpapi"
    if value and enc:
        data.pop(field, None)
        data[dp_field] = enc
    elif value:
        data[field] = value
        data.pop(dp_field, None)
    else:
        data.pop(field, None)
        data.pop(dp_field, None)
    _write_raw(data)


def _get_secret_field(field: str) -> str | None:
    data = _read_raw()
    plain = data.get(field)
    if isinstance(plain, str) and plain.strip():
        # Migrate to DPAPI on Windows when possible.
        if platform.system() == "Windows" and not data.get(field + "_dpapi"):
            enc = _dpapi_encrypt(plain.strip())
            if enc:
                data.pop(field, None)
                data[field + "_dpapi"] = enc
                _write_raw(data)
        return plain.strip()
    enc = data.get(field + "_dpapi")
    if isinstance(enc, str) and enc.strip():
        return _dpapi_decrypt(enc.strip())
    return None


def get_openai_key() -> str | None:
    return _get_secret_field("openai_api_key")


def save_openai_key(value: str) -> None:
    _save_secret_field("openai_api_key", value)


def get_anthropic_key() -> str | None:
    return _get_secret_field("anthropic_api_key")


def save_anthropic_key(value: str) -> None:
    _save_secret_field("anthropic_api_key", value)


def get_brain_settings() -> dict:
    d = load_api_keys()
    return {
        "provider": (d.get("brain_provider", "auto") or "auto").strip().lower(),
        "openai_model": d.get("openai_model", "gpt-5.6-terra") or "gpt-5.6-terra",
        "anthropic_model": d.get("anthropic_model", "claude-sonnet-5") or "claude-sonnet-5",
        "gemini_model": d.get("gemini_text_model", "gemini-flash-latest") or "gemini-flash-latest",
        "local_provider": (d.get("llm_provider", "ollama") or "ollama").strip().lower(),
        "local_url": (d.get("llm_url", "http://localhost:11434") or "http://localhost:11434").rstrip("/"),
        "local_model": d.get("llm_model", "llama3.2") or "llama3.2",
    }


def save_brain_settings(*, provider: str | None = None, openai_model: str | None = None,
                        anthropic_model: str | None = None, gemini_model: str | None = None,
                        local_provider: str | None = None, local_url: str | None = None,
                        local_model: str | None = None) -> None:
    fields = {}
    if provider is not None:
        fields["brain_provider"] = (provider or "auto").strip().lower()
    if openai_model is not None:
        fields["openai_model"] = (openai_model or "gpt-5.6-terra").strip()
    if anthropic_model is not None:
        fields["anthropic_model"] = (anthropic_model or "claude-sonnet-5").strip()
    if gemini_model is not None:
        fields["gemini_text_model"] = (gemini_model or "gemini-flash-latest").strip()
    if local_provider is not None:
        lp = (local_provider or "ollama").strip().lower()
        fields["llm_provider"] = "openai" if lp in {"openai", "lmstudio", "llamacpp", "jan", "localai"} else "ollama"
    if local_url is not None:
        fields["llm_url"] = (local_url or "http://localhost:11434").strip().rstrip("/")
    if local_model is not None:
        fields["llm_model"] = (local_model or "llama3.2").strip()
    if fields:
        _patch_config(**fields)
