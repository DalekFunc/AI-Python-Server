import importlib
import json
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture
def configured_app(tmp_path):
  os.environ["SUBMISSION_LOG_PATH"] = str(tmp_path / "submissions.jsonl")
  os.environ["MAGNET_REACHABILITY_PROBE"] = "0"

  if "app" in sys.modules:
    del sys.modules["app"]

  module = importlib.import_module("app")
  return module.app, Path(os.environ["SUBMISSION_LOG_PATH"])


def test_submit_rejects_invalid_magnet_and_logs_reason(configured_app):
  app, log_path = configured_app
  client = app.test_client()

  response = client.post("/submit", data={"magnet": "magnet:?dn=no_xt"})

  assert response.status_code == 400
  assert b"Invalid magnet link" in response.data

  log_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
  assert log_lines, "Expected at least one log entry."
  last_entry = json.loads(log_lines[-1])

  assert last_entry["status"] == "rejected"
  assert last_entry["validation"]["errors"]
  assert "Missing required xt parameter." in last_entry["validation"]["errors"]
