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
from typing import Annotated, Any, Optional
from contextlib import nullcontext

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

import fuzzbin as fuzzbin_module
from fuzzbin.api.discogs_client import DiscogsClient
from fuzzbin.api.imvdb_client import IMVDbClient
from fuzzbin.api.spotify_client import SpotifyClient
from fuzzbin.auth.schemas import UserInfo
from fuzzbin.clients.ytdlp_client import YTDLPClient
from fuzzbin.common.config import YTDLPConfig
from fuzzbin.common.string_utils import normalize_spotify_title
from fuzzbin.services.musicbrainz_enrichment import MusicBrainzEnrichmentService
from fuzzbin.services.track_enrichment import TrackEnrichmentService
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
    ArtistBatchImportRequest,
    ArtistBatchImportResponse,
    ArtistSearchRequest,
    ArtistSearchResponse,
    ArtistSearchResultItem,
    ArtistVideoEnrichRequest,
    ArtistVideoEnrichResponse,
    ArtistVideoPreviewItem,
    ArtistVideosPreviewResponse,
    BatchPreviewItem,
    BatchPreviewRequest,
    BatchPreviewResponse,
    IMVDbEnrichmentData,
    MusicBrainzEnrichmentData,
    NFOScanResponse,
    SpotifyBatchImportRequest,
    SpotifyBatchImportResponse,
    SpotifyImportRequest,
    SpotifyImportResponse,
    SpotifyTrackEnrichRequest,
    SpotifyTrackEnrichResponse,
    YouTubeMetadataRequest,
    YouTubeMetadataResponse,
    YouTubeSearchRequest,
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

            # Collect unique album IDs to fetch label information
            album_ids = list({track.album.id for track in tracks if track.album})

            # Fetch album details including labels (batched up to 20 per request)
            album_labels: dict[str, Optional[str]] = {}
            if album_ids:
                logger.info(
                    "spotify_fetching_album_labels",
                    playlist_id=playlist_id,
                    unique_albums=len(album_ids),
                )
                albums = await spotify_client.get_albums(album_ids)
                album_labels = {album.id: album.label for album in albums}
                logger.info(
                    "spotify_album_labels_fetched",
                    playlist_id=playlist_id,
                    albums_with_labels=sum(1 for label in album_labels.values() if label),
                )

            # Collect unique primary artist IDs to fetch genre information
            artist_ids = list(
                {track.artists[0].id for track in tracks if track.artists and track.artists[0].id}
            )

            # Fetch artist details including genres (batched up to 50 per request)
            artist_genres: dict[str, list[str]] = {}
            if artist_ids:
                logger.info(
                    "spotify_fetching_artist_genres",
                    playlist_id=playlist_id,
                    unique_artists=len(artist_ids),
                )
                artists = await spotify_client.get_artists(artist_ids)
                artist_genres = {artist.id: artist.genres or [] for artist in artists}
                logger.info(
                    "spotify_artist_genres_fetched",
                    playlist_id=playlist_id,
                    artists_with_genres=sum(1 for genres in artist_genres.values() if genres),
                )

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
        # Get label from album_labels mapping (fetched separately)
        label = album_labels.get(track.album.id) if track.album else None

        year: Optional[int] = None
        if track.album and track.album.release_date:
            # release_date can be YYYY or YYYY-MM-DD
            try:
                year = int(track.album.release_date.split("-")[0])
            except Exception:
                year = None

        already_exists = False
        if title and primary_artist:
            # Normalize titles for duplicate detection
            normalized_title = normalize_spotify_title(
                title,
                remove_version_qualifiers_flag=True,
                remove_featured=True,
            )

            # Query by artist first, then compare normalized titles
            query = repository.query().where_artist(primary_artist)
            results = await query.execute()

            # Check if any result matches normalized title
            for result in results:
                db_title = result.get("title", "")
                db_normalized = normalize_spotify_title(
                    db_title,
                    remove_version_qualifiers_flag=True,
                    remove_featured=True,
                )
                if db_normalized == normalized_title:
                    already_exists = True
                    break

        if already_exists:
            existing_count += 1
        else:
            new_count += 1

        # Limit returned items to first 100 to keep response lightweight
        if idx < 100:
            # Get primary artist ID and genres
            primary_artist_id = track.artists[0].id if track.artists else None
            track_artist_genres = (
                artist_genres.get(primary_artist_id, []) if primary_artist_id else []
            )

            items.append(
                BatchPreviewItem(
                    kind="spotify_track",
                    title=title or track.id,
                    artist=primary_artist or "Unknown",
                    album=album,
                    year=year,
                    label=label,
                    isrc=track.isrc,  # Include ISRC for MusicBrainz lookup
                    already_exists=already_exists,
                    spotify_track_id=track.id,
                    spotify_playlist_id=playlist_id,
                    spotify_artist_id=primary_artist_id,
                    artist_genres=track_artist_genres if track_artist_genres else None,
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


@router.get(
    "/check-exists",
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Check if video already exists in library",
    description="Check if a video with the given IMVDb ID or YouTube ID already exists in the library.",
)
async def check_video_exists(
    imvdb_id: Optional[str] = None,
    youtube_id: Optional[str] = None,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)] = None,
) -> dict[str, Any]:
    """
    Check if a video already exists in the library.

    Returns:
        {"exists": bool, "video_id": int | null, "title": str | null, "artist": str | null}
    """
    repository = await fuzzbin_module.get_repository()

    result = {
        "exists": False,
        "video_id": None,
        "title": None,
        "artist": None,
    }

    try:
        video = None

        if imvdb_id:
            try:
                video = await repository.get_video_by_imvdb_id(imvdb_id, include_deleted=False)
            except Exception:
                pass  # Video not found

        if not video and youtube_id:
            try:
                video = await repository.get_video_by_youtube_id(youtube_id, include_deleted=False)
            except Exception:
                pass  # Video not found

        if video:
            result["exists"] = True
            result["video_id"] = video.get("id")
            result["title"] = video.get("title")
            result["artist"] = video.get("artist")

    except Exception as e:
        logger.error("check_exists_failed", error=str(e))
        # Don't fail the request, just return exists=False

    return result


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
            "auto_download": request.auto_download,
            "prefetched_metadata": request.metadata,
        },
    )

    queue = get_job_queue()
    await queue.submit(job)

    return AddSingleImportResponse(job_id=job.id, source=request.source, id=request.id)


# Enhanced Spotify import endpoints (interactive workflow)


@router.post(
    "/spotify/enrich-track",
    response_model=SpotifyTrackEnrichResponse,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Enrich Spotify track with MusicBrainz and IMVDb metadata",
    description="Unified enrichment using ISRC → MusicBrainz → IMVDb pipeline",
)
async def enrich_spotify_track(
    request: SpotifyTrackEnrichRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> SpotifyTrackEnrichResponse:
    """
    Enrich a single Spotify track with MusicBrainz and IMVDb metadata.

    This endpoint:
    1. Searches MusicBrainz using ISRC (preferred) or artist/title
    2. Extracts canonical metadata, album, label, year, genres from MusicBrainz
    3. Classifies genres from MusicBrainz tags (with Spotify fallback)
    4. Searches IMVDb using canonical artist/title for better matching
    5. Extracts directors, featured artists, YouTube IDs from IMVDb
    6. Checks if track already exists in library

    Returns unified enrichment data with MusicBrainz and IMVDb sections.
    """
    user_label = current_user.username if current_user else "anonymous"
    logger.info(
        "spotify_enrich_track_start",
        artist=request.artist,
        track_title=request.track_title,
        spotify_track_id=request.spotify_track_id,
        has_isrc=bool(request.isrc),
        user=user_label,
    )

    # Get API configs
    musicbrainz_config = _get_api_config("musicbrainz")
    imvdb_config = _get_api_config("imvdb")

    # Initialize services
    try:
        repository = await fuzzbin_module.get_repository()

        # Create MusicBrainz enrichment service
        mb_service = MusicBrainzEnrichmentService(config=musicbrainz_config)

        # Create IMVDb client (will be used in context manager)
        imvdb_client = IMVDbClient.from_config(imvdb_config) if imvdb_config else None

        if not imvdb_client:
            logger.warning(
                "imvdb_not_configured",
                spotify_track_id=request.spotify_track_id,
            )

        # Use async context manager for IMVDb client
        async with imvdb_client if imvdb_client else nullcontext():
            # Create unified enrichment service
            enrichment_service = TrackEnrichmentService(
                repository=repository,
                musicbrainz_service=mb_service,
                imvdb_client=imvdb_client,
            )

            # Perform enrichment
            result = await enrichment_service.enrich(
                artist=request.artist,
                title=request.track_title,
                isrc=request.isrc,
                spotify_artist_genres=request.artist_genres,
            )

            # Check if track already exists (by ISRC, MusicBrainz ID, or IMVDb ID)
            existing_video = None
            existing_video_id = None

            # Try ISRC first
            if request.isrc:
                try:
                    existing_video = await repository.get_video_by_isrc(
                        request.isrc, include_deleted=False
                    )
                    if existing_video:
                        existing_video_id = existing_video.get("id")
                        logger.debug(
                            "found_existing_video_by_isrc",
                            isrc=request.isrc,
                            existing_video_id=existing_video_id,
                        )
                except Exception:
                    pass

            # Try MusicBrainz recording ID
            if not existing_video and result.mb_recording_mbid:
                try:
                    existing_video = await repository.get_video_by_musicbrainz_recording(
                        result.mb_recording_mbid, include_deleted=False
                    )
                    if existing_video:
                        existing_video_id = existing_video.get("id")
                        logger.debug(
                            "found_existing_video_by_mb_recording",
                            recording_mbid=result.mb_recording_mbid,
                            existing_video_id=existing_video_id,
                        )
                except Exception:
                    pass

            # Try IMVDb ID
            if not existing_video and result.imvdb_id:
                try:
                    existing_video = await repository.get_video_by_imvdb_id(
                        str(result.imvdb_id), include_deleted=False
                    )
                    if existing_video:
                        existing_video_id = existing_video.get("id")
                        logger.debug(
                            "found_existing_video_by_imvdb_id",
                            imvdb_id=result.imvdb_id,
                            existing_video_id=existing_video_id,
                        )
                except Exception:
                    pass

            # Try first YouTube ID
            if not existing_video and result.imvdb_youtube_ids:
                try:
                    existing_video = await repository.get_video_by_youtube_id(
                        result.imvdb_youtube_ids[0], include_deleted=False
                    )
                    if existing_video:
                        existing_video_id = existing_video.get("id")
                        logger.debug(
                            "found_existing_video_by_youtube_id",
                            youtube_id=result.imvdb_youtube_ids[0],
                            existing_video_id=existing_video_id,
                        )
                except Exception:
                    pass

            # Build response
            response = SpotifyTrackEnrichResponse(
                spotify_track_id=request.spotify_track_id,
                musicbrainz=MusicBrainzEnrichmentData(
                    recording_mbid=result.mb_recording_mbid,
                    release_mbid=result.mb_release_mbid,
                    canonical_title=result.mb_canonical_title,
                    canonical_artist=result.mb_canonical_artist,
                    album=result.mb_album,
                    year=result.mb_year,
                    label=result.mb_label,
                    genre=result.mb_genre,
                    classified_genre=result.mb_classified_genre,
                    all_genres=result.mb_all_genres,
                    match_score=result.mb_match_score,
                    match_method=result.mb_match_method,
                    confident_match=result.mb_confident_match,
                ),
                imvdb=IMVDbEnrichmentData(
                    imvdb_id=result.imvdb_id,
                    imvdb_url=result.imvdb_url,
                    year=result.imvdb_year,
                    directors=result.imvdb_directors,
                    featured_artists=result.imvdb_featured_artists,
                    youtube_ids=result.imvdb_youtube_ids,
                    thumbnail_url=result.imvdb_thumbnail_url,
                    match_found=result.imvdb_found,
                ),
                title=result.final_title,
                artist=result.final_artist,
                album=result.final_album,
                year=result.final_year,
                label=result.final_label,
                genre=result.final_genre,
                directors=result.imvdb_directors,
                featured_artists=result.imvdb_featured_artists,
                youtube_ids=result.imvdb_youtube_ids,
                thumbnail_url=result.imvdb_thumbnail_url,
                already_exists=existing_video is not None,
                existing_video_id=existing_video_id,
            )

            logger.info(
                "spotify_enrich_track_success",
                spotify_track_id=request.spotify_track_id,
                mb_confident_match=result.mb_confident_match,
                imvdb_found=result.imvdb_found,
                already_exists=response.already_exists,
                user=user_label,
            )

            return response

    except Exception as e:
        logger.error(
            "spotify_enrich_track_failed",
            artist=request.artist,
            track_title=request.track_title,
            error=str(e),
            user=user_label,
            exc_info=True,
        )
        # Return empty enrichment on error
        return SpotifyTrackEnrichResponse(
            spotify_track_id=request.spotify_track_id,
            musicbrainz=MusicBrainzEnrichmentData(),
            imvdb=IMVDbEnrichmentData(),
            title=request.track_title,
            artist=request.artist,
            already_exists=False,
        )


@router.post(
    "/youtube/search",
    response_model=AddSearchResponse,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Search YouTube for videos",
    description="Search YouTube using yt-dlp for video results. Returns results in the same format as /add/search.",
)
async def search_youtube(
    request: YouTubeSearchRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> AddSearchResponse:
    """
    Search YouTube for videos matching artist and track title.

    This is a thin wrapper around the existing YouTube search functionality,
    used when IMVDb doesn't have a match and the user wants to manually select a video.
    """
    user_label = current_user.username if current_user else "anonymous"
    logger.info(
        "youtube_search_start",
        artist=request.artist,
        track_title=request.track_title,
        max_results=request.max_results,
        user=user_label,
    )

    results: list[AddSearchResultItem] = []
    skipped: list[AddSearchSkippedSource] = []

    try:
        ytdlp_config = _get_ytdlp_config()
        async with YTDLPClient.from_config(ytdlp_config) as ytdlp_client:
            yt_results = await ytdlp_client.search(
                artist=request.artist,
                track_title=request.track_title,
                max_results=request.max_results,
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

        results.extend(yt_items)

        logger.info(
            "youtube_search_success",
            result_count=len(yt_items),
            user=user_label,
        )
    except Exception as e:
        logger.warning(
            "youtube_search_failed",
            error=str(e),
            user=user_label,
        )
        skipped.append(
            AddSearchSkippedSource(
                source=AddSearchSource.YOUTUBE,
                reason=f"YouTube search failed: {e}",
            )
        )

    return AddSearchResponse(
        artist=request.artist,
        track_title=request.track_title,
        results=results,
        skipped=skipped,
        counts={AddSearchSource.YOUTUBE.value: len(results)},
    )


@router.post(
    "/spotify/import-selected",
    response_model=SpotifyBatchImportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Import selected tracks from Spotify playlist",
    description="Submit a job to import only the selected tracks from a Spotify playlist with optional metadata overrides and auto-download.",
)
async def import_selected_spotify_tracks(
    request: SpotifyBatchImportRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> SpotifyBatchImportResponse:
    """
    Import selected tracks from a Spotify playlist.

    This endpoint creates a background job that:
    1. Creates/updates video records for each selected track
    2. Applies user metadata overrides
    3. Associates IMVDb IDs and YouTube IDs if provided
    4. Optionally queues download jobs for tracks with YouTube IDs

    This is used by the enhanced Spotify import workflow where users can:
    - Select specific tracks to import
    - Edit metadata before import
    - Choose YouTube videos for each track
    """
    user_label = current_user.username if current_user else "anonymous"

    # Normalize playlist ID
    normalized_playlist_id = normalize_spotify_playlist_id(request.playlist_id)
    if not normalized_playlist_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Spotify playlist ID",
        )

    logger.info(
        "spotify_batch_import_job_submitting",
        playlist_id=normalized_playlist_id,
        track_count=len(request.tracks),
        initial_status=request.initial_status,
        auto_download=request.auto_download,
        user=user_label,
    )

    # Create job
    job = Job(
        type=JobType.IMPORT_SPOTIFY_BATCH,
        metadata={
            "playlist_id": normalized_playlist_id,
            "tracks": [t.model_dump() for t in request.tracks],
            "initial_status": request.initial_status,
            "auto_download": request.auto_download,
        },
    )

    queue = get_job_queue()
    await queue.submit(job)

    return SpotifyBatchImportResponse(
        job_id=job.id,
        playlist_id=normalized_playlist_id,
        track_count=len(request.tracks),
        auto_download=request.auto_download,
    )


@router.post(
    "/youtube/metadata",
    response_model=YouTubeMetadataResponse,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Get YouTube video metadata",
    description="Fetch YouTube video metadata (view count, duration, channel) using yt-dlp.",
)
async def get_youtube_metadata(
    request: YouTubeMetadataRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> YouTubeMetadataResponse:
    """
    Get YouTube video metadata using yt-dlp.

    This endpoint:
    1. Calls yt-dlp to fetch video metadata
    2. Returns view count, duration, and channel name
    3. Handles errors gracefully (e.g., video unavailable)
    """
    user_label = current_user.username if current_user else "anonymous"
    logger.info(
        "youtube_metadata_fetching",
        youtube_id=request.youtube_id,
        user=user_label,
    )

    try:
        # Create YTDLPClient instance
        ytdlp_config = _get_ytdlp_config()
        async with YTDLPClient.from_config(ytdlp_config) as client:
            # Fetch video info
            video_info = await client.get_video_info(request.youtube_id)

            logger.info(
                "youtube_metadata_fetched",
                youtube_id=request.youtube_id,
                view_count=video_info.view_count,
                duration=video_info.duration,
                channel=video_info.channel,
            )

            return YouTubeMetadataResponse(
                youtube_id=request.youtube_id,
                available=True,
                view_count=video_info.view_count,
                duration=video_info.duration,
                channel=video_info.channel,
                title=video_info.title,
                error=None,
            )

    except Exception as e:
        # Handle errors (video unavailable, network errors, etc.)
        error_msg = str(e)
        logger.warning(
            "youtube_metadata_error",
            youtube_id=request.youtube_id,
            error=error_msg,
        )

        return YouTubeMetadataResponse(
            youtube_id=request.youtube_id,
            available=False,
            view_count=None,
            duration=None,
            channel=None,
            title=None,
            error=error_msg,
        )


# ==================== Artist Import Routes ====================


@router.post(
    "/search/artist",
    response_model=ArtistSearchResponse,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Search for artists on IMVDb",
    description="Search for artists by name and return those with videos available.",
)
async def search_artists(
    request: ArtistSearchRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> ArtistSearchResponse:
    """
    Search IMVDb for artists by name.

    Returns artists with artist_video_count > 0 to support the artist import workflow.
    """
    user_label = current_user.username if current_user else "anonymous"
    logger.info(
        "add_artist_search_start",
        artist_name=request.artist_name,
        per_page=request.per_page,
        user=user_label,
    )

    api_config = _get_api_config("imvdb")
    if not api_config:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IMVDb API is not configured",
        )

    try:
        async with IMVDbClient.from_config(api_config) as imvdb_client:
            search_result = await imvdb_client.search_entities(
                artist_name=request.artist_name,
                page=1,
                per_page=request.per_page,
            )

            # Filter to artists with videos (based on initial search result)
            candidates = [e for e in search_result.results if (e.artist_video_count or 0) > 0]

            # Fetch entity details for each candidate to get accurate counts and sample tracks
            results_with_videos = []
            for entity in candidates:
                try:
                    # Fetch first page of entity videos to get accurate count and sample tracks
                    entity_videos = await imvdb_client.get_entity_videos(
                        entity_id=entity.id,
                        page=1,
                        per_page=3,  # Only need first 3 for sample tracks
                    )

                    # Extract sample track titles (first 3)
                    sample_tracks = [
                        video.song_title for video in entity_videos.videos if video.song_title
                    ][:3]

                    # Use entity_name from videos page (which extracts from first video if needed)
                    artist_name = entity_videos.entity_name or entity.name or entity.slug

                    results_with_videos.append(
                        ArtistSearchResultItem(
                            id=entity.id,
                            name=artist_name,
                            slug=entity.slug,
                            url=entity.url,
                            image=entity.image,
                            discogs_id=entity.discogs_id,
                            artist_video_count=entity_videos.total_videos,  # Accurate count from entity details
                            featured_video_count=entity.featured_video_count or 0,
                            sample_tracks=sample_tracks,
                        )
                    )
                except Exception as e:
                    # If entity fetch fails, log and skip this result
                    logger.warning(
                        "add_artist_search_entity_fetch_failed",
                        entity_id=entity.id,
                        entity_slug=entity.slug,
                        error=str(e),
                    )
                    continue

        logger.info(
            "add_artist_search_complete",
            artist_name=request.artist_name,
            total_results=search_result.pagination.total_results,
            results_with_videos=len(results_with_videos),
        )

        return ArtistSearchResponse(
            artist_name=request.artist_name,
            total_results=search_result.pagination.total_results,
            results=results_with_videos,
        )

    except Exception as e:
        logger.error(
            "add_artist_search_error",
            artist_name=request.artist_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to search IMVDb: {str(e)}",
        )


@router.get(
    "/artist/preview/{entity_id}",
    response_model=ArtistVideosPreviewResponse,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Get paginated artist videos for selection",
    description="Fetch videos for an artist with duplicate detection against existing library.",
)
async def preview_artist_videos(
    entity_id: int,
    page: int = 1,
    per_page: int = 50,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)] = None,
) -> ArtistVideosPreviewResponse:
    """
    Get paginated artist videos for the selection grid.

    Checks each video against the existing library for duplicate detection.
    """
    user_label = current_user.username if current_user else "anonymous"
    logger.info(
        "add_artist_preview_start",
        entity_id=entity_id,
        page=page,
        per_page=per_page,
        user=user_label,
    )

    api_config = _get_api_config("imvdb")
    if not api_config:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IMVDb API is not configured",
        )

    try:
        async with IMVDbClient.from_config(api_config) as imvdb_client:
            videos_page = await imvdb_client.get_entity_videos(
                entity_id=entity_id,
                page=page,
                per_page=per_page,
            )

        # Check for duplicates against existing library
        repository = await fuzzbin_module.get_repository()

        preview_items: list[ArtistVideoPreviewItem] = []
        existing_count = 0
        new_count = 0

        for v in videos_page.videos:
            # Extract thumbnail URL
            thumbnail_url = None
            image = getattr(v, "image", None)
            if isinstance(image, dict):
                thumbnail_url = image.get("o") or image.get("l") or image.get("b")

            # Check for existing video by IMVDb ID
            already_exists = False
            existing_video_id = None

            try:
                existing = await repository.get_video_by_imvdb_id(str(v.id), include_deleted=False)
                already_exists = True
                existing_video_id = existing.get("id")
            except Exception:
                pass  # Video not found, check by artist + title match

            if not already_exists:
                # Also check by artist + title match
                title = v.song_title or ""
                if title and videos_page.entity_name:
                    normalized_title = normalize_spotify_title(
                        title,
                        remove_version_qualifiers_flag=True,
                        remove_featured=True,
                    )
                    query = repository.query().where_artist(videos_page.entity_name)
                    results = await query.execute()

                    for result in results:
                        db_title = result.get("title", "")
                        db_normalized = normalize_spotify_title(
                            db_title,
                            remove_version_qualifiers_flag=True,
                            remove_featured=True,
                        )
                        if db_normalized == normalized_title:
                            already_exists = True
                            existing_video_id = result.get("id")
                            break

            if already_exists:
                existing_count += 1
            else:
                new_count += 1

            preview_items.append(
                ArtistVideoPreviewItem(
                    id=v.id,
                    song_title=v.song_title,
                    year=v.year,
                    url=v.url,
                    thumbnail_url=thumbnail_url,
                    production_status=v.production_status,
                    version_name=v.version_name,
                    already_exists=already_exists,
                    existing_video_id=existing_video_id,
                )
            )

        logger.info(
            "add_artist_preview_complete",
            entity_id=entity_id,
            page=page,
            videos_on_page=len(preview_items),
            existing_count=existing_count,
            new_count=new_count,
        )

        return ArtistVideosPreviewResponse(
            entity_id=videos_page.entity_id,
            entity_name=videos_page.entity_name,
            entity_slug=videos_page.entity_slug,
            total_videos=videos_page.total_videos,
            current_page=videos_page.current_page,
            per_page=videos_page.per_page,
            total_pages=videos_page.total_pages,
            has_more=videos_page.has_more,
            videos=preview_items,
            existing_count=existing_count,
            new_count=new_count,
        )

    except Exception as e:
        logger.error(
            "add_artist_preview_error",
            entity_id=entity_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch artist videos: {str(e)}",
        )


@router.post(
    "/enrich/imvdb-video",
    response_model=ArtistVideoEnrichResponse,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Enrich a single IMVDb video with MusicBrainz data",
    description="Fetch full video details from IMVDb and enrich with MusicBrainz metadata.",
)
async def enrich_imvdb_video(
    request: ArtistVideoEnrichRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> ArtistVideoEnrichResponse:
    """
    Enrich a single IMVDb video with MusicBrainz metadata.

    This endpoint:
    1. Fetches full video details from IMVDb (directors, sources, featured artists)
    2. Queries MusicBrainz for album, year, label, and genre
    3. Returns merged data with enrichment status indicator
    """
    user_label = current_user.username if current_user else "anonymous"
    logger.info(
        "add_enrich_imvdb_video_start",
        imvdb_id=request.imvdb_id,
        artist=request.artist,
        track_title=request.track_title,
        user=user_label,
    )

    api_config = _get_api_config("imvdb")
    if not api_config:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IMVDb API is not configured",
        )

    # Fetch full video details from IMVDb
    directors = None
    featured_artists = None
    youtube_ids: list[str] = []
    imvdb_url = None

    try:
        async with IMVDbClient.from_config(api_config) as imvdb_client:
            video = await imvdb_client.get_video(request.imvdb_id)

        imvdb_url = video.url

        # Extract directors
        if video.directors:
            directors = ", ".join(d.entity_name for d in video.directors)

        # Extract featured artists
        if video.featured_artists:
            featured_artists = ", ".join(a.name for a in video.featured_artists)

        # Extract YouTube IDs from sources
        if video.sources:
            for source in video.sources:
                if source.source_slug == "youtube" and source.source_data:
                    youtube_ids.append(str(source.source_data))

    except Exception as e:
        logger.warning(
            "add_enrich_imvdb_video_fetch_failed",
            imvdb_id=request.imvdb_id,
            error=str(e),
        )
        # Continue with enrichment even if IMVDb details fail

    # MusicBrainz enrichment
    mb_config = _get_api_config("musicbrainz")
    mb_data = MusicBrainzEnrichmentData(
        match_method="none",
        confident_match=False,
    )
    enrichment_status = "not_found"

    try:
        mb_service = MusicBrainzEnrichmentService(config=mb_config)
        mb_result = await mb_service.enrich(
            artist=request.artist,
            title=request.track_title,
            isrc=None,  # No ISRC available from IMVDb
        )

        if mb_result:
            mb_data = MusicBrainzEnrichmentData(
                recording_mbid=mb_result.recording_mbid,
                release_mbid=mb_result.release_mbid,
                canonical_title=mb_result.canonical_title,
                canonical_artist=mb_result.canonical_artist,
                album=mb_result.album,
                year=mb_result.year,
                label=mb_result.label,
                genre=mb_result.genre,
                classified_genre=mb_result.classified_genre,
                all_genres=mb_result.all_genres or [],
                match_score=mb_result.match_score or 0.0,
                match_method=mb_result.match_method or "search",
                confident_match=mb_result.confident_match or False,
            )

            if mb_result.confident_match:
                enrichment_status = "success"
            else:
                enrichment_status = "partial"

    except Exception as e:
        logger.warning(
            "add_enrich_imvdb_video_musicbrainz_failed",
            imvdb_id=request.imvdb_id,
            error=str(e),
        )
        enrichment_status = "not_found"

    # Resolve final values (MusicBrainz takes priority where available)
    resolved_title = mb_data.canonical_title or request.track_title
    resolved_artist = mb_data.canonical_artist or request.artist
    resolved_year = mb_data.year or request.year
    resolved_album = mb_data.album
    resolved_label = mb_data.label
    resolved_genre = mb_data.classified_genre or mb_data.genre

    # Check for existing video
    repository = await fuzzbin_module.get_repository()
    already_exists = False
    existing_video_id = None

    try:
        existing = await repository.get_video_by_imvdb_id(
            str(request.imvdb_id), include_deleted=False
        )
        already_exists = True
        existing_video_id = existing.get("id")
    except Exception:
        pass  # Video not found

    logger.info(
        "add_enrich_imvdb_video_complete",
        imvdb_id=request.imvdb_id,
        enrichment_status=enrichment_status,
        has_directors=bool(directors),
        youtube_ids_count=len(youtube_ids),
        already_exists=already_exists,
    )

    return ArtistVideoEnrichResponse(
        imvdb_id=request.imvdb_id,
        directors=directors,
        featured_artists=featured_artists,
        youtube_ids=youtube_ids,
        imvdb_url=imvdb_url,
        musicbrainz=mb_data,
        title=resolved_title,
        artist=resolved_artist,
        album=resolved_album,
        year=resolved_year,
        label=resolved_label,
        genre=resolved_genre,
        thumbnail_url=request.thumbnail_url,
        enrichment_status=enrichment_status,
        already_exists=already_exists,
        existing_video_id=existing_video_id,
    )


@router.post(
    "/artist/import",
    response_model=ArtistBatchImportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Import selected videos from an artist",
    description="Submit a batch import job for selected artist videos.",
)
async def submit_artist_import(
    request: ArtistBatchImportRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> ArtistBatchImportResponse:
    """
    Submit a batch import job for selected artist videos.

    Creates video records with provided metadata and optionally queues
    download jobs for videos with YouTube IDs.
    """
    user_label = current_user.username if current_user else "anonymous"

    if not request.videos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one video is required",
        )

    logger.info(
        "add_artist_import_job_submitting",
        entity_id=request.entity_id,
        entity_name=request.entity_name,
        video_count=len(request.videos),
        initial_status=request.initial_status,
        auto_download=request.auto_download,
        user=user_label,
    )

    job = Job(
        type=JobType.IMPORT_IMVDB_ARTIST,
        metadata={
            "entity_id": request.entity_id,
            "entity_name": request.entity_name,
            "videos": [v.model_dump() for v in request.videos],
            "initial_status": request.initial_status,
            "auto_download": request.auto_download,
        },
    )

    queue = get_job_queue()
    await queue.submit(job)

    return ArtistBatchImportResponse(
        job_id=job.id,
        entity_id=request.entity_id,
        video_count=len(request.videos),
        auto_download=request.auto_download,
    )
