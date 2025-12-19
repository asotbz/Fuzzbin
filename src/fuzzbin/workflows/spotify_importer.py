"""Spotify playlist importer workflow for importing tracks into the database."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

from ..api.spotify_client import SpotifyClient
from ..core.db.repository import VideoRepository
from ..parsers.spotify_models import SpotifyTrack
from ..parsers.spotify_parser import SpotifyParser


logger = structlog.get_logger(__name__)


@dataclass
class ImportResult:
    """Result of playlist import operation."""

    playlist_id: str
    playlist_name: str
    total_tracks: int
    imported_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    failed_tracks: List[Dict[str, str]] = field(default_factory=list)
    duration_seconds: float = 0.0


class SpotifyPlaylistImporter:
    """
    Import Spotify playlist tracks into the video database.

    This workflow:
    1. Fetches playlist metadata from Spotify
    2. Retrieves all tracks (handling pagination)
    3. Maps Spotify track data to database schema
    4. Creates video and artist records
    5. Links artists to videos via junction table
    6. Reports import statistics

    Example:
        >>> import asyncio
        >>> from fuzzbin.api.spotify_client import SpotifyClient
        >>> from fuzzbin.core.db.repository import VideoRepository
        >>> from fuzzbin.workflows.spotify_importer import SpotifyPlaylistImporter
        >>>
        >>> async def main():
        ...     spotify_client = SpotifyClient.from_config(config.apis["spotify"])
        ...     repository = await VideoRepository.from_config(config.database)
        ...
        ...     importer = SpotifyPlaylistImporter(
        ...         spotify_client=spotify_client,
        ...         video_repository=repository,
        ...         initial_status="discovered",
        ...         skip_existing=True,
        ...     )
        ...
        ...     result = await importer.import_playlist("37i9dQZF1DXcBWIGoYBM5M")
        ...     print(f"Imported {result.imported_count} tracks")
        ...
        ...     await repository.close()
        ...     await spotify_client.aclose()
        >>>
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        spotify_client: SpotifyClient,
        video_repository: VideoRepository,
        initial_status: str = "discovered",
        skip_existing: bool = True,
    ):
        """
        Initialize playlist importer.

        Args:
            spotify_client: Configured SpotifyClient instance
            video_repository: Database repository
            initial_status: Status for newly imported tracks (default: "discovered")
            skip_existing: Skip tracks that already exist in database (default: True)
        """
        self.spotify_client = spotify_client
        self.repository = video_repository
        self.initial_status = initial_status
        self.skip_existing = skip_existing
        self.logger = structlog.get_logger(__name__)

    async def import_playlist(self, playlist_id: str) -> ImportResult:
        """
        Import all tracks from a Spotify playlist into the database.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            ImportResult with statistics about the import operation

        Raises:
            httpx.HTTPStatusError: If Spotify API returns an error
            QueryError: If database operations fail

        Example:
            >>> result = await importer.import_playlist("37i9dQZF1DXcBWIGoYBM5M")
            >>> print(f"Imported: {result.imported_count}/{result.total_tracks}")
            >>> print(f"Skipped: {result.skipped_count}, Failed: {result.failed_count}")
        """
        start_time = time.time()

        # Fetch playlist metadata
        self.logger.info("spotify_import_start", playlist_id=playlist_id)
        playlist = await self.spotify_client.get_playlist(playlist_id)

        # Fetch all tracks
        tracks = await self.spotify_client.get_all_playlist_tracks(playlist_id)

        self.logger.info(
            "spotify_playlist_fetched",
            playlist_id=playlist_id,
            playlist_name=playlist.name,
            total_tracks=len(tracks),
        )

        # Import tracks
        result = await self._import_tracks(
            playlist_id=playlist_id,
            playlist_name=playlist.name,
            tracks=tracks,
        )

        result.duration_seconds = time.time() - start_time

        self.logger.info(
            "spotify_import_complete",
            playlist_id=playlist_id,
            imported=result.imported_count,
            skipped=result.skipped_count,
            failed=result.failed_count,
            duration=result.duration_seconds,
        )

        return result

    async def _import_tracks(
        self,
        playlist_id: str,
        playlist_name: str,
        tracks: List[SpotifyTrack],
    ) -> ImportResult:
        """
        Import list of tracks into database.

        Args:
            playlist_id: Spotify playlist ID
            playlist_name: Playlist name
            tracks: List of Spotify tracks to import

        Returns:
            ImportResult with statistics
        """
        result = ImportResult(
            playlist_id=playlist_id,
            playlist_name=playlist_name,
            total_tracks=len(tracks),
        )

        # Import each track within a transaction
        async with self.repository.transaction():
            for idx, track in enumerate(tracks, start=1):
                try:
                    # Check if track already exists
                    if self.skip_existing and await self._check_track_exists(track):
                        self.logger.debug(
                            "track_skipped_exists",
                            track_id=track.id,
                            track_name=track.name,
                            artist=track.artists[0].name if track.artists else "Unknown",
                        )
                        result.skipped_count += 1
                        continue

                    # Import track
                    video_id = await self._import_single_track(track)

                    if video_id is not None:
                        result.imported_count += 1

                        # Log progress every 10 tracks
                        if idx % 10 == 0:
                            self.logger.info(
                                "import_progress",
                                processed=idx,
                                total=len(tracks),
                                imported=result.imported_count,
                                skipped=result.skipped_count,
                                failed=result.failed_count,
                            )
                    else:
                        result.failed_count += 1

                except Exception as e:
                    self.logger.error(
                        "track_import_failed",
                        track_id=track.id,
                        track_name=track.name,
                        error=str(e),
                    )
                    result.failed_count += 1
                    result.failed_tracks.append(
                        {
                            "track_id": track.id,
                            "name": track.name,
                            "error": str(e),
                        }
                    )

        return result

    async def _import_single_track(self, track: SpotifyTrack) -> Optional[int]:
        """
        Import a single track into the database.

        Args:
            track: Spotify track to import

        Returns:
            Video ID if successful, None if failed

        Raises:
            Exception: If import fails
        """
        # Map track to video data
        video_data = self._map_track_to_video_data(track)

        # Create video record
        video_id = await self.repository.create_video(**video_data)

        # Upsert artists and link to video
        for position, artist in enumerate(track.artists):
            # Upsert artist
            artist_id = await self.repository.upsert_artist(name=artist.name)

            # Link artist to video
            await self.repository.link_video_artist(
                video_id=video_id,
                artist_id=artist_id,
                role="primary",
                position=position,
            )

        self.logger.info(
            "track_imported",
            video_id=video_id,
            track_id=track.id,
            track_name=track.name,
            artist=track.artists[0].name if track.artists else "Unknown",
            artist_count=len(track.artists),
        )

        return video_id

    def _map_track_to_video_data(self, track: SpotifyTrack) -> Dict[str, Any]:
        """
        Map Spotify track to video database fields.

        Args:
            track: Spotify track

        Returns:
            Dictionary suitable for repository.create_video()
        """
        # Extract year from album release date
        year = None
        if track.album and track.album.release_date:
            year = SpotifyParser.extract_year_from_release_date(
                track.album.release_date
            )

        # Map to video fields
        return {
            "title": track.name,
            "artist": track.artists[0].name if track.artists else None,
            "album": track.album.name if track.album else None,
            "year": year,
            "status": self.initial_status,
            "download_source": "spotify",
        }

    async def _check_track_exists(self, track: SpotifyTrack) -> bool:
        """
        Check if track already exists in database.

        Queries by title + artist combination.

        Args:
            track: Spotify track

        Returns:
            True if track exists, False otherwise
        """
        if not track.artists:
            return False

        try:
            # Query by title and artist
            query = self.repository.query()
            query = query.where_title(track.name)
            query = query.where_artist(track.artists[0].name)

            results = await query.execute()
            return len(results) > 0

        except Exception as e:
            # If query fails, assume doesn't exist
            self.logger.warning(
                "track_exists_check_failed",
                track_id=track.id,
                error=str(e),
            )
            return False
