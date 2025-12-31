"""Discogs metadata enrichment service.

This service enriches music video metadata with album, label, and genre information
from Discogs by linking IMVDb entities to Discogs artists and fuzzy-matching track titles.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog
from rapidfuzz import fuzz

from fuzzbin.api.discogs_client import DiscogsClient
from fuzzbin.api.imvdb_client import IMVDbClient
from fuzzbin.common.config import APIClientConfig

logger = structlog.get_logger(__name__)


@dataclass
class DiscogsTrackMatch:
    """Result of matching a track title in Discogs tracklist."""

    master_id: int
    release_id: Optional[int]
    album_title: str
    year: Optional[int]
    labels: List[str]
    genres: List[str]
    styles: List[str]
    track_title: str
    track_position: str
    match_score: float


@dataclass
class DiscogsEnrichmentResult:
    """Result of Discogs enrichment for a video."""

    # Source information
    discogs_artist_id: Optional[int]
    discogs_master_id: Optional[int]

    # Enriched metadata
    album: Optional[str]
    label: Optional[str]
    genre: Optional[str]
    year: Optional[int]

    # Match details
    match_score: float
    match_method: str  # 'artist_releases', 'text_search', 'none'
    track_matches: List[DiscogsTrackMatch]

    # Whether confident enough to auto-populate
    confident_match: bool


class DiscogsEnrichmentService:
    """Service for enriching video metadata from Discogs.

    This service attempts to find album, label, and genre information for
    a music video by:

    1. Using the IMVDb entity's linked Discogs artist ID (if available)
    2. Fetching artist releases from Discogs
    3. Fuzzy-matching track titles in release tracklists
    4. Falling back to Discogs text search if no artist ID is available

    Example:
        >>> config = get_config()
        >>> service = DiscogsEnrichmentService(
        ...     imvdb_config=config.apis['imvdb'],
        ...     discogs_config=config.apis['discogs'],
        ... )
        >>> result = await service.enrich_from_imvdb_video(
        ...     imvdb_video_id=12345,
        ...     track_title="Smells Like Teen Spirit",
        ...     artist_name="Nirvana",
        ... )
        >>> if result.confident_match:
        ...     print(f"Album: {result.album}, Label: {result.label}")
    """

    # Default fuzzy match threshold (0-100)
    DEFAULT_MATCH_THRESHOLD = 80

    def __init__(
        self,
        imvdb_config: Optional[APIClientConfig] = None,
        discogs_config: Optional[APIClientConfig] = None,
        match_threshold: int = DEFAULT_MATCH_THRESHOLD,
    ):
        """Initialize the enrichment service.

        Args:
            imvdb_config: Configuration for IMVDb client
            discogs_config: Configuration for Discogs client
            match_threshold: Minimum fuzzy match score (0-100) to consider a match
        """
        self.imvdb_config = imvdb_config
        self.discogs_config = discogs_config
        self.match_threshold = match_threshold

    async def enrich_from_imvdb_video(
        self,
        imvdb_video_id: int,
        track_title: str,
        artist_name: str,
    ) -> DiscogsEnrichmentResult:
        """Enrich metadata from IMVDb video via Discogs.

        Attempts to find Discogs metadata by:
        1. Getting the IMVDb entity for the first artist on the video
        2. Using the entity's discogs_id if available
        3. Fetching artist releases and fuzzy-matching track titles
        4. Falling back to Discogs search if no artist ID

        Args:
            imvdb_video_id: IMVDb video ID
            track_title: Track title to search for in tracklists
            artist_name: Artist name for fallback search

        Returns:
            DiscogsEnrichmentResult with matched metadata
        """
        if not self.imvdb_config or not self.discogs_config:
            logger.warning(
                "discogs_enrichment_skipped",
                reason="missing_config",
                imvdb_video_id=imvdb_video_id,
            )
            return self._empty_result()

        discogs_artist_id: Optional[int] = None

        # Step 1: Get IMVDb entity to find Discogs artist ID
        try:
            async with IMVDbClient.from_config(self.imvdb_config) as imvdb_client:
                # Search for the artist entity
                entity_search = await imvdb_client.search_entities(artist_name)

                if entity_search.results:
                    # Take the first matching entity
                    entity_result = entity_search.results[0]
                    discogs_artist_id = entity_result.discogs_id

                    logger.info(
                        "discogs_enrichment_found_entity",
                        imvdb_video_id=imvdb_video_id,
                        imvdb_entity_id=entity_result.id,
                        discogs_artist_id=discogs_artist_id,
                    )

        except Exception as e:
            logger.warning(
                "discogs_enrichment_imvdb_failed",
                imvdb_video_id=imvdb_video_id,
                error=str(e),
            )

        # Step 2: Try to enrich via artist releases or fallback to search
        if discogs_artist_id:
            result = await self._enrich_via_artist_releases(
                discogs_artist_id=discogs_artist_id,
                track_title=track_title,
            )
            if result.confident_match:
                return result

        # Fallback: Discogs text search
        return await self._enrich_via_text_search(
            artist_name=artist_name,
            track_title=track_title,
        )

    async def enrich_from_discogs_artist(
        self,
        discogs_artist_id: int,
        track_title: str,
    ) -> DiscogsEnrichmentResult:
        """Enrich metadata directly from Discogs artist ID.

        Args:
            discogs_artist_id: Discogs artist ID
            track_title: Track title to search for in tracklists

        Returns:
            DiscogsEnrichmentResult with matched metadata
        """
        return await self._enrich_via_artist_releases(
            discogs_artist_id=discogs_artist_id,
            track_title=track_title,
        )

    async def _enrich_via_artist_releases(
        self,
        discogs_artist_id: int,
        track_title: str,
    ) -> DiscogsEnrichmentResult:
        """Enrich by fetching artist releases and matching tracklists.

        Args:
            discogs_artist_id: Discogs artist ID
            track_title: Track title to match

        Returns:
            DiscogsEnrichmentResult
        """
        if not self.discogs_config:
            return self._empty_result()

        track_matches: List[DiscogsTrackMatch] = []

        try:
            async with DiscogsClient.from_config(self.discogs_config) as discogs_client:
                # Fetch artist releases (paginated, get first few pages)
                all_releases: List[Dict[str, Any]] = []
                page = 1
                max_pages = 3  # Limit to first 3 pages (150 releases)

                while page <= max_pages:
                    releases_resp = await discogs_client.get_artist_releases(
                        artist_id=discogs_artist_id,
                        page=page,
                        per_page=50,
                        sort="year",
                        sort_order="asc",
                    )

                    releases = releases_resp.get("releases", [])
                    all_releases.extend(releases)

                    pagination = releases_resp.get("pagination", {})
                    total_pages = pagination.get("pages", 1)
                    if page >= total_pages:
                        break
                    page += 1

                logger.info(
                    "discogs_enrichment_fetched_releases",
                    discogs_artist_id=discogs_artist_id,
                    release_count=len(all_releases),
                )

                # Filter to masters only (more reliable metadata)
                masters = [r for r in all_releases if r.get("type") == "master"]

                # For each master, fetch details and match tracklist
                for release in masters[:20]:  # Limit to first 20 masters
                    master_id = release.get("id")
                    if not master_id:
                        continue

                    try:
                        master = await discogs_client.get_master(master_id)
                        match = self._match_tracklist(
                            track_title=track_title,
                            tracklist=master.get("tracklist", []),
                            master_id=master_id,
                            album_title=master.get("title", ""),
                            year=master.get("year"),
                            labels=self._extract_labels(master),
                            genres=master.get("genres", []),
                            styles=master.get("styles", []),
                        )

                        if match:
                            track_matches.append(match)

                    except Exception as e:
                        logger.debug(
                            "discogs_enrichment_master_fetch_failed",
                            master_id=master_id,
                            error=str(e),
                        )
                        continue

        except Exception as e:
            logger.warning(
                "discogs_enrichment_artist_releases_failed",
                discogs_artist_id=discogs_artist_id,
                error=str(e),
            )
            return self._empty_result()

        # Sort matches by score and return best
        return self._build_result_from_matches(
            track_matches=track_matches,
            discogs_artist_id=discogs_artist_id,
            match_method="artist_releases",
        )

    async def _enrich_via_text_search(
        self,
        artist_name: str,
        track_title: str,
    ) -> DiscogsEnrichmentResult:
        """Enrich by searching Discogs for artist + track.

        Args:
            artist_name: Artist name
            track_title: Track title

        Returns:
            DiscogsEnrichmentResult
        """
        if not self.discogs_config:
            return self._empty_result()

        track_matches: List[DiscogsTrackMatch] = []

        try:
            async with DiscogsClient.from_config(self.discogs_config) as discogs_client:
                # Search for masters containing this track
                search_resp = await discogs_client.search(
                    artist=artist_name,
                    track=track_title,
                    page=1,
                    per_page=10,
                )

                results = search_resp.get("results", [])

                logger.info(
                    "discogs_enrichment_text_search",
                    artist=artist_name,
                    track=track_title,
                    result_count=len(results),
                )

                # Fetch master details for top results
                for result in results[:5]:
                    master_id = result.get("id")
                    if not master_id or result.get("type") != "master":
                        continue

                    try:
                        master = await discogs_client.get_master(master_id)
                        match = self._match_tracklist(
                            track_title=track_title,
                            tracklist=master.get("tracklist", []),
                            master_id=master_id,
                            album_title=master.get("title", ""),
                            year=master.get("year"),
                            labels=self._extract_labels(master),
                            genres=master.get("genres", []),
                            styles=master.get("styles", []),
                        )

                        if match:
                            track_matches.append(match)

                    except Exception as e:
                        logger.debug(
                            "discogs_enrichment_search_master_failed",
                            master_id=master_id,
                            error=str(e),
                        )
                        continue

        except Exception as e:
            logger.warning(
                "discogs_enrichment_text_search_failed",
                artist=artist_name,
                track=track_title,
                error=str(e),
            )
            return self._empty_result()

        return self._build_result_from_matches(
            track_matches=track_matches,
            discogs_artist_id=None,
            match_method="text_search",
        )

    def _match_tracklist(
        self,
        track_title: str,
        tracklist: List[Dict[str, Any]],
        master_id: int,
        album_title: str,
        year: Optional[int],
        labels: List[str],
        genres: List[str],
        styles: List[str],
    ) -> Optional[DiscogsTrackMatch]:
        """Match track title against a tracklist using fuzzy matching.

        Args:
            track_title: Track title to match
            tracklist: Discogs tracklist array
            master_id: Master release ID
            album_title: Album title
            year: Release year
            labels: Label names
            genres: Genres
            styles: Styles

        Returns:
            DiscogsTrackMatch if a good match found, None otherwise
        """
        best_match: Optional[DiscogsTrackMatch] = None
        best_score = 0.0

        for track in tracklist:
            discogs_title = track.get("title", "")
            if not discogs_title:
                continue

            # Use token_sort_ratio for best results with different word orders
            score = fuzz.token_sort_ratio(
                track_title.lower(),
                discogs_title.lower(),
            )

            if score > best_score:
                best_score = score
                best_match = DiscogsTrackMatch(
                    master_id=master_id,
                    release_id=None,
                    album_title=album_title,
                    year=year,
                    labels=labels,
                    genres=genres,
                    styles=styles,
                    track_title=discogs_title,
                    track_position=track.get("position", ""),
                    match_score=score,
                )

        if best_match and best_score >= self.match_threshold:
            return best_match

        return None

    def _extract_labels(self, release_data: Dict[str, Any]) -> List[str]:
        """Extract label names from release data.

        Args:
            release_data: Discogs release/master data

        Returns:
            List of label names
        """
        labels = release_data.get("labels", [])
        if not labels:
            return []

        return [label.get("name", "") for label in labels if label.get("name")]

    def _build_result_from_matches(
        self,
        track_matches: List[DiscogsTrackMatch],
        discogs_artist_id: Optional[int],
        match_method: str,
    ) -> DiscogsEnrichmentResult:
        """Build enrichment result from track matches.

        Args:
            track_matches: List of track matches
            discogs_artist_id: Discogs artist ID if known
            match_method: Method used to find matches

        Returns:
            DiscogsEnrichmentResult
        """
        if not track_matches:
            return DiscogsEnrichmentResult(
                discogs_artist_id=discogs_artist_id,
                discogs_master_id=None,
                album=None,
                label=None,
                genre=None,
                year=None,
                match_score=0.0,
                match_method=match_method,
                track_matches=[],
                confident_match=False,
            )

        # Sort by score descending
        track_matches.sort(key=lambda m: m.match_score, reverse=True)
        best_match = track_matches[0]

        return DiscogsEnrichmentResult(
            discogs_artist_id=discogs_artist_id,
            discogs_master_id=best_match.master_id,
            album=best_match.album_title,
            label=best_match.labels[0] if best_match.labels else None,
            genre=best_match.genres[0] if best_match.genres else None,
            year=best_match.year,
            match_score=best_match.match_score,
            match_method=match_method,
            track_matches=track_matches[:5],  # Return top 5 matches
            confident_match=best_match.match_score >= self.match_threshold,
        )

    def _empty_result(self) -> DiscogsEnrichmentResult:
        """Return an empty enrichment result."""
        return DiscogsEnrichmentResult(
            discogs_artist_id=None,
            discogs_master_id=None,
            album=None,
            label=None,
            genre=None,
            year=None,
            match_score=0.0,
            match_method="none",
            track_matches=[],
            confident_match=False,
        )
