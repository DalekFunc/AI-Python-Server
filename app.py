"""
Simple Flask web server (Python 3.14) that mimics a minimalist Google-style home page
and logs submitted magnet links as JSON lines on disk.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from flask import Flask, Request, Response, render_template_string, request

from magnet_utils import MagnetValidationResult, validate_magnet_link


LOG_PATH = Path("logs/submissions.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("APP_SECRET_KEY", "dev-secret-key")


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

  validation: MagnetValidationResult = validate_magnet_link(magnet_link)
  if not validation.is_valid:
    return render_template_string(
      TEMPLATE,
      message=f"Invalid magnet link: {validation.first_error()}",
    )

  entry = {
    "received_at": datetime.now(timezone.utc).isoformat(),
    "client_ip": _client_ip(request),
    "user_agent": request.headers.get("User-Agent", ""),
    "magnet_link": magnet_link,
    "btih_xt": validation.xt,
    "btih_info_hash": validation.info_hash,
    "btih_encoding": validation.info_hash_encoding,
  }
  _log_submission(entry)
  return render_template_string(TEMPLATE, message="Magnet link received. Thank you!")


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=False)
