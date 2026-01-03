"""Parser for MusicBrainz API responses."""

from typing import Any, Dict, List

import structlog

from .musicbrainz_models import (
    MusicBrainzArtist,
    MusicBrainzArtistSearchResponse,
    MusicBrainzISRCResponse,
    MusicBrainzRecording,
    MusicBrainzRecordingSearchResponse,
    MusicBrainzRelease,
)

logger = structlog.get_logger(__name__)


class MusicBrainzParser:
    """Parser for MusicBrainz API responses."""

    @staticmethod
    def parse_recording(data: Dict[str, Any]) -> MusicBrainzRecording:
        """
        Parse MusicBrainz recording response into validated model.

        Args:
            data: Raw recording response from MusicBrainz API

        Returns:
            Validated MusicBrainzRecording model

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get("/recording/{mbid}")
            >>> recording = MusicBrainzParser.parse_recording(response.json())
            >>> print(recording.title)
            'Smells Like Teen Spirit'
        """
        return MusicBrainzRecording.model_validate(data)

    @staticmethod
    def parse_recording_search_results(data: Dict[str, Any]) -> MusicBrainzRecordingSearchResponse:
        """
        Parse MusicBrainz recording search results response.

        Args:
            data: Raw search results response from MusicBrainz API

        Returns:
            Validated MusicBrainzRecordingSearchResponse model

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get("/recording", params={"query": "..."})
            >>> results = MusicBrainzParser.parse_recording_search_results(response.json())
            >>> print(f"Found {results.count} recordings")
        """
        return MusicBrainzRecordingSearchResponse.model_validate(data)

    @staticmethod
    def parse_artist(data: Dict[str, Any]) -> MusicBrainzArtist:
        """
        Parse MusicBrainz artist response into validated model.

        Args:
            data: Raw artist response from MusicBrainz API

        Returns:
            Validated MusicBrainzArtist model

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get("/artist/{mbid}")
            >>> artist = MusicBrainzParser.parse_artist(response.json())
            >>> print(artist.name)
            'Nirvana'
        """
        return MusicBrainzArtist.model_validate(data)

    @staticmethod
    def parse_artist_search_results(data: Dict[str, Any]) -> MusicBrainzArtistSearchResponse:
        """
        Parse MusicBrainz artist search results response.

        Args:
            data: Raw search results response from MusicBrainz API

        Returns:
            Validated MusicBrainzArtistSearchResponse model

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get("/artist", params={"query": "..."})
            >>> results = MusicBrainzParser.parse_artist_search_results(response.json())
            >>> print(f"Found {results.count} artists")
        """
        return MusicBrainzArtistSearchResponse.model_validate(data)

    @staticmethod
    def parse_isrc_response(data: Dict[str, Any]) -> MusicBrainzISRCResponse:
        """
        Parse MusicBrainz ISRC lookup response.

        Args:
            data: Raw ISRC lookup response from MusicBrainz API

        Returns:
            Validated MusicBrainzISRCResponse model

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get("/isrc/{isrc_code}")
            >>> result = MusicBrainzParser.parse_isrc_response(response.json())
            >>> print(f"Found {len(result.recordings)} recordings for ISRC")
        """
        return MusicBrainzISRCResponse.model_validate(data)

    @staticmethod
    def parse_recordings_list(data: List[Dict[str, Any]]) -> List[MusicBrainzRecording]:
        """
        Parse a list of recording data into validated models.

        Args:
            data: List of raw recording data from MusicBrainz API

        Returns:
            List of validated MusicBrainzRecording models

        Example:
            >>> recordings = MusicBrainzParser.parse_recordings_list(data["recordings"])
        """
        return [MusicBrainzRecording.model_validate(r) for r in data]

    @staticmethod
    def parse_release(data: Dict[str, Any]) -> MusicBrainzRelease:
        """
        Parse MusicBrainz release response into validated model.

        Args:
            data: Raw release response from MusicBrainz API

        Returns:
            Validated MusicBrainzRelease model

        Raises:
            ValidationError: If response data is invalid

        Example:
            >>> response = await client.get("/release/{mbid}?inc=labels")
            >>> release = MusicBrainzParser.parse_release(response.json())
            >>> print(release.label_info[0].label.name if release.label_info else "No label")
        """
        return MusicBrainzRelease.model_validate(data)
