"""Spotify API routes for playlist and track access.

These endpoints provide access to the Spotify Web API through the shared
SpotifyClient, with proper rate limiting, caching, and authentication.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
import structlog

from fuzzbin.api.spotify_client import SpotifyClient

from ..dependencies import get_spotify_client
from ..schemas.spotify import (
    SpotifyAllTracksResponseSchema,
    SpotifyPlaylistSchema,
    SpotifyPlaylistTracksResponseSchema,
    SpotifyTrackSchema,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/spotify", tags=["Spotify"])


@router.get(
    "/playlists/{playlist_id}",
    response_model=SpotifyPlaylistSchema,
    summary="Get playlist metadata",
    description="Retrieve metadata for a Spotify playlist by ID.",
)
async def get_playlist(
    playlist_id: str,
    client: SpotifyClient = Depends(get_spotify_client),
) -> SpotifyPlaylistSchema:
    """
    Get metadata for a Spotify playlist.

    Args:
        playlist_id: Spotify playlist ID (e.g., "37i9dQZF1DXcBWIGoYBM5M")

    Returns:
        Playlist metadata including name, owner, and track count

    Raises:
        HTTPException(404): Playlist not found
        HTTPException(503): Spotify API unavailable
    """
    logger.debug("spotify_get_playlist", playlist_id=playlist_id)

    try:
        playlist = await client.get_playlist(playlist_id)
        return SpotifyPlaylistSchema.model_validate(playlist.model_dump())
    except Exception as e:
        error_message = str(e)
        if "404" in error_message or "not found" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Playlist not found: {playlist_id}",
            )
        logger.error("spotify_get_playlist_error", playlist_id=playlist_id, error=error_message)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch playlist from Spotify: {error_message}",
        )


@router.get(
    "/playlists/{playlist_id}/tracks",
    response_model=SpotifyPlaylistTracksResponseSchema,
    summary="Get playlist tracks (paginated)",
    description="Retrieve tracks from a Spotify playlist with pagination.",
)
async def get_playlist_tracks(
    playlist_id: str,
    limit: int = Query(default=50, ge=1, le=100, description="Items per page (max 100)"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    client: SpotifyClient = Depends(get_spotify_client),
) -> SpotifyPlaylistTracksResponseSchema:
    """
    Get tracks from a Spotify playlist with pagination.

    Args:
        playlist_id: Spotify playlist ID
        limit: Maximum number of tracks to return (1-100)
        offset: Number of tracks to skip

    Returns:
        Paginated list of playlist tracks with navigation links

    Raises:
        HTTPException(404): Playlist not found
        HTTPException(503): Spotify API unavailable
    """
    logger.debug(
        "spotify_get_playlist_tracks",
        playlist_id=playlist_id,
        limit=limit,
        offset=offset,
    )

    try:
        tracks_response = await client.get_playlist_tracks(
            playlist_id=playlist_id, limit=limit, offset=offset
        )
        return SpotifyPlaylistTracksResponseSchema.model_validate(tracks_response.model_dump())
    except Exception as e:
        error_message = str(e)
        if "404" in error_message or "not found" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Playlist not found: {playlist_id}",
            )
        logger.error(
            "spotify_get_playlist_tracks_error",
            playlist_id=playlist_id,
            error=error_message,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch playlist tracks from Spotify: {error_message}",
        )


@router.get(
    "/playlists/{playlist_id}/tracks/all",
    response_model=SpotifyAllTracksResponseSchema,
    summary="Get all playlist tracks",
    description="Retrieve all tracks from a Spotify playlist (handles pagination automatically).",
)
async def get_all_playlist_tracks(
    playlist_id: str,
    client: SpotifyClient = Depends(get_spotify_client),
) -> SpotifyAllTracksResponseSchema:
    """
    Get all tracks from a Spotify playlist.

    This endpoint automatically handles pagination and returns all tracks
    in the playlist. For large playlists, this may take longer as it needs
    to fetch multiple pages.

    Args:
        playlist_id: Spotify playlist ID

    Returns:
        All tracks in the playlist with total count

    Raises:
        HTTPException(404): Playlist not found
        HTTPException(503): Spotify API unavailable
    """
    logger.debug("spotify_get_all_playlist_tracks", playlist_id=playlist_id)

    try:
        tracks = await client.get_all_playlist_tracks(playlist_id)
        return SpotifyAllTracksResponseSchema(
            playlist_id=playlist_id,
            total=len(tracks),
            tracks=[SpotifyTrackSchema.model_validate(t.model_dump()) for t in tracks],
        )
    except Exception as e:
        error_message = str(e)
        if "404" in error_message or "not found" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Playlist not found: {playlist_id}",
            )
        logger.error(
            "spotify_get_all_playlist_tracks_error",
            playlist_id=playlist_id,
            error=error_message,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch all playlist tracks from Spotify: {error_message}",
        )


@router.get(
    "/tracks/{track_id}",
    response_model=SpotifyTrackSchema,
    summary="Get track metadata",
    description="Retrieve metadata for a Spotify track by ID.",
)
async def get_track(
    track_id: str,
    client: SpotifyClient = Depends(get_spotify_client),
) -> SpotifyTrackSchema:
    """
    Get metadata for a Spotify track.

    Args:
        track_id: Spotify track ID (e.g., "11dFghVXANMlKmJXsNCbNl")

    Returns:
        Track metadata including name, artists, album, and duration

    Raises:
        HTTPException(404): Track not found
        HTTPException(503): Spotify API unavailable
    """
    logger.debug("spotify_get_track", track_id=track_id)

    try:
        track = await client.get_track(track_id)
        return SpotifyTrackSchema.model_validate(track.model_dump())
    except Exception as e:
        error_message = str(e)
        if "404" in error_message or "not found" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Track not found: {track_id}",
            )
        logger.error("spotify_get_track_error", track_id=track_id, error=error_message)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch track from Spotify: {error_message}",
        )
