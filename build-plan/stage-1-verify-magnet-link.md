# Stage 1 – Magnet Link Validation

## Goal
Ensure `app.py` rejects malformed or non-resolvable magnet links before any downstream processing, giving actionable feedback to callers.

## Plan
1. **Define validation interface**
   - Add a `validate_magnet(magnet: str) -> MagnetValidationResult` helper in a new module (e.g., `magnet/utils.py`).
   - Result object holds `is_valid`, parsed components, and `errors` list for logging.
2. **Implement syntax checks**
   - Verify scheme (`magnet:?`), ensure required xt parameter exists, and decode URL params.
   - Confirm exact hash length/charset (40 hex for BTIH); support optional dn, tr params.
   - Reject non-ASCII control characters / whitespace.
3. **Add DHT/metadata reachability probe (optional but logged)**
   - Use `libtorrent` (if available) or lightweight tracker HTTP HEAD to confirm info hash resolves.
   - Guard with timeout + feature flag so environments without network access can bypass.
4. **Surface validation in API**
   - Wire helper into main request handler in `app.py`; fail fast with 400 + reasons.
   - Emit structured logs to `logs/submissions.jsonl` for observability.
5. **Testing**
   - Add unit tests for helper covering good/bad magnets, missing params, invalid hashes.
   - Add integration test hitting endpoint with invalid magnet to confirm 400 response and log entry.

## References
- Git stage reference: `stage-1-verify-magnet-link`
- PR checklist anchor: `Stage 1 – Magnet Validation`
