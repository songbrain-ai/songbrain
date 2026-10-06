# Security policy

## Reporting a vulnerability

Please email **support@songbrain.ai** with "Security" in the subject. Do **not** open a public GitHub issue, discussion or pull request for a vulnerability.

Include what you found, how to reproduce it and what an attacker could do with it. Request ids (`req_…`) and timestamps help. Never include a working API key; revoke any key you used for testing.

We confirm receipt within 2 working days, keep you updated while we fix it, and credit you in the changelog if you want.

## Scope

- The SDKs, examples and cookbook in this repository.
- The Songbrain API (`api.songbrain.ai`), its MCP server and webhook signing.

Please don't run load tests or automated scanners against the API, and don't access data that isn't yours. Use test mode (`"test": true`) and your own account for experiments.

## Supported versions

Security fixes go into the latest release of each SDK. Upgrade with `pip install -U songbrain` or `npm install songbrain@latest`.

## Handling keys

- Keep API keys and webhook secrets on your server. Never ship them in a browser or app bundle, and never commit them.
- Verify every webhook with `Songbrain-Signature` against the raw body (both SDKs do it for you) and dedupe on the event `id`.
- A leaked key can be revoked at any time in the [developer console](https://app.songbrain.ai/developers).
