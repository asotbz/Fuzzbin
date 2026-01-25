"""Tests for /add import hub endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from fuzzbin.api.spotify_client import SpotifyClient
from fuzzbin.parsers.spotify_models import (
    SpotifyAlbum,
    SpotifyArtist,
    SpotifyPlaylist,
    SpotifyTrack,
)
from fuzzbin.common.config import APIClientConfig
import fuzzbin


class TestAddPreviewBatchNFO:
    def test_preview_batch_nfo_success(self, test_app: TestClient, tmp_path: Path):
        # Create a minimal musicvideo.nfo
        directory = tmp_path / "nfo"
        directory.mkdir(parents=True)

        nfo_path = directory / "musicvideo.nfo"
        nfo_path.write_text(
            """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<musicvideo>
  <title>Smells Like Teen Spirit</title>
  <artist>Nirvana</artist>
  <album>Nevermind</album>
  <year>1991</year>
</musicvideo>
""",
            encoding="utf-8",
        )

        response = test_app.post(
            "/add/preview-batch",
            json={
                "mode": "nfo",
                "nfo_directory": str(directory),
                "recursive": True,
                "skip_existing": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "nfo"
        assert data["directory"] == str(directory)
        assert data["total_count"] == 1
        assert data["existing_count"] in (0, 1)
        assert data["new_count"] in (0, 1)
        assert len(data["items"]) == 1
        assert data["items"][0]["kind"] == "nfo"
        assert data["items"][0]["title"] == "Smells Like Teen Spirit"
        assert data["items"][0]["artist"] == "Nirvana"
        assert data["items"][0]["nfo_path"].endswith("musicvideo.nfo")


class TestAddPreviewBatchSpotify:
    @pytest.fixture
    def mock_spotify_client(self):
        playlist_id = "37i9dQZF1DXcBWIGoYBM5M"
        playlist = SpotifyPlaylist(
            id=playlist_id,
            name="Test Playlist",
            description=None,
            uri=f"spotify:playlist:{playlist_id}",
            owner={"id": "spotify"},
            tracks=None,
            public=True,
            collaborative=False,
        )

        tracks = [
            SpotifyTrack(
                id="t1",
                name="Smells Like Teen Spirit",
                uri="spotify:track:t1",
                artists=[
                    SpotifyArtist(
                        id="a1",
                        name="Nirvana",
                        uri="spotify:artist:a1",
                        href=None,
                    )
                ],
                album=SpotifyAlbum(
                    id="al1",
                    name="Nevermind",
                    release_date="1991-09-24",
                    release_date_precision="day",
                    uri="spotify:album:al1",
                    images=[],
                ),
                duration_ms=123,
                popularity=50,
                explicit=False,
            ),
            SpotifyTrack(
                id="t2",
                name="In Bloom",
                uri="spotify:track:t2",
                artists=[
                    SpotifyArtist(
                        id="a1",
                        name="Nirvana",
                        uri="spotify:artist:a1",
                        href=None,
                    )
                ],
                album=SpotifyAlbum(
                    id="al1",
                    name="Nevermind",
                    release_date="1991-09-24",
                    release_date_precision="day",
                    uri="spotify:album:al1",
                    images=[],
                ),
                duration_ms=123,
                popularity=50,
                explicit=False,
            ),
        ]

        mock_client = MagicMock(spec=SpotifyClient)
        mock_client.get_playlist = AsyncMock(return_value=playlist)
        mock_client.get_all_playlist_tracks = AsyncMock(return_value=tracks)
        return mock_client

    def test_preview_batch_spotify_marks_existing(
        self, test_app: TestClient, mock_spotify_client, monkeypatch
    ):
        # Ensure spotify is configured for the /add endpoint
        config = fuzzbin.get_config()
        config.apis = config.apis or {}
        config.apis["spotify"] = APIClientConfig(
            name="spotify",
            base_url="https://api.spotify.com/v1",
        )

        # Patch SpotifyClient.from_config to return an async context manager yielding our mock
        class _ClientCM:
            async def __aenter__(self):
                return mock_spotify_client

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(SpotifyClient, "from_config", classmethod(lambda cls, cfg: _ClientCM()))

        # Create a video that should match track 1
        create_resp = test_app.post(
            "/videos",
            json={
                "title": "Smells Like Teen Spirit",
                "artist": "Nirvana",
                "album": "Nevermind",
                "year": 1991,
            },
        )
        assert create_resp.status_code in (200, 201)

        response = test_app.post(
            "/add/preview-batch",
            json={
                "mode": "spotify",
                "spotify_playlist_id": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
                "skip_existing": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "spotify"
        assert data["total_count"] == 2
        assert data["playlist_name"] == "Test Playlist"
        assert data["existing_count"] == 1
        assert data["new_count"] == 1
        assert len(data["items"]) == 2
        assert data["items"][0]["kind"] == "spotify_track"
        assert data["items"][0]["spotify_playlist_id"] == "37i9dQZF1DXcBWIGoYBM5M"


class TestAddSpotifyImport:
    def test_submit_spotify_import_job(self, test_app: TestClient):
        response = test_app.post(
            "/add/spotify",
            json={
                "playlist_id": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
                "skip_existing": True,
                "initial_status": "discovered",
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["playlist_id"] == "37i9dQZF1DXcBWIGoYBM5M"
        assert isinstance(data["job_id"], str)
        assert data["status"] == "pending"


class TestAddNFOScan:
    """Tests for POST /add/nfo-scan endpoint."""

    def test_submit_nfo_scan_job(self, test_app: TestClient, tmp_path: Path):
        """Test submitting an NFO scan job."""
        # Create test directory
        directory = tmp_path / "nfo_scan"
        directory.mkdir(parents=True)

        response = test_app.post(
            "/add/nfo-scan",
            json={
                "directory": str(directory),
                "mode": "discovery",
                "recursive": True,
                "skip_existing": True,
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["directory"] == str(directory)
        assert data["mode"] == "discovery"
        assert isinstance(data["job_id"], str)

    def test_submit_nfo_scan_invalid_directory(self, test_app: TestClient):
        """Test NFO scan with non-existent directory."""
        response = test_app.post(
            "/add/nfo-scan",
            json={
                "directory": "/nonexistent/path/that/does/not/exist",
                "mode": "discovery",
            },
        )

        assert response.status_code in (400, 404)


class TestAddSearch:
    """Tests for POST /add/search endpoint."""

    def test_search_empty_request(self, test_app: TestClient):
        """Test search with minimal request - no APIs configured so expects empty results."""
        response = test_app.post(
            "/add/search",
            json={
                "artist": "Nirvana",
                "track_title": "Smells Like Teen Spirit",
            },
        )

        # May return 200 with empty results or skipped sources when APIs aren't configured
        assert response.status_code == 200
        data = response.json()
        assert data["artist"] == "Nirvana"
        assert data["track_title"] == "Smells Like Teen Spirit"
        assert "results" in data
        assert "skipped" in data
        assert "counts" in data

    def test_search_with_sources_filter(self, test_app: TestClient):
        """Test search with specific sources filter."""
        response = test_app.post(
            "/add/search",
            json={
                "artist": "R.E.M.",
                "track_title": "Losing My Religion",
                "include_sources": ["youtube"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["artist"] == "R.E.M."
        assert data["track_title"] == "Losing My Religion"


class TestAddPreview:
    """Tests for GET /add/preview/{source}/{item_id} endpoint."""

    def test_preview_invalid_source(self, test_app: TestClient):
        """Test preview with invalid source."""
        response = test_app.get("/add/preview/invalid_source/12345")

        # Should return 422 (validation error) for invalid enum value
        assert response.status_code == 422

    def test_preview_imvdb_not_configured(self, test_app: TestClient):
        """Test preview IMVDb when not configured."""
        response = test_app.get("/add/preview/imvdb/12345")

        # Should return 503 when IMVDb is not configured
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"].lower()


class TestAddCheckExists:
    """Tests for GET /add/check-exists endpoint."""

    def test_check_exists_video_not_found(self, test_app: TestClient):
        """Test check-exists for non-existent video."""
        response = test_app.get(
            "/add/check-exists",
            params={"imvdb_id": "99999999"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is False
        assert data["video_id"] is None

    def test_check_exists_by_imvdb_id(self, test_app: TestClient):
        """Test check-exists by IMVDb ID when video exists."""
        # First create a video with imvdb_video_id
        create_resp = test_app.post(
            "/videos",
            json={
                "title": "Test Video",
                "artist": "Test Artist",
                "imvdb_video_id": "12345678",
            },
        )
        assert create_resp.status_code in (200, 201)

        # Now check if it exists
        response = test_app.get(
            "/add/check-exists",
            params={"imvdb_id": "12345678"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
        assert data["title"] == "Test Video"
        assert data["artist"] == "Test Artist"

    def test_check_exists_by_youtube_id(self, test_app: TestClient):
        """Test check-exists by YouTube ID when video exists."""
        # First create a video with youtube_id
        create_resp = test_app.post(
            "/videos",
            json={
                "title": "YouTube Test Video",
                "artist": "YouTube Test Artist",
                "youtube_id": "dQw4w9WgXcQ",
            },
        )
        assert create_resp.status_code in (200, 201)

        # Now check if it exists
        response = test_app.get(
            "/add/check-exists",
            params={"youtube_id": "dQw4w9WgXcQ"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
        assert data["title"] == "YouTube Test Video"


class TestAddImport:
    """Tests for POST /add/import endpoint."""

    def test_import_single_video(self, test_app: TestClient):
        """Test submitting a single video import job."""
        response = test_app.post(
            "/add/import",
            json={
                "source": "imvdb",
                "id": "123456",
                "initial_status": "discovered",
                "auto_download": False,
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["source"] == "imvdb"
        assert data["id"] == "123456"
        assert isinstance(data["job_id"], str)

    def test_import_with_youtube_id(self, test_app: TestClient):
        """Test import with YouTube ID for download."""
        response = test_app.post(
            "/add/import",
            json={
                "source": "youtube",
                "id": "dQw4w9WgXcQ",
                "youtube_id": "dQw4w9WgXcQ",
                "initial_status": "discovered",
                "auto_download": True,
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert isinstance(data["job_id"], str)


class TestSpotifyEnrichTrack:
    """Tests for POST /add/spotify/enrich-track endpoint."""

    def test_enrich_track_basic(self, test_app: TestClient):
        """Test track enrichment returns response even without API configs."""
        response = test_app.post(
            "/add/spotify/enrich-track",
            json={
                "spotify_track_id": "track123",
                "artist": "Nirvana",
                "track_title": "Smells Like Teen Spirit",
                "isrc": "USGF19942501",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["spotify_track_id"] == "track123"
        assert "musicbrainz" in data
        assert "imvdb" in data
        # Returns original values when enrichment fails
        assert data["title"] == "Smells Like Teen Spirit"
        assert data["artist"] == "Nirvana"

    def test_enrich_track_with_artist_genres(self, test_app: TestClient):
        """Test track enrichment with artist genres from Spotify."""
        response = test_app.post(
            "/add/spotify/enrich-track",
            json={
                "spotify_track_id": "track456",
                "artist": "R.E.M.",
                "track_title": "Losing My Religion",
                "artist_genres": ["alternative rock", "jangle pop"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["spotify_track_id"] == "track456"


class TestYouTubeSearch:
    """Tests for POST /add/youtube/search endpoint."""

    def test_youtube_search_basic(self, test_app: TestClient):
        """Test YouTube search returns response structure."""
        response = test_app.post(
            "/add/youtube/search",
            json={
                "artist": "Nirvana",
                "track_title": "Smells Like Teen Spirit",
                "max_results": 5,
            },
        )

        # May fail if yt-dlp not available, but should return valid response or error
        assert response.status_code in (200, 500, 503)

        if response.status_code == 200:
            data = response.json()
            assert data["artist"] == "Nirvana"
            assert data["track_title"] == "Smells Like Teen Spirit"
            assert "results" in data
            assert "skipped" in data


class TestSpotifyImportSelected:
    """Tests for POST /add/spotify/import-selected endpoint."""

    def test_import_selected_tracks(self, test_app: TestClient):
        """Test importing selected Spotify tracks."""
        response = test_app.post(
            "/add/spotify/import-selected",
            json={
                "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
                "tracks": [
                    {
                        "spotify_track_id": "track1",
                        "metadata": {
                            "title": "Song One",
                            "artist": "Artist One",
                            "year": 2023,
                        },
                    },
                    {
                        "spotify_track_id": "track2",
                        "metadata": {
                            "title": "Song Two",
                            "artist": "Artist Two",
                        },
                        "youtube_id": "abc123xyz",
                    },
                ],
                "initial_status": "discovered",
                "auto_download": True,
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["playlist_id"] == "37i9dQZF1DXcBWIGoYBM5M"
        assert data["track_count"] == 2
        assert data["auto_download"] is True
        assert isinstance(data["job_id"], str)

    def test_import_selected_empty_tracks(self, test_app: TestClient):
        """Test importing with empty tracks list."""
        response = test_app.post(
            "/add/spotify/import-selected",
            json={
                "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
                "tracks": [],
                "initial_status": "discovered",
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["track_count"] == 0


class TestYouTubeMetadata:
    """Tests for POST /add/youtube/metadata endpoint."""

    def test_youtube_metadata_basic(self, test_app: TestClient):
        """Test YouTube metadata endpoint structure."""
        response = test_app.post(
            "/add/youtube/metadata",
            json={
                "youtube_id": "dQw4w9WgXcQ",
            },
        )

        # May return available or unavailable based on yt-dlp availability
        assert response.status_code == 200
        data = response.json()
        assert data["youtube_id"] == "dQw4w9WgXcQ"
        assert "available" in data
        # If unavailable, should have error field
        if not data["available"]:
            assert "error" in data


# ==================== Artist Import Tests ====================


class TestArtistSearch:
    """Tests for POST /add/search/artist endpoint."""

    def test_artist_search_imvdb_not_configured(self, test_app: TestClient):
        """Test artist search when IMVDb is not configured."""
        response = test_app.post(
            "/add/search/artist",
            json={
                "artist_name": "Nirvana",
            },
        )

        # Should return 503 when IMVDb is not configured
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"].lower()

    def test_artist_search_validation(self, test_app: TestClient):
        """Test artist search validates request body."""
        response = test_app.post(
            "/add/search/artist",
            json={},  # Missing required artist_name
        )

        assert response.status_code == 422


class TestArtistPreview:
    """Tests for GET /add/artist/preview/{entity_id} endpoint."""

    def test_artist_preview_imvdb_not_configured(self, test_app: TestClient):
        """Test artist preview when IMVDb is not configured."""
        response = test_app.get("/add/artist/preview/12345")

        # Should return 503 when IMVDb is not configured
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"].lower()

    def test_artist_preview_with_pagination(self, test_app: TestClient):
        """Test artist preview accepts pagination params."""
        response = test_app.get(
            "/add/artist/preview/12345",
            params={"page": 1, "per_page": 25},
        )

        # Should return 503 when IMVDb is not configured
        assert response.status_code == 503


class TestEnrichImvdbVideo:
    """Tests for POST /add/enrich/imvdb-video endpoint."""

    def test_enrich_imvdb_video_not_configured(self, test_app: TestClient):
        """Test IMVDb video enrichment when IMVDb is not configured."""
        response = test_app.post(
            "/add/enrich/imvdb-video",
            json={
                "imvdb_id": 12345,
                "artist": "Nirvana",
                "track_title": "Smells Like Teen Spirit",
            },
        )

        # Should return 503 when IMVDb is not configured
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"].lower()

    def test_enrich_imvdb_video_validation(self, test_app: TestClient):
        """Test IMVDb video enrichment validates request body."""
        response = test_app.post(
            "/add/enrich/imvdb-video",
            json={
                "imvdb_id": 12345,
                # Missing required artist and track_title
            },
        )

        assert response.status_code == 422


class TestArtistImport:
    """Tests for POST /add/artist/import endpoint."""

    def test_artist_import_basic(self, test_app: TestClient):
        """Test submitting artist import job."""
        response = test_app.post(
            "/add/artist/import",
            json={
                "entity_id": 12345,
                "entity_name": "Nirvana",
                "videos": [
                    {
                        "imvdb_id": 100001,
                        "metadata": {
                            "title": "Smells Like Teen Spirit",
                            "artist": "Nirvana",
                            "year": 1991,
                        },
                        "youtube_id": "hTWKbfoikeg",
                    },
                    {
                        "imvdb_id": 100002,
                        "metadata": {
                            "title": "In Bloom",
                            "artist": "Nirvana",
                            "year": 1992,
                        },
                    },
                ],
                "initial_status": "discovered",
                "auto_download": True,
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["entity_id"] == 12345
        assert data["video_count"] == 2
        assert data["auto_download"] is True
        assert isinstance(data["job_id"], str)

    def test_artist_import_empty_videos(self, test_app: TestClient):
        """Test artist import with empty videos list fails."""
        response = test_app.post(
            "/add/artist/import",
            json={
                "entity_id": 12345,
                "entity_name": "Nirvana",
                "videos": [],
                "initial_status": "discovered",
            },
        )

        # Should fail with 400 - at least one video is required
        assert response.status_code == 400
        assert "at least one video" in response.json()["detail"].lower()

    def test_artist_import_validation(self, test_app: TestClient):
        """Test artist import validates request body."""
        response = test_app.post(
            "/add/artist/import",
            json={
                # Missing required videos field
                "entity_id": 12345,
            },
        )

        assert response.status_code == 422
