"""
Example usage of YTDLPClient for searching YouTube videos.

This example demonstrates:
1. Searching for music videos by artist and track
2. Accessing search result metadata (views, channel, duration)
3. Filtering and ranking results

Run with:
    python examples/ytdlp_search_example.py
"""

import asyncio
from pathlib import Path

import fuzzbin
from fuzzbin.clients.ytdlp_client import YTDLPClient


async def main():
    """Search example."""
    print("\n" + "=" * 60)
    print("yt-dlp Search Example")
    print("=" * 60)

    # Configure fuzzbin
    config_path = Path(__file__).parent.parent / "config.yaml"
    fuzzbin.configure(config_path=config_path)

    # Get configuration
    config = fuzzbin.get_config()

    # Create yt-dlp client
    async with YTDLPClient.from_config(config.ytdlp) as client:
        print("\nSearching for: Robin Thicke - Blurred Lines")

        results = await client.search(
            artist="Robin Thicke",
            track_title="Blurred Lines",
            max_results=5,
        )

        print(f"\nFound {len(results)} results:\n")

        for i, result in enumerate(results, 1):
            print(f"{i}. {result.title}")
            print(f"   URL: {result.url}")
            if result.channel:
                print(f"   Channel: {result.channel}")
            if result.view_count:
                print(f"   Views: {result.view_count:,}")
            if result.channel_follower_count:
                print(f"   Subscribers: {result.channel_follower_count:,}")
            if result.duration:
                minutes = result.duration // 60
                seconds = result.duration % 60
                print(f"   Duration: {minutes}:{seconds:02d}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
