import importlib
import json
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture
def app_loader(tmp_path, monkeypatch):
  def _load(**env_overrides):
    base_env = {
      "SUBMISSION_LOG_PATH": str(tmp_path / "submissions.jsonl"),
      "TORRENT_JOB_LOG_PATH": str(tmp_path / "jobs.jsonl"),
      "MAGNET_REACHABILITY_PROBE": "0",
    }
    merged_env = {**base_env, **env_overrides}
    for key, value in merged_env.items():
      monkeypatch.setenv(key, value)

    if "app" in sys.modules:
      del sys.modules["app"]

    module = importlib.import_module("app")
    return module, Path(merged_env["SUBMISSION_LOG_PATH"]), Path(merged_env["TORRENT_JOB_LOG_PATH"])

  return _load


def test_submit_rejects_invalid_magnet_and_logs_reason(app_loader):
  module, log_path, _ = app_loader()
  client = module.app.test_client()

  response = client.post("/submit", data={"magnet": "magnet:?dn=no_xt"})

  assert response.status_code == 400
  assert b"Invalid magnet link" in response.data

  log_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
  assert log_lines, "Expected at least one log entry."
  last_entry = json.loads(log_lines[-1])

  assert last_entry["status"] == "rejected"
  assert last_entry["validation"]["errors"]
  assert "Missing required xt parameter." in last_entry["validation"]["errors"]


def test_submit_acknowledges_when_qbittorrent_disabled(app_loader):
  module, _, job_log_path = app_loader()
  client = module.app.test_client()

  valid_magnet = "magnet:?xt=urn:btih:{hash}&dn=Example".format(hash="A" * 40)
  response = client.post("/submit", data={"magnet": valid_magnet})

  assert response.status_code == 200
  assert b"qBittorrent integration is disabled" in response.data
  assert not job_log_path.exists() or not job_log_path.read_text(encoding="utf-8").strip()


def test_submit_enqueues_when_qbittorrent_enabled(app_loader):
  module, _, job_log_path = app_loader(
    QB_ENABLED="1",
    QB_URL="http://localhost:8081",
    QB_USER="admin",
    QB_PASS="adminadmin",
    QB_CATEGORY="Smoke",
  )

  class StubClient:
    def __init__(self):
      self.health_checks = 0
      self.add_calls = []

    def health_check(self):
      self.health_checks += 1
      return "4.6.4"

    def add_magnet(self, magnet_link, *, category):
      self.add_calls.append((magnet_link, category))

  stub = StubClient()
  module.QBITTORRENT_CLIENT = stub

  valid_magnet = "magnet:?xt=urn:btih:{hash}&dn=Example".format(hash="B" * 40)
  response = module.app.test_client().post("/submit", data={"magnet": valid_magnet})

  assert response.status_code == 202
  assert stub.health_checks == 1
  assert stub.add_calls == [(valid_magnet, "Smoke")]

  log_lines = job_log_path.read_text(encoding="utf-8").strip().splitlines()
  assert log_lines, "Expected a job log entry."
  job_entry = json.loads(log_lines[-1])
  assert job_entry["info_hash"] == "b" * 40
  assert job_entry["status"] == "queued"


def test_submit_accepts_page_url_and_resolves_magnet(app_loader, monkeypatch):
  module, log_path, _ = app_loader()

  info_hash = "C" * 40
  expected_magnet = f"magnet:?xt=urn:btih:{info_hash}&dn=FromPage"
  html_doc = f'<html><a href="{expected_magnet}">download</a></html>'

  class StubResponse:
    def __init__(self, body: bytes):
      self._body = body
      self.status_code = 200
      self.encoding = "utf-8"

    def raise_for_status(self):
      return None

    def iter_content(self, chunk_size: int = 65536):
      yield self._body

  def stub_get(*args, **kwargs):
    return StubResponse(html_doc.encode("utf-8"))

  import requests

  monkeypatch.setattr(requests, "get", stub_get)

  submitted_url = "https://example.com/post/123"
  response = module.app.test_client().post("/submit", data={"magnet": submitted_url})

  assert response.status_code == 200
  assert b"qBittorrent integration is disabled" in response.data

  log_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
  assert log_lines, "Expected at least one log entry."
  last_entry = json.loads(log_lines[-1])
  assert last_entry["submitted_value"] == submitted_url
  assert last_entry["source_url"] == submitted_url
  assert last_entry["magnet_link"] == expected_magnet
