"""
Advanced example of YTDLPClient with hooks and cancellation.

This example demonstrates:
1. Download lifecycle hooks (on_start, on_progress, on_complete, on_error)
2. Cancelling downloads mid-progress
3. Async and sync hook callbacks
4. Error handling with hooks

Run with:
    python examples/ytdlp_hooks_cancellation_example.py
"""

import asyncio
import sys
from pathlib import Path

import fuzzbin
from fuzzbin.clients.ytdlp_client import YTDLPClient
from fuzzbin.core.exceptions import DownloadCancelledError
from fuzzbin.parsers.ytdlp_models import (
    CancellationToken,
    DownloadHooks,
    DownloadProgress,
)


def format_bytes(bytes_value: float) -> str:
    """Format bytes to human-readable string."""
    if bytes_value is None:
        return "Unknown"

    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB"


async def example_1_basic_hooks():
    """Example 1: Basic lifecycle hooks."""
    print("\n" + "=" * 70)
    print("Example 1: Download with Lifecycle Hooks")
    print("=" * 70)

    config_path = Path(__file__).parent.parent / "config.yaml"
    fuzzbin.configure(config_path=config_path)
    config = fuzzbin.get_config()

    download_dir = Path(__file__).parent / "downloads"
    download_dir.mkdir(exist_ok=True)

    # Define hooks
    def on_start():
        print("\n[HOOK] Download started!")

    async def on_progress(progress: DownloadProgress):
        """Async progress callback."""
        await asyncio.sleep(0)  # Simulate async work
        bar_width = 30
        filled = int(bar_width * progress.percent / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        speed = format_bytes(progress.speed_bytes_per_sec) + "/s" if progress.speed_bytes_per_sec else "?"
        sys.stdout.write(f"\r[HOOK] [{bar}] {progress.percent:5.1f}% | {speed}")
        sys.stdout.flush()

    def on_complete(result):
        print(f"\n[HOOK] Download complete! File size: {format_bytes(result.file_size)}")
        print(f"[HOOK] Saved to: {result.output_path}")

    def on_error(error):
        print(f"\n[HOOK] Error occurred: {error}")

    hooks = DownloadHooks(
        on_start=on_start,
        on_progress=on_progress,
        on_complete=on_complete,
        on_error=on_error,
    )

    async with YTDLPClient.from_config(config.ytdlp) as client:
        print("\nSearching for: Bush - Machinehead")
        results = await client.search(
            artist="Bush",
            track_title="Machinehead",
            max_results=1,
        )

        if not results:
            print("No results found!")
            return

        video = results[0]
        print(f"Found: {video.title}")

        output_path = download_dir / "bush_machinehead_hooks.mp4"
        print(f"Downloading to: {output_path}\n")

        try:
            await client.download(
                video.url,
                output_path,
                hooks=hooks,
            )
        except Exception as e:
            print(f"\nDownload failed: {e}")


async def example_2_cancellation():
    """Example 2: Cancel download after 50%."""
    print("\n" + "=" * 70)
    print("Example 2: Cancelling Download at 50%")
    print("=" * 70)

    config_path = Path(__file__).parent.parent / "config.yaml"
    fuzzbin.configure(config_path=config_path)
    config = fuzzbin.get_config()

    download_dir = Path(__file__).parent / "downloads"
    download_dir.mkdir(exist_ok=True)

    # Create cancellation token
    token = CancellationToken()

    def on_start():
        print("\n[HOOK] Download started (will cancel at 50%)")

    def on_progress(progress: DownloadProgress):
        bar_width = 30
        filled = int(bar_width * progress.percent / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        sys.stdout.write(f"\r[HOOK] [{bar}] {progress.percent:5.1f}%")
        sys.stdout.flush()

        # Cancel when we hit 50%
        if progress.percent >= 50.0:
            print("\n[HOOK] Reached 50%, cancelling download...")
            token.cancel()

    hooks = DownloadHooks(
        on_start=on_start,
        on_progress=on_progress,
    )

    async with YTDLPClient.from_config(config.ytdlp) as client:
        print("\nSearching for: The Offspring - Self Esteem")
        results = await client.search(
            artist="The Offspring",
            track_title="Self Esteem",
            max_results=1,
        )

        if not results:
            print("No results found!")
            return

        video = results[0]
        print(f"Found: {video.title}")

        output_path = download_dir / "offspring_self_esteem_cancelled.mp4"
        print(f"Downloading to: {output_path}\n")

        try:
            await client.download(
                video.url,
                output_path,
                hooks=hooks,
                cancellation_token=token,
            )
        except DownloadCancelledError:
            print("\n[SUCCESS] Download was cancelled successfully!")
            # Clean up partial file
            if output_path.exists():
                output_path.unlink()
                print(f"[CLEANUP] Removed partial file: {output_path}")


async def example_3_timeout_cancellation():
    """Example 3: Auto-cancel after timeout."""
    print("\n" + "=" * 70)
    print("Example 3: Auto-Cancel After 5 Seconds")
    print("=" * 70)

    config_path = Path(__file__).parent.parent / "config.yaml"
    fuzzbin.configure(config_path=config_path)
    config = fuzzbin.get_config()

    download_dir = Path(__file__).parent / "downloads"
    download_dir.mkdir(exist_ok=True)

    token = CancellationToken()
    start_time = None

    def on_start():
        nonlocal start_time
        import time
        start_time = time.time()
        print("\n[HOOK] Download started (will auto-cancel after 5 seconds)")

    def on_progress(progress: DownloadProgress):
        import time
        elapsed = time.time() - start_time if start_time else 0
        bar_width = 25
        filled = int(bar_width * progress.percent / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        sys.stdout.write(
            f"\r[HOOK] [{bar}] {progress.percent:5.1f}% | Elapsed: {elapsed:.1f}s"
        )
        sys.stdout.flush()

        # Cancel after 5 seconds
        if elapsed >= 5.0:
            print("\n[HOOK] 5 seconds elapsed, cancelling...")
            token.cancel()

    hooks = DownloadHooks(
        on_start=on_start,
        on_progress=on_progress,
    )

    async with YTDLPClient.from_config(config.ytdlp) as client:
        print("\nSearching for: Nirvana - Smells Like Teen Spirit")
        results = await client.search(
            artist="Nirvana",
            track_title="Smells Like Teen Spirit",
            max_results=1,
        )

        if not results:
            print("No results found!")
            return

        video = results[0]
        print(f"Found: {video.title}")

        output_path = download_dir / "nirvana_timeout_cancelled.mp4"
        print(f"Downloading to: {output_path}\n")

        try:
            await client.download(
                video.url,
                output_path,
                hooks=hooks,
                cancellation_token=token,
            )
        except DownloadCancelledError:
            print("\n[SUCCESS] Download cancelled after timeout!")
            if output_path.exists():
                output_path.unlink()
                print(f"[CLEANUP] Removed partial file")


async def example_4_error_handling():
    """Example 4: Error handling with hooks."""
    print("\n" + "=" * 70)
    print("Example 4: Error Handling with Hooks")
    print("=" * 70)

    config_path = Path(__file__).parent.parent / "config.yaml"
    fuzzbin.configure(config_path=config_path)
    config = fuzzbin.get_config()

    download_dir = Path(__file__).parent / "downloads"
    download_dir.mkdir(exist_ok=True)

    error_captured = []

    async def on_error(error):
        """Async error handler."""
        await asyncio.sleep(0)  # Simulate async logging
        error_captured.append(str(error))
        print(f"\n[HOOK] Error captured: {type(error).__name__}")
        print(f"[HOOK] Message: {error}")

    hooks = DownloadHooks(on_error=on_error)

    async with YTDLPClient.from_config(config.ytdlp) as client:
        print("\nAttempting to download from invalid URL...")

        output_path = download_dir / "invalid_download.mp4"

        try:
            await client.download(
                "https://www.youtube.com/watch?v=INVALID_VIDEO_ID",
                output_path,
                hooks=hooks,
            )
        except Exception as e:
            print(f"\n[MAIN] Exception caught: {type(e).__name__}")
            print(f"[INFO] Error hook was called: {len(error_captured) > 0}")


async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("YTDLPClient Advanced Features: Hooks and Cancellation")
    print("=" * 70)

    # Run examples
    await example_1_basic_hooks()
    await asyncio.sleep(1)

    await example_2_cancellation()
    await asyncio.sleep(1)

    await example_3_timeout_cancellation()
    await asyncio.sleep(1)

    await example_4_error_handling()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
