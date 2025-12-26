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
from fuzzbin.api.discogs_client import DiscogsClient
from fuzzbin.api.imvdb_client import IMVDbClient
from fuzzbin.api.spotify_client import SpotifyClient
from fuzzbin.auth.schemas import UserInfo
from fuzzbin.clients.ytdlp_client import YTDLPClient
from fuzzbin.common.config import YTDLPConfig
from fuzzbin.tasks import Job, JobType, get_job_queue
from fuzzbin.web.dependencies import get_current_user
from fuzzbin.web.schemas.add import (
    AddPreviewResponse,
    AddSingleImportRequest,
    AddSingleImportResponse,
    AddSearchRequest,
    AddSearchResponse,
    AddSearchResultItem,
    AddSearchSkippedSource,
    AddSearchSource,
    BatchPreviewItem,
    BatchPreviewRequest,
    BatchPreviewResponse,
    NFOScanResponse,
    SpotifyImportRequest,
    SpotifyImportResponse,
    normalize_spotify_playlist_id,
)
from fuzzbin.web.schemas.common import AUTH_ERROR_RESPONSES, COMMON_ERROR_RESPONSES
from fuzzbin.web.schemas.imvdb import IMVDbVideoDetail
from fuzzbin.web.schemas.scan import ImportMode, ScanJobResponse, ScanRequest
from fuzzbin.web.schemas.ytdlp import YTDLPVideoInfo, YTDLPVideoInfoResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/add", tags=["Add"])


def _get_api_config(service: str):
    config = fuzzbin_module.get_config()
    apis = config.apis or {}
    return apis.get(service)


def _get_ytdlp_config() -> YTDLPConfig:
    config = fuzzbin_module.get_config()
    return config.ytdlp or YTDLPConfig()


def _safe_int(value: object) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(str(value))
    except Exception:
        return None


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
        album = track.album.name if track.album else None

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


@router.post(
    "/search",
    response_model=AddSearchResponse,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Search for a single video across sources",
    description="Aggregates IMVDb, Discogs, and YouTube (yt-dlp) search results into a single UI-friendly list.",
)
async def search_single_video(
    request: AddSearchRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> AddSearchResponse:
    sources = request.include_sources or [
        AddSearchSource.IMVDB,
        AddSearchSource.DISCOGS_MASTER,
        AddSearchSource.DISCOGS_RELEASE,
        AddSearchSource.YOUTUBE,
    ]

    want_imvdb = AddSearchSource.IMVDB in sources
    want_discogs = any(
        s in (AddSearchSource.DISCOGS_MASTER, AddSearchSource.DISCOGS_RELEASE) for s in sources
    )
    want_youtube = AddSearchSource.YOUTUBE in sources

    user_label = current_user.username if current_user else "anonymous"
    logger.info(
        "add_search_start",
        artist=request.artist,
        track_title=request.track_title,
        sources=[s.value for s in sources],
        user=user_label,
    )

    results: list[AddSearchResultItem] = []
    skipped: list[AddSearchSkippedSource] = []
    counts: dict[str, int] = {}

    if want_imvdb:
        api_config = _get_api_config("imvdb")
        if not api_config:
            logger.info(
                "add_search_source_skipped",
                source=AddSearchSource.IMVDB.value,
                reason="IMVDb API is not configured",
                user=user_label,
            )
            skipped.append(
                AddSearchSkippedSource(
                    source=AddSearchSource.IMVDB,
                    reason="IMVDb API is not configured",
                )
            )
        else:
            try:
                async with IMVDbClient.from_config(api_config) as imvdb_client:
                    imvdb_result = await imvdb_client.search_videos(
                        artist=request.artist,
                        track_title=request.track_title,
                        page=1,
                        per_page=request.imvdb_per_page,
                    )

                imvdb_items: list[AddSearchResultItem] = []
                for v in imvdb_result.results:
                    primary_artist = None
                    if getattr(v, "artists", None):
                        primary_artist = getattr(v.artists[0], "name", None)

                    thumb = None
                    image = getattr(v, "image", None)
                    if isinstance(image, dict):
                        thumb = image.get("o") or image.get("l") or image.get("b")

                    imvdb_items.append(
                        AddSearchResultItem(
                            source=AddSearchSource.IMVDB,
                            id=str(v.id),
                            title=(getattr(v, "song_title", None) or str(v.id)),
                            artist=primary_artist,
                            year=getattr(v, "year", None),
                            url=getattr(v, "url", None),
                            thumbnail=thumb,
                            extra={
                                "multiple_versions": getattr(v, "multiple_versions", None),
                                "version_name": getattr(v, "version_name", None),
                            },
                        )
                    )

                counts[AddSearchSource.IMVDB.value] = len(imvdb_items)
                results.extend(imvdb_items)
            except Exception as e:
                logger.warning(
                    "add_search_source_failed",
                    source=AddSearchSource.IMVDB.value,
                    error=str(e),
                    user=user_label,
                )
                skipped.append(
                    AddSearchSkippedSource(
                        source=AddSearchSource.IMVDB,
                        reason=f"IMVDb search failed: {e}",
                    )
                )

    if want_discogs:
        api_config = _get_api_config("discogs")
        if not api_config:
            logger.info(
                "add_search_source_skipped",
                source="discogs",
                reason="Discogs API is not configured",
                user=user_label,
            )
            skipped.append(
                AddSearchSkippedSource(
                    source=AddSearchSource.DISCOGS_MASTER,
                    reason="Discogs API is not configured",
                )
            )
            skipped.append(
                AddSearchSkippedSource(
                    source=AddSearchSource.DISCOGS_RELEASE,
                    reason="Discogs API is not configured",
                )
            )
        else:
            try:
                async with DiscogsClient.from_config(api_config) as discogs_client:
                    discogs_result = await discogs_client.search(
                        artist=request.artist,
                        track=request.track_title,
                        page=1,
                        per_page=request.discogs_per_page,
                    )

                discogs_master_items: list[AddSearchResultItem] = []
                discogs_release_items: list[AddSearchResultItem] = []

                for r in discogs_result.get("results", []):
                    r_type = r.get("type")
                    if r_type not in ("master", "release"):
                        continue

                    source = (
                        AddSearchSource.DISCOGS_MASTER
                        if r_type == "master"
                        else AddSearchSource.DISCOGS_RELEASE
                    )

                    if source not in sources:
                        continue

                    # Filter master releases: require community engagement (want > 0 and have > 0)
                    if r_type == "master":
                        community = r.get("community", {})
                        want = community.get("want", 0)
                        have = community.get("have", 0)
                        if want == 0 or have == 0:
                            continue

                    title = r.get("title") or ""
                    artist = None
                    if " - " in title:
                        artist = title.split(" - ", 1)[0].strip() or None

                    year = _safe_int(r.get("year"))

                    item = AddSearchResultItem(
                        source=source,
                        id=str(r.get("id")),
                        title=title or str(r.get("id")),
                        artist=artist,
                        year=year,
                        url=r.get("uri"),
                        thumbnail=r.get("thumb") or r.get("cover_image"),
                        extra={
                            "format": r.get("format", []),
                            "label": r.get("label", []),
                            "genre": r.get("genre", []),
                            "style": r.get("style", []),
                            "country": r.get("country"),
                        },
                    )

                    if source == AddSearchSource.DISCOGS_MASTER:
                        discogs_master_items.append(item)
                    else:
                        discogs_release_items.append(item)

                counts[AddSearchSource.DISCOGS_MASTER.value] = len(discogs_master_items)
                counts[AddSearchSource.DISCOGS_RELEASE.value] = len(discogs_release_items)
                results.extend(discogs_master_items)
                results.extend(discogs_release_items)
            except Exception as e:
                logger.warning(
                    "add_search_source_failed",
                    source="discogs",
                    error=str(e),
                    user=user_label,
                )
                skipped.append(
                    AddSearchSkippedSource(
                        source=AddSearchSource.DISCOGS_MASTER,
                        reason=f"Discogs search failed: {e}",
                    )
                )
                skipped.append(
                    AddSearchSkippedSource(
                        source=AddSearchSource.DISCOGS_RELEASE,
                        reason=f"Discogs search failed: {e}",
                    )
                )

    if want_youtube:
        try:
            ytdlp_config = _get_ytdlp_config()
            async with YTDLPClient.from_config(ytdlp_config) as ytdlp_client:
                yt_results = await ytdlp_client.search(
                    artist=request.artist,
                    track_title=request.track_title,
                    max_results=request.youtube_max_results,
                )

            yt_items = [
                AddSearchResultItem(
                    source=AddSearchSource.YOUTUBE,
                    id=str(r.id),
                    title=r.title,
                    artist=None,
                    year=None,
                    url=r.url,
                    thumbnail=getattr(r, "thumbnail", None),
                    extra={
                        "channel": getattr(r, "channel", None),
                        "duration": getattr(r, "duration", None),
                        "view_count": getattr(r, "view_count", None),
                    },
                )
                for r in yt_results
            ]

            counts[AddSearchSource.YOUTUBE.value] = len(yt_items)
            results.extend(yt_items)
        except Exception as e:
            skipped.append(
                AddSearchSkippedSource(
                    source=AddSearchSource.YOUTUBE,
                    reason=f"YouTube search failed: {e}",
                )
            )

    logger.info(
        "add_search_complete",
        artist=request.artist,
        track_title=request.track_title,
        total_results=len(results),
        skipped=len(skipped),
        counts=counts,
        skipped_sources=[{"source": s.source.value, "reason": s.reason} for s in skipped],
    )

    return AddSearchResponse(
        artist=request.artist,
        track_title=request.track_title,
        results=results,
        skipped=skipped,
        counts=counts,
    )


@router.get(
    "/preview/{source}/{item_id}",
    response_model=AddPreviewResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        400: COMMON_ERROR_RESPONSES[400],
        404: COMMON_ERROR_RESPONSES[404],
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Preview a selected search result",
    description="Fetches a detail payload suitable for a UI preview for one of the supported sources.",
)
async def preview_single_video(
    source: AddSearchSource,
    item_id: str,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> AddPreviewResponse:
    user_label = current_user.username if current_user else "anonymous"
    logger.info(
        "add_preview_start",
        source=source.value,
        item_id=item_id,
        user=user_label,
    )

    if source == AddSearchSource.IMVDB:
        api_config = _get_api_config("imvdb")
        if not api_config:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="IMVDb API is not configured",
            )

        try:
            video_id = int(item_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid IMVDb video id: {item_id}",
            )

        async with IMVDbClient.from_config(api_config) as imvdb_client:
            video = await imvdb_client.get_video(video_id)

        data_model = IMVDbVideoDetail(
            id=video.id,
            production_status=video.production_status,
            song_title=video.song_title,
            song_slug=video.song_slug,
            url=video.url,
            multiple_versions=video.multiple_versions,
            version_name=video.version_name,
            version_number=video.version_number,
            is_imvdb_pick=video.is_imvdb_pick,
            aspect_ratio=video.aspect_ratio,
            year=video.year,
            verified_credits=video.verified_credits,
            artists=[
                {"name": a.name, "slug": getattr(a, "slug", None), "url": getattr(a, "url", None)}
                for a in (video.artists or [])
            ],
            featured_artists=[
                {"name": a.name, "slug": getattr(a, "slug", None), "url": getattr(a, "url", None)}
                for a in (getattr(video, "featured_artists", None) or [])
            ],
            image=video.image,
            sources=[
                {
                    "source": s.source,
                    "source_slug": s.source_slug,
                    "source_data": s.source_data,
                    "is_primary": s.is_primary,
                }
                for s in (video.sources or [])
            ],
            directors=[
                {
                    "position_name": d.position_name,
                    "position_code": d.position_code,
                    "entity_name": d.entity_name,
                    "entity_slug": d.entity_slug,
                    "entity_id": d.entity_id,
                    "entity_url": d.entity_url,
                    "position_notes": d.position_notes,
                    "position_id": d.position_id,
                }
                for d in (video.directors or [])
            ],
            credits=video.credits,
        )

        youtube_ids: list[str] = []
        for s in video.sources or []:
            if getattr(s, "source_slug", None) != "youtube":
                continue
            sd = getattr(s, "source_data", None)
            if isinstance(sd, str) and sd:
                youtube_ids.append(sd)
            elif isinstance(sd, dict):
                candidate = sd.get("id") or sd.get("video_id") or sd.get("youtube_id")
                if isinstance(candidate, str) and candidate:
                    youtube_ids.append(candidate)

        # Fetch thumbnail from yt-dlp if we have a YouTube ID
        thumbnail_url: Optional[str] = None
        if youtube_ids:
            try:
                ytdlp_config = _get_ytdlp_config()
                async with YTDLPClient.from_config(ytdlp_config) as ytdlp_client:
                    yt_info = await ytdlp_client.get_video_info(youtube_ids[0])
                    thumbnail_url = getattr(yt_info, "thumbnail", None)
            except Exception as e:
                logger.warning(
                    "add_preview_ytdlp_thumbnail_failed",
                    youtube_id=youtube_ids[0],
                    error=str(e),
                    user=user_label,
                )

        return AddPreviewResponse(
            source=source,
            id=str(video.id),
            data=data_model.model_dump(),
            extra={
                "youtube_ids": list(dict.fromkeys(youtube_ids)),
                "thumbnail": thumbnail_url,
            },
        )

    if source in (AddSearchSource.DISCOGS_MASTER, AddSearchSource.DISCOGS_RELEASE):
        api_config = _get_api_config("discogs")
        if not api_config:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Discogs API is not configured",
            )

        try:
            discogs_id = int(item_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid Discogs id: {item_id}",
            )

        async with DiscogsClient.from_config(api_config) as discogs_client:
            if source == AddSearchSource.DISCOGS_MASTER:
                payload = await discogs_client.get_master(discogs_id)
            else:
                payload = await discogs_client.get_release(discogs_id)

        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected Discogs response shape",
            )

        return AddPreviewResponse(source=source, id=str(discogs_id), data=payload, extra={})

    if source == AddSearchSource.YOUTUBE:
        ytdlp_config = _get_ytdlp_config()
        async with YTDLPClient.from_config(ytdlp_config) as ytdlp_client:
            yt = await ytdlp_client.get_video_info(item_id)

        video_info = YTDLPVideoInfo(
            id=yt.id,
            title=yt.title,
            url=yt.url,
            channel=getattr(yt, "channel", None),
            channel_follower_count=getattr(yt, "channel_follower_count", None),
            view_count=getattr(yt, "view_count", None),
            duration=getattr(yt, "duration", None),
        )

        data = YTDLPVideoInfoResponse(video=video_info).model_dump()
        return AddPreviewResponse(
            source=source,
            id=str(video_info.id),
            data=data,
            extra={"thumbnail": getattr(yt, "thumbnail", None)},
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported source: {source}",
    )


@router.post(
    "/import",
    response_model=AddSingleImportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Submit a single-video import job",
    description="Creates/updates a video record based on a selected search result (IMVDb/Discogs/YouTube).",
)
async def submit_single_import(
    request: AddSingleImportRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> AddSingleImportResponse:
    logger.info(
        "add_single_import_job_submitting",
        source=request.source.value,
        item_id=request.id,
        skip_existing=request.skip_existing,
        initial_status=request.initial_status,
        user=current_user.username if current_user else "anonymous",
    )

    job = Job(
        type=JobType.IMPORT_ADD_SINGLE,
        metadata={
            "source": request.source.value,
            "id": request.id,
            "youtube_id": request.youtube_id,
            "youtube_url": request.youtube_url,
            "skip_existing": request.skip_existing,
            "initial_status": request.initial_status,
        },
    )

    queue = get_job_queue()
    await queue.submit(job)

    return AddSingleImportResponse(job_id=job.id, source=request.source, id=request.id)
