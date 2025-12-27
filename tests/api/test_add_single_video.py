"""Tests for /add single-video aggregator endpoints."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import fuzzbin
from fuzzbin.api.discogs_client import DiscogsClient
from fuzzbin.api.imvdb_client import IMVDbClient
from fuzzbin.clients.ytdlp_client import YTDLPClient
from fuzzbin.common.config import APIClientConfig, YTDLPConfig


class TestAddSearch:
    def test_add_search_aggregates_sources(self, test_app: TestClient, monkeypatch):
        config = fuzzbin.get_config()
        config.apis = config.apis or {}
        config.apis["imvdb"] = APIClientConfig(name="imvdb", base_url="https://imvdb.example")
        config.apis["discogs"] = APIClientConfig(name="discogs", base_url="https://discogs.example")
        config.ytdlp = config.ytdlp or YTDLPConfig()

        # IMVDb mock
        imvdb_result = SimpleNamespace(
            pagination=SimpleNamespace(total_results=1, current_page=1, per_page=10, total_pages=1),
            results=[
                SimpleNamespace(
                    id=123,
                    song_title="Smells Like Teen Spirit",
                    year=1991,
                    url="https://imvdb.com/video/123",
                    artists=[SimpleNamespace(name="Nirvana")],
                    image={"t": "https://imvdb.example/thumb.jpg"},
                    multiple_versions=False,
                    version_name=None,
                )
            ],
        )

        mock_imvdb = MagicMock(spec=IMVDbClient)
        mock_imvdb.search_videos = AsyncMock(return_value=imvdb_result)

        class _IMVDbCM:
            async def __aenter__(self):
                return mock_imvdb

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(IMVDbClient, "from_config", classmethod(lambda cls, cfg: _IMVDbCM()))

        # Discogs mock
        discogs_result = {
            "pagination": {"page": 1, "pages": 1, "per_page": 10, "items": 2},
            "results": [
                {
                    "id": 100,
                    "type": "master",
                    "title": "Nirvana - Nevermind",
                    "year": "1991",
                    "uri": "https://www.discogs.com/master/100",
                    "thumb": "https://discogs.example/thumb.jpg",
                    "community": {"want": 100, "have": 50},
                },
                {
                    "id": 200,
                    "type": "release",
                    "title": "Nirvana - Nevermind (CD)",
                    "year": "1992",
                    "uri": "https://www.discogs.com/release/200",
                    "thumb": None,
                },
            ],
        }

        mock_discogs = MagicMock(spec=DiscogsClient)
        mock_discogs.search = AsyncMock(return_value=discogs_result)

        class _DiscogsCM:
            async def __aenter__(self):
                return mock_discogs

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(
            DiscogsClient, "from_config", classmethod(lambda cls, cfg: _DiscogsCM())
        )

        # yt-dlp mock
        yt_results = [
            SimpleNamespace(
                id="dQw4w9WgXcQ",
                title="Nirvana - Smells Like Teen Spirit (Official Video)",
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                channel="YouTube",
                channel_follower_count=None,
                view_count=1,
                duration=210,
            )
        ]

        mock_ytdlp = MagicMock(spec=YTDLPClient)
        mock_ytdlp.search = AsyncMock(return_value=yt_results)

        class _YTDLPCM:
            async def __aenter__(self):
                return mock_ytdlp

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(YTDLPClient, "from_config", classmethod(lambda cls, cfg: _YTDLPCM()))

        resp = test_app.post(
            "/add/search",
            json={"artist": "Nirvana", "track_title": "Smells Like Teen Spirit"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["artist"] == "Nirvana"
        assert data["track_title"] == "Smells Like Teen Spirit"

        sources = {r["source"] for r in data["results"]}
        assert "imvdb" in sources
        assert "discogs_master" in sources
        assert "discogs_release" in sources
        assert "youtube" in sources

        assert data["counts"]["imvdb"] == 1
        assert data["counts"]["discogs_master"] == 1
        assert data["counts"]["discogs_release"] == 1
        assert data["counts"]["youtube"] == 1


class TestAddPreview:
    def test_add_preview_imvdb(self, test_app: TestClient, monkeypatch):
        config = fuzzbin.get_config()
        config.apis = config.apis or {}
        config.apis["imvdb"] = APIClientConfig(name="imvdb", base_url="https://imvdb.example")

        video = SimpleNamespace(
            id=123,
            production_status=None,
            song_title="Smells Like Teen Spirit",
            song_slug=None,
            url="https://imvdb.com/video/123",
            multiple_versions=False,
            version_name=None,
            version_number=None,
            is_imvdb_pick=None,
            aspect_ratio=None,
            year=1991,
            verified_credits=None,
            artists=[SimpleNamespace(name="Nirvana", slug=None, url=None)],
            featured_artists=[],
            image={"t": "https://imvdb.example/thumb.jpg"},
            sources=[
                SimpleNamespace(
                    source="YouTube",
                    source_slug="youtube",
                    source_data="dQw4w9WgXcQ",
                    is_primary=True,
                )
            ],
            directors=[],
            credits=None,
        )

        mock_imvdb = MagicMock(spec=IMVDbClient)
        mock_imvdb.get_video = AsyncMock(return_value=video)

        class _IMVDbCM:
            async def __aenter__(self):
                return mock_imvdb

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(IMVDbClient, "from_config", classmethod(lambda cls, cfg: _IMVDbCM()))

        resp = test_app.get("/add/preview/imvdb/123")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["source"] == "imvdb"
        assert payload["id"] == "123"
        assert payload["data"]["song_title"] == "Smells Like Teen Spirit"
        assert payload["extra"]["youtube_ids"] == ["dQw4w9WgXcQ"]

    def test_add_preview_youtube(self, test_app: TestClient, monkeypatch):
        config = fuzzbin.get_config()
        config.ytdlp = config.ytdlp or YTDLPConfig()

        yt = SimpleNamespace(
            id="dQw4w9WgXcQ",
            title="Video",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            channel="YouTube",
            channel_follower_count=None,
            view_count=1,
            duration=210,
        )

        mock_ytdlp = MagicMock(spec=YTDLPClient)
        mock_ytdlp.get_video_info = AsyncMock(return_value=yt)

        class _YTDLPCM:
            async def __aenter__(self):
                return mock_ytdlp

            async def __aexit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(YTDLPClient, "from_config", classmethod(lambda cls, cfg: _YTDLPCM()))

        resp = test_app.get("/add/preview/youtube/dQw4w9WgXcQ")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["source"] == "youtube"
        assert payload["id"] == "dQw4w9WgXcQ"
        assert payload["data"]["video"]["id"] == "dQw4w9WgXcQ"
