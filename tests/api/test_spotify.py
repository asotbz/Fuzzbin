"""Tests for Spotify API endpoints."""

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from fuzzbin.api.spotify_client import SpotifyClient
from fuzzbin.parsers.spotify_models import (
    SpotifyAlbum,
    SpotifyArtist,
    SpotifyPlaylist,
    SpotifyPlaylistTrack,
    SpotifyPlaylistTracksResponse,
    SpotifyTrack,
)
from fuzzbin.web.dependencies import get_spotify_client


class TestSpotifyGetPlaylist:
    """Tests for Spotify get playlist endpoint."""

    @pytest.fixture
    def mock_playlist(self):
        """Create a mock playlist response."""
        return SpotifyPlaylist(
            id="37i9dQZF1DXcBWIGoYBM5M",
            name="Today's Top Hits",
            description="The hottest 50 songs in the world right now",
            uri="spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
            owner={"id": "spotify", "display_name": "Spotify"},
            tracks=SpotifyPlaylistTracksResponse(
                href="https://api.spotify.com/v1/playlists/37i9dQZF1DXcBWIGoYBM5M/tracks",
                items=[],
                limit=100,
                next=None,
                offset=0,
                previous=None,
                total=50,
            ),
            public=True,
            collaborative=False,
        )

    @pytest.fixture
    def mock_spotify_client(self, mock_playlist):
        """Create a mock Spotify client."""
        mock_client = MagicMock(spec=SpotifyClient)
        mock_client.get_playlist = AsyncMock(return_value=mock_playlist)
        mock_client.get_playlist_tracks = AsyncMock()
        mock_client.get_all_playlist_tracks = AsyncMock()
        mock_client.get_track = AsyncMock()
        return mock_client

    def test_get_playlist_success(self, test_app: TestClient, mock_spotify_client):
        """Test successful playlist retrieval."""

        async def override_get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
            yield mock_spotify_client

        test_app.app.dependency_overrides[get_spotify_client] = override_get_spotify_client

        try:
            response = test_app.get("/spotify/playlists/37i9dQZF1DXcBWIGoYBM5M")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "37i9dQZF1DXcBWIGoYBM5M"
            assert data["name"] == "Today's Top Hits"
            assert data["description"] == "The hottest 50 songs in the world right now"
            assert data["public"] is True
            assert data["collaborative"] is False
            assert data["owner"]["display_name"] == "Spotify"
            assert data["tracks"]["total"] == 50
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)

    def test_get_playlist_not_found(self, test_app: TestClient, mock_spotify_client):
        """Test playlist not found error."""
        mock_spotify_client.get_playlist = AsyncMock(
            side_effect=Exception("404 - Playlist not found")
        )

        async def override_get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
            yield mock_spotify_client

        test_app.app.dependency_overrides[get_spotify_client] = override_get_spotify_client

        try:
            response = test_app.get("/spotify/playlists/nonexistent123")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)


class TestSpotifyGetPlaylistTracks:
    """Tests for Spotify get playlist tracks endpoint."""

    @pytest.fixture
    def mock_tracks_response(self):
        """Create a mock playlist tracks response."""
        return SpotifyPlaylistTracksResponse(
            href="https://api.spotify.com/v1/playlists/37i9dQZF1DXcBWIGoYBM5M/tracks",
            items=[
                SpotifyPlaylistTrack(
                    track=SpotifyTrack(
                        id="11dFghVXANMlKmJXsNCbNl",
                        name="Smells Like Teen Spirit",
                        uri="spotify:track:11dFghVXANMlKmJXsNCbNl",
                        artists=[
                            SpotifyArtist(
                                id="6olE6TJLqED3rqDCT0FyPh",
                                name="Nirvana",
                                uri="spotify:artist:6olE6TJLqED3rqDCT0FyPh",
                                href="https://api.spotify.com/v1/artists/6olE6TJLqED3rqDCT0FyPh",
                            )
                        ],
                        album=SpotifyAlbum(
                            id="2guirTSEqLizK7j9i1MTTZ",
                            name="Nevermind",
                            release_date="1991-09-24",
                            release_date_precision="day",
                            uri="spotify:album:2guirTSEqLizK7j9i1MTTZ",
                            images=[
                                {
                                    "url": "https://i.scdn.co/image/cover.jpg",
                                    "width": 640,
                                    "height": 640,
                                }
                            ],
                        ),
                        duration_ms=301920,
                        popularity=85,
                        explicit=False,
                    ),
                    added_at="2024-01-15T12:00:00Z",
                    added_by={"id": "user123"},
                ),
                SpotifyPlaylistTrack(
                    track=SpotifyTrack(
                        id="7pKfPomDEeI4TPT6EOYjn9",
                        name="In Bloom",
                        uri="spotify:track:7pKfPomDEeI4TPT6EOYjn9",
                        artists=[
                            SpotifyArtist(
                                id="6olE6TJLqED3rqDCT0FyPh",
                                name="Nirvana",
                                uri="spotify:artist:6olE6TJLqED3rqDCT0FyPh",
                                href="https://api.spotify.com/v1/artists/6olE6TJLqED3rqDCT0FyPh",
                            )
                        ],
                        album=SpotifyAlbum(
                            id="2guirTSEqLizK7j9i1MTTZ",
                            name="Nevermind",
                            release_date="1991-09-24",
                            release_date_precision="day",
                            uri="spotify:album:2guirTSEqLizK7j9i1MTTZ",
                            images=[],
                        ),
                        duration_ms=254667,
                        popularity=75,
                        explicit=False,
                    ),
                    added_at="2024-01-15T12:01:00Z",
                    added_by={"id": "user123"},
                ),
            ],
            limit=50,
            next="https://api.spotify.com/v1/playlists/37i9dQZF1DXcBWIGoYBM5M/tracks?offset=50",
            offset=0,
            previous=None,
            total=100,
        )

    @pytest.fixture
    def mock_spotify_client(self, mock_tracks_response):
        """Create a mock Spotify client."""
        mock_client = MagicMock(spec=SpotifyClient)
        mock_client.get_playlist_tracks = AsyncMock(return_value=mock_tracks_response)
        mock_client.get_playlist = AsyncMock()
        mock_client.get_all_playlist_tracks = AsyncMock()
        mock_client.get_track = AsyncMock()
        return mock_client

    def test_get_playlist_tracks_success(self, test_app: TestClient, mock_spotify_client):
        """Test successful playlist tracks retrieval."""

        async def override_get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
            yield mock_spotify_client

        test_app.app.dependency_overrides[get_spotify_client] = override_get_spotify_client

        try:
            response = test_app.get("/spotify/playlists/37i9dQZF1DXcBWIGoYBM5M/tracks")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 100
            assert data["limit"] == 50
            assert data["offset"] == 0
            assert data["next"] is not None
            assert data["previous"] is None
            assert len(data["items"]) == 2
            assert data["items"][0]["track"]["name"] == "Smells Like Teen Spirit"
            assert data["items"][0]["track"]["artists"][0]["name"] == "Nirvana"
            assert data["items"][0]["track"]["album"]["name"] == "Nevermind"
            assert data["items"][0]["track"]["duration_ms"] == 301920
            assert data["items"][0]["added_at"] == "2024-01-15T12:00:00Z"
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)

    def test_get_playlist_tracks_with_pagination(self, test_app: TestClient, mock_spotify_client):
        """Test playlist tracks with custom pagination parameters."""

        async def override_get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
            yield mock_spotify_client

        test_app.app.dependency_overrides[get_spotify_client] = override_get_spotify_client

        try:
            response = test_app.get(
                "/spotify/playlists/37i9dQZF1DXcBWIGoYBM5M/tracks",
                params={"limit": 25, "offset": 50},
            )

            assert response.status_code == 200
            mock_spotify_client.get_playlist_tracks.assert_called_once_with(
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                limit=25,
                offset=50,
            )
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)

    def test_get_playlist_tracks_limit_max(self, test_app: TestClient, mock_spotify_client):
        """Test playlist tracks validates limit max value."""

        async def override_get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
            yield mock_spotify_client

        test_app.app.dependency_overrides[get_spotify_client] = override_get_spotify_client

        try:
            response = test_app.get(
                "/spotify/playlists/37i9dQZF1DXcBWIGoYBM5M/tracks",
                params={"limit": 101},  # Exceeds max of 100
            )
            assert response.status_code == 422  # Validation error
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)

    def test_get_playlist_tracks_not_found(self, test_app: TestClient, mock_spotify_client):
        """Test playlist tracks not found error."""
        mock_spotify_client.get_playlist_tracks = AsyncMock(
            side_effect=Exception("404 - Not found")
        )

        async def override_get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
            yield mock_spotify_client

        test_app.app.dependency_overrides[get_spotify_client] = override_get_spotify_client

        try:
            response = test_app.get("/spotify/playlists/nonexistent123/tracks")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)


class TestSpotifyGetAllPlaylistTracks:
    """Tests for Spotify get all playlist tracks endpoint."""

    @pytest.fixture
    def mock_all_tracks(self):
        """Create a mock all tracks response."""
        return [
            SpotifyTrack(
                id="11dFghVXANMlKmJXsNCbNl",
                name="Smells Like Teen Spirit",
                uri="spotify:track:11dFghVXANMlKmJXsNCbNl",
                artists=[
                    SpotifyArtist(
                        id="6olE6TJLqED3rqDCT0FyPh",
                        name="Nirvana",
                        uri="spotify:artist:6olE6TJLqED3rqDCT0FyPh",
                        href="https://api.spotify.com/v1/artists/6olE6TJLqED3rqDCT0FyPh",
                    )
                ],
                album=SpotifyAlbum(
                    id="2guirTSEqLizK7j9i1MTTZ",
                    name="Nevermind",
                    release_date="1991-09-24",
                    release_date_precision="day",
                    uri="spotify:album:2guirTSEqLizK7j9i1MTTZ",
                    images=[],
                ),
                duration_ms=301920,
                popularity=85,
                explicit=False,
            ),
            SpotifyTrack(
                id="7pKfPomDEeI4TPT6EOYjn9",
                name="In Bloom",
                uri="spotify:track:7pKfPomDEeI4TPT6EOYjn9",
                artists=[
                    SpotifyArtist(
                        id="6olE6TJLqED3rqDCT0FyPh",
                        name="Nirvana",
                        uri="spotify:artist:6olE6TJLqED3rqDCT0FyPh",
                        href="https://api.spotify.com/v1/artists/6olE6TJLqED3rqDCT0FyPh",
                    )
                ],
                album=SpotifyAlbum(
                    id="2guirTSEqLizK7j9i1MTTZ",
                    name="Nevermind",
                    release_date="1991-09-24",
                    release_date_precision="day",
                    uri="spotify:album:2guirTSEqLizK7j9i1MTTZ",
                    images=[],
                ),
                duration_ms=254667,
                popularity=75,
                explicit=False,
            ),
            SpotifyTrack(
                id="2TjnCxxQRYn56Ye7DJ8Xyg",
                name="Come as You Are",
                uri="spotify:track:2TjnCxxQRYn56Ye7DJ8Xyg",
                artists=[
                    SpotifyArtist(
                        id="6olE6TJLqED3rqDCT0FyPh",
                        name="Nirvana",
                        uri="spotify:artist:6olE6TJLqED3rqDCT0FyPh",
                        href="https://api.spotify.com/v1/artists/6olE6TJLqED3rqDCT0FyPh",
                    )
                ],
                album=SpotifyAlbum(
                    id="2guirTSEqLizK7j9i1MTTZ",
                    name="Nevermind",
                    release_date="1991-09-24",
                    release_date_precision="day",
                    uri="spotify:album:2guirTSEqLizK7j9i1MTTZ",
                    images=[],
                ),
                duration_ms=218880,
                popularity=80,
                explicit=False,
            ),
        ]

    @pytest.fixture
    def mock_spotify_client(self, mock_all_tracks):
        """Create a mock Spotify client."""
        mock_client = MagicMock(spec=SpotifyClient)
        mock_client.get_all_playlist_tracks = AsyncMock(return_value=mock_all_tracks)
        mock_client.get_playlist = AsyncMock()
        mock_client.get_playlist_tracks = AsyncMock()
        mock_client.get_track = AsyncMock()
        return mock_client

    def test_get_all_playlist_tracks_success(self, test_app: TestClient, mock_spotify_client):
        """Test successful retrieval of all playlist tracks."""

        async def override_get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
            yield mock_spotify_client

        test_app.app.dependency_overrides[get_spotify_client] = override_get_spotify_client

        try:
            response = test_app.get("/spotify/playlists/37i9dQZF1DXcBWIGoYBM5M/tracks/all")

            assert response.status_code == 200
            data = response.json()
            assert data["playlist_id"] == "37i9dQZF1DXcBWIGoYBM5M"
            assert data["total"] == 3
            assert len(data["tracks"]) == 3
            assert data["tracks"][0]["name"] == "Smells Like Teen Spirit"
            assert data["tracks"][1]["name"] == "In Bloom"
            assert data["tracks"][2]["name"] == "Come as You Are"
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)

    def test_get_all_playlist_tracks_empty(self, test_app: TestClient, mock_spotify_client):
        """Test retrieval of empty playlist."""
        mock_spotify_client.get_all_playlist_tracks = AsyncMock(return_value=[])

        async def override_get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
            yield mock_spotify_client

        test_app.app.dependency_overrides[get_spotify_client] = override_get_spotify_client

        try:
            response = test_app.get("/spotify/playlists/empty_playlist/tracks/all")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["tracks"] == []
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)

    def test_get_all_playlist_tracks_not_found(self, test_app: TestClient, mock_spotify_client):
        """Test all playlist tracks not found error."""
        mock_spotify_client.get_all_playlist_tracks = AsyncMock(
            side_effect=Exception("404 - Playlist not found")
        )

        async def override_get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
            yield mock_spotify_client

        test_app.app.dependency_overrides[get_spotify_client] = override_get_spotify_client

        try:
            response = test_app.get("/spotify/playlists/nonexistent123/tracks/all")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)


class TestSpotifyGetTrack:
    """Tests for Spotify get track endpoint."""

    @pytest.fixture
    def mock_track(self):
        """Create a mock track response."""
        return SpotifyTrack(
            id="11dFghVXANMlKmJXsNCbNl",
            name="Smells Like Teen Spirit",
            uri="spotify:track:11dFghVXANMlKmJXsNCbNl",
            artists=[
                SpotifyArtist(
                    id="6olE6TJLqED3rqDCT0FyPh",
                    name="Nirvana",
                    uri="spotify:artist:6olE6TJLqED3rqDCT0FyPh",
                    href="https://api.spotify.com/v1/artists/6olE6TJLqED3rqDCT0FyPh",
                )
            ],
            album=SpotifyAlbum(
                id="2guirTSEqLizK7j9i1MTTZ",
                name="Nevermind",
                release_date="1991-09-24",
                release_date_precision="day",
                uri="spotify:album:2guirTSEqLizK7j9i1MTTZ",
                images=[
                    {"url": "https://i.scdn.co/image/cover.jpg", "width": 640, "height": 640},
                    {"url": "https://i.scdn.co/image/cover_300.jpg", "width": 300, "height": 300},
                ],
            ),
            duration_ms=301920,
            popularity=85,
            explicit=False,
        )

    @pytest.fixture
    def mock_spotify_client(self, mock_track):
        """Create a mock Spotify client."""
        mock_client = MagicMock(spec=SpotifyClient)
        mock_client.get_track = AsyncMock(return_value=mock_track)
        mock_client.get_playlist = AsyncMock()
        mock_client.get_playlist_tracks = AsyncMock()
        mock_client.get_all_playlist_tracks = AsyncMock()
        return mock_client

    def test_get_track_success(self, test_app: TestClient, mock_spotify_client):
        """Test successful track retrieval."""

        async def override_get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
            yield mock_spotify_client

        test_app.app.dependency_overrides[get_spotify_client] = override_get_spotify_client

        try:
            response = test_app.get("/spotify/tracks/11dFghVXANMlKmJXsNCbNl")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "11dFghVXANMlKmJXsNCbNl"
            assert data["name"] == "Smells Like Teen Spirit"
            assert data["duration_ms"] == 301920
            assert data["popularity"] == 85
            assert data["explicit"] is False
            assert len(data["artists"]) == 1
            assert data["artists"][0]["name"] == "Nirvana"
            assert data["album"]["name"] == "Nevermind"
            assert data["album"]["release_date"] == "1991-09-24"
            assert len(data["album"]["images"]) == 2
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)

    def test_get_track_not_found(self, test_app: TestClient, mock_spotify_client):
        """Test track not found error."""
        mock_spotify_client.get_track = AsyncMock(side_effect=Exception("404 - Track not found"))

        async def override_get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
            yield mock_spotify_client

        test_app.app.dependency_overrides[get_spotify_client] = override_get_spotify_client

        try:
            response = test_app.get("/spotify/tracks/nonexistent123")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)


class TestSpotifyServiceUnavailable:
    """Tests for Spotify service unavailable scenarios."""

    def test_service_unavailable(self, test_app: TestClient):
        """Test when Spotify is not configured."""
        from fastapi import HTTPException

        async def override_unavailable() -> AsyncGenerator[SpotifyClient, None]:
            raise HTTPException(status_code=503, detail="Spotify API is not configured")
            yield  # Never reached, but makes it a generator

        test_app.app.dependency_overrides[get_spotify_client] = override_unavailable

        try:
            response = test_app.get("/spotify/playlists/test123")

            assert response.status_code == 503
            assert "not configured" in response.json()["detail"]
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)

    def test_api_error(self, test_app: TestClient):
        """Test generic API error handling."""
        mock_client = MagicMock(spec=SpotifyClient)
        mock_client.get_playlist = AsyncMock(side_effect=Exception("API rate limit exceeded"))

        async def override_get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
            yield mock_client

        test_app.app.dependency_overrides[get_spotify_client] = override_get_spotify_client

        try:
            response = test_app.get("/spotify/playlists/test123")

            assert response.status_code == 503
            assert "Failed to fetch" in response.json()["detail"]
        finally:
            test_app.app.dependency_overrides.pop(get_spotify_client, None)
