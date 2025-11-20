import pytest

from config import ConfigError, load_config


def _seed_log_paths(monkeypatch, tmp_path):
  monkeypatch.setenv("SUBMISSION_LOG_PATH", str(tmp_path / "sub.jsonl"))
  monkeypatch.setenv("TORRENT_JOB_LOG_PATH", str(tmp_path / "jobs.jsonl"))


def test_load_config_errors_when_qb_env_missing(monkeypatch, tmp_path):
  _seed_log_paths(monkeypatch, tmp_path)
  monkeypatch.setenv("QB_ENABLED", "1")
  monkeypatch.delenv("QB_URL", raising=False)
  monkeypatch.delenv("QB_USER", raising=False)
  monkeypatch.delenv("QB_PASS", raising=False)

  with pytest.raises(ConfigError) as excinfo:
    load_config()

  assert "QB_URL" in str(excinfo.value)


def test_load_config_reflects_rotation_strategy(monkeypatch, tmp_path):
  _seed_log_paths(monkeypatch, tmp_path)
  monkeypatch.setenv("LOG_ROTATION_STRATEGY", "truncate")
  monkeypatch.setenv("LOG_MAX_MB", "0.5")

  config = load_config()

  assert config.storage.rotation_strategy == "truncate"
  assert config.storage.max_bytes == int(0.5 * 1024 * 1024)


def test_load_config_rejects_bad_timeout(monkeypatch, tmp_path):
  _seed_log_paths(monkeypatch, tmp_path)
  monkeypatch.setenv("MAGNET_REACHABILITY_TIMEOUT", "not-a-number")

  with pytest.raises(ConfigError):
    load_config()


def test_load_config_includes_retry_policy(monkeypatch, tmp_path):
  _seed_log_paths(monkeypatch, tmp_path)
  monkeypatch.setenv("QB_RETRY_ATTEMPTS", "5")
  monkeypatch.setenv("QB_RETRY_BACKOFF_INITIAL", "0.1")
  monkeypatch.setenv("QB_RETRY_BACKOFF_FACTOR", "1.5")

  config = load_config()

  assert config.qbittorrent_retry.attempts == 5
  assert config.qbittorrent_retry.initial_delay == 0.1
  assert config.qbittorrent_retry.backoff_factor == 1.5
