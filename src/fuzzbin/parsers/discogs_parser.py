"""Parser for Discogs API responses."""

from typing import Any, Dict, List, Optional

import structlog

from ..common.string_utils import normalize_for_matching
from .discogs_models import (
    DiscogsArtistRelease,
    DiscogsArtistReleasesResult,
    DiscogsMaster,
    DiscogsPagination,
    DiscogsRelease,
    DiscogsSearchResult,
    DiscogsSearchResultItem,
    DiscogsVideo,
    EmptySearchResultsError,
    MasterNotFoundError,
)

logger = structlog.get_logger(__name__)


class DiscogsParser:
    """Parser for Discogs API responses with domain methods for release matching."""

    @staticmethod
    def parse_search_response(data: Dict[str, Any]) -> DiscogsSearchResult:
        """
        Parse Discogs search response into validated model.

        Args:
            data: Raw search response from Discogs API

        Returns:
            Validated DiscogsSearchResult model with pagination metadata

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.search_releases("Nirvana", "Nevermind")
            >>> results = DiscogsParser.parse_search_response(response)
            >>> print(f"Found {results.pagination.items} results")
            'Found 10 results'
        """
        return DiscogsSearchResult.model_validate(data)

    @staticmethod
    def parse_master_response(
        data: Dict[str, Any],
        artist: Optional[str] = None,
        track_title: Optional[str] = None,
    ) -> DiscogsMaster:
        """
        Parse Discogs master release response into validated model.

        Optionally validates that the specified artist and track title appear
        on the release. If validation fails, sets is_exact_match=False.

        Args:
            data: Raw master response from Discogs API
            artist: Artist name to validate (checks main artists only)
            track_title: Track title to validate (searches entire tracklist)

        Returns:
            Validated DiscogsMaster model with is_exact_match flag

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get_master(13814)
            >>> master = DiscogsParser.parse_master_response(
            ...     response, artist="Nirvana", track_title="Smells Like Teen Spirit"
            ... )
            >>> print(master.is_exact_match)
            True
        """
        master = DiscogsMaster.model_validate(data)

        # If validation requested, check artist and track
        if artist is not None or track_title is not None:
            is_match = DiscogsParser._validate_artist_and_track(
                artists=master.artists,
                tracklist=master.tracklist,
                artist=artist,
                track_title=track_title,
            )
            master.is_exact_match = is_match

            if not is_match:
                logger.warning(
                    "master_validation_failed",
                    master_id=master.id,
                    master_title=master.title,
                    requested_artist=artist,
                    requested_track=track_title,
                    found_artists=[a.name for a in master.artists],
                    found_tracks=[t.title for t in master.tracklist],
                )
            else:
                logger.info(
                    "master_validation_success",
                    master_id=master.id,
                    master_title=master.title,
                    artist=artist,
                    track_title=track_title,
                )

        return master

    @staticmethod
    def parse_release_response(
        data: Dict[str, Any],
        artist: Optional[str] = None,
        track_title: Optional[str] = None,
    ) -> DiscogsRelease:
        """
        Parse Discogs release response into validated model.

        Optionally validates that the specified artist and track title appear
        on the release. If validation fails, sets is_exact_match=False.

        Args:
            data: Raw release response from Discogs API
            artist: Artist name to validate (checks main artists only)
            track_title: Track title to validate (searches entire tracklist)

        Returns:
            Validated DiscogsRelease model with is_exact_match flag

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get_release(25823602)
            >>> release = DiscogsParser.parse_release_response(
            ...     response, artist="Nirvana", track_title="Lithium"
            ... )
            >>> print(release.is_exact_match)
            True
        """
        release = DiscogsRelease.model_validate(data)

        # If validation requested, check artist and track
        if artist is not None or track_title is not None:
            is_match = DiscogsParser._validate_artist_and_track(
                artists=release.artists,
                tracklist=release.tracklist,
                artist=artist,
                track_title=track_title,
            )
            release.is_exact_match = is_match

            if not is_match:
                logger.warning(
                    "release_validation_failed",
                    release_id=release.id,
                    release_title=release.title,
                    requested_artist=artist,
                    requested_track=track_title,
                    found_artists=[a.name for a in release.artists],
                    found_tracks=[t.title for t in release.tracklist],
                )
            else:
                logger.info(
                    "release_validation_success",
                    release_id=release.id,
                    release_title=release.title,
                    artist=artist,
                    track_title=track_title,
                )

        return release

    @staticmethod
    def parse_artist_releases_response(
        data: Dict[str, Any],
    ) -> DiscogsArtistReleasesResult:
        """
        Parse Discogs artist releases response into validated model.

        Filters results to only include type "master" releases.

        Args:
            data: Raw artist releases response from Discogs API

        Returns:
            Validated DiscogsArtistReleasesResult with only master releases

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get_artist_releases(125246)
            >>> releases = DiscogsParser.parse_artist_releases_response(response)
            >>> print(f"Found {len(releases.releases)} master releases")
            'Found 45 master releases'
        """
        # Parse full response
        full_result = DiscogsArtistReleasesResult.model_validate(data)

        # Filter to master releases only
        master_releases = [r for r in full_result.releases if r.type == "master"]

        logger.debug(
            "filtered_artist_releases",
            total_releases=len(full_result.releases),
            master_releases=len(master_releases),
        )

        # Return filtered result
        return DiscogsArtistReleasesResult(
            pagination=full_result.pagination,
            releases=master_releases,
        )

    @staticmethod
    def find_earliest_master(
        search_results: DiscogsSearchResult,
        artist: Optional[str] = None,
        track_title: Optional[str] = None,
    ) -> DiscogsSearchResultItem:
        """
        Find the earliest master release from search results.

        Filters to master type results, finds the earliest year, and returns
        the result with the lowest master_id from that year (as a tie-breaker).

        Args:
            search_results: Validated search results
            artist: Artist name for logging context (optional)
            track_title: Track title for logging context (optional)

        Returns:
            DiscogsSearchResultItem with earliest year and lowest master_id

        Raises:
            EmptySearchResultsError: If no master releases found in results

        Example:
            >>> results = DiscogsParser.parse_search_response(response)
            >>> earliest = DiscogsParser.find_earliest_master(results, "Nirvana", "Nevermind")
            >>> print(f"Master ID: {earliest.master_id}, Year: {earliest.year}")
            'Master ID: 13814, Year: 1992'
        """
        # Filter to master type results
        master_results = [r for r in search_results.results if r.type == "master"]

        if not master_results:
            logger.warning(
                "no_master_releases_in_search",
                artist=artist,
                title=track_title,
                total_results=len(search_results.results),
            )
            raise EmptySearchResultsError(artist=artist, title=track_title)

        logger.debug(
            "searching_for_earliest_master",
            artist=artist,
            title=track_title,
            master_count=len(master_results),
        )

        # Find earliest year (convert to int, handle None)
        results_with_years = []
        for result in master_results:
            try:
                year = int(result.year) if result.year else 9999
                results_with_years.append((result, year))
            except (ValueError, TypeError):
                # Skip results with invalid years
                logger.debug(
                    "skipping_result_invalid_year",
                    master_id=result.master_id,
                    year=result.year,
                )
                continue

        if not results_with_years:
            logger.warning(
                "no_valid_years_in_results",
                artist=artist,
                title=track_title,
            )
            raise EmptySearchResultsError(artist=artist, title=track_title)

        # Sort by year (ascending), then by master_id (ascending)
        results_with_years.sort(key=lambda x: (x[1], x[0].master_id or 9999999))

        earliest = results_with_years[0][0]
        earliest_year = results_with_years[0][1]

        # Find all results from the same year for logging
        same_year_results = [r for r, y in results_with_years if y == earliest_year]

        logger.info(
            "earliest_master_found",
            master_id=earliest.master_id,
            year=earliest_year,
            title=earliest.title,
            same_year_count=len(same_year_results),
            artist=artist,
            track_title=track_title,
        )

        return earliest

    @staticmethod
    def _filter_music_videos(videos: List[DiscogsVideo]) -> List[DiscogsVideo]:
        """
        Filter video list to music videos only.

        Excludes videos with "audio", "lyric", or "live" in title (case-insensitive).

        Args:
            videos: List of DiscogsVideo objects

        Returns:
            Filtered list containing only music videos

        Example:
            >>> videos = master.videos
            >>> music_videos = DiscogsParser._filter_music_videos(videos)
            >>> print(f"Found {len(music_videos)} music videos")
            'Found 4 music videos'
        """
        excluded_keywords = ["audio", "lyric", "live"]

        filtered = []
        for video in videos:
            title_lower = video.title.lower()
            if not any(keyword in title_lower for keyword in excluded_keywords):
                filtered.append(video)
            else:
                logger.debug(
                    "excluding_video",
                    title=video.title,
                    reason="contains excluded keyword",
                )

        logger.debug(
            "filtered_videos",
            original_count=len(videos),
            filtered_count=len(filtered),
        )

        return filtered

    @staticmethod
    def _validate_artist_and_track(
        artists: List[Any],
        tracklist: List[Any],
        artist: Optional[str] = None,
        track_title: Optional[str] = None,
    ) -> bool:
        """
        Validate that artist and/or track appear in release.

        Checks main artists only (not extraartists). Track can appear in any
        position on tracklist. Uses normalized exact matching.

        Args:
            artists: List of DiscogsArtist objects
            tracklist: List of DiscogsTrack objects
            artist: Artist name to validate (optional)
            track_title: Track title to validate (optional)

        Returns:
            True if all specified criteria match, False otherwise
        """
        artist_match = True
        track_match = True

        # Validate artist if specified
        if artist is not None:
            normalized_artist = normalize_for_matching(artist)
            artist_match = any(
                normalize_for_matching(a.name) == normalized_artist for a in artists
            )

            logger.debug(
                "artist_validation",
                requested=artist,
                normalized=normalized_artist,
                found_artists=[a.name for a in artists],
                match=artist_match,
            )

        # Validate track if specified
        if track_title is not None:
            normalized_track = normalize_for_matching(track_title)
            track_match = any(
                normalize_for_matching(t.title) == normalized_track for t in tracklist
            )

            logger.debug(
                "track_validation",
                requested=track_title,
                normalized=normalized_track,
                found_tracks=[t.title for t in tracklist],
                match=track_match,
            )

        return artist_match and track_match
