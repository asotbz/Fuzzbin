"""Parser for IMVDb API responses."""

from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import structlog

from ..common.string_utils import normalize_for_matching
from .imvdb_models import (
    EmptySearchResultsError,
    IMVDbEntity,
    IMVDbEntitySearchResponse,
    IMVDbEntitySearchResult,
    IMVDbEntityVideo,
    IMVDbPagination,
    IMVDbVideo,
    IMVDbVideoSearchResult,
    VideoNotFoundError,
)

logger = structlog.get_logger(__name__)


class IMVDbParser:
    """Parser for IMVDb API responses with domain methods for video matching."""

    @staticmethod
    def parse_video(data: Dict[str, Any]) -> IMVDbVideo:
        """
        Parse IMVDb video response into validated model.

        Args:
            data: Raw video response from IMVDb API

        Returns:
            Validated IMVDbVideo model

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get("/video/121779770452")
            >>> video = IMVDbParser.parse_video(response.json())
            >>> print(video.song_title)
            'Blurred Lines'
        """
        return IMVDbVideo.model_validate(data)

    @staticmethod
    def parse_entity(data: Dict[str, Any]) -> IMVDbEntity:
        """
        Parse IMVDb entity response into validated model.

        Args:
            data: Raw entity response from IMVDb API

        Returns:
            Validated IMVDbEntity model

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get("/entity/838673")
            >>> entity = IMVDbParser.parse_entity(response.json())
            >>> print(entity.slug)
            'robin-thicke'
        """
        # Extract nested video lists and totals
        artist_videos_data = data.get("artist_videos", {})
        featured_videos_data = data.get("featured_artist_videos", {})

        # Prepare entity data with flattened structure
        entity_data = {
            **data,
            "artist_videos": artist_videos_data.get("videos", []),
            "featured_artist_videos": featured_videos_data.get("videos", []),
            "artist_videos_total": artist_videos_data.get("total_videos"),
            "featured_videos_total": featured_videos_data.get("total_videos"),
        }

        return IMVDbEntity.model_validate(entity_data)

    @staticmethod
    def parse_search_results(data: Dict[str, Any]) -> IMVDbVideoSearchResult:
        """
        Parse IMVDb search results response into validated model.

        Args:
            data: Raw search results response from IMVDb API

        Returns:
            Validated IMVDbVideoSearchResult model with pagination metadata

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get("/search/videos", params={"q": "blurred lines"})
            >>> results = IMVDbParser.parse_search_results(response.json())
            >>> print(f"Found {results.pagination.total_results} videos")
            'Found 196 videos'
        """
        pagination = IMVDbPagination(
            total_results=data.get("total_results", 0),
            current_page=data.get("current_page", 1),
            per_page=data.get("per_page", 25),
            total_pages=data.get("total_pages", 0),
        )

        return IMVDbVideoSearchResult(
            pagination=pagination,
            results=data.get("results", []),
        )

    @staticmethod
    def parse_entity_search_results(data: Dict[str, Any]):
        """
        Parse IMVDb entity search results response into validated model.

        Args:
            data: Raw entity search results response from IMVDb API

        Returns:
            Validated IMVDbEntitySearchResponse model with pagination metadata

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get("/search/entities", params={"q": "robin thicke"})
            >>> results = IMVDbParser.parse_entity_search_results(response.json())
            >>> print(f"Found {results.pagination.total_results} entities")
            'Found 386 entities'
            >>> print(results.results[0].discogs_id)
            61556
        """
        pagination = IMVDbPagination(
            total_results=data.get("total_results", 0),
            current_page=data.get("current_page", 1),
            per_page=data.get("per_page", 25),
            total_pages=data.get("total_pages", 0),
        )

        return IMVDbEntitySearchResponse(
            pagination=pagination,
            results=data.get("results", []),
        )

    @staticmethod
    def find_best_video_match(
        results: List[IMVDbEntityVideo],
        artist: str,
        title: str,
        threshold: float = 0.8,
    ) -> IMVDbVideo:
        """
        Find the best matching video from search results.

        Uses normalized exact matching first, then falls back to fuzzy matching
        with SequenceMatcher if no exact match is found. Returns the highest-scoring
        match above the threshold.

        Args:
            results: List of video results from search
            artist: Artist name to match (will be normalized)
            title: Song title to match (will be normalized)
            threshold: Minimum similarity score for fuzzy matching (0.0-1.0, default: 0.8)

        Returns:
            IMVDbVideo with best match, includes is_exact_match field

        Raises:
            EmptySearchResultsError: If results list is empty
            VideoNotFoundError: If no match found above threshold

        Example:
            >>> results = search_results.results
            >>> video = IMVDbParser.find_best_video_match(results, "Robin Thicke", "Blurred Lines")
            >>> print(video.is_exact_match)
            True
        """
        if not results:
            logger.warning("empty_search_results", artist=artist, title=title)
            raise EmptySearchResultsError(artist=artist, title=title)

        # Normalize search criteria
        normalized_artist = normalize_for_matching(artist)
        normalized_title = normalize_for_matching(title)

        logger.debug(
            "searching_for_video_match",
            artist=artist,
            title=title,
            normalized_artist=normalized_artist,
            normalized_title=normalized_title,
            result_count=len(results),
        )

        # First attempt: exact normalized match on primary artists only
        for video in results:
            video_title = normalize_for_matching(video.song_title or "")

            # Check if any primary artist matches
            for video_artist in video.artists:
                video_artist_name = normalize_for_matching(video_artist.name)

                if video_artist_name == normalized_artist and video_title == normalized_title:
                    logger.info(
                        "exact_match_found",
                        video_id=video.id,
                        artist=video_artist.name,
                        title=video.song_title,
                    )
                    # Convert to full IMVDbVideo model
                    video_data = video.model_dump()
                    video_data["is_exact_match"] = True
                    return IMVDbVideo.model_validate(video_data)

        # Second attempt: fuzzy matching with scoring
        logger.debug("no_exact_match_attempting_fuzzy_match", threshold=threshold)

        best_match: Optional[IMVDbEntityVideo] = None
        best_score: float = 0.0
        candidates: List[tuple[IMVDbEntityVideo, float, str]] = []

        for video in results:
            video_title = normalize_for_matching(video.song_title or "")

            # Check each primary artist
            for video_artist in video.artists:
                video_artist_name = normalize_for_matching(video_artist.name)

                # Combine artist + title for fuzzy matching
                search_string = f"{normalized_artist} {normalized_title}"
                video_string = f"{video_artist_name} {video_title}"

                # Calculate similarity
                score = SequenceMatcher(None, search_string, video_string).ratio()

                if score > threshold:
                    candidates.append((video, score, video_artist.name))
                    if score > best_score:
                        best_score = score
                        best_match = video

        if best_match:
            # Log warning about fuzzy match
            candidate_info = [
                {"id": v.id, "artist": a, "title": v.song_title, "score": round(s, 3)}
                for v, s, a in sorted(candidates, key=lambda x: x[1], reverse=True)
            ]

            logger.warning(
                "fuzzy_match_found",
                video_id=best_match.id,
                score=round(best_score, 3),
                threshold=threshold,
                candidates=candidate_info,
            )

            # Convert to full IMVDbVideo model with is_exact_match=False
            video_data = best_match.model_dump()
            video_data["is_exact_match"] = False
            return IMVDbVideo.model_validate(video_data)

        # No match found
        logger.error(
            "no_match_found",
            artist=artist,
            title=title,
            threshold=threshold,
            result_count=len(results),
        )
        raise VideoNotFoundError(artist=artist, title=title)
