# Stage 2 – qBittorrent Integration

## Goal
When a valid magnet is received, automatically enqueue it on the co-hosted qBittorrent instance and begin downloading, with visibility into job status.

## Plan
1. **Surface configuration**
   - Add `QB_URL`, `QB_USER`, `QB_PASS`, and `QB_CATEGORY` env vars (document in `README.md`).
   - Provide config loader (`config.py`) that validates presence when integration is enabled.
2. **Authentication client**
   - Create `qbittorrent/client.py` encapsulating WebUI API calls (login, addMagnet, getTorrentInfo).
   - Manage cookie/session persistence and CSRF token; auto-refresh on 403.
3. **Request workflow changes**
   - After passing Stage 1 validation, call client `add_magnet(magnet, save_path?, category)`.
   - Store torrent hash/job metadata in persistent log or lightweight DB for later tracking.
   - Return 202 Accepted with job identifier, include poll endpoint stub for future work.
4. **Error handling & retries**
   - Map qBittorrent errors (auth failure, duplicate torrent, server unavailable) to API responses with actionable messages.
   - Implement limited retry with exponential backoff for transient network issues.
5. **Testing**
   - Mock client to unit test integration path without live qBittorrent.
   - Provide smoke script or integration test hitting a local qBittorrent container (document docker-compose snippet for manual verification).

## References
- Git stage reference: `stage-2-qbittorrent-integration`
- PR checklist anchor: `Stage 2 – Torrent Dispatch`
