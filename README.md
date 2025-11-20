# Magnet Drop Test Server

  Small Flask application that mimics a minimalist Google-like home page with a wide input box for submitting magnet links. Every submission is appended to `logs/submissions.jsonl` as one JSON object per line, capturing the magnet link, received timestamp (UTC), client IP, and user agent.

  Magnet links are validated and must include an `xt` parameter pointing to a BTIH info hash. Both Base16 (40 hex characters) and Base32 (32 characters, `A-Z` / `2-7`) encodings are accepted.

## Requirements

- Python 3.14 (or the closest available Python 3.12+ interpreter)
- `pip install -r requirements.txt`

## Running

```bash
python3 app.py
```

The server listens on `0.0.0.0:8080` by default. Override the port with `PORT=<port> python3 app.py`.

## Log Format

`logs/submissions.jsonl` is created automatically. Each line resembles:

```json
  {
    "received_at": "2025-11-19T12:00:00.000000+00:00",
    "client_ip": "203.0.113.10",
    "user_agent": "Mozilla/5.0 ...",
    "magnet_link": "magnet:?xt=urn:btih:...",
    "btih_xt": "urn:btih:...",
    "btih_info_hash": "0123abcd...",
    "btih_encoding": "base16"
  }
```

You can tail the file while testing:

```bash
tail -f logs/submissions.jsonl
```
