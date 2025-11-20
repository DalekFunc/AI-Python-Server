"""
Simple Flask web server (Python 3.14) that mimics a minimalist Google-style home page
and logs submitted magnet links as JSON lines on disk.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, Request, Response, jsonify, render_template_string, request

from config import AppConfig, QbittorrentConfig, load_config
from magnet import validate_magnet
from qbittorrent import (
  QbittorrentClient,
  QbittorrentError,
  TorrentDuplicateError,
  TorrentServerUnavailable,
)


def _env_flag(name: str, default: str = "0") -> bool:
  return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


LOG_PATH = Path(os.environ.get("SUBMISSION_LOG_PATH", "logs/submissions.jsonl"))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

APP_CONFIG: AppConfig = load_config()
JOB_LOG_PATH = APP_CONFIG.job_log_path

QBITTORRENT_CLIENT: Optional[QbittorrentClient] = None
if APP_CONFIG.qbittorrent:
  qb_cfg = APP_CONFIG.qbittorrent
  QBITTORRENT_CLIENT = QbittorrentClient(
    base_url=qb_cfg.url,
    username=qb_cfg.username,
    password=qb_cfg.password,
    category=qb_cfg.category,
    timeout=qb_cfg.timeout,
  )

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("APP_SECRET_KEY", "dev-secret-key")
app.config["MAGNET_REACHABILITY_PROBE"] = _env_flag("MAGNET_REACHABILITY_PROBE", "0")
app.config["MAGNET_REACHABILITY_TIMEOUT"] = float(os.environ.get("MAGNET_REACHABILITY_TIMEOUT", "2.0"))
app.config["APP_CONFIG"] = APP_CONFIG


TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Magnet Drop</title>
    <style>
      body {
        font-family: Arial, sans-serif;
        background-color: #f8f9fb;
        margin: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        min-height: 100vh;
      }

      main {
        flex: 1;
        display: flex;
        align-items: center;
      }

      .container {
        text-align: center;
      }

      h1 {
        font-size: 3rem;
        color: #4285f4;
        letter-spacing: -2px;
        margin-bottom: 1.5rem;
      }

      form {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        width: min(90vw, 700px);
      }

      input[type="text"] {
        font-size: 1.2rem;
        padding: 1rem 1.5rem;
        border: 1px solid #dcdcdc;
        border-radius: 999px;
        box-shadow: 0 2px 5px rgba(32, 33, 36, 0.28);
        outline: none;
        transition: box-shadow 0.2s ease;
      }

      input[type="text"]:focus {
        box-shadow: 0 2px 8px rgba(32, 33, 36, 0.4);
      }

      button {
        align-self: center;
        padding: 0.75rem 2.5rem;
        border-radius: 24px;
        border: 1px solid #f8f9fa;
        background-color: #f8f9fa;
        cursor: pointer;
        transition: box-shadow 0.2s ease;
        font-size: 1rem;
      }

      button:hover {
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
      }

      .message {
        margin-top: 1rem;
        font-size: 1rem;
        color: #0f9d58;
      }
    </style>
  </head>
  <body>
    <main>
      <div class="container">
        <h1>Magnet Drop</h1>
        <form method="post" action="/submit">
          <input
            type="text"
            name="magnet"
            placeholder="Paste your magnet link here"
            required
          />
          <button type="submit">Send</button>
        </form>
        {% if message %}
        <div class="message">{{ message }}</div>
        {% endif %}
      </div>
    </main>
  </body>
</html>
"""


def _client_ip(req: Request) -> str:
  """Return the best-effort client IP address."""
  forwarded_for = req.headers.get("X-Forwarded-For")
  if forwarded_for:
    # Take the first IP in the comma-separated list.
    return forwarded_for.split(",")[0].strip()
  return req.remote_addr or "unknown"


def _log_submission(payload: Dict[str, Any]) -> None:
  """Append a JSON entry to the log file."""
  with LOG_PATH.open("a", encoding="utf-8") as fp:
    fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _log_job(payload: Dict[str, Any]) -> None:
  with JOB_LOG_PATH.open("a", encoding="utf-8") as fp:
    fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _load_job(job_id: str) -> Optional[Dict[str, Any]]:
  if not JOB_LOG_PATH.exists():
    return None
  with JOB_LOG_PATH.open("r", encoding="utf-8") as fp:
    for line in fp:
      try:
        entry = json.loads(line)
      except json.JSONDecodeError:
        continue
      if entry.get("job_id") == job_id:
        return entry
  return None


def _wants_json(req: Request) -> bool:
  accept_header = req.headers.get("Accept", "")
  return "application/json" in accept_header.lower()


@app.get("/")
def home() -> str:
  return render_template_string(TEMPLATE, message=None)


@app.post("/submit")
def submit() -> Response | str:
  magnet_link = request.form.get("magnet", "").strip()
  if not magnet_link:
    return render_template_string(
      TEMPLATE,
      message="Please provide a magnet link.",
    )

  validation = validate_magnet(
    magnet_link,
    probe_reachability=app.config["MAGNET_REACHABILITY_PROBE"],
    probe_timeout=app.config["MAGNET_REACHABILITY_TIMEOUT"],
  )

  entry = {
    "received_at": datetime.now(timezone.utc).isoformat(),
    "client_ip": _client_ip(request),
    "user_agent": request.headers.get("User-Agent", ""),
    "magnet_link": magnet_link,
    "status": "accepted" if validation.is_valid else "rejected",
    "validation": validation.to_dict(),
  }
  _log_submission(entry)

  if not validation.is_valid:
    reasons = "; ".join(validation.errors)
    return (
      render_template_string(TEMPLATE, message=f"Invalid magnet link: {reasons}"),
      400,
    )

  if not APP_CONFIG.qbittorrent:
    return render_template_string(
      TEMPLATE,
      message="Magnet link received. qBittorrent integration is disabled.",
    )

  enqueue_result = _dispatch_to_qbittorrent(
    magnet_link,
    validation.components.get("info_hash"),
    APP_CONFIG.qbittorrent,
  )

  if not enqueue_result["ok"]:
    payload = {"error": enqueue_result["message"]}
    status_code = enqueue_result["status"]
    if _wants_json(request):
      return jsonify(payload), status_code
    return render_template_string(TEMPLATE, message=enqueue_result["message"]), status_code

  status_code = 202
  payload = {
    "job_id": enqueue_result["job"]["job_id"],
    "info_hash": enqueue_result["job"]["info_hash"],
    "status": enqueue_result["job"]["status"],
    "message": "Magnet link queued with qBittorrent.",
  }
  if _wants_json(request):
    return jsonify(payload), status_code
  return render_template_string(
    TEMPLATE,
    message=f"Magnet accepted as job {payload['job_id']} (status {payload['status']}).",
  ), status_code


@app.get("/jobs/<job_id>")
def job_status(job_id: str) -> Response:
  job = _load_job(job_id)
  if not job:
    return jsonify({"error": f"Job '{job_id}' not found."}), 404
  return jsonify(job)


def _dispatch_to_qbittorrent(
  magnet_link: str,
  info_hash: Optional[str],
  qb_cfg: QbittorrentConfig,
) -> Dict[str, Any]:
  client = QBITTORRENT_CLIENT
  if not client:
    return {"ok": False, "message": "qBittorrent client is not configured.", "status": 500}

  try:
    version = client.health_check()
  except TorrentServerUnavailable as exc:
    return {
      "ok": False,
      "message": f"qBittorrent is unreachable: {exc}",
      "status": 503,
    }

  try:
    _enqueue_with_retry(client, magnet_link, category=qb_cfg.category)
  except TorrentDuplicateError as exc:
    return {
      "ok": False,
      "message": str(exc),
      "status": 409,
    }
  except QbittorrentError as exc:
    return {
      "ok": False,
      "message": f"Failed to queue magnet link: {exc}",
      "status": 502,
    }

  job = {
    "job_id": uuid.uuid4().hex,
    "info_hash": info_hash,
    "magnet_link": magnet_link,
    "category": qb_cfg.category,
    "status": "queued",
    "queued_at": datetime.now(timezone.utc).isoformat(),
    "qbittorrent_version": version,
  }
  _log_job(job)
  return {"ok": True, "job": job}


def _enqueue_with_retry(client: QbittorrentClient, magnet_link: str, *, category: str) -> None:
  delay = 0.25
  attempts = 3
  for attempt in range(1, attempts + 1):
    try:
      client.add_magnet(magnet_link, category=category)
      return
    except TorrentServerUnavailable:
      if attempt == attempts:
        raise
      time.sleep(delay)
      delay *= 2


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=False)
