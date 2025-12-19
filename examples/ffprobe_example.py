"""Example demonstrating FFProbe integration for video file analysis."""

import asyncio
from pathlib import Path

from fuzzbin import (
    Config,
    FFProbeClient,
    VideoRepository,
    FFProbeParser,
)


async def main():
    """Demonstrate FFProbe video file analysis and database integration."""
    print("=" * 70)
    print("FFProbe Video Analysis Example")
    print("=" * 70)

    # Load configuration
    config_path = Path("config.yaml")
    config = Config.from_yaml(config_path)

    # Initialize FFProbe client
    print("\n1. Initializing FFProbe client...")
    async with FFProbeClient.from_config(config.ffprobe) as ffprobe_client:
        print(f"   FFProbe binary: {ffprobe_client.ffprobe_path}")
        print(f"   Timeout: {ffprobe_client.config.timeout}s")

        # Example video file path (adjust to your actual file)
        video_path = Path("downloads/sample_video.mp4")

        if not video_path.exists():
            print(f"\n⚠️  Video file not found: {video_path}")
            print("   This example requires a video file to analyze.")
            print("   Update the 'video_path' variable with a valid path.\n")
            return

        # Analyze video file
        print(f"\n2. Analyzing video file: {video_path.name}")
        media_info = await ffprobe_client.get_media_info(video_path)

        # Display format information
        print("\n   Format Information:")
        print(f"   - Container: {media_info.format.format_name}")
        print(f"   - Duration: {media_info.format.duration:.2f}s")
        print(f"   - File size: {media_info.format.size:,} bytes")
        print(f"   - Bitrate: {media_info.format.bit_rate:,} bps")

        # Display video stream information
        video_stream = media_info.get_primary_video_stream()
        if video_stream:
            print("\n   Video Stream:")
            print(f"   - Codec: {video_stream.codec_name}")
            print(
                f"   - Resolution: {video_stream.width}x{video_stream.height}"
            )
            print(
                f"   - Aspect Ratio: {video_stream.display_aspect_ratio or 'N/A'}"
            )
            frame_rate = video_stream.get_frame_rate_as_float()
            if frame_rate:
                print(f"   - Frame Rate: {frame_rate:.2f} fps")
            if video_stream.bit_rate:
                print(f"   - Bitrate: {video_stream.bit_rate:,} bps")

        # Display audio stream information
        audio_stream = media_info.get_primary_audio_stream()
        if audio_stream:
            print("\n   Audio Stream:")
            print(f"   - Codec: {audio_stream.codec_name}")
            print(
                f"   - Sample Rate: {audio_stream.sample_rate} Hz"
            )
            print(
                f"   - Channels: {audio_stream.channels} ({audio_stream.channel_layout or 'unknown'})"
            )
            if audio_stream.bit_rate:
                print(f"   - Bitrate: {audio_stream.bit_rate:,} bps")

        # Extract metadata for database storage
        print("\n3. Extracting metadata for database...")
        metadata = FFProbeParser.extract_video_metadata(media_info)
        print(f"   Extracted {len([k for k, v in metadata.items() if v is not None])} fields")

        # Initialize database repository
        print("\n4. Connecting to database...")
        repo = await VideoRepository.from_config(config.database)

        # Set FFProbe client for automatic analysis
        repo.set_ffprobe_client(ffprobe_client)
        print("   FFProbe client configured for automatic analysis")

        # Create a video record
        print("\n5. Creating video record...")
        video_id = await repo.create_video(
            title="Sample Video",
            artist="Example Artist",
            status="discovered",
        )
        print(f"   Created video ID: {video_id}")

        # Manually analyze and update metadata
        print("\n6. Analyzing and updating metadata...")
        await repo.analyze_video_file(video_id, file_path=video_path)

        # Fetch updated record
        video = await repo.get_video_by_id(video_id)
        print("\n   Updated Video Metadata:")
        print(f"   - Title: {video['title']}")
        print(f"   - Duration: {video['duration']:.2f}s")
        print(f"   - Resolution: {video['width']}x{video['height']}")
        print(f"   - Video Codec: {video['video_codec']}")
        print(f"   - Audio Codec: {video['audio_codec']}")
        print(f"   - Container: {video['container_format']}")
        print(f"   - Frame Rate: {video['frame_rate']:.2f} fps")

        # Demonstrate automatic analysis on download
        print("\n7. Testing automatic analysis on download...")
        video_id2 = await repo.create_video(
            title="Auto-Analyzed Video",
            artist="Test Artist",
            status="downloading",
        )
        
        # Mark as downloaded (triggers automatic analysis)
        await repo.mark_as_downloaded(
            video_id2,
            file_path=str(video_path),
            file_size=video_path.stat().st_size,
        )

        video2 = await repo.get_video_by_id(video_id2)
        print(f"   Video ID {video_id2} automatically analyzed:")
        print(f"   - Resolution: {video2['width']}x{video2['height']}")
        print(f"   - Codec: {video2['video_codec']}")

        # Query videos by metadata
        print("\n8. Querying videos by metadata...")

        # Find HD videos (at least 1280x720)
        hd_videos = await repo.query().where_min_resolution(1280, 720).execute()
        print(f"   Found {len(hd_videos)} HD videos (≥720p)")

        # Find videos by duration range (3-5 minutes)
        medium_videos = (
            await repo.query().where_duration_range(180, 300).execute()
        )
        print(f"   Found {len(medium_videos)} videos between 3-5 minutes")

        # Find H.264 videos
        h264_videos = await repo.query().where_codec(video_codec="h264").execute()
        print(f"   Found {len(h264_videos)} H.264 encoded videos")

        # Combined query: HD H.264 videos over 3 minutes
        quality_videos = (
            await repo.query()
            .where_min_resolution(1280, 720)
            .where_codec(video_codec="h264")
            .where_duration_range(min_seconds=180)
            .execute()
        )
        print(
            f"   Found {len(quality_videos)} HD H.264 videos over 3 minutes"
        )

        # Cleanup
        await repo.close()

    print("\n" + "=" * 70)
    print("FFProbe example complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
