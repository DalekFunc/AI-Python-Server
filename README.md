# Magnet Drop Test Server

Small Flask application that mimics a minimalist Google-like home page with a wide input box for submitting magnet links. Every submission is appended to `logs/submissions.jsonl` as one JSON object per line, capturing the magnet link, received timestamp (UTC), client IP, and user agent.

## Requirements

- Python 3.14 (or the closest available Python 3.12+ interpreter)
- `pip install -r requirements.txt`
- Docker + `docker compose` if you want to run the bundled qBittorrent stack

## Running

### Flask server only

```bash
python3 app.py
```

The server listens on `0.0.0.0:8080` by default. Override the port with `PORT=<port> python3 app.py`.

### With qBittorrent dispatch

Provide qBittorrent credentials through environment variables (see below) and start the server:

```bash
export QB_ENABLED=1
export QB_URL=http://127.0.0.1:8081
export QB_USER=admin
export QB_PASS=adminadmin
python3 app.py
```

When enabled, every valid magnet is queued through qBittorrent, logged with a job identifier, and exposed via `GET /jobs/<job_id>`.

## Configuration

| Variable | Description | Default |
| --- | --- | --- |
| `SUBMISSION_LOG_PATH` | JSONL file where incoming submissions are appended. | `logs/submissions.jsonl` |
| `TORRENT_JOB_LOG_PATH` | JSONL file storing qBittorrent job metadata. | `logs/jobs.jsonl` |
| `MAGNET_REACHABILITY_PROBE` | `"1"` to probe the first HTTP(S) tracker for reachability. | `0` |
| `MAGNET_REACHABILITY_TIMEOUT` | Timeout (seconds) for tracker probes. | `2.0` |
| `QB_ENABLED` | `"1"` to enable qBittorrent integration. Automatically enabled when any `QB_*` credential is present. | `0` |
| `QB_URL` | qBittorrent WebUI base URL (e.g., `http://127.0.0.1:8081`). | _required when enabled_ |
| `QB_USER` / `QB_PASS` | WebUI credentials. | _required when enabled_ |
| `QB_CATEGORY` | Category/name assigned to queued torrents. | `MagnetDrop` |
| `QB_TIMEOUT` | HTTP timeout (seconds) for qBittorrent API calls. | `10.0` |

## qBittorrent stack & helper script

A ready-to-use qBittorrent container is described in `docker-compose.yml` using the `linuxserver/qbittorrent` image. Persistent configuration and downloads are mounted under `docker/qbittorrent/`.

To launch qBittorrent and the Flask app together:

```bash
./scripts/start_stack.sh
```

The script:

- Sources `.env` if present so you can centralize credentials.
- Boots the qBittorrent container via `docker compose` and waits for it to report healthy.
- Sets sensible defaults for the required `QB_*` variables (overridable).
- Finally starts `python3 app.py`, forwarding any CLI arguments you pass to the script.

You can also manage the container manually:

```bash
docker compose up -d qbittorrent
# After the WebUI is reachable:
QB_ENABLED=1 QB_URL=http://127.0.0.1:8081 QB_USER=admin QB_PASS=adminadmin python3 app.py
```

## Logs & job tracking

Submission log entries live in `logs/submissions.jsonl`, e.g.:

```json
{
  "received_at": "2025-11-19T12:00:00.000000+00:00",
  "client_ip": "203.0.113.10",
  "user_agent": "Mozilla/5.0 ...",
  "magnet_link": "magnet:?xt=urn:btih:..."
}
```

When qBittorrent integration is enabled, each accepted magnet produces a job entry in `logs/jobs.jsonl`, including a server-generated `job_id`, the normalized info hash, and the qBittorrent version that accepted the job. Query `GET /jobs/<job_id>` to retrieve the raw JSON payload for the latest state (currently persisted at enqueue time).
