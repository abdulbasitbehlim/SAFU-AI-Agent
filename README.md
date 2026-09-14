<div align="center">

# SAFU AI Automation Agent

**A Windows-first personal AI automation assistant for voice interaction, intelligent desktop workflows, file and document creation, research, and multi-model AI support.**

[![Version](https://img.shields.io/badge/version-v0.0.1-5865F2)](./VERSION)
[![Python](https://img.shields.io/badge/Python-3.11%20--%203.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)](#platform)
[![Docker](https://img.shields.io/badge/Docker-supported-2496ED?logo=docker&logoColor=white)](#docker)
[![Privacy](https://img.shields.io/badge/Privacy-public--safe-success)](#privacy--security)

**Talk • Automate • Create • Get Things Done**

</div>

## Interface & Automation Overview

![SAFU AI Automation Agent interface and automation overview](assets/safu-ai-automation-agent-overview.png)

> The image above is a project overview/visual preview of SAFU's interface and automation capabilities. Actual appearance can vary by configuration and platform.

## About SAFU

**SAFU AI Automation Agent** is a personal desktop AI assistant designed to make everyday computer work faster and more practical. It combines real-time voice interaction, multilingual understanding, English voice replies, file and document management, desktop automation, research tools, and optional multi-model AI routing in one application.

SAFU can help create and manage files, open applications, search local drives, automate multi-step tasks, create office documents, assist with coding and research, and delegate harder tasks to supported cloud or local AI models.

**Public release:** `v0.0.1`

## Key Features

- **Voice assistant** with the wake phrase **“Hey Safu”**
- **Multilingual input** — speak in different languages while SAFU replies in English
- **Fast conversational mode** using Gemini Live when configured
- **Multi-model support** for Gemini, OpenAI, Anthropic/Claude, Ollama, and OpenAI-compatible local servers
- **Desktop automation** for applications, windows, common system actions, and multi-step workflows
- **File and folder automation** across normal Windows drives and user folders
- **Document creation** for TXT, Markdown, JSON, CSV, DOCX, XLSX, and PPTX
- **Research and web tools** for search, summaries, briefings, and browser-assisted tasks
- **Local model option** through Ollama or compatible local inference servers
- **Privacy-focused public configuration** with secrets and personal memory excluded from Git
- **Safety boundaries** around destructive or sensitive automation actions

## Platform

SAFU is designed primarily for **Windows 10/11** because several features depend on Windows APIs, user folders, DPAPI secret protection, native application launching, microphone access, and desktop control.

Recommended Python version:

```text
Python 3.11 - 3.13
```

Newer Python versions may still work, but local PocketSphinx wake-word support can fall back to the online wake path when a compatible binary wheel is unavailable.

## Quick Start

### 1. Clone the repository

```powershell
git clone https://github.com/abdulbasitbehlim/SAFU-AI-Agent-.git
cd SAFU-AI-Agent-
```

### 2. Install the standard dependencies

```powershell
python setup.py
```

For browser automation and heavier optional integrations:

```powershell
python setup.py --full
```

### 3. Verify the installation

```powershell
python verify_safu.py --strict
```

### 4. Start SAFU

```powershell
python main.py
```

or double-click:

```text
run_safu.bat
```

## AI Models

SAFU can work with multiple AI providers. The main real-time voice experience can use Gemini Live, while harder text tasks can optionally be delegated to another configured model.

| Provider | Use | Internet |
|---|---|---|
| Gemini | Voice + text AI | Required |
| OpenAI | Optional secondary model | Required |
| Anthropic / Claude | Optional secondary model | Required |
| Ollama | Local models | Not required after model setup |
| OpenAI-compatible server | LM Studio, llama.cpp, LocalAI, Jan, etc. | Depends on server |

Example Ollama configuration:

```text
Provider: Ollama
URL:      http://localhost:11434
Model:    llama3.2
```

See [`MODELS_AND_AUTOMATION.md`](MODELS_AND_AUTOMATION.md) for additional details.

## Example Commands

```text
Hey Safu, create a Word document on my Desktop called ProjectPlan.docx.

Find my latest PDF on D drive and open it.

Create a folder called MyProject on my Desktop, add a notes file,
and open the folder when you are finished.

Summarize this document and create an Excel table from the important data.

Open my browser and search for the latest information about this topic.
```

## Project Structure

```text
SAFU-AI-Agent-/
├── actions/                # Automation and tool actions
├── assets/                 # README/project visual assets
├── config/                 # Public assets and safe configuration template
├── core/                   # Audio, wake word, model routing, safety helpers
├── dashboard/              # Optional remote dashboard
├── memory/                 # Memory code + empty example schema only
├── plugins/                # Drop-in plugin framework
├── scripts/                # Public-repository/privacy checks
├── .github/                # GitHub Actions and pull-request template
├── main.py                 # Application entry point
├── ui.py                   # PyQt6 desktop interface
├── setup.py                # Standard/full installer
├── Dockerfile              # Headless verification/development container
├── docker-compose.yml      # Docker verification + optional Ollama service
├── requirements.txt        # Full dependencies
├── requirements-lite.txt   # Lightweight dependencies
└── VERSION                 # Public release version
```

## Docker

Docker is included for **headless verification/development** and optional local-model infrastructure. It is not intended to replace the native Windows desktop application because a Linux container cannot normally control the Windows desktop, launch host applications, use Windows DPAPI, or access the native GUI/microphone in the same way.

Build and run the verifier:

```bash
docker build -t safu-ai .
docker run --rm safu-ai
```

or:

```bash
docker compose up --build safu-check
```

Optional Ollama service:

```bash
docker compose --profile local-llm up -d ollama
```

## Privacy & Security

This public repository intentionally does **not** include your personal runtime data or credentials.

The following files and data are excluded by `.gitignore` and the public-repository audit:

```text
config/api_keys.json
memory/long_term.json
memory/*.db
config/certs/
config/whatsapp_web/
**/token*.json
**/client_secret*.json
.env*
logs/
screenshots/
downloads/
```

Safe examples are provided instead:

- `config/api_keys.example.json`
- `memory/long_term.example.json`

Before publishing changes, run:

```powershell
python scripts/check_public_repo.py
```

For security guidance, see [`SECURITY.md`](SECURITY.md).

## Verification

Standard package check:

```powershell
python verify_safu.py
```

Full Windows runtime check after dependencies are installed:

```powershell
python verify_safu.py --strict
```

## Contributing

Issues, bug reports, ideas, and pull requests are welcome. When contributing, do not commit personal API keys, authentication tokens, browser sessions, memory databases, or other private runtime data.

## License & Attribution

See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE) for the applicable license and attribution requirements. Required upstream attribution has been retained.

---

<div align="center">

**SAFU AI Automation Agent v0.0.1**

Built and customized by **Abdul Basit Behlim**

[Repository](https://github.com/abdulbasitbehlim/SAFU-AI-Agent-)

</div>
