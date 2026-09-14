# Local configuration

`api_keys.json` is intentionally **not committed** to this repository.

On first run SAFU creates/updates its local configuration. If you want to prepare
one manually, copy `api_keys.example.json` to `api_keys.json` and fill values on
your own machine.

Never commit `api_keys.json`, OAuth tokens, browser/WhatsApp sessions, TLS private
keys, or other credentials. On Windows, supported cloud-provider secrets are
stored with user-scoped DPAPI protection when possible.
