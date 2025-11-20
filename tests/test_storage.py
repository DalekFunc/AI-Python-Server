import json

from storage import JsonlStore


def test_jsonl_store_rotates_files_when_exceeding_cap(tmp_path):
  store = JsonlStore(
    path=tmp_path / "submissions.jsonl",
    max_bytes=300,
    max_backups=1,
    rotation_strategy="rotate",
  )
  payload = {"message": "x" * 180}

  store.append(payload)
  assert list(tmp_path.glob("submissions.jsonl.*")) == []

  store.append(payload)
  rotated = list(tmp_path.glob("submissions.jsonl.*"))
  assert rotated, "Expected rotated file when cap exceeded."

  current_lines = (tmp_path / "submissions.jsonl").read_text(encoding="utf-8").strip().splitlines()
  assert len(current_lines) == 1
  assert json.loads(current_lines[0]) == payload


def test_jsonl_store_truncates_when_strategy_is_truncate(tmp_path):
  store = JsonlStore(
    path=tmp_path / "jobs.jsonl",
    max_bytes=80,
    max_backups=1,
    rotation_strategy="truncate",
  )
  payload_one = {"job_id": "a" * 40}
  payload_two = {"job_id": "b" * 40}

  store.append(payload_one)
  store.append(payload_two)

  assert list(tmp_path.glob("jobs.jsonl.*")) == []
  lines = (tmp_path / "jobs.jsonl").read_text(encoding="utf-8").strip().splitlines()
  assert len(lines) == 1
  assert json.loads(lines[0]) == payload_two


def test_jsonl_store_find_one_uses_index(tmp_path):
  store = JsonlStore(
    path=tmp_path / "indexed.jsonl",
    max_bytes=500,
    max_backups=1,
    rotation_strategy="rotate",
    index_fields=("job_id",),
  )

  store.append({"job_id": "alpha", "value": 1})
  store.append({"job_id": "beta", "value": 2})

  result = store.find_one("job_id", "beta")
  assert result is not None
  assert result["value"] == 2
