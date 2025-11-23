"""YouTube download client using yt-dlp."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


class YouTubeDownloadError(Exception):
  """Base exception for YouTube download errors."""

  pass


class YouTubeVideoUnavailableError(YouTubeDownloadError):
  """Raised when the video is unavailable (deleted, private, age-restricted, etc.)."""

  pass


class YouTubeDownloadTimeoutError(YouTubeDownloadError):
  """Raised when the download operation times out."""

  pass


@dataclass
class DownloadResult:
  """Result of a YouTube video download operation."""

  success: bool
  video_id: str
  url: str
  output_path: Path | None = None
  title: str | None = None
  duration: float | None = None
  file_size: int | None = None
  error: str | None = None
  metadata: Dict[str, Any] = field(default_factory=dict)

  def to_dict(self) -> Dict[str, Any]:
    return {
      "success": self.success,
      "video_id": self.video_id,
      "url": self.url,
      "output_path": str(self.output_path) if self.output_path else None,
      "title": self.title,
      "duration": self.duration,
      "file_size": self.file_size,
      "error": self.error,
      "metadata": self.metadata,
    }


class YouTubeDownloadClient:
  """Client for downloading YouTube videos using yt-dlp."""

  def __init__(
    self,
    download_path: Path,
    *,
    format: str = "bestvideo",
    timeout: float = 300.0,
    ytdlp_command: str = "yt-dlp",
  ) -> None:
    """
    Initialize the YouTube download client.

    Args:
      download_path: Directory where downloaded videos will be stored.
      format: Video format selector (default: "bestvideo" for video-only).
      timeout: Maximum time in seconds for download operations.
      ytdlp_command: Command to invoke yt-dlp (default: "yt-dlp").
    """
    self.download_path = Path(download_path)
    self.download_path.mkdir(parents=True, exist_ok=True)
    self.format = format
    self.timeout = timeout
    self.ytdlp_command = ytdlp_command

  def _check_ytdlp_available(self) -> None:
    """Check if yt-dlp is available in PATH."""
    if not shutil.which(self.ytdlp_command):
      raise YouTubeDownloadError(
        f"yt-dlp is not installed or not available in PATH. "
        f"Install it with: pip install yt-dlp or visit https://github.com/yt-dlp/yt-dlp"
      )

  def download_video(self, url: str, video_id: str) -> DownloadResult:
    """
    Download a YouTube video.

    Args:
      url: YouTube video URL.
      video_id: Extracted video ID.

    Returns:
      DownloadResult with download status and metadata.
    """
    self._check_ytdlp_available()

    # Output template: {title}-{id}.{ext}
    output_template = str(self.download_path / "%(title)s-%(id)s.%(ext)s")

    # Build yt-dlp command
    cmd = [
      self.ytdlp_command,
      "--format",
      self.format,
      "--output",
      output_template,
      "--no-playlist",  # Only download single video
      "--no-warnings",  # Suppress warnings in output
      url,
    ]

    try:
      # First, get video metadata
      metadata_cmd = [
        self.ytdlp_command,
        "--dump-json",
        "--no-playlist",
        "--no-warnings",
        url,
      ]
      metadata_result = subprocess.run(
        metadata_cmd,
        capture_output=True,
        text=True,
        timeout=self.timeout,
        check=False,
      )

      if metadata_result.returncode != 0:
        error_msg = metadata_result.stderr or metadata_result.stdout or "Unknown error"
        if "Video unavailable" in error_msg or "Private video" in error_msg or "This video is not available" in error_msg:
          raise YouTubeVideoUnavailableError(f"Video is unavailable: {error_msg}")
        raise YouTubeDownloadError(f"Failed to fetch video metadata: {error_msg}")

      try:
        metadata = json.loads(metadata_result.stdout)
      except json.JSONDecodeError as exc:
        raise YouTubeDownloadError(f"Failed to parse video metadata: {exc}")

      title = metadata.get("title")
      duration = metadata.get("duration")

      # Now perform the actual download
      download_result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=self.timeout,
        check=False,
      )

      if download_result.returncode != 0:
        error_msg = download_result.stderr or download_result.stdout or "Unknown error"
        if "Video unavailable" in error_msg or "Private video" in error_msg:
          raise YouTubeVideoUnavailableError(f"Video is unavailable: {error_msg}")
        raise YouTubeDownloadError(f"Download failed: {error_msg}")

      # Find the downloaded file
      # yt-dlp outputs the final filename to stdout on the last line
      output_lines = download_result.stdout.strip().split("\n")
      downloaded_file = None

      # Try to find the file by matching the output template pattern
      if title:
        # Sanitize title for filename matching
        safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in title)
        for file in self.download_path.iterdir():
          if video_id in file.name and file.is_file():
            downloaded_file = file
            break

      if not downloaded_file:
        # Fallback: find the most recently modified file in the download directory
        files = sorted(self.download_path.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
          downloaded_file = files[0]

      file_size = downloaded_file.stat().st_size if downloaded_file and downloaded_file.exists() else None

      return DownloadResult(
        success=True,
        video_id=video_id,
        url=url,
        output_path=downloaded_file,
        title=title,
        duration=duration,
        file_size=file_size,
        metadata=metadata,
      )

    except subprocess.TimeoutExpired:
      raise YouTubeDownloadTimeoutError(f"Download operation timed out after {self.timeout} seconds")
    except YouTubeVideoUnavailableError:
      raise
    except YouTubeDownloadError:
      raise
    except Exception as exc:
      raise YouTubeDownloadError(f"Unexpected error during download: {exc}") from exc

