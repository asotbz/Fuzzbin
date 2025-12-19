"""
Example usage of YTDLPClient with progress monitoring.

This example demonstrates:
1. Real-time download progress monitoring
2. Progress callback with live updates
3. Displaying download statistics

Run with:
    python examples/ytdlp_progress_example.py
"""

import asyncio
import sys
from pathlib import Path

import fuzzbin
from fuzzbin.clients.ytdlp_client import YTDLPClient
from fuzzbin.parsers.ytdlp_models import DownloadProgress


def format_bytes(bytes_value: float) -> str:
    """Format bytes to human-readable string."""
    if bytes_value is None:
        return "Unknown"

    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB"


def format_time(seconds: int) -> str:
    """Format seconds to MM:SS."""
    if seconds is None:
        return "Unknown"
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


async def main():
    """Progress monitoring example."""
    print("\n" + "=" * 60)
    print("yt-dlp Download with Progress Monitoring")
    print("=" * 60)

    # Configure fuzzbin
    config_path = Path(__file__).parent.parent / "config.yaml"
    fuzzbin.configure(config_path=config_path)

    # Get configuration
    config = fuzzbin.get_config()

    # Create download directory
    download_dir = Path(__file__).parent / "downloads"
    download_dir.mkdir(exist_ok=True)

    # Create progress callback
    last_percent = -1

    def on_progress(progress: DownloadProgress):
        """Display progress updates."""
        nonlocal last_percent

        # Only print when percent changes to avoid spam
        if int(progress.percent) != int(last_percent):
            last_percent = progress.percent

            # Build progress bar
            bar_width = 40
            filled = int(bar_width * progress.percent / 100)
            bar = "█" * filled + "░" * (bar_width - filled)

            # Build status line
            speed_str = (
                format_bytes(progress.speed_bytes_per_sec) + "/s"
                if progress.speed_bytes_per_sec
                else "Unknown"
            )
            eta_str = format_time(progress.eta_seconds) if progress.eta_seconds else "Unknown"
            size_str = format_bytes(progress.total_bytes) if progress.total_bytes else "Unknown"

            # Print with carriage return to overwrite line
            sys.stdout.write(
                f"\r[{bar}] {progress.percent:5.1f}% | "
                f"{format_bytes(progress.downloaded_bytes)} / {size_str} | "
                f"{speed_str} | ETA: {eta_str}"
            )
            sys.stdout.flush()

            # Print newline when complete
            if progress.status == "finished":
                print()

    # Create yt-dlp client
    async with YTDLPClient.from_config(config.ytdlp) as client:
        # Search for video
        print("\nSearching for: Robin Thicke - Blurred Lines")
        results = await client.search(
            artist="Robin Thicke",
            track_title="Blurred Lines",
            max_results=1,
        )

        if not results:
            print("No results found!")
            return

        video = results[0]
        print(f"Found: {video.title}")
        print(f"URL: {video.url}")

        # Download with progress monitoring
        output_path = download_dir / "robin_thicke_blurred_lines_progress.mp4"

        print(f"\nDownloading to: {output_path}")
        print()

        result = await client.download(
            video.url,
            output_path,
            progress_callback=on_progress,  # ← Progress callback
        )

        print(f"\nDownload complete!")
        print(f"File size: {result.file_size / (1024 * 1024):.2f} MB")
        print(f"Saved to: {result.output_path}")


if __name__ == "__main__":
    asyncio.run(main())
