"""
Simple Flask web server (Python 3.14) that mimics a minimalist Google-style home page
and logs submitted magnet links as JSON lines on disk.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from flask import (
  Flask,
  Request,
  Response,
  current_app,
  jsonify,
  render_template_string,
  request,
)

from config import AppConfig, QbittorrentConfig, RetryPolicy, load_config
from magnet import validate_magnet
from qbittorrent import (
  AuthenticationError,
  QbittorrentClient,
  QbittorrentError,
  TorrentDuplicateError,
  TorrentRejectedError,
  TorrentServerUnavailable,
)
from storage import LogStorage


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


def create_app(
  config: AppConfig | None = None,
  *,
  qb_client_factory: Callable[[QbittorrentConfig], QbittorrentClient] | None = None,
) -> Flask:
  config = config or load_config()
  app = Flask(__name__)
  app.config["SECRET_KEY"] = config.secret_key
  app.config["APP_CONFIG"] = config
  app.extensions["logs"] = LogStorage(config.storage)
  app.extensions["qb_client"] = None

  if config.qbittorrent:
    factory = qb_client_factory or _build_qbittorrent_client
    app.extensions["qb_client"] = factory(config.qbittorrent)

  @app.get("/")
  def home() -> str:
    return render_template_string(TEMPLATE, message=None)

  @app.post("/submit")
  def submit() -> Response | str:
    cfg: AppConfig = current_app.config["APP_CONFIG"]
    logs: LogStorage = current_app.extensions["logs"]

    magnet_link = request.form.get("magnet", "").strip()
    if not magnet_link:
      return render_template_string(
        TEMPLATE,
        message="Please provide a magnet link.",
      )

    validation = validate_magnet(
      magnet_link,
      probe_reachability=cfg.magnet_probe.enabled,
      probe_timeout=cfg.magnet_probe.timeout,
    )

    entry = {
      "received_at": datetime.now(timezone.utc).isoformat(),
      "client_ip": _client_ip(request),
      "user_agent": request.headers.get("User-Agent", ""),
      "magnet_link": magnet_link,
      "status": "accepted" if validation.is_valid else "rejected",
      "validation": validation.to_dict(),
    }
    logs.submissions.append(entry)

    if not validation.is_valid:
      reasons = "; ".join(validation.errors)
      return (
        render_template_string(TEMPLATE, message=f"Invalid magnet link: {reasons}"),
        400,
      )

    if not cfg.qbittorrent:
      return render_template_string(
        TEMPLATE,
        message="Magnet link received. qBittorrent integration is disabled.",
      )

    enqueue_result = _dispatch_to_qbittorrent(
      magnet_link=magnet_link,
      info_hash=validation.components.get("info_hash"),
      qb_cfg=cfg.qbittorrent,
      retry=cfg.qbittorrent_retry,
      qb_client=current_app.extensions.get("qb_client"),
      logs=logs,
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
    logs: LogStorage = current_app.extensions["logs"]
    job = logs.jobs.find_one("job_id", job_id)
    if not job:
      return jsonify({"error": f"Job '{job_id}' not found."}), 404
    return jsonify(job)

  return app


def _build_qbittorrent_client(qb_cfg: QbittorrentConfig) -> QbittorrentClient:
  return QbittorrentClient(
    base_url=qb_cfg.url,
    username=qb_cfg.username,
    password=qb_cfg.password,
    category=qb_cfg.category,
    timeout=qb_cfg.timeout,
  )


def _client_ip(req: Request) -> str:
  """Return the best-effort client IP address."""
  forwarded_for = req.headers.get("X-Forwarded-For")
  if forwarded_for:
    return forwarded_for.split(",")[0].strip()
  return req.remote_addr or "unknown"


def _wants_json(req: Request) -> bool:
  accept_header = req.headers.get("Accept", "")
  return "application/json" in accept_header.lower()


def _dispatch_to_qbittorrent(
  *,
  magnet_link: str,
  info_hash: Optional[str],
  qb_cfg: QbittorrentConfig,
  retry: RetryPolicy,
  qb_client: Optional[QbittorrentClient],
  logs: LogStorage,
) -> Dict[str, Any]:
  client = qb_client
  if not client:
    return {"ok": False, "message": "qBittorrent client is not configured.", "status": 500}

  try:
    version = client.health_check()
  except AuthenticationError as exc:
    return {
      "ok": False,
      "message": f"qBittorrent authentication failed: {exc}",
      "status": 401,
    }
  except TorrentServerUnavailable as exc:
    return {
      "ok": False,
      "message": f"qBittorrent is unreachable: {exc}",
      "status": 503,
    }

  try:
    _enqueue_with_retry(
      client,
      magnet_link,
      category=qb_cfg.category,
      retry=retry,
    )
  except TorrentDuplicateError as exc:
    return {
      "ok": False,
      "message": str(exc),
      "status": 409,
    }
  except AuthenticationError as exc:
    return {
      "ok": False,
      "message": f"qBittorrent authentication failed while queuing: {exc}",
      "status": 401,
    }
  except TorrentServerUnavailable as exc:
    return {
      "ok": False,
      "message": f"qBittorrent became unreachable: {exc}",
      "status": 503,
    }
  except TorrentRejectedError as exc:
    return {
      "ok": False,
      "message": f"qBittorrent rejected the magnet link: {exc}",
      "status": 422,
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
  logs.jobs.append(job)
  return {"ok": True, "job": job}


def _enqueue_with_retry(
  client: QbittorrentClient,
  magnet_link: str,
  *,
  category: str,
  retry: RetryPolicy,
) -> None:
  delay = retry.initial_delay
  for attempt in range(1, retry.attempts + 1):
    try:
      client.add_magnet(magnet_link, category=category)
      return
    except TorrentServerUnavailable:
      if attempt == retry.attempts:
        raise
      if delay > 0:
        time.sleep(delay)
      delay *= retry.backoff_factor


app = create_app()


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=False)
