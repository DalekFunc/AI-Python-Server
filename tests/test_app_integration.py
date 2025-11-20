import json
from pathlib import Path

import pytest

from qbittorrent import TorrentDuplicateError, TorrentServerUnavailable

from app import create_app
from config import load_config


@pytest.fixture
def app_loader(tmp_path, monkeypatch):
  def _load(*, qb_client=None, **env_overrides):
    base_env = {
      "SUBMISSION_LOG_PATH": str(tmp_path / "submissions.jsonl"),
      "TORRENT_JOB_LOG_PATH": str(tmp_path / "jobs.jsonl"),
      "MAGNET_REACHABILITY_PROBE": "0",
    }
    merged_env = {**base_env, **env_overrides}
    for key, value in merged_env.items():
      monkeypatch.setenv(key, value)

    config = load_config()

    qb_factory = None
    if qb_client is not None:
      def _factory(_cfg):
        return qb_client

      qb_factory = _factory

    app = create_app(config=config, qb_client_factory=qb_factory)

    return app, Path(merged_env["SUBMISSION_LOG_PATH"]), Path(merged_env["TORRENT_JOB_LOG_PATH"])

  return _load


def test_submit_rejects_invalid_magnet_and_logs_reason(app_loader):
  app, log_path, _ = app_loader()
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


def test_submit_acknowledges_when_qbittorrent_disabled(app_loader):
  app, _, job_log_path = app_loader()
  client = app.test_client()

  valid_magnet = "magnet:?xt=urn:btih:{hash}&dn=Example".format(hash="A" * 40)
  response = client.post("/submit", data={"magnet": valid_magnet})

  assert response.status_code == 200
  assert b"qBittorrent integration is disabled" in response.data
  assert not job_log_path.exists() or not job_log_path.read_text(encoding="utf-8").strip()


def test_submit_enqueues_when_qbittorrent_enabled(app_loader):
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

  app, _, job_log_path = app_loader(
    qb_client=stub,
    QB_ENABLED="1",
    QB_URL="http://localhost:8081",
    QB_USER="admin",
    QB_PASS="adminadmin",
    QB_CATEGORY="Smoke",
  )

  valid_magnet = "magnet:?xt=urn:btih:{hash}&dn=Example".format(hash="B" * 40)
  response = app.test_client().post("/submit", data={"magnet": valid_magnet})

  assert response.status_code == 202
  assert stub.health_checks == 1
  assert stub.add_calls == [(valid_magnet, "Smoke")]

  log_lines = job_log_path.read_text(encoding="utf-8").strip().splitlines()
  assert log_lines, "Expected a job log entry."
  job_entry = json.loads(log_lines[-1])
  assert job_entry["info_hash"] == "b" * 40
  assert job_entry["status"] == "queued"


def test_submit_returns_conflict_on_duplicate_torrent(app_loader):
  class StubClient:
    def health_check(self):
      return "4.6.4"

    def add_magnet(self, *_args, **_kwargs):
      raise TorrentDuplicateError("Magnet already exists.")

  stub = StubClient()
  app, _, _ = app_loader(
    qb_client=stub,
    QB_ENABLED="1",
    QB_URL="http://localhost:8081",
    QB_USER="user",
    QB_PASS="pass",
  )
  valid_magnet = "magnet:?xt=urn:btih:{hash}&dn=Example".format(hash="C" * 40)

  response = app.test_client().post("/submit", data={"magnet": valid_magnet})

  assert response.status_code == 409
  assert b"already exists" in response.data


def test_submit_reports_unreachable_qbittorrent(app_loader):
  class StubClient:
    def health_check(self):
      raise TorrentServerUnavailable("connection refused")

  stub = StubClient()
  app, _, _ = app_loader(
    qb_client=stub,
    QB_ENABLED="1",
    QB_URL="http://localhost:8081",
    QB_USER="user",
    QB_PASS="pass",
  )
  valid_magnet = "magnet:?xt=urn:btih:{hash}&dn=Example".format(hash="D" * 40)

  response = app.test_client().post("/submit", data={"magnet": valid_magnet})

  assert response.status_code == 503
  assert b"unreachable" in response.data


def test_reachability_probe_toggle_logs_tracker(monkeypatch, app_loader):
  class DummyResponse:
    def __init__(self, status_code):
      self.status_code = status_code

  def fake_head(url, **_kwargs):
    fake_head.called = True
    return DummyResponse(204)

  fake_head.called = False
  monkeypatch.setattr("requests.head", fake_head)

  app, log_path, _ = app_loader(MAGNET_REACHABILITY_PROBE="1")
  client = app.test_client()

  magnet = "magnet:?xt=urn:btih:{hash}&dn=Example&tr=https://tracker.example.com/announce".format(
    hash="E" * 40
  )
  response = client.post("/submit", data={"magnet": magnet})

  assert response.status_code == 200
  assert fake_head.called is True

  last_entry = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
  reachability = last_entry["validation"]["reachability"]
  assert reachability["enabled"] is True
  assert reachability["succeeded"] is True
  assert reachability["tracker_url"] == "https://tracker.example.com/announce"
