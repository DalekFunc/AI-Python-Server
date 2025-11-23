"""Tests for YouTube download client."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from youtube import (
  DownloadResult,
  YouTubeDownloadClient,
  YouTubeDownloadError,
  YouTubeDownloadTimeoutError,
  YouTubeVideoUnavailableError,
)


def test_youtube_client_checks_ytdlp_available(tmp_path):
  client = YouTubeDownloadClient(download_path=tmp_path, ytdlp_command="nonexistent-yt-dlp")
  with pytest.raises(YouTubeDownloadError, match="yt-dlp is not installed"):
    client.download_video("https://youtube.com/watch?v=test", "test")


@patch("youtube.client.subprocess.run")
@patch("youtube.client.shutil.which")
def test_youtube_client_download_success(mock_which, mock_run, tmp_path):
  mock_which.return_value = "/usr/bin/yt-dlp"

  # Mock metadata fetch
  metadata = {
    "title": "Test Video",
    "duration": 120.5,
    "id": "test123",
  }
  metadata_result = MagicMock()
  metadata_result.returncode = 0
  metadata_result.stdout = json.dumps(metadata)
  metadata_result.stderr = ""

  # Mock download
  download_result = MagicMock()
  download_result.returncode = 0
  download_result.stdout = "Downloaded successfully"
  download_result.stderr = ""

  # Create a dummy file to simulate download
  downloaded_file = tmp_path / "Test Video-test123.mp4"
  downloaded_file.write_bytes(b"fake video content")

  mock_run.side_effect = [metadata_result, download_result]

  client = YouTubeDownloadClient(download_path=tmp_path)
  result = client.download_video("https://youtube.com/watch?v=test123", "test123")

  assert result.success is True
  assert result.video_id == "test123"
  assert result.title == "Test Video"
  assert result.duration == 120.5
  assert result.output_path == downloaded_file


@patch("youtube.client.subprocess.run")
@patch("youtube.client.shutil.which")
def test_youtube_client_handles_unavailable_video(mock_which, mock_run, tmp_path):
  mock_which.return_value = "/usr/bin/yt-dlp"

  metadata_result = MagicMock()
  metadata_result.returncode = 1
  metadata_result.stdout = ""
  metadata_result.stderr = "ERROR: Video unavailable"

  mock_run.return_value = metadata_result

  client = YouTubeDownloadClient(download_path=tmp_path)
  with pytest.raises(YouTubeVideoUnavailableError, match="Video is unavailable"):
    client.download_video("https://youtube.com/watch?v=test", "test")


@patch("youtube.client.subprocess.run")
@patch("youtube.client.shutil.which")
def test_youtube_client_handles_timeout(mock_which, mock_run, tmp_path):
  mock_which.return_value = "/usr/bin/yt-dlp"

  mock_run.side_effect = subprocess.TimeoutExpired("yt-dlp", timeout=300.0)

  client = YouTubeDownloadClient(download_path=tmp_path, timeout=300.0)
  with pytest.raises(YouTubeDownloadTimeoutError, match="timed out"):
    client.download_video("https://youtube.com/watch?v=test", "test")


@patch("youtube.client.subprocess.run")
@patch("youtube.client.shutil.which")
def test_youtube_client_handles_download_failure(mock_which, mock_run, tmp_path):
  mock_which.return_value = "/usr/bin/yt-dlp"

  metadata = {"title": "Test", "id": "test"}
  metadata_result = MagicMock()
  metadata_result.returncode = 0
  metadata_result.stdout = json.dumps(metadata)
  metadata_result.stderr = ""

  download_result = MagicMock()
  download_result.returncode = 1
  download_result.stdout = ""
  download_result.stderr = "Download failed"

  mock_run.side_effect = [metadata_result, download_result]

  client = YouTubeDownloadClient(download_path=tmp_path)
  with pytest.raises(YouTubeDownloadError, match="Download failed"):
    client.download_video("https://youtube.com/watch?v=test", "test")

