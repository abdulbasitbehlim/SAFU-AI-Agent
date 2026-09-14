# Public repository audit

This package is the public GitHub release of SAFU v0.0.1. Personal/runtime
material removed.

## Explicitly excluded

- `config/api_keys.json`
- `memory/long_term.json`
- memory databases
- OAuth/client-secret/token files
- WhatsApp/browser linked sessions
- local TLS private material
- Python caches
- logs, screenshots and downloads

## Included replacements

- `config/api_keys.example.json` — blank, non-secret configuration schema
- `memory/long_term.example.json` — empty personal-memory schema
- `.gitignore` and `.dockerignore` — block private runtime files
- `SECURITY.md` — public-secret-handling guidance
- `Dockerfile` / `docker-compose.yml` — headless verification and optional Ollama
- `.github/workflows/ci.yml` — compile/package checks

Before every public release, run `python verify_safu.py` and inspect staged files.

## README visual asset

The public package includes `assets/safu-ai-automation-agent-overview.png`, a generic SAFU project/interface overview used by the README. It contains no API keys, personal memory, authentication data, or local runtime files.
