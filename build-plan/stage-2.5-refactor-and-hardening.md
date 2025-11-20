## Goal
Stabilize the toy app before automation by cleaning up architecture pain points, tightening config management, and expanding test coverage so Stage 3 CI runs have meaningful signal.

## Plan
1. **Application structure**
   - Introduce `create_app(config: AppConfig | None = None)` that wires Flask, templates, and qBittorrent client per instance.
   - Replace module-level globals (`APP_CONFIG`, `QBITTORRENT_CLIENT`) with objects stored in `app.config` or request context to improve reloads/tests.
2. **Config consolidation**
   - Deduplicate `_env_flag` helpers and move reachability flags/timeouts into `config.load_config()`.
   - Validate env inputs centrally (types, mandatory pairs) and surface friendly error messages on startup.
3. **Logging + storage helpers**
   - Wrap submission/job JSONL writers behind a small storage module with rotation support and indexed lookups for `GET /jobs/<id>`.
   - Add guardrails for large files (size cap, optional truncation) to keep homelab disks tidy.
4. **qBittorrent error handling**
   - Ensure `_dispatch_to_qbittorrent` differentiates duplicate torrents, auth failures, and outages with precise HTTP responses.
   - Add retry/backoff parameters to config so homelab users can tweak behavior without code changes.
5. **Test coverage**
   - Extend `tests/test_app_integration.py` with cases for duplicate torrent errors, unreachable qBittorrent, and reachability probe toggles (mock `requests.head`).
   - Add unit tests for the new storage helpers and config validation routines.
6. **Packaging metadata**
   - Declare `requires-python = ">=3.14"` in `pyproject.toml`.
   - Split dev dependencies (pytest, tooling) into `requirements-dev.txt` or `pyproject` optional dependencies so runtime installs stay lean.

## Exit criteria
- App factory pattern merged and used across scripts/tests.
- Logs are managed through the shared helper with rotation safeguards documented.
- Config/environment parsing lives in one module with meaningful errors.
- New tests cover negative qBittorrent paths and reachability probes, all passing on Python 3.14.
- Project metadata reflects Python 3.14 baseline and separates dev dependencies.
