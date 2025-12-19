"""
Complete workflow: Search, download, and organize music videos.

This example demonstrates the full integration of:
1. YTDLPClient for search and download
2. IMVDbClient for metadata lookup
3. Organizer for file organization
4. NFO file writing

Run with:
    python examples/ytdlp_workflow_example.py
"""

import asyncio
from pathlib import Path

import fuzzbin
from fuzzbin.clients.ytdlp_client import YTDLPClient
from fuzzbin.api.imvdb_client import IMVDbClient
from fuzzbin.core import build_media_paths
from fuzzbin.parsers import MusicVideoNFO, MusicVideoNFOParser


async def main():
    """Complete workflow example."""
    print("\n" + "=" * 60)
    print("Complete Music Video Workflow")
    print("=" * 60)

    # Configure fuzzbin
    config_path = Path(__file__).parent.parent / "config.yaml"
    fuzzbin.configure(config_path=config_path)
    config = fuzzbin.get_config()

    # Input
    artist = "Robin Thicke"
    track = "Blurred Lines"

    # Step 1: Search YouTube
    print(f"\n1. Searching YouTube for: {artist} - {track}")
    async with YTDLPClient.from_config(config.ytdlp) as ytdlp:
        videos = await ytdlp.search(artist, track, max_results=5)

        print(f"   Found {len(videos)} videos")
        if videos:
            print(f"   Top result: {videos[0].title}")
            print(f"   Channel: {videos[0].channel}")
            print(f"   Views: {videos[0].view_count:,}" if videos[0].view_count else "")
        top_video = videos[0]

    # Step 2: Get metadata from IMVDb
    print(f"\n2. Fetching metadata from IMVDb...")
    try:
        async with IMVDbClient.from_config(config.apis["imvdb"]) as imvdb:
            imvdb_results = await imvdb.search_videos(artist, track)

            if imvdb_results:
                imvdb_video = imvdb_results[0]
                print(f"   Title: {imvdb_video.song_title}")
                print(f"   Year: {imvdb_video.year}")
                if imvdb_video.directors:
                    print(f"   Directors: {', '.join(d.entity_name for d in imvdb_video.directors)}")
            else:
                print("   No IMVDb results found, using YouTube metadata")
                imvdb_video = None
    except Exception as e:
        print(f"   IMVDb lookup failed: {e}")
        imvdb_video = None

    # Step 3: Create NFO metadata
    print(f"\n3. Creating NFO metadata...")
    if imvdb_video:
        nfo = MusicVideoNFO(
            title=imvdb_video.song_title,
            artist=imvdb_video.artists[0].name if imvdb_video.artists else artist,
            year=imvdb_video.year,
            director=(
                imvdb_video.directors[0].entity_name if imvdb_video.directors else None
            ),
        )
    else:
        # Fallback to YouTube metadata
        nfo = MusicVideoNFO(
            title=track,
            artist=artist,
            year=None,
        )

    print(f"   Artist: {nfo.artist}")
    print(f"   Title: {nfo.title}")
    if nfo.year:
        print(f"   Year: {nfo.year}")

    # Step 4: Generate organized paths
    print(f"\n4. Generating organized paths...")
    root_path = Path(__file__).parent / "music_videos"

    # Use year in path if available, otherwise just artist/title
    if nfo.year:
        pattern = "{artist}/{year}/{title}"
    else:
        pattern = "{artist}/{title}"

    paths = build_media_paths(
        root_path=root_path,
        pattern=pattern,
        nfo_data=nfo,
        video_extension=".mp4",
        normalize=True,
    )

    print(f"   Video: {paths.video_path}")
    print(f"   NFO: {paths.nfo_path}")

    # Step 5: Download video
    print(f"\n5. Downloading video...")
    # Create directory structure
    paths.video_path.parent.mkdir(parents=True, exist_ok=True)

    async with YTDLPClient.from_config(config.ytdlp) as ytdlp:
        result = await ytdlp.download(top_video.url, paths.video_path)
        print(f"   Downloaded: {result.file_size / (1024 * 1024):.2f} MB")
        print(f"   Location: {result.output_path}")

    # Step 6: Write NFO file
    print(f"\n6. Writing NFO file...")
    parser = MusicVideoNFOParser()
    parser.write_file(nfo, paths.nfo_path)
    print(f"   Written: {paths.nfo_path}")

    print("\n" + "=" * 60)
    print("Workflow complete!")
    print("=" * 60)
    print(f"\nFiles created:")
    print(f"  - {paths.video_path}")
    print(f"  - {paths.nfo_path}")


if __name__ == "__main__":
    asyncio.run(main())
