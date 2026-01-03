"""Unified track enrichment service combining MusicBrainz and IMVDb."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import structlog

from fuzzbin.api import IMVDbClient
from fuzzbin.common.genre_buckets import classify_genres
from fuzzbin.core.db import VideoRepository
from fuzzbin.parsers import IMVDbVideo
from fuzzbin.services.base import BaseService
from fuzzbin.services.musicbrainz_enrichment import MusicBrainzEnrichmentService

logger = structlog.get_logger(__name__)


@dataclass
class TrackEnrichmentResult:
    """Combined enrichment result from MusicBrainz + IMVDb."""

    # MusicBrainz data
    mb_recording_mbid: Optional[str] = None
    mb_release_mbid: Optional[str] = None
    mb_canonical_title: Optional[str] = None
    mb_canonical_artist: Optional[str] = None
    mb_album: Optional[str] = None
    mb_year: Optional[int] = None
    mb_label: Optional[str] = None
    mb_genre: Optional[str] = None
    mb_classified_genre: Optional[str] = None
    mb_all_genres: list[str] = field(default_factory=list)
    mb_match_score: float = 0.0
    mb_match_method: str = "none"
    mb_confident_match: bool = False

    # IMVDb data
    imvdb_id: Optional[int] = None
    imvdb_url: Optional[str] = None
    imvdb_year: Optional[int] = None
    imvdb_directors: Optional[str] = None
    imvdb_featured_artists: Optional[str] = None
    imvdb_youtube_ids: list[str] = field(default_factory=list)
    imvdb_thumbnail_url: Optional[str] = None
    imvdb_found: bool = False

    # Resolved final values (priority: MB canonical > IMVDb > original)
    final_title: str = ""
    final_artist: str = ""
    final_album: Optional[str] = None
    final_year: Optional[int] = None
    final_label: Optional[str] = None
    final_genre: Optional[str] = None


class TrackEnrichmentService(BaseService):
    """Unified enrichment service combining MusicBrainz and IMVDb.

    This service orchestrates metadata enrichment from multiple sources:
    1. MusicBrainz: Canonical metadata via ISRC or artist/title search
    2. Genre classification: MusicBrainz tags with Spotify fallback
    3. IMVDb: Video-specific metadata (directors, YouTube IDs)
    """

    def __init__(
        self,
        repository: VideoRepository,
        musicbrainz_service: MusicBrainzEnrichmentService,
        imvdb_client: IMVDbClient,
    ):
        """Initialize the track enrichment service.

        Args:
            repository: Video repository for database operations
            musicbrainz_service: MusicBrainz enrichment service
            imvdb_client: IMVDb API client
        """
        super().__init__(repository)
        self._musicbrainz_service = musicbrainz_service
        self._imvdb_client = imvdb_client

    async def enrich(
        self,
        artist: str,
        title: str,
        isrc: Optional[str] = None,
        spotify_artist_genres: Optional[list[str]] = None,
    ) -> TrackEnrichmentResult:
        """Enrich track metadata from MusicBrainz and IMVDb.

        Flow:
        1. MusicBrainz: ISRC search → canonical data, album, year, label, genres
        2. Genre classifier: Tags with count > 1 → bucket classification
           - If no classified genre from MusicBrainz, fall back to Spotify artist genres
        3. IMVDb: Search using canonical artist/title → directors, YouTube IDs
        4. Return canonical values that replace original Spotify metadata

        Args:
            artist: Artist name from Spotify
            title: Track title from Spotify
            isrc: ISRC code from Spotify (preferred for MusicBrainz lookup)
            spotify_artist_genres: Spotify artist genres (used as fallback)

        Returns:
            TrackEnrichmentResult with combined metadata from all sources
        """
        log = logger.bind(artist=artist, title=title, isrc=isrc)
        result = TrackEnrichmentResult()

        # Initialize final values with input data
        result.final_title = title
        result.final_artist = artist

        # Step 1: MusicBrainz enrichment
        log.info("musicbrainz_enrichment_started")
        mb_result = await self._enrich_from_musicbrainz(artist, title, isrc)

        if mb_result:
            result.mb_recording_mbid = mb_result.recording_mbid
            result.mb_release_mbid = mb_result.release_mbid
            result.mb_canonical_title = mb_result.canonical_title
            result.mb_canonical_artist = mb_result.canonical_artist
            result.mb_album = mb_result.album
            result.mb_year = mb_result.year
            result.mb_label = mb_result.label
            result.mb_genre = mb_result.genre
            result.mb_all_genres = mb_result.all_genres
            result.mb_match_method = mb_result.match_method
            result.mb_confident_match = mb_result.confident_match

            # Use canonical values if available
            if mb_result.canonical_title:
                result.final_title = mb_result.canonical_title
            if mb_result.canonical_artist:
                result.final_artist = mb_result.canonical_artist
            if mb_result.album:
                result.final_album = mb_result.album
            if mb_result.year:
                result.final_year = mb_result.year
            if mb_result.label:
                result.final_label = mb_result.label

            log.info(
                "musicbrainz_enrichment_completed",
                recording_mbid=result.mb_recording_mbid,
                canonical_title=result.mb_canonical_title,
                confident_match=result.mb_confident_match,
            )

        # Step 2: Genre classification
        log.info("genre_classification_started")
        classified_genre = await self._classify_genre(
            mb_result.all_genres if mb_result else [],
            spotify_artist_genres,
        )
        result.mb_classified_genre = classified_genre
        result.final_genre = classified_genre
        log.info("genre_classification_completed", genre=classified_genre)

        # Step 3: IMVDb enrichment using canonical values
        log.info("imvdb_enrichment_started")
        search_artist = result.final_artist
        search_title = result.final_title

        imvdb_result = await self._enrich_from_imvdb(search_artist, search_title)

        if imvdb_result:
            result.imvdb_id = imvdb_result.id
            result.imvdb_url = imvdb_result.url
            result.imvdb_year = imvdb_result.year
            result.imvdb_directors = (
                ", ".join(d.entity_name for d in imvdb_result.directors)
                if imvdb_result.directors
                else None
            )
            result.imvdb_featured_artists = (
                ", ".join(imvdb_result.featured_artists) if imvdb_result.featured_artists else None
            )
            result.imvdb_youtube_ids = self._extract_youtube_ids(imvdb_result)
            result.imvdb_thumbnail_url = (
                imvdb_result.image.get("o")
                or imvdb_result.image.get("l")
                or imvdb_result.image.get("b")
                if imvdb_result.image and isinstance(imvdb_result.image, dict)
                else None
            )
            result.imvdb_found = True

            # Use IMVDb year if MusicBrainz didn't provide one
            if not result.final_year and imvdb_result.year:
                result.final_year = imvdb_result.year

            log.info(
                "imvdb_enrichment_completed",
                imvdb_id=result.imvdb_id,
                youtube_ids=result.imvdb_youtube_ids,
            )
        else:
            log.info("imvdb_enrichment_no_match")

        return result

    async def _enrich_from_musicbrainz(
        self,
        artist: str,
        title: str,
        isrc: Optional[str] = None,
    ):
        """Enrich from MusicBrainz using ISRC or search.

        Args:
            artist: Artist name
            title: Track title
            isrc: ISRC code (preferred)

        Returns:
            MusicBrainzEnrichmentResult or None
        """
        log = logger.bind(artist=artist, title=title, isrc=isrc)

        try:
            # Try ISRC lookup first if available
            if isrc:
                log.debug("musicbrainz_lookup_isrc")
                result = await self._musicbrainz_service.enrich_from_isrc(isrc)
                if result and result.recording_mbid:
                    log.info("musicbrainz_isrc_match", recording_mbid=result.recording_mbid)
                    return result
                log.debug("musicbrainz_isrc_no_match")

            # Fall back to artist/title search
            log.debug("musicbrainz_search_artist_title")
            result = await self._musicbrainz_service.enrich_from_search(artist, title)
            if result and result.recording_mbid:
                log.info("musicbrainz_search_match", recording_mbid=result.recording_mbid)
                return result

            log.info("musicbrainz_no_match")
            return None

        except Exception as exc:
            log.error("musicbrainz_enrichment_error", error=str(exc))
            return None

    async def _classify_genre(
        self,
        mb_genres: list[str],
        spotify_genres: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Classify genre with MusicBrainz priority and Spotify fallback.

        Args:
            mb_genres: MusicBrainz genre tags (already filtered by count > 1)
            spotify_genres: Spotify artist genres (fallback)

        Returns:
            Classified genre bucket or None
        """
        log = logger.bind(mb_genres=mb_genres, spotify_genres=spotify_genres)

        # Try MusicBrainz genres first
        if mb_genres:
            log.debug("classifying_musicbrainz_genres")
            classified, _ = classify_genres(mb_genres)
            if classified:
                log.info("genre_classified_from_musicbrainz", genre=classified)
                return classified

        # Fall back to Spotify genres
        if spotify_genres:
            log.debug("classifying_spotify_genres")
            classified, _ = classify_genres(spotify_genres)
            if classified:
                log.info("genre_classified_from_spotify", genre=classified)
                return classified

        log.info("genre_classification_no_match")
        return None

    async def _enrich_from_imvdb(
        self,
        artist: str,
        title: str,
    ) -> Optional[IMVDbVideo]:
        """Search IMVDb for video metadata.

        Args:
            artist: Artist name (preferably canonical from MusicBrainz)
            title: Track title (preferably canonical from MusicBrainz)

        Returns:
            IMVDbVideo or None if no match found
        """
        log = logger.bind(artist=artist, title=title)

        try:
            log.debug("imvdb_search_started")
            results = await self._imvdb_client.search_videos(artist=artist, track_title=title)

            if not results.results:
                log.info("imvdb_search_no_results")
                return None

            # For now, take the first result (TODO: implement fuzzy matching)
            video = results.results[0]
            log.info("imvdb_search_match", imvdb_id=video.id, url=video.url)

            # Fetch full video details to get all sources
            full_video = await self._imvdb_client.get_video(video.id)
            return full_video

        except Exception as exc:
            log.error("imvdb_enrichment_error", error=str(exc))
            return None

    def _extract_youtube_ids(self, video: IMVDbVideo) -> list[str]:
        """Extract all YouTube video IDs from IMVDb sources.

        Args:
            video: IMVDb video with sources

        Returns:
            List of unique YouTube video IDs
        """
        youtube_ids = []

        if not video.sources:
            return youtube_ids

        for source in video.sources:
            if source.source == "youtube" and source.source_data:
                youtube_id = source.source_data
                if youtube_id and youtube_id not in youtube_ids:
                    youtube_ids.append(youtube_id)

        return youtube_ids
