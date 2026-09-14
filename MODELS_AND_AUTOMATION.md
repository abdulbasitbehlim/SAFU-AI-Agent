# SAFU 0.0.1 — Multi-Model + Automation

## Model brain
Safu keeps Gemini Live as the realtime voice/orchestration channel. For heavy text tasks it can delegate to:

- Gemini text models
- OpenAI Responses API models
- Anthropic Claude models
- Ollama local models
- OpenAI-compatible local servers such as LM Studio, llama.cpp server, Jan and LocalAI

Open **Controls → MODEL BRAIN** to choose a preferred provider, local endpoint/model, and optional cloud API keys. Cloud keys are stored with Windows DPAPI when available. Local Ollama/LM Studio does not require an API key.

Default model entries are suggestions and can be changed in the UI. Model availability depends on the provider/account.

## Desktop file creation fix
Safu no longer assumes the desktop is `C:\\Users\\<name>\\Desktop`. It reads Windows Explorer's **User Shell Folders** setting, which correctly handles OneDrive and other Desktop redirection. Requests such as:

- `Create notes.txt on my desktop`
- `Make a Word document called meeting.docx on Desktop and put these notes in it`
- `Create an Excel file on my desktop from this table`

now use the real Desktop path. Existing files are never silently overwritten by `document_creator`; a duplicate-safe filename is chosen.

## Multi-step agent
`agent_task` turns a dependent multi-step request into a short tool plan and executes the available Safu actions in order. It is designed for workflows such as creating files, organizing folders, opening apps, browser tasks and chained desktop operations.

Safu is deliberately **not an unrestricted arbitrary-command executor**. Protected system paths, irreversible system actions and sensitive/destructive operations retain safety controls and confirmation gates.
