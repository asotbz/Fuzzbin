"""Tests for /add import hub endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from fuzzbin.api.spotify_client import SpotifyClient
from fuzzbin.parsers.spotify_models import SpotifyAlbum, SpotifyArtist, SpotifyPlaylist, SpotifyTrack
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
