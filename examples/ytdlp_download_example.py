"""
Example usage of YTDLPClient for downloading YouTube videos.

This example demonstrates:
1. Downloading a video by URL
2. Custom output path specification
3. Download result metadata

Run with:
    python examples/ytdlp_download_example.py
"""

import asyncio
from pathlib import Path

import fuzzbin
from fuzzbin.clients.ytdlp_client import YTDLPClient


async def main():
    """Download example."""
    print("\n" + "=" * 60)
    print("yt-dlp Download Example")
    print("=" * 60)

    # Configure fuzzbin
    config_path = Path(__file__).parent.parent / "config.yaml"
    fuzzbin.configure(config_path=config_path)

    # Get configuration
    config = fuzzbin.get_config()

    # Create download directory
    download_dir = Path(__file__).parent / "downloads"
    download_dir.mkdir(exist_ok=True)

    # Create yt-dlp client
    async with YTDLPClient.from_config(config.ytdlp) as client:
        # First, search for the video
        print("\nSearching for video...")
        results = await client.search(
            artist="Robin Thicke",
            track_title="Blurred Lines",
            max_results=1,
        )

        if not results:
            print("No results found!")
            return

        video = results[0]
        print(f"\nFound: {video.title}")
        print(f"URL: {video.url}")

        # Download the video
        output_path = download_dir / "robin_thicke_blurred_lines.mp4"

        print(f"\nDownloading to: {output_path}")
        print("This may take a few minutes...")

        result = await client.download(video.url, output_path)

        print("\nDownload complete!")
        print(f"File size: {result.file_size / (1024 * 1024):.2f} MB")
        print(f"Saved to: {result.output_path}")


if __name__ == "__main__":
    asyncio.run(main())
