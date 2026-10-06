# Contributing

Thanks for helping. Bug reports, fixes, docs and cookbook recipes are welcome.

- **Bugs and ideas:** open an [issue](https://github.com/songbrain-ai/songbrain/issues/new/choose). For questions about your account or a specific song, email support@songbrain.ai with the request id (`req_…`).
- **Security:** see [SECURITY.md](SECURITY.md). Never in a public issue.
- **Bigger changes:** open an issue first, so we can agree on the shape before you write code.

## Development

```bash
# Python (3.9+)
cd python
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]" mypy types-requests
python -m mypy --strict src/songbrain
python -m pytest -m "not live"                    # offline; drop -m to include live example calls

# JavaScript / TypeScript (Node 18+)
cd js
npm ci
npm run typecheck
npm test                                          # SONGBRAIN_OFFLINE=1 skips the live example calls
```

## Rules of thumb

- Keep both SDKs in step: a feature lands in Python and JS in the same pull request, with tests in both.
- No new runtime dependencies (Python: only `requests`; JS: none).
- Tests are offline and mock HTTP. Live tests only call the no-key example endpoints.
- Response fields keep the API's names (snake_case) in both SDKs; method names follow each language.
- Add a line to [CHANGELOG.md](CHANGELOG.md) under the next version.
- Cookbook recipes must run with `--example` and, if they call paid services, have a `--dry-run`.

Releases are cut by maintainers with tags (`py-v*`, `js-v*`, `mcp-v*`).

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE).
