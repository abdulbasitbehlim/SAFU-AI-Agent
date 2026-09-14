# Security and privacy

## Never commit personal runtime data

This repository intentionally excludes:

- `config/api_keys.json`
- `memory/long_term.json` and memory databases
- OAuth tokens and client-secret files
- WhatsApp/browser linked-session data
- TLS private keys/certificates generated locally
- logs, screenshots and downloads

Use the included `*.example.json` files only as schemas. Keep real values local.

## Before publishing changes

Run:

```bash
python verify_safu.py
```

and inspect staged files:

```bash
git diff --cached --name-only
git grep -n -E 'AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}' --cached
```

If a secret is ever committed, revoke/rotate it immediately. Removing it from the
latest commit is not enough because Git history may still contain it.

## Automation safety

SAFU deliberately keeps confirmation boundaries around destructive or sensitive
operations. Do not remove those safeguards in a public build without reviewing
the security implications.
