"""Background job handlers.

Each handler is an async function that processes a specific job type.
Handlers receive a Job instance and are responsible for:
1. Reading job.metadata for parameters
2. Calling job.update_progress() periodically
3. Calling job.mark_completed(result) on success
4. Raising exceptions on failure (queue will call job.mark_failed())
5. Checking job.status for cancellation requests
"""

import asyncio
from pathlib import Path
from typing import Any

import structlog

import fuzzbin
from fuzzbin.tasks.models import Job, JobStatus, JobType
from fuzzbin.tasks.queue import JobQueue, get_job_queue
from fuzzbin.workflows.nfo_importer import NFOImporter

logger = structlog.get_logger(__name__)


async def handle_nfo_import(job: Job) -> None:
    """Handle NFO import job.

    Wraps NFOImporter workflow with progress callback for real-time updates.

    Job metadata parameters:
        directory (str, required): Path to directory containing NFO files
        recursive (bool, optional): Scan subdirectories (default: True)
        skip_existing (bool, optional): Skip already imported videos (default: True)

    Job result on completion:
        imported: Number of videos imported
        skipped: Number of videos skipped (already exist)
        failed: Number of import failures
        total_files: Total NFO files found
        duration_seconds: Time taken for import

    Args:
        job: Job instance with metadata containing import parameters

    Raises:
        ValueError: If directory parameter is missing or invalid
    """
    # Extract parameters from job metadata
    directory_str = job.metadata.get("directory")
    if not directory_str:
        raise ValueError("Missing required parameter: directory")

    directory = Path(directory_str)
    if not directory.exists():
        raise ValueError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise ValueError(f"Path is not a directory: {directory}")

    recursive = job.metadata.get("recursive", True)
    skip_existing = job.metadata.get("skip_existing", True)
    initial_status = job.metadata.get("initial_status", "discovered")
    update_file_paths = job.metadata.get("update_file_paths", True)

    logger.info(
        "nfo_import_job_starting",
        job_id=job.id,
        directory=str(directory),
        recursive=recursive,
        skip_existing=skip_existing,
        initial_status=initial_status,
    )

    job.update_progress(0, 1, "Initializing import...")

    # Define progress callback that updates the job
    def progress_callback(processed: int, total: int, current_file: str) -> None:
        # Check for cancellation
        if job.status == JobStatus.CANCELLED:
            raise asyncio.CancelledError("Job cancelled by user")

        job.update_progress(processed, total, f"Importing {current_file}...")

    # Get repository from fuzzbin global state
    repository = await fuzzbin.get_repository()

    # Create importer with progress callback
    importer = NFOImporter(
        video_repository=repository,
        initial_status=initial_status,
        skip_existing=skip_existing,
        progress_callback=progress_callback,
    )

    # Run import
    import asyncio

    result = await importer.import_from_directory(
        root_path=directory,
        recursive=recursive,
        update_file_paths=update_file_paths,
    )

    # Check for cancellation after import
    if job.status == JobStatus.CANCELLED:
        return

    # Mark completed with result
    job.mark_completed(
        {
            "imported": result.imported_count,
            "skipped": result.skipped_count,
            "failed": result.failed_count,
            "total_files": result.total_tracks,
            "duration_seconds": result.duration_seconds,
            "failed_tracks": result.failed_tracks[:10],  # Limit to first 10 failures
            "initial_status": initial_status,
        }
    )

    logger.info(
        "nfo_import_job_completed",
        job_id=job.id,
        imported=result.imported_count,
        skipped=result.skipped_count,
        initial_status=initial_status,
        failed=result.failed_count,
    )


async def handle_spotify_import(job: Job) -> None:
    """Handle Spotify playlist import job.

    Wraps SpotifyPlaylistImporter workflow with progress callback.

    Job metadata parameters:
        playlist_id (str, required): Spotify playlist ID
        skip_existing (bool, optional): Skip already imported tracks (default: True)
        initial_status (str, optional): Status for new tracks (default: "discovered")

    Job result on completion:
        imported: Number of tracks imported
        skipped: Number of tracks skipped (already exist)
        failed: Number of import failures
        total_tracks: Total tracks in playlist
        playlist_name: Name of the imported playlist
        duration_seconds: Time taken for import

    Args:
        job: Job instance with metadata containing import parameters

    Raises:
        ValueError: If playlist_id parameter is missing
        RuntimeError: If Spotify client cannot be initialized
    """
    from fuzzbin.api.spotify_client import SpotifyClient
    from fuzzbin.workflows.spotify_importer import SpotifyPlaylistImporter

    # Extract parameters
    playlist_id = job.metadata.get("playlist_id")
    if not playlist_id:
        raise ValueError("Missing required parameter: playlist_id")

    skip_existing = job.metadata.get("skip_existing", True)
    initial_status = job.metadata.get("initial_status", "discovered")

    logger.info(
        "spotify_import_job_starting",
        job_id=job.id,
        playlist_id=playlist_id,
        skip_existing=skip_existing,
    )

    job.update_progress(0, 1, "Connecting to Spotify...")

    # Define progress callback
    def progress_callback(processed: int, total: int, current_item: str) -> None:
        if job.status == JobStatus.CANCELLED:
            raise asyncio.CancelledError("Job cancelled by user")
        job.update_progress(processed, total, f"Importing {current_item}...")

    # Get config and repository
    config = fuzzbin.get_config()
    repository = await fuzzbin.get_repository()

    # Check if Spotify is configured
    spotify_config = config.apis.get("spotify")
    if not spotify_config:
        raise RuntimeError("Spotify API not configured in config.yaml")

    # Create Spotify client and importer
    async with SpotifyClient.from_config(spotify_config) as spotify_client:
        importer = SpotifyPlaylistImporter(
            spotify_client=spotify_client,
            video_repository=repository,
            initial_status=initial_status,
            skip_existing=skip_existing,
            progress_callback=progress_callback,
        )

        # Run import
        result = await importer.import_playlist(playlist_id)

    # Check for cancellation
    if job.status == JobStatus.CANCELLED:
        return

    # Mark completed
    job.mark_completed(
        {
            "imported": result.imported_count,
            "skipped": result.skipped_count,
            "failed": result.failed_count,
            "total_tracks": result.total_tracks,
            "playlist_name": result.playlist_name,
            "duration_seconds": result.duration_seconds,
            "failed_tracks": result.failed_tracks[:10],
        }
    )

    logger.info(
        "spotify_import_job_completed",
        job_id=job.id,
        playlist_id=playlist_id,
        imported=result.imported_count,
        skipped=result.skipped_count,
        failed=result.failed_count,
    )


async def handle_file_organize(job: Job) -> None:
    """Handle batch file organization job.

    Placeholder for future implementation.

    Job metadata parameters:
        video_ids (list[int], required): List of video IDs to organize
        pattern (str, optional): Target path pattern
        normalize (bool, optional): Normalize filenames (default: False)

    Args:
        job: Job instance with metadata containing organization parameters
    """
    # TODO: Implement when FileManager.organize_video() is available
    video_ids = job.metadata.get("video_ids")
    if video_ids is None:
        raise ValueError("Missing required parameter: video_ids")

    job.update_progress(0, max(len(video_ids), 1), "Starting file organization...")

    # Placeholder - mark completed immediately
    job.mark_completed(
        {
            "organized": 0,
            "errors": 0,
            "total_videos": len(video_ids),
            "message": "File organization not yet implemented",
        }
    )


async def handle_youtube_download(job: Job) -> None:
    """Handle YouTube video download job.

    Supports two modes:
    1. Direct URL download: Provide `url` and `output_path` for single video download
    2. Batch download: Provide `video_ids` to download videos from database entries

    Job metadata parameters (Direct URL mode):
        url (str, required): YouTube video URL or video ID
        output_path (str, required): Full path where to save the video
        format_spec (str, optional): yt-dlp format specification

    Job metadata parameters (Batch mode):
        video_ids (list[int], required): List of video IDs to download
        output_directory (str, optional): Download destination directory
        format (str, optional): yt-dlp format string (default from config)

    Job result on completion (Direct URL mode):
        url: Source URL that was downloaded
        file_path: Path to the downloaded file
        file_size: File size in bytes

    Job result on completion (Batch mode):
        downloaded: Number of videos downloaded
        skipped: Number of videos skipped (no YouTube URL or already downloaded)
        failed: Number of download failures
        total_videos: Total videos to process
        failed_videos: List of failed video IDs with errors

    Args:
        job: Job instance with metadata containing download parameters

    Raises:
        ValueError: If required parameters are missing
    """
    from fuzzbin.clients.ytdlp_client import YTDLPClient
    from fuzzbin.core.exceptions import DownloadCancelledError
    from fuzzbin.parsers.ytdlp_models import CancellationToken, DownloadHooks, DownloadProgress

    # Determine mode based on metadata
    url = job.metadata.get("url")
    output_path = job.metadata.get("output_path")
    video_ids = job.metadata.get("video_ids")

    # Direct URL download mode
    if url and output_path:
        await _handle_direct_url_download(job, url, output_path)
        return

    # Batch download mode (original behavior)
    if video_ids is not None:
        await _handle_batch_youtube_download(job, video_ids)
        return

    raise ValueError("Missing required parameters: provide either (url, output_path) or video_ids")


async def _handle_direct_url_download(job: Job, url: str, output_path: str) -> None:
    """Handle direct URL download for a single YouTube video.

    Args:
        job: Job instance
        url: YouTube URL or video ID
        output_path: Destination file path
    """
    from fuzzbin.clients.ytdlp_client import YTDLPClient
    from fuzzbin.core.exceptions import DownloadCancelledError
    from fuzzbin.parsers.ytdlp_models import CancellationToken, DownloadHooks, DownloadProgress

    format_spec = job.metadata.get("format_spec")

    logger.info(
        "youtube_direct_download_starting",
        job_id=job.id,
        url=url,
        output_path=output_path,
    )

    # Create cancellation token that checks job status
    cancellation_token = CancellationToken()

    # Progress hook with cancellation check
    def on_progress(progress: DownloadProgress) -> None:
        # Check job status and signal cancellation if needed
        if job.status == JobStatus.CANCELLED:
            cancellation_token.cancel()
            return

        # Update job progress
        job.progress = progress.percent / 100.0
        speed_str = ""
        if progress.speed_bytes_per_sec:
            speed_mb = progress.speed_bytes_per_sec / (1024 * 1024)
            speed_str = f" at {speed_mb:.1f} MB/s"

        eta_str = ""
        if progress.eta_seconds:
            eta_str = f" (ETA: {progress.eta_seconds}s)"

        job.current_step = f"Downloading: {progress.percent:.1f}%{speed_str}{eta_str}"

    hooks = DownloadHooks(on_progress=on_progress)

    # Get config
    config = fuzzbin.get_config()
    ytdlp_config = config.ytdlp if hasattr(config, "ytdlp") else None

    # Ensure output directory exists
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        async with (
            YTDLPClient.from_config(ytdlp_config) if ytdlp_config else YTDLPClient()
        ) as client:
            result = await client.download(
                url=url,
                output_path=output_file,
                format_spec=format_spec,
                hooks=hooks,
                cancellation_token=cancellation_token,
            )

        # Check for cancellation after download
        if job.status == JobStatus.CANCELLED:
            logger.info("youtube_direct_download_cancelled", job_id=job.id)
            return

        # Mark completed
        job.mark_completed(
            {
                "url": url,
                "file_path": str(result.file_path),
                "file_size": result.file_size,
            }
        )

        logger.info(
            "youtube_direct_download_completed",
            job_id=job.id,
            file_path=str(result.file_path),
            file_size=result.file_size,
        )

    except DownloadCancelledError:
        logger.info("youtube_direct_download_cancelled", job_id=job.id)
        # Job already marked as cancelled by queue
        return

    except Exception as e:
        logger.error(
            "youtube_direct_download_failed",
            job_id=job.id,
            url=url,
            error=str(e),
        )
        raise


async def _handle_batch_youtube_download(job: Job, video_ids: list) -> None:
    """Handle batch YouTube download for database videos.

    Args:
        job: Job instance
        video_ids: List of video IDs to download
    """
    from fuzzbin.clients.ytdlp_client import YTDLPClient
    from fuzzbin.parsers.ytdlp_models import DownloadHooks, DownloadProgress

    output_directory = job.metadata.get("output_directory")
    format_spec = job.metadata.get("format")

    logger.info(
        "youtube_download_job_starting",
        job_id=job.id,
        video_count=len(video_ids),
        output_directory=output_directory,
    )

    # Get config and repository
    config = fuzzbin.get_config()
    repository = await fuzzbin.get_repository()

    # Determine output directory - default to downloads in library_dir
    if output_directory:
        output_path = Path(output_directory)
    else:
        library_dir = config.library_dir
        if not library_dir:
            from fuzzbin.common.config import _get_default_library_dir

            library_dir = _get_default_library_dir()
        output_path = library_dir / "downloads"

    output_path.mkdir(parents=True, exist_ok=True)

    # Track progress across all videos
    downloaded = 0
    skipped = 0
    failed = 0
    failed_videos: list[dict[str, Any]] = []
    current_video_idx = 0

    # Create yt-dlp client
    ytdlp_config = config.ytdlp if hasattr(config, "ytdlp") else None
    async with YTDLPClient.from_config(ytdlp_config) if ytdlp_config else YTDLPClient() as client:
        for idx, video_id in enumerate(video_ids, start=1):
            current_video_idx = idx

            # Check for cancellation
            if job.status == JobStatus.CANCELLED:
                logger.info("youtube_download_job_cancelled", job_id=job.id)
                return

            job.update_progress(idx - 1, len(video_ids), f"Processing video {video_id}...")

            try:
                # Get video from database
                video = await repository.get_video(video_id)
                if not video:
                    logger.warning("video_not_found", video_id=video_id)
                    skipped += 1
                    continue

                # Check if video has a YouTube URL
                youtube_url = getattr(video, "youtube_url", None) or getattr(
                    video, "download_url", None
                )
                if not youtube_url:
                    logger.debug(
                        "video_no_youtube_url",
                        video_id=video_id,
                        title=video.title,
                    )
                    skipped += 1
                    continue

                # Check if already downloaded
                if video.file_path and Path(video.file_path).exists():
                    logger.debug(
                        "video_already_downloaded",
                        video_id=video_id,
                        file_path=video.file_path,
                    )
                    skipped += 1
                    continue

                # Create progress hook for this video
                def on_progress(progress: DownloadProgress) -> None:
                    if job.status == JobStatus.CANCELLED:
                        raise asyncio.CancelledError("Job cancelled")
                    # Update job with download progress
                    percent = progress.percent / 100.0
                    overall_progress = (current_video_idx - 1 + percent) / len(video_ids)
                    job.progress = min(overall_progress, 1.0)
                    job.current_step = f"Downloading {video.title}: {progress.percent:.1f}%"

                hooks = DownloadHooks(on_progress=on_progress)

                # Generate output filename
                safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in video.title)
                output_file = output_path / f"{safe_title}.mp4"

                # Download video
                result = await client.download(
                    url=youtube_url,
                    output_path=output_file,
                    format_spec=format_spec,
                    hooks=hooks,
                )

                # Update database with file path
                await repository.update_video(video_id, file_path=str(result.file_path))

                downloaded += 1
                logger.info(
                    "video_downloaded",
                    video_id=video_id,
                    file_path=str(result.file_path),
                    file_size=result.file_size,
                )

            except asyncio.CancelledError:
                raise
            except Exception as e:
                failed += 1
                failed_videos.append({"video_id": video_id, "error": str(e)})
                logger.error(
                    "video_download_failed",
                    video_id=video_id,
                    error=str(e),
                )

    # Check for cancellation
    if job.status == JobStatus.CANCELLED:
        return

    # Mark completed
    job.mark_completed(
        {
            "downloaded": downloaded,
            "skipped": skipped,
            "failed": failed,
            "total_videos": len(video_ids),
            "failed_videos": failed_videos[:10],
        }
    )

    logger.info(
        "youtube_download_job_completed",
        job_id=job.id,
        downloaded=downloaded,
        skipped=skipped,
        failed=failed,
    )


async def handle_duplicate_resolution(job: Job) -> None:
    """Handle batch duplicate resolution job.

    Scans for duplicate videos and optionally resolves them.

    Job metadata parameters:
        video_ids (list[int], optional): Specific videos to check for duplicates
        scan_all (bool, optional): Scan entire library (default: False)
        strategy (str, optional): Resolution strategy - "report_only", "keep_best",
            "keep_first", "keep_newest" (default: "report_only")
        min_confidence (float, optional): Minimum confidence threshold (default: 0.8)
        dry_run (bool, optional): Just report, don't delete (default: True)

    Job result on completion:
        duplicates_found: Number of duplicate groups found
        videos_deleted: Number of videos deleted (0 if dry_run)
        videos_kept: Number of videos kept
        duplicate_groups: List of duplicate groups with details

    Args:
        job: Job instance with metadata containing resolution parameters
    """
    from fuzzbin.core.file_manager import FileManager

    # Extract parameters
    video_ids = job.metadata.get("video_ids", [])
    scan_all = job.metadata.get("scan_all", False)
    strategy = job.metadata.get("strategy", "report_only")
    min_confidence = job.metadata.get("min_confidence", 0.8)
    dry_run = job.metadata.get("dry_run", True)

    if not video_ids and not scan_all:
        raise ValueError("Must provide video_ids or set scan_all=True")

    logger.info(
        "duplicate_resolution_job_starting",
        job_id=job.id,
        video_count=len(video_ids) if video_ids else "all",
        strategy=strategy,
        dry_run=dry_run,
    )

    job.update_progress(0, 1, "Initializing duplicate scan...")

    # Get repository and file manager
    config = fuzzbin.get_config()
    repository = await fuzzbin.get_repository()
    file_manager = FileManager.from_config(config.file_manager)

    # Get videos to scan
    if scan_all:
        all_videos = await repository.list_videos(limit=10000)
        video_ids = [v.id for v in all_videos]

    if not video_ids:
        job.mark_completed(
            {
                "duplicates_found": 0,
                "videos_deleted": 0,
                "videos_kept": 0,
                "duplicate_groups": [],
                "message": "No videos to scan",
            }
        )
        return

    # Track results
    duplicate_groups: list[dict[str, Any]] = []
    videos_deleted = 0
    videos_kept = 0
    processed_ids: set[int] = set()

    # Scan for duplicates
    for idx, video_id in enumerate(video_ids, start=1):
        if job.status == JobStatus.CANCELLED:
            return

        # Skip if already processed as part of another group
        if video_id in processed_ids:
            continue

        job.update_progress(idx, len(video_ids), f"Scanning video {video_id} for duplicates...")

        try:
            # Find duplicates for this video
            duplicates = await file_manager.find_all_duplicates(video_id, repository)

            # Filter by confidence threshold
            duplicates = [d for d in duplicates if d.confidence >= min_confidence]

            if duplicates:
                # Get the original video
                original = await repository.get_video(video_id)
                if not original:
                    continue

                # Create duplicate group
                group = {
                    "primary_video_id": video_id,
                    "primary_title": original.title,
                    "duplicates": [
                        {
                            "video_id": d.video_id,
                            "title": d.title,
                            "confidence": d.confidence,
                            "match_type": d.match_type,
                        }
                        for d in duplicates
                    ],
                }
                duplicate_groups.append(group)

                # Mark all as processed
                processed_ids.add(video_id)
                for d in duplicates:
                    processed_ids.add(d.video_id)

                # Apply resolution strategy if not dry_run
                if not dry_run and strategy != "report_only":
                    # Determine which to keep based on strategy
                    all_videos_in_group = [await repository.get_video(video_id)] + [
                        await repository.get_video(d.video_id) for d in duplicates
                    ]
                    all_videos_in_group = [v for v in all_videos_in_group if v]

                    if strategy == "keep_best":
                        # Keep the one with highest quality (file size as proxy)
                        def get_size(v: Any) -> int:
                            if v.file_path and Path(v.file_path).exists():
                                return Path(v.file_path).stat().st_size
                            return 0

                        all_videos_in_group.sort(key=get_size, reverse=True)
                    elif strategy == "keep_newest":
                        # Keep the newest by created_at
                        all_videos_in_group.sort(key=lambda v: v.created_at or 0, reverse=True)
                    # keep_first uses original order

                    # Delete all except first
                    keep_video = all_videos_in_group[0]
                    for v in all_videos_in_group[1:]:
                        await repository.delete_video(v.id)
                        videos_deleted += 1
                        logger.info(
                            "duplicate_deleted",
                            video_id=v.id,
                            kept_video_id=keep_video.id,
                        )

                    videos_kept += 1

        except Exception as e:
            logger.error(
                "duplicate_scan_error",
                video_id=video_id,
                error=str(e),
            )

    # Mark completed
    job.mark_completed(
        {
            "duplicates_found": len(duplicate_groups),
            "videos_deleted": videos_deleted,
            "videos_kept": videos_kept,
            "duplicate_groups": duplicate_groups[:50],  # Limit result size
            "dry_run": dry_run,
            "strategy": strategy,
        }
    )

    logger.info(
        "duplicate_resolution_job_completed",
        job_id=job.id,
        duplicates_found=len(duplicate_groups),
        videos_deleted=videos_deleted,
    )


async def handle_metadata_enrich(job: Job) -> None:
    """Handle metadata enrichment job.

    Enriches video metadata from external APIs (IMVDb, Discogs).

    Job metadata parameters:
        video_ids (list[int], required): List of video IDs to enrich
        sources (list[str], optional): APIs to use - ["imvdb", "discogs"]
            (default: ["imvdb"])
        overwrite (bool, optional): Overwrite existing metadata (default: False)
        fields (list[str], optional): Specific fields to enrich (default: all)

    Job result on completion:
        enriched: Number of videos enriched
        skipped: Number of videos skipped (no matches or already complete)
        failed: Number of enrichment failures
        total_videos: Total videos to process

    Args:
        job: Job instance with metadata containing enrichment parameters

    Raises:
        ValueError: If video_ids parameter is missing
    """
    # Extract parameters
    video_ids = job.metadata.get("video_ids")
    if not video_ids:
        raise ValueError("Missing required parameter: video_ids")

    sources = job.metadata.get("sources", ["imvdb"])
    overwrite = job.metadata.get("overwrite", False)
    fields = job.metadata.get("fields")  # None means all fields

    logger.info(
        "metadata_enrich_job_starting",
        job_id=job.id,
        video_count=len(video_ids),
        sources=sources,
        overwrite=overwrite,
    )

    job.update_progress(0, 1, "Initializing metadata enrichment...")

    # Get config and repository
    config = fuzzbin.get_config()
    repository = await fuzzbin.get_repository()

    # Initialize API clients based on sources
    imvdb_client = None
    discogs_client = None

    if "imvdb" in sources:
        imvdb_config = config.apis.get("imvdb")
        if imvdb_config:
            from fuzzbin.api.imvdb_client import IMVDbClient

            imvdb_client = IMVDbClient.from_config(imvdb_config)

    if "discogs" in sources:
        discogs_config = config.apis.get("discogs")
        if discogs_config:
            from fuzzbin.api.discogs_client import DiscogsClient

            discogs_client = DiscogsClient.from_config(discogs_config)

    # Track results
    enriched = 0
    skipped = 0
    failed = 0

    try:
        for idx, video_id in enumerate(video_ids, start=1):
            if job.status == JobStatus.CANCELLED:
                return

            job.update_progress(idx, len(video_ids), f"Enriching video {video_id}...")

            try:
                # Get video
                video = await repository.get_video(video_id)
                if not video:
                    skipped += 1
                    continue

                # Track if any enrichment happened
                was_enriched = False
                updates: dict[str, Any] = {}

                # Try IMVDb
                if imvdb_client and video.title and video.artist:
                    try:
                        results = await imvdb_client.search_videos(
                            artist=video.artist,
                            title=video.title,
                        )
                        if results:
                            # Get full details of best match
                            best_match = results[0]
                            video_data = await imvdb_client.get_video(best_match.id)

                            # Map IMVDb fields to our model
                            if video_data:
                                if (overwrite or not video.director) and video_data.directors:
                                    updates["director"] = video_data.directors[0].name
                                if (overwrite or not video.year) and video_data.year:
                                    updates["year"] = video_data.year
                                if (
                                    overwrite or not getattr(video, "imvdb_id", None)
                                ) and video_data.id:
                                    updates["imvdb_id"] = str(video_data.id)

                                was_enriched = bool(updates)

                    except Exception as e:
                        logger.warning(
                            "imvdb_enrichment_error",
                            video_id=video_id,
                            error=str(e),
                        )

                # Try Discogs
                if discogs_client and video.artist:
                    try:
                        results = await discogs_client.search(
                            query=f"{video.artist} {video.title or ''}",
                            type="release",
                        )
                        if results and results.results:
                            # Get best match
                            best = results.results[0]
                            if (overwrite or not video.genre) and best.genre:
                                updates["genre"] = best.genre[0] if best.genre else None
                            if (overwrite or not video.year) and best.year:
                                updates["year"] = int(best.year)
                            if (overwrite or not getattr(video, "discogs_id", None)) and best.id:
                                updates["discogs_release_id"] = best.id

                            was_enriched = bool(updates)

                    except Exception as e:
                        logger.warning(
                            "discogs_enrichment_error",
                            video_id=video_id,
                            error=str(e),
                        )

                # Apply updates if any
                if updates:
                    # Filter to requested fields if specified
                    if fields:
                        updates = {k: v for k, v in updates.items() if k in fields}

                    if updates:
                        await repository.update_video(video_id, **updates)
                        enriched += 1
                        logger.info(
                            "video_enriched",
                            video_id=video_id,
                            updates=list(updates.keys()),
                        )
                    else:
                        skipped += 1
                elif was_enriched:
                    skipped += 1  # Had data but nothing new
                else:
                    skipped += 1

            except Exception as e:
                failed += 1
                logger.error(
                    "metadata_enrich_error",
                    video_id=video_id,
                    error=str(e),
                )

    finally:
        # Clean up clients
        if imvdb_client:
            await imvdb_client.aclose()
        if discogs_client:
            await discogs_client.aclose()

    # Mark completed
    job.mark_completed(
        {
            "enriched": enriched,
            "skipped": skipped,
            "failed": failed,
            "total_videos": len(video_ids),
            "sources": sources,
        }
    )

    logger.info(
        "metadata_enrich_job_completed",
        job_id=job.id,
        enriched=enriched,
        skipped=skipped,
        failed=failed,
    )


async def handle_metadata_refresh(job: Job) -> None:
    """Handle metadata refresh job.

    Refreshes metadata for videos that may be stale or incomplete.
    Used by scheduled tasks to periodically update video information.

    Job metadata parameters:
        max_age_days (int, optional): Only refresh videos not updated in N days
            (default: 30)
        sources (list[str], optional): APIs to use - ["imvdb", "discogs"]
            (default: ["imvdb"])
        limit (int, optional): Maximum videos to process (default: 100)

    Job result on completion:
        refreshed: Number of videos refreshed
        skipped: Number of videos skipped
        failed: Number of refresh failures
        total_checked: Total videos checked

    Args:
        job: Job instance with metadata containing refresh parameters
    """
    max_age_days = job.metadata.get("max_age_days", 30)
    sources = job.metadata.get("sources", ["imvdb"])
    limit = job.metadata.get("limit", 100)

    logger.info(
        "metadata_refresh_job_starting",
        job_id=job.id,
        max_age_days=max_age_days,
        sources=sources,
        limit=limit,
    )

    job.update_progress(0, 1, "Finding videos to refresh...")

    config = fuzzbin.get_config()
    repository = await fuzzbin.get_repository()

    # Find videos that need refresh (old or incomplete metadata)
    from datetime import datetime, timedelta, timezone

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    # Query for videos that need refresh
    query = repository.query()
    videos = await query.execute()

    # Filter to videos that need refresh
    videos_to_refresh = []
    for v in videos:
        updated_at = v.get("updated_at")
        if updated_at:
            if isinstance(updated_at, str):
                # Parse ISO format
                try:
                    updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                except Exception:
                    videos_to_refresh.append(v)
                    continue
            else:
                updated = updated_at

            if updated < cutoff_date:
                videos_to_refresh.append(v)
        else:
            # No updated_at, needs refresh
            videos_to_refresh.append(v)

    # Apply limit
    videos_to_refresh = videos_to_refresh[:limit]

    if not videos_to_refresh:
        job.mark_completed(
            {
                "refreshed": 0,
                "skipped": 0,
                "failed": 0,
                "total_checked": len(videos),
                "message": "No videos need refresh",
            }
        )
        return

    job.update_progress(0, len(videos_to_refresh), "Refreshing metadata...")

    # Track results
    refreshed = 0
    skipped = 0
    failed = 0

    # Initialize API clients
    imvdb_client = None
    discogs_client = None

    if "imvdb" in sources:
        imvdb_config = config.apis.get("imvdb")
        if imvdb_config:
            from fuzzbin.api.imvdb_client import IMVDbClient

            imvdb_client = IMVDbClient.from_config(imvdb_config)

    if "discogs" in sources:
        discogs_config = config.apis.get("discogs")
        if discogs_config:
            from fuzzbin.api.discogs_client import DiscogsClient

            discogs_client = DiscogsClient.from_config(discogs_config)

    try:
        for idx, video in enumerate(videos_to_refresh, start=1):
            if job.status == JobStatus.CANCELLED:
                return

            video_id = video["id"]
            job.update_progress(idx, len(videos_to_refresh), f"Refreshing video {video_id}...")

            try:
                title = video.get("title")
                artist = video.get("artist")

                if not title or not artist:
                    skipped += 1
                    continue

                updates: dict[str, Any] = {}

                # Try IMVDb
                if imvdb_client:
                    try:
                        results = await imvdb_client.search_videos(
                            artist=artist,
                            title=title,
                        )
                        if results:
                            video_data = await imvdb_client.get_video(results[0].id)
                            if video_data:
                                if video_data.directors and not video.get("director"):
                                    updates["director"] = video_data.directors[0]
                                if video_data.year and not video.get("year"):
                                    updates["year"] = video_data.year
                    except Exception as e:
                        logger.warning("imvdb_refresh_error", video_id=video_id, error=str(e))

                # Try Discogs
                if discogs_client:
                    try:
                        results = await discogs_client.search(
                            query=f"{artist} {title}",
                            search_type="release",
                        )
                        if results and results.results:
                            release = results.results[0]
                            if release.label and not video.get("studio"):
                                updates["studio"] = release.label[0] if release.label else None
                            if release.genre and not video.get("genre"):
                                updates["genre"] = release.genre[0] if release.genre else None
                    except Exception as e:
                        logger.warning("discogs_refresh_error", video_id=video_id, error=str(e))

                if updates:
                    await repository.update_video(video_id, **updates)
                    refreshed += 1
                else:
                    skipped += 1

            except Exception as e:
                failed += 1
                logger.error(
                    "metadata_refresh_error",
                    video_id=video_id,
                    error=str(e),
                )

    finally:
        if imvdb_client:
            await imvdb_client.aclose()
        if discogs_client:
            await discogs_client.aclose()

    job.mark_completed(
        {
            "refreshed": refreshed,
            "skipped": skipped,
            "failed": failed,
            "total_checked": len(videos),
            "videos_needing_refresh": len(videos_to_refresh),
        }
    )

    logger.info(
        "metadata_refresh_job_completed",
        job_id=job.id,
        refreshed=refreshed,
        skipped=skipped,
        failed=failed,
    )


async def handle_library_scan(job: Job) -> None:
    """Handle library scan job.

    Scans the library for new or modified files.
    Used by scheduled tasks for periodic library maintenance.

    Job metadata parameters:
        directory (str, optional): Directory to scan (default: workspace root)
        recursive (bool, optional): Scan subdirectories (default: True)
        import_nfo (bool, optional): Import found NFO files (default: True)

    Job result on completion:
        new_files_found: Number of new files discovered
        nfo_imported: Number of NFO files imported
        errors: Number of errors encountered

    Args:
        job: Job instance with metadata containing scan parameters
    """
    directory_str = job.metadata.get("directory")
    recursive = job.metadata.get("recursive", True)
    import_nfo = job.metadata.get("import_nfo", True)

    logger.info(
        "library_scan_job_starting",
        job_id=job.id,
        directory=directory_str,
        recursive=recursive,
        import_nfo=import_nfo,
    )

    job.update_progress(0, 1, "Scanning library...")

    config = fuzzbin.get_config()
    repository = await fuzzbin.get_repository()

    # Determine directory - default to library_dir
    if directory_str:
        directory = Path(directory_str)
    else:
        library_dir = config.library_dir
        if not library_dir:
            from fuzzbin.common.config import _get_default_library_dir

            library_dir = _get_default_library_dir()
        directory = library_dir

    if not directory.exists():
        raise ValueError(f"Directory not found: {directory}")

    # Find NFO files
    pattern = "**/*.nfo" if recursive else "*.nfo"
    nfo_files = list(directory.glob(pattern))

    if not nfo_files:
        job.mark_completed(
            {
                "new_files_found": 0,
                "nfo_imported": 0,
                "errors": 0,
                "message": "No NFO files found",
            }
        )
        return

    new_files_found = 0
    nfo_imported = 0
    errors = 0

    if import_nfo:
        # Progress callback
        def progress_callback(processed: int, total: int, current_file: str) -> None:
            if job.status == JobStatus.CANCELLED:
                raise asyncio.CancelledError("Job cancelled by user")
            job.update_progress(processed, total, f"Processing {current_file}...")

        # Use NFOImporter
        importer = NFOImporter(
            video_repository=repository,
            skip_existing=True,
            progress_callback=progress_callback,
        )

        result = await importer.import_from_directory(
            root_path=directory,
            recursive=recursive,
        )

        new_files_found = result.total_files
        nfo_imported = result.imported
        errors = result.failed
    else:
        # Just count files
        new_files_found = len(nfo_files)

    job.mark_completed(
        {
            "new_files_found": new_files_found,
            "nfo_imported": nfo_imported,
            "errors": errors,
            "directory": str(directory),
        }
    )

    logger.info(
        "library_scan_job_completed",
        job_id=job.id,
        new_files_found=new_files_found,
        nfo_imported=nfo_imported,
        errors=errors,
    )


async def handle_import(job: Job) -> None:
    """Handle generic import job.

    Handles imports from various sources (YouTube, IMVDb).
    Used by the imports API for background processing.

    Job metadata parameters:
        source (str, required): Import source - "youtube" or "imvdb"
        urls (list[str], optional): YouTube URLs (for youtube source)
        video_ids (list[str], optional): IMVDb video IDs (for imvdb source)
        search_queries (list[str], optional): IMVDb search queries (for imvdb source)

    Job result on completion:
        imported: Number of items imported
        failed: Number of failures
        total: Total items processed

    Args:
        job: Job instance with metadata containing import parameters
    """
    source = job.metadata.get("source")
    if not source:
        raise ValueError("Missing required parameter: source")

    logger.info(
        "import_job_starting",
        job_id=job.id,
        source=source,
    )

    job.update_progress(0, 1, f"Starting {source} import...")

    config = fuzzbin.get_config()
    repository = await fuzzbin.get_repository()

    imported = 0
    failed = 0
    total = 0

    if source == "youtube":
        urls = job.metadata.get("urls", [])
        if not urls:
            raise ValueError("Missing required parameter: urls")

        total = len(urls)

        from fuzzbin.clients import YTDLPClient

        async with YTDLPClient.from_config(config) as client:
            for idx, url in enumerate(urls, start=1):
                if job.status == JobStatus.CANCELLED:
                    return

                job.update_progress(idx, total, f"Processing {url}...")

                try:
                    info = await client.extract_info(url)
                    if info:
                        # Create video record
                        video_data = {
                            "title": info.get("title"),
                            "artist": info.get("artist") or info.get("uploader"),
                            "youtube_id": info.get("id"),
                            "video_file_path": None,  # Not downloaded yet
                            "status": "pending",
                        }
                        await repository.create_video(**video_data)
                        imported += 1
                except Exception as e:
                    logger.error("youtube_import_error", url=url, error=str(e))
                    failed += 1

    elif source == "imvdb":
        video_ids = job.metadata.get("video_ids", [])
        search_queries = job.metadata.get("search_queries", [])

        imvdb_config = config.apis.get("imvdb")
        if not imvdb_config:
            raise ValueError("IMVDb API not configured")

        from fuzzbin.api.imvdb_client import IMVDbClient

        client = IMVDbClient.from_config(imvdb_config)

        try:
            # Process video IDs
            if video_ids:
                total += len(video_ids)
                for idx, vid in enumerate(video_ids, start=1):
                    if job.status == JobStatus.CANCELLED:
                        return

                    job.update_progress(idx, total, f"Fetching video {vid}...")

                    try:
                        video_data = await client.get_video(vid)
                        if video_data:
                            # Create video record
                            record = {
                                "title": video_data.song_title or video_data.title,
                                "artist": (
                                    ", ".join(video_data.artists) if video_data.artists else None
                                ),
                                "imvdb_video_id": str(video_data.id),
                                "director": (
                                    video_data.directors[0] if video_data.directors else None
                                ),
                                "year": video_data.year,
                                "status": "complete",
                            }
                            await repository.create_video(**record)
                            imported += 1
                    except Exception as e:
                        logger.error("imvdb_import_error", video_id=vid, error=str(e))
                        failed += 1

            # Process search queries
            if search_queries:
                total += len(search_queries)
                for idx, query in enumerate(search_queries, start=1):
                    if job.status == JobStatus.CANCELLED:
                        return

                    job.update_progress(len(video_ids) + idx, total, f"Searching: {query}...")

                    try:
                        results = await client.search_videos(query=query)
                        for result in results[:10]:  # Limit per query
                            video_data = await client.get_video(result.id)
                            if video_data:
                                record = {
                                    "title": video_data.song_title or video_data.title,
                                    "artist": (
                                        ", ".join(video_data.artists)
                                        if video_data.artists
                                        else None
                                    ),
                                    "imvdb_video_id": str(video_data.id),
                                    "director": (
                                        video_data.directors[0] if video_data.directors else None
                                    ),
                                    "year": video_data.year,
                                    "status": "complete",
                                }
                                await repository.create_video(**record)
                                imported += 1
                    except Exception as e:
                        logger.error("imvdb_search_error", query=query, error=str(e))
                        failed += 1

        finally:
            await client.aclose()

    else:
        raise ValueError(f"Unknown import source: {source}")

    job.mark_completed(
        {
            "imported": imported,
            "failed": failed,
            "total": total,
            "source": source,
        }
    )

    logger.info(
        "import_job_completed",
        job_id=job.id,
        source=source,
        imported=imported,
        failed=failed,
    )


def _extract_youtube_id_from_imvdb_sources(sources: list[Any] | None) -> str | None:
    if not sources:
        return None
    for s in sources:
        try:
            if getattr(s, "source_slug", None) != "youtube":
                continue
            source_data = getattr(s, "source_data", None)
            if isinstance(source_data, str) and source_data:
                return source_data
            if isinstance(source_data, dict):
                candidate = (
                    source_data.get("id")
                    or source_data.get("video_id")
                    or source_data.get("youtube_id")
                )
                if isinstance(candidate, str) and candidate:
                    return candidate
        except Exception:
            continue
    return None


async def handle_add_single_import(job: Job) -> None:
    """Handle /add single-video import job.

    Job metadata parameters:
        source (str, required): One of 'imvdb', 'discogs_master', 'discogs_release', 'youtube'
        id (str, required): Source-specific identifier
        youtube_id (str, optional): Explicit YouTube id to associate
        youtube_url (str, optional): Optional URL to resolve via yt-dlp
        skip_existing (bool, optional): Skip if a matching record already exists (default True)
        initial_status (str, optional): Status for new/updated records (default 'discovered')
    """

    source = job.metadata.get("source")
    item_id = job.metadata.get("id")
    if not source or not item_id:
        raise ValueError("Missing required parameters: source, id")

    skip_existing = job.metadata.get("skip_existing", True)
    initial_status = job.metadata.get("initial_status", "discovered")
    youtube_id_override = job.metadata.get("youtube_id")
    youtube_url = job.metadata.get("youtube_url")

    logger.info(
        "add_single_import_job_starting",
        job_id=job.id,
        source=source,
        item_id=item_id,
        skip_existing=skip_existing,
        initial_status=initial_status,
    )

    job.update_progress(0, 3, "Initializing import...")
    repository = await fuzzbin.get_repository()
    config = fuzzbin.get_config()

    if job.status == JobStatus.CANCELLED:
        return

    created = False
    skipped = False
    video_id: int | None = None
    youtube_id: str | None = None
    imvdb_video_id: str | None = None

    if source == "imvdb":
        imvdb_config = (config.apis or {}).get("imvdb")
        if not imvdb_config:
            raise ValueError("IMVDb API not configured")

        try:
            vid = int(item_id)
        except Exception:
            raise ValueError(f"Invalid IMVDb id: {item_id}")

        from fuzzbin.api.imvdb_client import IMVDbClient

        job.update_progress(1, 3, f"Fetching IMVDb video {vid}...")
        async with IMVDbClient.from_config(imvdb_config) as client:
            video = await client.get_video(vid)

        imvdb_video_id = str(video.id)
        youtube_id = youtube_id_override or _extract_youtube_id_from_imvdb_sources(video.sources)

        if skip_existing:
            try:
                existing = await repository.get_video_by_imvdb_id(imvdb_video_id)
                video_id = int(existing["id"])
                skipped = True
            except Exception:
                pass

        if not skipped:
            title = (video.song_title or str(video.id)).strip()
            artist = None
            if getattr(video, "artists", None):
                artist = getattr(video.artists[0], "name", None)

            job.update_progress(2, 3, "Creating video record...")
            video_id = await repository.create_video(
                title=title,
                artist=artist,
                year=getattr(video, "year", None),
                director=(
                    getattr(video.directors[0], "entity_name", None)
                    if getattr(video, "directors", None)
                    else None
                ),
                imvdb_video_id=imvdb_video_id,
                youtube_id=youtube_id,
                download_source=("youtube" if youtube_id else None),
                status=initial_status,
            )
            created = True

    elif source in ("discogs_master", "discogs_release"):
        discogs_config = (config.apis or {}).get("discogs")
        if not discogs_config:
            raise ValueError("Discogs API not configured")

        try:
            did = int(item_id)
        except Exception:
            raise ValueError(f"Invalid Discogs id: {item_id}")

        from fuzzbin.api.discogs_client import DiscogsClient

        job.update_progress(1, 3, f"Fetching Discogs {source} {did}...")
        async with DiscogsClient.from_config(discogs_config) as client:
            payload = await (
                client.get_master(did) if source == "discogs_master" else client.get_release(did)
            )

        if not isinstance(payload, dict):
            raise ValueError("Unexpected Discogs response")

        title = (payload.get("title") or str(did)).strip()
        artists = payload.get("artists") or []
        artist = None
        if artists and isinstance(artists, list) and isinstance(artists[0], dict):
            artist = artists[0].get("name")

        year = payload.get("year")
        if isinstance(year, str):
            try:
                year = int(year)
            except Exception:
                year = None

        if skip_existing and title and artist:
            try:
                existing = (
                    await repository.query().where_title(title).where_artist(artist).execute()
                )
                if existing:
                    video_id = (
                        int(existing[0]["id"])
                        if isinstance(existing[0], dict)
                        else int(existing[0].id)
                    )
                    skipped = True
            except Exception:
                pass

        youtube_id = youtube_id_override

        if not skipped:
            job.update_progress(2, 3, "Creating video record...")
            video_id = await repository.create_video(
                title=title,
                artist=artist,
                album=title,
                year=year if isinstance(year, int) else None,
                youtube_id=youtube_id,
                download_source=("youtube" if youtube_id else None),
                status=initial_status,
            )
            created = True

    elif source == "youtube":
        from fuzzbin.clients.ytdlp_client import YTDLPClient
        from fuzzbin.common.config import YTDLPConfig

        ytdlp_config = config.ytdlp or YTDLPConfig()
        target = youtube_url or item_id

        job.update_progress(1, 3, f"Fetching YouTube metadata for {target}...")
        async with YTDLPClient.from_config(ytdlp_config) as client:
            info = await client.get_video_info(target)

        youtube_id = youtube_id_override or getattr(info, "id", None)

        if skip_existing and youtube_id:
            try:
                existing = await repository.get_video_by_youtube_id(youtube_id)
                video_id = int(existing["id"])
                skipped = True
            except Exception:
                pass

        if not skipped:
            job.update_progress(2, 3, "Creating video record...")
            video_id = await repository.create_video(
                title=(getattr(info, "title", None) or youtube_id or "YouTube Video"),
                artist=getattr(info, "channel", None),
                youtube_id=youtube_id,
                download_source="youtube",
                status=initial_status,
            )
            created = True

    else:
        raise ValueError(f"Unsupported source: {source}")

    if job.status == JobStatus.CANCELLED:
        return

    job.update_progress(3, 3, "Import complete")

    # If youtube_id exists and video was created, queue download job
    download_job_id: str | None = None
    if created and youtube_id:
        logger.info(
            "queueing_download_job",
            job_id=job.id,
            video_id=video_id,
            youtube_id=youtube_id,
        )

        # Update video status to pending_download
        await repository.update_video(video_id, status="pending_download")

        # Queue download job with parent relationship
        queue = get_job_queue()
        download_job = Job(
            type=JobType.IMPORT_DOWNLOAD,
            metadata={
                "video_id": video_id,
                "youtube_id": youtube_id,
            },
            parent_job_id=job.id,
        )
        await queue.submit(download_job)
        download_job_id = download_job.id
    elif created and not youtube_id:
        # No YouTube ID, mark as discovered for manual download later
        await repository.update_video(video_id, status="discovered")

    job.mark_completed(
        {
            "created": created,
            "skipped": skipped,
            "video_id": video_id,
            "source": source,
            "id": item_id,
            "imvdb_video_id": imvdb_video_id,
            "youtube_id": youtube_id,
            "initial_status": initial_status,
            "download_job_id": download_job_id,
        }
    )

    logger.info(
        "add_single_import_job_completed",
        job_id=job.id,
        source=source,
        item_id=item_id,
        created=created,
        skipped=skipped,
        video_id=video_id,
        download_job_queued=download_job_id is not None,
    )


async def handle_import_download(job: Job) -> None:
    """Handle video download job for imported videos.

    Downloads video from YouTube using yt-dlp to a temporary location,
    updates video status, then queues organize job.

    Job metadata parameters:
        video_id (int, required): Video database ID
        youtube_id (str, required): YouTube video ID to download

    Job result on completion:
        video_id: Database video ID
        youtube_id: YouTube video ID
        temp_path: Temporary file path where video was downloaded
        file_size: Downloaded file size in bytes

    Args:
        job: Job instance with metadata containing download parameters

    Raises:
        ValueError: If required parameters missing
        YTDLPError: If download fails
    """
    video_id = job.metadata.get("video_id")
    youtube_id = job.metadata.get("youtube_id")

    if not video_id or not youtube_id:
        raise ValueError("Missing required parameters: video_id, youtube_id")

    logger.info(
        "import_download_job_starting",
        job_id=job.id,
        video_id=video_id,
        youtube_id=youtube_id,
    )

    import fuzzbin
    from fuzzbin.clients.ytdlp_client import YTDLPClient
    from fuzzbin.common.config import YTDLPConfig
    from fuzzbin.core.exceptions import YTDLPError

    job.update_progress(0, 3, "Initializing download...")

    repository = await fuzzbin.get_repository()
    config = fuzzbin.get_config()
    ytdlp_config = config.ytdlp or YTDLPConfig()

    # Check for cancellation
    if job.status == JobStatus.CANCELLED:
        return

    # Update video status to downloading
    await repository.update_video(video_id, status="downloading")

    # Create temp directory for download
    import tempfile

    temp_dir = Path(tempfile.mkdtemp(prefix="fuzzbin_download_"))
    temp_file = temp_dir / f"{youtube_id}.mp4"

    try:
        job.update_progress(1, 3, f"Downloading video {youtube_id}...")

        async with YTDLPClient.from_config(ytdlp_config) as client:
            result = await client.download(
                url=f"https://www.youtube.com/watch?v={youtube_id}",
                output_path=temp_file,
            )

        if job.status == JobStatus.CANCELLED:
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()
            return

        # Update video status to downloaded
        await repository.update_video(video_id, status="downloaded")

        job.update_progress(2, 3, "Queuing organize job...")

        # Queue organize job with parent relationship
        queue = get_job_queue()
        organize_job = Job(
            type=JobType.IMPORT_ORGANIZE,
            metadata={
                "video_id": video_id,
                "temp_path": str(temp_file),
            },
            parent_job_id=job.id,
        )
        await queue.submit(organize_job)

        job.update_progress(3, 3, "Download complete")
        job.mark_completed(
            {
                "video_id": video_id,
                "youtube_id": youtube_id,
                "temp_path": str(temp_file),
                "file_size": result.file_size,
                "organize_job_id": organize_job.id,
            }
        )

        logger.info(
            "import_download_job_completed",
            job_id=job.id,
            video_id=video_id,
            file_size=result.file_size,
        )

    except (YTDLPError, Exception) as e:
        # Clean up temp file on error
        if temp_file.exists():
            temp_file.unlink()
        if temp_dir.exists():
            temp_dir.rmdir()

        # Update video status to download_failed
        await repository.update_video(video_id, status="download_failed")

        # Extract stderr if it's a YTDLPExecutionError
        error_details = {"error": str(e)}
        if hasattr(e, "stderr") and e.stderr:
            error_details["stderr"] = e.stderr[:1000]  # First 1000 chars
        if hasattr(e, "returncode"):
            error_details["returncode"] = e.returncode

        logger.error(
            "import_download_job_failed",
            job_id=job.id,
            video_id=video_id,
            **error_details,
        )
        raise


async def handle_import_organize(job: Job) -> None:
    """Handle video file organization for imported videos.

    Moves video from temp location to final organized path using configured
    pattern, updates database, then queues NFO generation job.

    Job metadata parameters:
        video_id (int, required): Video database ID
        temp_path (str, required): Temporary file path from download

    Job result on completion:
        video_id: Database video ID
        video_path: Final organized video file path
        nfo_path: Path where NFO file will be created

    Args:
        job: Job instance with metadata containing organize parameters

    Raises:
        ValueError: If required parameters missing or video not found
        FileNotFoundError: If temp file doesn't exist
    """
    video_id = job.metadata.get("video_id")
    temp_path_str = job.metadata.get("temp_path")

    if not video_id or not temp_path_str:
        raise ValueError("Missing required parameters: video_id, temp_path")

    temp_path = Path(temp_path_str)
    if not temp_path.exists():
        raise FileNotFoundError(f"Temp file not found: {temp_path}")

    logger.info(
        "import_organize_job_starting",
        job_id=job.id,
        video_id=video_id,
        temp_path=temp_path_str,
    )

    import fuzzbin
    from fuzzbin.core.organizer import build_media_paths
    from fuzzbin.parsers.models import MusicVideoNFO
    import shutil

    job.update_progress(0, 4, "Initializing organization...")

    repository = await fuzzbin.get_repository()
    config = fuzzbin.get_config()

    # Check for cancellation
    if job.status == JobStatus.CANCELLED:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()
            temp_path.parent.rmdir()
        return

    # Get video record
    video = await repository.get_video_by_id(video_id)

    # Update status to organizing
    await repository.update_video(video_id, status="organizing")

    try:
        job.update_progress(1, 4, "Building target paths...")

        # Build NFO data from video metadata
        nfo_data = MusicVideoNFO(
            title=video["title"],
            artist=video.get("artist"),
            album=video.get("album"),
            year=video.get("year"),
            director=video.get("director"),
            genre=video.get("genre"),
            studio=video.get("studio"),
        )

        # Build target paths using organizer config
        # Get library_dir from config (falls back to default if not set)
        library_dir = config.library_dir
        if library_dir is None:
            from fuzzbin.common.config import _get_default_library_dir

            library_dir = _get_default_library_dir()

        media_paths = build_media_paths(
            root_path=library_dir,
            nfo_data=nfo_data,
            config=config.organizer,
        )

        job.update_progress(2, 4, "Moving file to organized location...")

        # Create parent directory if needed
        media_paths.video_path.parent.mkdir(parents=True, exist_ok=True)

        # Move file from temp to final location
        shutil.move(str(temp_path), str(media_paths.video_path))

        # Clean up temp directory
        if temp_path.parent.exists():
            temp_path.parent.rmdir()

        # Update video record with file paths
        await repository.update_video(
            video_id,
            video_file_path=str(media_paths.video_path),
            nfo_file_path=str(media_paths.nfo_path),
            status="organized",
        )

        if job.status == JobStatus.CANCELLED:
            return

        job.update_progress(3, 4, "Queuing NFO generation job...")

        # Queue NFO generation job with parent relationship
        queue = get_job_queue()
        nfo_job = Job(
            type=JobType.IMPORT_NFO_GENERATE,
            metadata={
                "video_id": video_id,
            },
            parent_job_id=job.id,
        )
        await queue.submit(nfo_job)

        job.update_progress(4, 4, "Organization complete")
        job.mark_completed(
            {
                "video_id": video_id,
                "video_path": str(media_paths.video_path),
                "nfo_path": str(media_paths.nfo_path),
                "nfo_job_id": nfo_job.id,
            }
        )

        logger.info(
            "import_organize_job_completed",
            job_id=job.id,
            video_id=video_id,
            video_path=str(media_paths.video_path),
        )

    except Exception as e:
        # Clean up temp file on error
        if temp_path.exists():
            temp_path.unlink()
            if temp_path.parent.exists():
                temp_path.parent.rmdir()

        # Update video status to download_failed (allow retry)
        await repository.update_video(video_id, status="download_failed")

        logger.error(
            "import_organize_job_failed",
            job_id=job.id,
            video_id=video_id,
            error=str(e),
        )
        raise


async def handle_import_nfo_generate(job: Job) -> None:
    """Handle NFO file generation for imported videos.

    Generates musicvideo.nfo file at the configured location and updates
    video status to complete.

    Job metadata parameters:
        video_id (int, required): Video database ID

    Job result on completion:
        video_id: Database video ID
        nfo_path: Path to generated NFO file

    Args:
        job: Job instance with metadata containing NFO parameters

    Raises:
        ValueError: If required parameters missing or video not found
    """
    video_id = job.metadata.get("video_id")

    if not video_id:
        raise ValueError("Missing required parameter: video_id")

    logger.info(
        "import_nfo_generate_job_starting",
        job_id=job.id,
        video_id=video_id,
    )

    import fuzzbin
    from fuzzbin.core.db.exporter import NFOExporter

    job.update_progress(0, 2, "Initializing NFO generation...")

    repository = await fuzzbin.get_repository()

    # Check for cancellation
    if job.status == JobStatus.CANCELLED:
        return

    job.update_progress(1, 2, "Generating NFO file...")

    # Create NFO exporter and export
    exporter = NFOExporter(repository)
    nfo_path = await exporter.export_video_to_nfo(video_id)

    # Update video status to complete
    await repository.update_video(video_id, status="complete")

    job.update_progress(2, 2, "NFO generation complete")
    job.mark_completed(
        {
            "video_id": video_id,
            "nfo_path": str(nfo_path),
        }
    )

    logger.info(
        "import_nfo_generate_job_completed",
        job_id=job.id,
        video_id=video_id,
        nfo_path=str(nfo_path),
    )


async def handle_backup(job: Job) -> None:
    """Handle system backup job.

    Creates a complete backup of config, database, and thumbnails.

    Job metadata parameters:
        description (str, optional): Description for the backup
        retention_count (int, optional): Override retention count for cleanup

    Job result on completion:
        filename: Name of the backup file
        path: Full path to backup file
        size_bytes: Size of backup in bytes
        created_at: ISO timestamp of creation
        contains: List of items included (config, database, thumbnails)
        deleted_backups: List of old backups deleted during cleanup

    Args:
        job: Job instance with metadata containing backup parameters
    """
    import fuzzbin
    from fuzzbin.services.backup_service import BackupService

    logger.info("backup_job_starting", job_id=job.id)
    job.update_progress(0, 3, "Initializing backup...")

    # Check for cancellation
    if job.status == JobStatus.CANCELLED:
        return

    # Get config and create backup service
    config = fuzzbin.get_config()
    backup_service = BackupService(config)

    # Extract parameters
    description = job.metadata.get("description")
    retention_count = job.metadata.get("retention_count", config.backup.retention_count)

    job.update_progress(1, 3, "Creating backup archive...")

    # Create backup
    backup_info = await backup_service.create_backup(description=description)

    if job.status == JobStatus.CANCELLED:
        return

    job.update_progress(2, 3, "Cleaning up old backups...")

    # Cleanup old backups
    deleted_backups = backup_service.cleanup_old_backups(retention_count)

    job.update_progress(3, 3, "Backup complete")

    # Mark completed with result
    job.mark_completed(
        {
            "filename": backup_info["filename"],
            "path": backup_info["path"],
            "size_bytes": backup_info["size_bytes"],
            "created_at": backup_info["created_at"],
            "contains": backup_info["contains"],
            "deleted_backups": deleted_backups,
        }
    )

    logger.info(
        "backup_job_completed",
        job_id=job.id,
        filename=backup_info["filename"],
        size_bytes=backup_info["size_bytes"],
        deleted_count=len(deleted_backups),
    )


def register_all_handlers(queue: JobQueue) -> None:
    """Register all job handlers with the queue.

    This should be called during application startup after the queue is created.

    Args:
        queue: JobQueue instance to register handlers with
    """
    queue.register_handler(JobType.IMPORT_NFO, handle_nfo_import)
    queue.register_handler(JobType.IMPORT_SPOTIFY, handle_spotify_import)
    queue.register_handler(JobType.DOWNLOAD_YOUTUBE, handle_youtube_download)
    queue.register_handler(JobType.FILE_ORGANIZE, handle_file_organize)
    queue.register_handler(JobType.FILE_DUPLICATE_RESOLVE, handle_duplicate_resolution)
    queue.register_handler(JobType.METADATA_ENRICH, handle_metadata_enrich)
    # Phase 7: Scheduled task handlers
    queue.register_handler(JobType.METADATA_REFRESH, handle_metadata_refresh)
    queue.register_handler(JobType.LIBRARY_SCAN, handle_library_scan)
    queue.register_handler(JobType.IMPORT, handle_import)
    queue.register_handler(JobType.IMPORT_ADD_SINGLE, handle_add_single_import)
    # Import workflow handlers
    queue.register_handler(JobType.IMPORT_DOWNLOAD, handle_import_download)
    queue.register_handler(JobType.IMPORT_ORGANIZE, handle_import_organize)
    queue.register_handler(JobType.IMPORT_NFO_GENERATE, handle_import_nfo_generate)
    queue.register_handler(JobType.BACKUP, handle_backup)

    logger.info(
        "job_handlers_registered",
        handlers=[
            JobType.IMPORT_NFO.value,
            JobType.IMPORT_SPOTIFY.value,
            JobType.IMPORT_ADD_SINGLE.value,
            JobType.DOWNLOAD_YOUTUBE.value,
            JobType.FILE_ORGANIZE.value,
            JobType.FILE_DUPLICATE_RESOLVE.value,
            JobType.METADATA_ENRICH.value,
            JobType.METADATA_REFRESH.value,
            JobType.LIBRARY_SCAN.value,
            JobType.IMPORT.value,
            JobType.IMPORT_DOWNLOAD.value,
            JobType.IMPORT_ORGANIZE.value,
            JobType.IMPORT_NFO_GENERATE.value,
            JobType.BACKUP.value,
        ],
    )
