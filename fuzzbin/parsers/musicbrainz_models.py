"""Pydantic models for MusicBrainz API responses."""

from typing import List, Optional

from pydantic import BaseModel, Field


class MusicBrainzTag(BaseModel):
    """Model for MusicBrainz tag with vote count."""

    name: str = Field(description="Tag name")
    count: int = Field(description="Tag vote count")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class MusicBrainzAlias(BaseModel):
    """Model for MusicBrainz artist alias."""

    name: str = Field(description="Alias name")
    sort_name: Optional[str] = Field(default=None, alias="sort-name", description="Sort name")
    locale: Optional[str] = Field(default=None, description="Locale code")
    type: Optional[str] = Field(default=None, description="Alias type")
    primary: Optional[bool] = Field(default=None, description="Whether this is the primary alias")
    begin_date: Optional[str] = Field(default=None, alias="begin-date", description="Begin date")
    end_date: Optional[str] = Field(default=None, alias="end-date", description="End date")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
        "populate_by_name": True,
    }


class MusicBrainzArea(BaseModel):
    """Model for MusicBrainz area (country/region)."""

    id: str = Field(description="Area MBID")
    name: str = Field(description="Area name")
    sort_name: Optional[str] = Field(default=None, alias="sort-name", description="Sort name")
    iso_3166_1_codes: Optional[List[str]] = Field(
        default=None, alias="iso-3166-1-codes", description="ISO 3166-1 country codes"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
        "populate_by_name": True,
    }


class MusicBrainzLifeSpan(BaseModel):
    """Model for MusicBrainz artist life span."""

    begin: Optional[str] = Field(default=None, description="Start date")
    end: Optional[str] = Field(default=None, description="End date")
    ended: Optional[bool] = Field(default=None, description="Whether the entity has ended")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class MusicBrainzArtist(BaseModel):
    """Model for MusicBrainz artist information."""

    id: str = Field(description="Artist MBID")
    name: str = Field(description="Artist name")
    sort_name: Optional[str] = Field(default=None, alias="sort-name", description="Sort name")
    type: Optional[str] = Field(default=None, description="Artist type (Person, Group, etc.)")
    disambiguation: Optional[str] = Field(default=None, description="Disambiguation comment")
    country: Optional[str] = Field(default=None, description="Country code")
    score: Optional[int] = Field(default=None, description="Search score")
    aliases: Optional[List[MusicBrainzAlias]] = Field(default=None, description="Artist aliases")
    tags: Optional[List[MusicBrainzTag]] = Field(default=None, description="Artist tags")
    life_span: Optional[MusicBrainzLifeSpan] = Field(
        default=None, alias="life-span", description="Artist life span"
    )
    area: Optional[MusicBrainzArea] = Field(default=None, description="Artist area")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
        "populate_by_name": True,
    }


class MusicBrainzArtistCredit(BaseModel):
    """Model for MusicBrainz artist credit entry."""

    name: str = Field(description="Credited name")
    artist: MusicBrainzArtist = Field(description="Artist details")
    joinphrase: Optional[str] = Field(default=None, description="Join phrase (e.g., ' feat. ')")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class MusicBrainzReleaseGroup(BaseModel):
    """Model for MusicBrainz release group."""

    id: str = Field(description="Release group MBID")
    title: Optional[str] = Field(default=None, description="Release group title")
    primary_type: Optional[str] = Field(
        default=None, alias="primary-type", description="Primary type (Album, Single, EP, etc.)"
    )
    secondary_types: Optional[List[str]] = Field(
        default=None,
        alias="secondary-types",
        description="Secondary types (Compilation, Live, etc.)",
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
        "populate_by_name": True,
    }


class MusicBrainzReleaseEvent(BaseModel):
    """Model for MusicBrainz release event."""

    date: Optional[str] = Field(default=None, description="Release date")
    area: Optional[MusicBrainzArea] = Field(default=None, description="Release area")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class MusicBrainzTrack(BaseModel):
    """Model for MusicBrainz track in a media."""

    id: str = Field(description="Track MBID")
    number: Optional[str] = Field(default=None, description="Track number")
    title: str = Field(description="Track title")
    length: Optional[int] = Field(default=None, description="Track length in milliseconds")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class MusicBrainzMedia(BaseModel):
    """Model for MusicBrainz release media (CD, vinyl, etc.)."""

    position: Optional[int] = Field(default=None, description="Media position in release")
    format: Optional[str] = Field(
        default=None, description="Media format (CD, Vinyl, Digital, etc.)"
    )
    track_count: Optional[int] = Field(
        default=None, alias="track-count", description="Number of tracks"
    )
    track_offset: Optional[int] = Field(
        default=None, alias="track-offset", description="Track offset"
    )
    track: Optional[List[MusicBrainzTrack]] = Field(
        default=None, description="Tracks on this media"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
        "populate_by_name": True,
    }


class MusicBrainzRelease(BaseModel):
    """Model for MusicBrainz release."""

    id: str = Field(description="Release MBID")
    title: str = Field(description="Release title")
    status: Optional[str] = Field(
        default=None, description="Release status (Official, Bootleg, etc.)"
    )
    disambiguation: Optional[str] = Field(default=None, description="Disambiguation comment")
    date: Optional[str] = Field(default=None, description="Release date")
    country: Optional[str] = Field(default=None, description="Release country code")
    track_count: Optional[int] = Field(
        default=None, alias="track-count", description="Total track count"
    )
    release_group: Optional[MusicBrainzReleaseGroup] = Field(
        default=None, alias="release-group", description="Release group"
    )
    release_events: Optional[List[MusicBrainzReleaseEvent]] = Field(
        default=None, alias="release-events", description="Release events"
    )
    artist_credit: Optional[List[MusicBrainzArtistCredit]] = Field(
        default=None, alias="artist-credit", description="Artist credits"
    )
    media: Optional[List[MusicBrainzMedia]] = Field(
        default=None, description="Media in this release"
    )
    tags: Optional[List[MusicBrainzTag]] = Field(default=None, description="Release tags")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
        "populate_by_name": True,
    }


class MusicBrainzRecording(BaseModel):
    """Model for MusicBrainz recording (a specific performance/version of a song)."""

    id: str = Field(description="Recording MBID")
    title: str = Field(description="Recording title")
    score: Optional[int] = Field(default=None, description="Search score (0-100)")
    length: Optional[int] = Field(default=None, description="Recording length in milliseconds")
    video: Optional[bool] = Field(default=None, description="Whether this is a video recording")
    disambiguation: Optional[str] = Field(default=None, description="Disambiguation comment")
    first_release_date: Optional[str] = Field(
        default=None, alias="first-release-date", description="First release date"
    )
    artist_credit: Optional[List[MusicBrainzArtistCredit]] = Field(
        default=None, alias="artist-credit", description="Artist credits"
    )
    releases: Optional[List[MusicBrainzRelease]] = Field(
        default=None, description="Releases containing this recording"
    )
    tags: Optional[List[MusicBrainzTag]] = Field(default=None, description="Recording tags")
    isrcs: Optional[List[str]] = Field(default=None, description="ISRCs for this recording")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
        "populate_by_name": True,
    }

    @property
    def artist_name(self) -> Optional[str]:
        """Get the primary artist name from artist credits."""
        if self.artist_credit and len(self.artist_credit) > 0:
            return self.artist_credit[0].name
        return None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get duration in seconds from length in milliseconds."""
        if self.length:
            return self.length / 1000.0
        return None


class MusicBrainzRecordingSearchResponse(BaseModel):
    """Model for MusicBrainz recording search response."""

    created: Optional[str] = Field(default=None, description="Response creation timestamp")
    count: int = Field(description="Total number of matching recordings")
    offset: int = Field(default=0, description="Current offset in results")
    recordings: List[MusicBrainzRecording] = Field(
        default_factory=list, description="List of recordings"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class MusicBrainzArtistSearchResponse(BaseModel):
    """Model for MusicBrainz artist search response."""

    created: Optional[str] = Field(default=None, description="Response creation timestamp")
    count: int = Field(description="Total number of matching artists")
    offset: int = Field(default=0, description="Current offset in results")
    artists: List[MusicBrainzArtist] = Field(default_factory=list, description="List of artists")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class MusicBrainzISRCResponse(BaseModel):
    """Model for MusicBrainz ISRC lookup response."""

    isrc: Optional[str] = Field(default=None, description="The ISRC code")
    recordings: List[MusicBrainzRecording] = Field(
        default_factory=list, description="Recordings with this ISRC"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


# Custom Exceptions
class RecordingNotFoundError(ValueError):
    """Raised when a recording cannot be found matching the search criteria."""

    def __init__(
        self,
        artist: Optional[str] = None,
        recording: Optional[str] = None,
        isrc: Optional[str] = None,
        mbid: Optional[str] = None,
        message: Optional[str] = None,
    ):
        """
        Initialize RecordingNotFoundError.

        Args:
            artist: Artist name searched for
            recording: Recording title searched for
            isrc: ISRC code searched for
            mbid: MusicBrainz ID searched for
            message: Custom error message (overrides default)
        """
        if message:
            super().__init__(message)
        elif mbid:
            super().__init__(f"Recording not found for MBID '{mbid}'")
        elif isrc:
            super().__init__(f"Recording not found for ISRC '{isrc}'")
        elif artist and recording:
            super().__init__(
                f"Recording not found for artist '{artist}' and recording '{recording}'"
            )
        else:
            super().__init__("Recording not found")
        self.artist = artist
        self.recording = recording
        self.isrc = isrc
        self.mbid = mbid
