"""Import hub routes.

This router provides a UI-focused namespace under /add that composes existing
capabilities (Spotify endpoints, scan preview/import, background jobs).

Initial implementation is intentionally small:
- POST /add/preview-batch: preview Spotify playlist or NFO directory import
- POST /add/spotify: submit a Spotify import job
- POST /add/nfo-scan: submit an NFO scan/import job (alias of /scan)

Single-video search/preview/import will be added in later iterations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

import fuzzbin as fuzzbin_module
from fuzzbin.api.spotify_client import SpotifyClient
from fuzzbin.auth.schemas import UserInfo
from fuzzbin.tasks import Job, JobType, get_job_queue
from fuzzbin.web.dependencies import get_current_user
from fuzzbin.web.schemas.add import (
    BatchPreviewItem,
    BatchPreviewRequest,
    BatchPreviewResponse,
    NFOScanResponse,
    SpotifyImportRequest,
    SpotifyImportResponse,
    normalize_spotify_playlist_id,
)
from fuzzbin.web.schemas.common import AUTH_ERROR_RESPONSES, COMMON_ERROR_RESPONSES
from fuzzbin.web.schemas.scan import ImportMode, ScanJobResponse, ScanRequest

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/add", tags=["Add"])


@router.post(
    "/preview-batch",
    response_model=BatchPreviewResponse,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Preview a batch import",
    description="Preview what would be imported for Spotify playlists or NFO directory scans.",
)
async def preview_batch(
    request: BatchPreviewRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> BatchPreviewResponse:
    """Preview batch imports (Spotify playlist or NFO directory)."""

    user_label = current_user.username if current_user else "anonymous"

    if request.mode.value == "nfo":
        directory = Path(request.nfo_directory or "")
        if not directory.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Directory does not exist: {request.nfo_directory}",
            )
        if not directory.is_dir():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Path is not a directory: {request.nfo_directory}",
            )

        logger.info(
            "add_preview_batch_nfo_start",
            directory=str(directory),
            recursive=request.recursive,
            skip_existing=request.skip_existing,
            user=user_label,
        )

        # Reuse the existing scan preview implementation by calling the same logic via its schema.
        # We use discovery mode for preview semantics; it doesn't affect preview behavior.
        from fuzzbin.web.routes.scan import preview_scan

        scan_preview = await preview_scan(
            ScanRequest(
                directory=str(directory),
                mode=ImportMode.DISCOVERY,
                recursive=request.recursive,
                skip_existing=request.skip_existing,
            ),
            current_user=current_user,
        )

        items = [
            BatchPreviewItem(
                kind="nfo",
                title=i.title,
                artist=i.artist,
                album=i.album,
                year=i.year,
                already_exists=i.already_exists,
                nfo_path=i.nfo_path,
            )
            for i in scan_preview.items
        ]

        existing_count = scan_preview.would_skip
        new_count = scan_preview.would_import

        return BatchPreviewResponse(
            mode=request.mode,
            items=items,
            total_count=scan_preview.musicvideo_nfos,
            existing_count=existing_count,
            new_count=new_count,
            directory=scan_preview.directory,
        )

    # spotify
    playlist_id = normalize_spotify_playlist_id(request.spotify_playlist_id or "")
    if not playlist_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="spotify_playlist_id is required when mode=spotify",
        )

    logger.info(
        "add_preview_batch_spotify_start",
        playlist_id=playlist_id,
        skip_existing=request.skip_existing,
        user=user_label,
    )

    config = fuzzbin_module.get_config()
    api_config = (config.apis or {}).get("spotify")
    if not api_config:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Spotify API is not configured",
        )

    try:
        async with SpotifyClient.from_config(api_config) as spotify_client:
            playlist = await spotify_client.get_playlist(playlist_id)
            tracks = await spotify_client.get_all_playlist_tracks(playlist_id)
    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        if "404" in error_message or "not found" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Playlist not found: {playlist_id}",
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch playlist from Spotify: {error_message}",
        )

    repository = await fuzzbin_module.get_repository()

    total_count = len(tracks)
    existing_count = 0
    new_count = 0
    items: list[BatchPreviewItem] = []

    for idx, track in enumerate(tracks):
        title = (track.name or "").strip()
        primary_artist = (track.artists[0].name if track.artists else "").strip()
        album = (track.album.name if track.album else None)

        year: Optional[int] = None
        if track.album and track.album.release_date:
            # release_date can be YYYY or YYYY-MM-DD
            try:
                year = int(track.album.release_date.split("-")[0])
            except Exception:
                year = None

        already_exists = False
        if title and primary_artist:
            query = repository.query().where_title(title).where_artist(primary_artist)
            results = await query.execute()
            already_exists = len(results) > 0

        if already_exists:
            existing_count += 1
        else:
            new_count += 1

        # Limit returned items to first 100 to keep response lightweight
        if idx < 100:
            items.append(
                BatchPreviewItem(
                    kind="spotify_track",
                    title=title or track.id,
                    artist=primary_artist or "Unknown",
                    album=album,
                    year=year,
                    already_exists=already_exists,
                    spotify_track_id=track.id,
                    spotify_playlist_id=playlist_id,
                )
            )

    logger.info(
        "add_preview_batch_spotify_complete",
        playlist_id=playlist_id,
        total_count=total_count,
        existing_count=existing_count,
        new_count=new_count,
    )

    return BatchPreviewResponse(
        mode=request.mode,
        items=items,
        total_count=total_count,
        existing_count=existing_count,
        new_count=new_count,
        playlist_name=getattr(playlist, "name", None),
        extra={"playlist_uri": getattr(playlist, "uri", None)},
    )


@router.post(
    "/spotify",
    response_model=SpotifyImportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Submit a Spotify playlist import job",
    description="Submit a background job that imports playlist tracks into the DB.",
)
async def submit_spotify_import(
    request: SpotifyImportRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> SpotifyImportResponse:
    playlist_id = normalize_spotify_playlist_id(request.playlist_id)
    if not playlist_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="playlist_id is required",
        )

    logger.info(
        "add_spotify_import_job_submitting",
        playlist_id=playlist_id,
        skip_existing=request.skip_existing,
        initial_status=request.initial_status,
        user=current_user.username if current_user else "anonymous",
    )

    job = Job(
        type=JobType.IMPORT_SPOTIFY,
        metadata={
            "playlist_id": playlist_id,
            "skip_existing": request.skip_existing,
            "initial_status": request.initial_status,
        },
    )

    queue = get_job_queue()
    await queue.submit(job)

    return SpotifyImportResponse(job_id=job.id, playlist_id=playlist_id)


@router.post(
    "/nfo-scan",
    response_model=NFOScanResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Submit an NFO directory scan/import job",
    description="Alias of POST /scan for UI cohesion under /add.",
)
async def submit_nfo_scan(
    request: ScanRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> NFOScanResponse:
    # Delegate to the existing scan job submission to keep behavior identical.
    from fuzzbin.web.routes.scan import start_scan

    response: ScanJobResponse = await start_scan(request, current_user=current_user)

    return NFOScanResponse(
        job_id=response.job_id,
        directory=response.directory,
        mode=response.mode.value,
        initial_status=response.initial_status,
    )
