"""MusicBrainz metadata enrichment service.

This service enriches music track metadata with album, label, genre, and year information
from MusicBrainz by looking up tracks via ISRC or searching by artist/title.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import structlog
from rapidfuzz import fuzz

from fuzzbin.api.musicbrainz_client import MusicBrainzClient
from fuzzbin.common.config import APIClientConfig
from fuzzbin.common.genre_buckets import classify_genres
from fuzzbin.common.string_utils import normalize_spotify_title
from fuzzbin.parsers.musicbrainz_models import (
    MusicBrainzRecording,
    MusicBrainzRelease,
    RecordingNotFoundError,
)

logger = structlog.get_logger(__name__)


@dataclass
class MusicBrainzEnrichmentResult:
    """Result of MusicBrainz enrichment for a track."""

    # Source information
    recording_mbid: Optional[str] = None
    release_mbid: Optional[str] = None

    # Enriched metadata
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    label: Optional[str] = None

    # Canonical metadata from MusicBrainz (normalized titles without remaster tags, etc.)
    canonical_title: Optional[str] = None
    canonical_artist: Optional[str] = None

    # Genre classification (broad bucket: Metal, Rock, Pop, etc.)
    classified_genre: Optional[str] = None

    # Match details
    match_score: float = 0.0
    match_method: str = "none"  # 'isrc_search', 'search', 'none'
    confident_match: bool = False

    # Additional context
    all_genres: List[str] = field(default_factory=list)
    release_type: Optional[str] = None  # 'Album', 'Single', 'EP', etc.


class MusicBrainzEnrichmentService:
    """Service for enriching track metadata from MusicBrainz.

    This service attempts to find album, label, genre, and year information for
    a music track by:

    1. Looking up by ISRC code (most reliable when available)
    2. Falling back to search by artist + title with fuzzy matching

    For ISRC lookups, the service:
    - Finds the recording with the earliest first-release-date
    - Selects the earliest official studio album release for that recording
    - Extracts the top genre tag by vote count
    - Gets the label from the selected release

    Example:
        >>> service = MusicBrainzEnrichmentService()
        >>> result = await service.enrich(
        ...     isrc="USGF19942501",
        ...     artist="Nirvana",
        ...     title="Smells Like Teen Spirit",
        ... )
        >>> if result.confident_match:
        ...     print(f"Album: {result.album}, Year: {result.year}")
        ...     print(f"Genre: {result.genre}, Label: {result.label}")
    """

    # Default fuzzy match threshold (0-100) for search fallback
    DEFAULT_MATCH_THRESHOLD = 80

    def __init__(
        self,
        config: Optional[APIClientConfig] = None,
        config_dir: Optional[Path] = None,
        match_threshold: int = DEFAULT_MATCH_THRESHOLD,
    ):
        """Initialize the enrichment service.

        Args:
            config: Configuration for MusicBrainz client (optional, uses defaults)
            config_dir: Optional directory for cache storage
            match_threshold: Minimum fuzzy match score (0-100) to consider a match
        """
        self.config = config
        self.config_dir = config_dir
        self.match_threshold = match_threshold

    async def enrich(
        self,
        isrc: Optional[str] = None,
        artist: Optional[str] = None,
        title: Optional[str] = None,
    ) -> MusicBrainzEnrichmentResult:
        """Enrich track metadata from MusicBrainz.

        Tries ISRC lookup first if available, then falls back to search.

        Args:
            isrc: ISRC code (preferred lookup method)
            artist: Artist name for search fallback
            title: Track title for search fallback

        Returns:
            MusicBrainzEnrichmentResult with matched metadata
        """
        # Try ISRC lookup first
        if isrc:
            result = await self.enrich_from_isrc(isrc)
            if result.confident_match:
                return result
            logger.debug(
                "musicbrainz_enrichment_isrc_no_match",
                isrc=isrc,
                falling_back_to_search=bool(artist and title),
            )

        # Fallback to search if we have artist/title
        if artist and title:
            return await self.enrich_from_search(artist=artist, title=title)

        logger.warning(
            "musicbrainz_enrichment_no_criteria",
            isrc=isrc,
            artist=artist,
            title=title,
        )
        return self._empty_result()

    async def enrich_from_isrc(self, isrc: str) -> MusicBrainzEnrichmentResult:
        """Enrich metadata by searching for ISRC code.

        Uses the search endpoint which returns richer data than the dedicated
        ISRC lookup endpoint, including embedded release information.

        Args:
            isrc: ISRC code (format: CCXXXYYNNNNN)

        Returns:
            MusicBrainzEnrichmentResult with matched metadata
        """
        logger.info("musicbrainz_enrichment_isrc_start", isrc=isrc)

        try:
            async with MusicBrainzClient.from_config(
                self.config, config_dir=self.config_dir
            ) as client:
                # Use search endpoint which returns releases embedded in results
                search_response = await client.search_recordings(isrc=isrc, limit=10)

                if not search_response.recordings:
                    logger.info("musicbrainz_enrichment_isrc_no_recordings", isrc=isrc)
                    return self._empty_result()

                # Find the recording with earliest first-release-date
                recording = self._select_best_recording(search_response.recordings)

                logger.info(
                    "musicbrainz_enrichment_selected_recording",
                    isrc=isrc,
                    recording_mbid=recording.id,
                    recording_title=recording.title,
                    first_release_date=recording.first_release_date,
                    recordings_count=len(search_response.recordings),
                    releases_count=len(recording.releases or []),
                )

                return await self._build_result_from_recording(
                    client=client,
                    recording=recording,
                    match_method="isrc_search",
                    match_score=100.0,  # ISRC is an exact match
                )

        except RecordingNotFoundError:
            logger.info("musicbrainz_enrichment_isrc_not_found", isrc=isrc)
            return self._empty_result()
        except Exception as e:
            logger.warning(
                "musicbrainz_enrichment_isrc_failed",
                isrc=isrc,
                error=str(e),
            )
            return self._empty_result()

    async def enrich_from_search(
        self,
        artist: str,
        title: str,
    ) -> MusicBrainzEnrichmentResult:
        """Enrich metadata by searching for artist + title.

        Args:
            artist: Artist name
            title: Track title

        Returns:
            MusicBrainzEnrichmentResult with matched metadata
        """
        # Normalize title to remove version qualifiers
        normalized_title = normalize_spotify_title(
            title,
            remove_version_qualifiers_flag=True,
            remove_featured=True,
        )

        logger.info(
            "musicbrainz_enrichment_search_start",
            artist=artist,
            original_title=title,
            normalized_title=normalized_title,
        )

        try:
            async with MusicBrainzClient.from_config(
                self.config, config_dir=self.config_dir
            ) as client:
                search_response = await client.search_recordings(
                    artist=artist,
                    recording=normalized_title,
                    limit=10,
                )

                if not search_response.recordings:
                    logger.info(
                        "musicbrainz_enrichment_search_no_results",
                        artist=artist,
                        title=normalized_title,
                    )
                    return self._empty_result()

                # Filter recordings to studio audio tracks with official releases
                # before fuzzy matching to avoid matching videos/bootlegs/live recordings
                filtered_recordings = self._filter_studio_recordings(search_response.recordings)

                if not filtered_recordings:
                    logger.warning(
                        "musicbrainz_enrichment_search_no_studio_recordings",
                        artist=artist,
                        title=normalized_title,
                        total_recordings=len(search_response.recordings),
                    )
                    return self._empty_result()

                # Find best match using fuzzy matching on title
                # Track all recordings with max score to break ties by release quality
                best_matches = []
                best_score = 0.0

                for recording in filtered_recordings:
                    score = fuzz.token_sort_ratio(
                        normalized_title.lower(),
                        recording.title.lower(),
                    )

                    # Also factor in artist match
                    if recording.artist_name:
                        artist_score = fuzz.token_sort_ratio(
                            artist.lower(),
                            recording.artist_name.lower(),
                        )
                        # Combined score weighted towards title match
                        combined_score = (score * 0.7) + (artist_score * 0.3)
                    else:
                        combined_score = score

                    if combined_score > best_score:
                        best_score = combined_score
                        best_matches = [recording]
                    elif combined_score == best_score:
                        best_matches.append(recording)

                # If multiple recordings have same score, prefer by release quality
                best_match = None
                if len(best_matches) > 1:
                    logger.debug(
                        "musicbrainz_enrichment_tie_breaking",
                        title=normalized_title,
                        tied_count=len(best_matches),
                        score=best_score,
                    )
                    # Prefer recordings with Album releases over EP/Single only
                    best_match = self._prefer_album_recordings(best_matches)
                elif best_matches:
                    best_match = best_matches[0]

                if not best_match or best_score < self.match_threshold:
                    logger.info(
                        "musicbrainz_enrichment_search_no_confident_match",
                        artist=artist,
                        title=normalized_title,
                        best_score=best_score,
                        threshold=self.match_threshold,
                    )
                    return self._empty_result()

                logger.info(
                    "musicbrainz_enrichment_search_match_found",
                    artist=artist,
                    title=normalized_title,
                    matched_title=best_match.title,
                    matched_artist=best_match.artist_name,
                    match_score=best_score,
                    recording_mbid=best_match.id,
                )

                return await self._build_result_from_recording(
                    client=client,
                    recording=best_match,
                    match_method="search",
                    match_score=best_score,
                )

        except Exception as e:
            logger.warning(
                "musicbrainz_enrichment_search_failed",
                artist=artist,
                title=title,
                error=str(e),
            )
            return self._empty_result()

    def _prefer_album_recordings(
        self, recordings: List[MusicBrainzRecording]
    ) -> MusicBrainzRecording:
        """Prefer recordings with suitable Album releases over EP/Single/Compilation-only recordings.

        When multiple recordings have the same fuzzy match score, this breaks
        ties by preferring recordings that have at least one suitable Album release
        (excluding Compilations, Live, Remix, DJ-mix secondary types).

        Args:
            recordings: List of recordings with same match score

        Returns:
            Recording with best release type (suitable Album preferred)
        """
        # Types to skip (same as _select_best_release)
        skip_types = {"Compilation", "Live", "Remix", "DJ-mix"}

        # First pass: prefer recordings with suitable Album releases
        suitable_album_recordings = []
        for rec in recordings:
            if rec.releases:
                has_suitable_album = any(
                    release.release_group
                    and release.release_group.primary_type == "Album"
                    and release.release_group.primary_type not in skip_types
                    and not any(
                        st in skip_types for st in (release.release_group.secondary_types or [])
                    )
                    for release in rec.releases
                )
                if has_suitable_album:
                    suitable_album_recordings.append(rec)

        if suitable_album_recordings:
            logger.debug(
                "musicbrainz_tie_break_suitable_album_preferred",
                suitable_album_count=len(suitable_album_recordings),
                total_count=len(recordings),
            )
            # Among suitable album recordings, prefer earliest release
            return self._select_best_recording(suitable_album_recordings)

        # No suitable albums found, fall back to standard selection (earliest)
        logger.debug(
            "musicbrainz_tie_break_no_suitable_albums",
            total_count=len(recordings),
        )
        return self._select_best_recording(recordings)

    def _filter_studio_recordings(
        self, recordings: List[MusicBrainzRecording]
    ) -> List[MusicBrainzRecording]:
        """Filter recordings to studio audio tracks with official releases.

        Filters out:
        - Video recordings (music videos)
        - Live recordings (by disambiguation field)
        - Recordings with only bootleg/promotional releases

        Args:
            recordings: List of recordings to filter

        Returns:
            Filtered list of studio audio recordings
        """
        logger.debug(
            "musicbrainz_recording_filter_start",
            total_recordings=len(recordings),
        )

        studio_recordings = []
        for rec in recordings:
            # Skip video recordings (music videos, not audio tracks)
            if rec.video is True:
                logger.debug(
                    "musicbrainz_recording_filtered",
                    recording_id=rec.id,
                    title=rec.title,
                    video=rec.video,
                    reason="video_recording",
                )
                continue

            # Skip live recordings (check disambiguation field)
            disambiguation_lower = (rec.disambiguation or "").lower()
            is_live = "live" in disambiguation_lower

            if is_live:
                logger.debug(
                    "musicbrainz_recording_filtered",
                    recording_id=rec.id,
                    title=rec.title,
                    disambiguation=rec.disambiguation,
                    reason="live_recording",
                )
                continue

            # Skip recordings that only have bootleg/promotional releases
            if rec.releases:
                has_official_release = any(release.status == "Official" for release in rec.releases)
                if not has_official_release:
                    logger.debug(
                        "musicbrainz_recording_filtered",
                        recording_id=rec.id,
                        title=rec.title,
                        release_statuses=[r.status for r in rec.releases],
                        reason="no_official_releases",
                    )
                    continue

            studio_recordings.append(rec)

        logger.debug(
            "musicbrainz_recording_filter_complete",
            total_input=len(recordings),
            total_output=len(studio_recordings),
            filtered_count=len(recordings) - len(studio_recordings),
        )

        return studio_recordings

    def _select_best_recording(
        self, recordings: List[MusicBrainzRecording]
    ) -> MusicBrainzRecording:
        """Select the best recording from a list (earliest studio audio recording).

        Filters out video recordings, live recordings, and bootleg-only recordings,
        then selects the earliest by first-release-date.

        Args:
            recordings: List of recordings

        Returns:
            Best recording (earliest studio audio recording)
        """
        # Filter to studio recordings
        studio_recordings = self._filter_studio_recordings(recordings)

        # If all recordings filtered out, fall back to original list
        if not studio_recordings:
            logger.warning(
                "musicbrainz_no_studio_recordings_fallback",
                total_recordings=len(recordings),
                fallback_recording_id=recordings[0].id,
            )
            studio_recordings = recordings

        if len(studio_recordings) == 1:
            selected = studio_recordings[0]
            logger.info(
                "musicbrainz_recording_selected",
                recording_id=selected.id,
                title=selected.title,
                disambiguation=selected.disambiguation,
                first_release_date=selected.first_release_date,
                total_candidates=len(studio_recordings),
            )
            return selected

        # Sort by first-release-date, earliest first
        # Recordings without dates go to the end
        def sort_key(rec: MusicBrainzRecording) -> str:
            return rec.first_release_date or "9999-99-99"

        sorted_recordings = sorted(studio_recordings, key=sort_key)
        selected = sorted_recordings[0]

        logger.info(
            "musicbrainz_recording_selected",
            recording_id=selected.id,
            title=selected.title,
            disambiguation=selected.disambiguation,
            first_release_date=selected.first_release_date,
            total_candidates=len(studio_recordings),
        )

        return selected

    def _select_best_release(
        self, releases: List[MusicBrainzRelease]
    ) -> Optional[MusicBrainzRelease]:
        """Select the best release from a recording (earliest official studio album).

        Prioritizes:
        1. Official status
        2. Album primary type (over Single, EP, etc.)
        3. Excludes Compilations, Live, Soundtrack secondary types
        4. Earliest release date

        Args:
            releases: List of releases

        Returns:
            Best release or None if no suitable release found
        """
        if not releases:
            return None

        logger.debug(
            "musicbrainz_release_selection_start",
            total_releases=len(releases),
            release_titles=[r.title for r in releases[:10]],  # First 10 for brevity
        )

        # Filter and score releases
        scored_releases: List[tuple[int, str, MusicBrainzRelease]] = []

        for release in releases:
            score = 0
            date = release.date or "9999-99-99"
            skip_reason = None

            # Title-based filtering for live albums (fallback when MusicBrainz metadata is incomplete)
            # Common patterns: dates in title, "Live at", "Live in", venue names
            title_lower = release.title.lower()
            live_patterns = [
                "live at",
                "live in",
                "live from",
                ": live",
                "(live)",
                "[live]",
            ]
            # Check for date patterns like "1993-10-13" or "1993.10.13"
            has_date_pattern = any(char in release.title for char in ["-", ".", "/"]) and any(
                year in release.title for year in [str(y) for y in range(1950, 2030)]
            )

            if any(pattern in title_lower for pattern in live_patterns) or has_date_pattern:
                skip_reason = "live_title_pattern"
                logger.debug(
                    "musicbrainz_release_skipped",
                    release_id=release.id,
                    title=release.title,
                    reason=skip_reason,
                )
                continue

            # Prefer Official status
            if release.status == "Official":
                score += 100

            # Check release group type
            if release.release_group:
                primary_type = release.release_group.primary_type
                secondary_types = release.release_group.secondary_types or []

                # Skip compilations, live albums, remixes (but NOT soundtracks - many
                # classic songs were released on movie soundtracks like Purple Rain)
                skip_types = {"Compilation", "Live", "Remix", "DJ-mix"}

                # Check both primary type and secondary types for live/compilation/etc
                if primary_type in skip_types:
                    skip_reason = f"primary_type_{primary_type}"
                    logger.debug(
                        "musicbrainz_release_skipped",
                        release_id=release.id,
                        title=release.title,
                        primary_type=primary_type,
                        reason=skip_reason,
                    )
                    continue
                if any(st in skip_types for st in secondary_types):
                    skip_reason = (
                        f"secondary_type_{[st for st in secondary_types if st in skip_types]}"
                    )
                    logger.debug(
                        "musicbrainz_release_skipped",
                        release_id=release.id,
                        title=release.title,
                        secondary_types=secondary_types,
                        reason=skip_reason,
                    )
                    continue

                # Prefer Albums over Singles/EPs
                if primary_type == "Album":
                    score += 50
                elif primary_type == "EP":
                    score += 20
                elif primary_type == "Single":
                    score += 10

                logger.debug(
                    "musicbrainz_release_scored",
                    release_id=release.id,
                    title=release.title,
                    status=release.status,
                    primary_type=primary_type,
                    secondary_types=secondary_types,
                    date=date,
                    score=score,
                )

            scored_releases.append((score, date, release))

        if not scored_releases:
            # No suitable releases found, return first available
            logger.warning(
                "musicbrainz_no_suitable_releases",
                total_releases=len(releases),
                fallback_title=releases[0].title if releases else None,
            )
            return releases[0] if releases else None

        # Sort by score descending, then date ascending
        scored_releases.sort(key=lambda x: (-x[0], x[1]))
        selected = scored_releases[0][2]

        logger.info(
            "musicbrainz_release_selected",
            release_id=selected.id,
            title=selected.title,
            status=selected.status,
            primary_type=selected.release_group.primary_type if selected.release_group else None,
            secondary_types=selected.release_group.secondary_types
            if selected.release_group
            else None,
            date=selected.date,
            score=scored_releases[0][0],
            total_candidates=len(scored_releases),
        )

        return selected

    def _extract_top_genre(self, recording: MusicBrainzRecording) -> Optional[str]:
        """Extract the top genre tag from a recording with count >= 2.

        Only includes tags with at least 2 votes to filter out noise.

        Args:
            recording: MusicBrainz recording

        Returns:
            Top genre tag by vote count (with count >= 2), or None
        """
        if not recording.tags:
            return None

        # Filter by count >= 2 and sort by vote count
        filtered_tags = [t for t in recording.tags if t.count >= 2]
        sorted_tags = sorted(filtered_tags, key=lambda t: t.count, reverse=True)
        return sorted_tags[0].name if sorted_tags else None

    def _extract_all_genres(self, recording: MusicBrainzRecording) -> List[str]:
        """Extract genre tags from a recording with count >= 2, sorted by vote count.

        Only includes tags with at least 2 votes to filter out noise.

        Args:
            recording: MusicBrainz recording

        Returns:
            List of genre tag names (count >= 2) sorted by vote count
        """
        if not recording.tags:
            return []

        # Filter by count >= 2 and sort by vote count
        filtered_tags = [t for t in recording.tags if t.count >= 2]
        sorted_tags = sorted(filtered_tags, key=lambda t: t.count, reverse=True)
        return [t.name for t in sorted_tags]

    def _extract_label(self, release: MusicBrainzRelease) -> Optional[str]:
        """Extract label name from a release.

        Args:
            release: MusicBrainz release

        Returns:
            Label name or None
        """
        if not release.label_info:
            return None

        for label_info in release.label_info:
            if label_info.label and label_info.label.name:
                return label_info.label.name

        return None

    def _extract_year(self, release: MusicBrainzRelease) -> Optional[int]:
        """Extract release year from a release.

        Args:
            release: MusicBrainz release

        Returns:
            Year as integer or None
        """
        date = release.date
        if not date:
            return None

        # Parse year from date string (YYYY, YYYY-MM, or YYYY-MM-DD)
        try:
            return int(date[:4])
        except (ValueError, IndexError):
            return None

    async def _build_result_from_recording(
        self,
        client: MusicBrainzClient,
        recording: MusicBrainzRecording,
        match_method: str,
        match_score: float,
    ) -> MusicBrainzEnrichmentResult:
        """Build enrichment result from a recording.

        Args:
            client: MusicBrainz client for additional API calls
            recording: MusicBrainz recording
            match_method: Method used to find the recording
            match_score: Match confidence score

        Returns:
            MusicBrainzEnrichmentResult
        """
        # Select best release
        release = self._select_best_release(recording.releases or [])

        # Extract metadata
        album = release.title if release else None
        year = self._extract_year(release) if release else None
        genre = self._extract_top_genre(recording)
        all_genres = self._extract_all_genres(recording)
        release_type = None
        if release and release.release_group:
            release_type = release.release_group.primary_type

        # Classify genre into broad bucket
        classified_genre, _ = classify_genres(all_genres) if all_genres else (None, [])

        # Fetch label info from release endpoint (not included in search results)
        label = None
        if release:
            try:
                release_details = await client.get_release(release.id)
                label = self._extract_label(release_details)
            except Exception as e:
                logger.warning(
                    "musicbrainz_enrichment_label_fetch_failed",
                    release_mbid=release.id,
                    error=str(e),
                )

        confident = match_score >= self.match_threshold

        logger.info(
            "musicbrainz_enrichment_result",
            recording_mbid=recording.id,
            release_mbid=release.id if release else None,
            canonical_title=recording.title,
            canonical_artist=recording.artist_name,
            album=album,
            year=year,
            genre=genre,
            classified_genre=classified_genre,
            label=label,
            release_type=release_type,
            match_method=match_method,
            match_score=match_score,
            confident_match=confident,
        )

        return MusicBrainzEnrichmentResult(
            recording_mbid=recording.id,
            release_mbid=release.id if release else None,
            album=album,
            year=year,
            genre=genre,
            label=label,
            canonical_title=recording.title,
            canonical_artist=recording.artist_name,
            classified_genre=classified_genre,
            match_score=match_score,
            match_method=match_method,
            confident_match=confident,
            all_genres=all_genres,
            release_type=release_type,
        )

    def _empty_result(self) -> MusicBrainzEnrichmentResult:
        """Return an empty enrichment result."""
        return MusicBrainzEnrichmentResult(
            recording_mbid=None,
            release_mbid=None,
            album=None,
            year=None,
            genre=None,
            label=None,
            canonical_title=None,
            canonical_artist=None,
            classified_genre=None,
            match_score=0.0,
            match_method="none",
            confident_match=False,
            all_genres=[],
            release_type=None,
        )
