"""Spotify playlist importer workflow for importing tracks into the database."""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import structlog

import fuzzbin

from ..api.spotify_client import SpotifyClient
from ..common.genre_buckets import classify_genres
from ..common.string_utils import normalize_spotify_title
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
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ):
        """
        Initialize playlist importer.

        Args:
            spotify_client: Configured SpotifyClient instance
            video_repository: Database repository
            initial_status: Status for newly imported tracks (default: "discovered")
            skip_existing: Skip tracks that already exist in database (default: True)
            progress_callback: Optional callback for progress updates.
                Signature: (processed: int, total: int, current_item: str) -> None
        """
        self.spotify_client = spotify_client
        self.repository = video_repository
        self.initial_status = initial_status
        self.skip_existing = skip_existing
        self.progress_callback = progress_callback
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

        # Collect unique primary artist IDs and fetch their full details (including genres)
        artist_genres_map = await self._fetch_artist_genres(tracks)

        # Import tracks
        result = await self._import_tracks(
            playlist_id=playlist_id,
            playlist_name=playlist.name,
            tracks=tracks,
            artist_genres_map=artist_genres_map,
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

    async def _fetch_artist_genres(self, tracks: List[SpotifyTrack]) -> Dict[str, List[str]]:
        """
        Fetch genres for all primary artists in the track list.

        Collects unique primary artist IDs from all tracks and fetches their
        full artist details (including genres) in batches of up to 50.

        Args:
            tracks: List of Spotify tracks

        Returns:
            Dictionary mapping artist ID to list of genre strings
        """
        # Collect unique primary artist IDs
        artist_ids = []
        seen = set()
        for track in tracks:
            if track.artists:
                primary_artist_id = track.artists[0].id
                if primary_artist_id not in seen:
                    seen.add(primary_artist_id)
                    artist_ids.append(primary_artist_id)

        if not artist_ids:
            return {}

        self.logger.info(
            "spotify_fetching_artist_genres",
            artist_count=len(artist_ids),
        )

        # Fetch full artist details (includes genres)
        artists = await self.spotify_client.get_artists(artist_ids)

        # Build mapping
        artist_genres_map = {artist.id: artist.genres for artist in artists}

        self.logger.info(
            "spotify_artist_genres_fetched",
            artists_with_genres=sum(1 for g in artist_genres_map.values() if g),
            total_artists=len(artist_genres_map),
        )

        return artist_genres_map

    async def _import_tracks(
        self,
        playlist_id: str,
        playlist_name: str,
        tracks: List[SpotifyTrack],
        artist_genres_map: Dict[str, List[str]],
    ) -> ImportResult:
        """
        Import list of tracks into database.

        Args:
            playlist_id: Spotify playlist ID
            playlist_name: Playlist name
            tracks: List of Spotify tracks to import
            artist_genres_map: Mapping of artist ID to list of genres

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
                # Call progress callback if provided
                if self.progress_callback:
                    track_name = track.name or "Unknown"
                    artist_name = track.artists[0].name if track.artists else "Unknown"
                    self.progress_callback(idx, len(tracks), f"{artist_name} - {track_name}")

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
                    video_id = await self._import_single_track(track, artist_genres_map)

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

    async def _import_single_track(
        self, track: SpotifyTrack, artist_genres_map: Dict[str, List[str]]
    ) -> Optional[int]:
        """
        Import a single track into the database.

        Args:
            track: Spotify track to import
            artist_genres_map: Mapping of artist ID to list of genres

        Returns:
            Video ID if successful, None if failed

        Raises:
            Exception: If import fails
        """
        # Get primary artist's genres
        artist_genres: List[str] = []
        if track.artists:
            primary_artist_id = track.artists[0].id
            artist_genres = artist_genres_map.get(primary_artist_id, [])

        # Map track to video data
        video_data = self._map_track_to_video_data(track, artist_genres)

        # Create video record
        video_id = await self.repository.create_video(**video_data)

        # Auto-add decade tag if year provided and auto_decade enabled
        if video_data.get("year"):
            config = fuzzbin.get_config()
            if config.tags.auto_decade.enabled:
                await self.repository.auto_add_decade_tag(
                    video_id, video_data["year"], tag_format=config.tags.auto_decade.format
                )

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

    def _map_track_to_video_data(
        self, track: SpotifyTrack, artist_genres: List[str]
    ) -> Dict[str, Any]:
        """
        Map Spotify track to video database fields.

        Args:
            track: Spotify track
            artist_genres: List of genre strings from the primary artist

        Returns:
            Dictionary suitable for repository.create_video()
        """
        # Extract year from album release date
        year = None
        if track.album and track.album.release_date:
            year = SpotifyParser.extract_year_from_release_date(track.album.release_date)

        # Classify genres to get broad bucket
        bucket, _ = classify_genres(artist_genres)

        # Serialize source genres as JSON if present
        source_genres_json = json.dumps(artist_genres) if artist_genres else None

        # Map to video fields
        return {
            "title": track.name,
            "artist": track.artists[0].name if track.artists else None,
            "album": track.album.name if track.album else None,
            "year": year,
            "genre": bucket,
            "source_genres": source_genres_json,
            "status": self.initial_status,
            "download_source": "spotify",
            "isrc": track.isrc,
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
            # Normalize incoming Spotify titles for comparison
            normalized_title = normalize_spotify_title(
                track.name,
                remove_version_qualifiers_flag=True,
                remove_featured=True,
            )

            # Query by artist first (more selective)
            query = self.repository.query()
            query = query.where_artist(track.artists[0].name)
            results = await query.execute()

            # Compare normalized titles to avoid false negatives
            # (e.g., "Jump" vs "Jump - 2015 Remaster")
            for result in results:
                db_title = result.get("title", "")
                db_normalized = normalize_spotify_title(
                    db_title,
                    remove_version_qualifiers_flag=True,
                    remove_featured=True,
                )
                if db_normalized == normalized_title:
                    self.logger.debug(
                        "duplicate_found",
                        spotify_title=track.name,
                        db_title=db_title,
                        normalized_title=normalized_title,
                    )
                    return True

            return False

        except Exception as e:
            # If query fails, assume doesn't exist
            self.logger.warning(
                "track_exists_check_failed",
                track_id=track.id,
                error=str(e),
            )
            return False
