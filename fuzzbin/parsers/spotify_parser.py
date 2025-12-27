"""Parser for Spotify Web API responses."""

from typing import Any, Dict, Optional

import structlog

from .spotify_models import (
    SpotifyAlbum,
    SpotifyPlaylist,
    SpotifyPlaylistTracksResponse,
    SpotifyTrack,
)

logger = structlog.get_logger(__name__)


class SpotifyParser:
    """Parser for Spotify Web API responses."""

    @staticmethod
    def parse_playlist(data: Dict[str, Any]) -> SpotifyPlaylist:
        """
        Parse Spotify playlist response.

        Args:
            data: Raw playlist response from Spotify API

        Returns:
            Validated SpotifyPlaylist model
        """
        return SpotifyPlaylist.model_validate(data)

    @staticmethod
    def parse_playlist_tracks(data: Dict[str, Any]) -> SpotifyPlaylistTracksResponse:
        """
        Parse Spotify playlist tracks response.

        Args:
            data: Raw tracks response from Spotify API

        Returns:
            Validated SpotifyPlaylistTracksResponse model
        """
        return SpotifyPlaylistTracksResponse.model_validate(data)

    @staticmethod
    def parse_track(data: Dict[str, Any]) -> SpotifyTrack:
        """
        Parse Spotify track response.

        Args:
            data: Raw track response from Spotify API

        Returns:
            Validated SpotifyTrack model
        """
        return SpotifyTrack.model_validate(data)

    @staticmethod
    def parse_album(data: Dict[str, Any]) -> SpotifyAlbum:
        """
        Parse Spotify album response.

        Args:
            data: Raw album response from Spotify API

        Returns:
            Validated SpotifyAlbum model
        """
        return SpotifyAlbum.model_validate(data)

    @staticmethod
    def extract_year_from_release_date(release_date: Optional[str]) -> Optional[int]:
        """
        Extract year from Spotify release date string.

        Spotify returns dates in format: YYYY, YYYY-MM, or YYYY-MM-DD

        Args:
            release_date: Release date string from Spotify

        Returns:
            Year as integer, or None if invalid

        Example:
            >>> SpotifyParser.extract_year_from_release_date("2013-03-26")
            2013
            >>> SpotifyParser.extract_year_from_release_date("2013-03")
            2013
            >>> SpotifyParser.extract_year_from_release_date("2013")
            2013
            >>> SpotifyParser.extract_year_from_release_date(None)
            None
        """
        if not release_date:
            return None

        try:
            # Split by '-' and take first part
            year_str = release_date.split("-")[0]
            return int(year_str)
        except (ValueError, IndexError):
            logger.warning("invalid_release_date", release_date=release_date)
            return None
