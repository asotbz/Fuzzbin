"""Tests for POST /add/import single-video job submission and handling."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import fuzzbin
from fuzzbin.api.imvdb_client import IMVDbClient
from fuzzbin.clients.ytdlp_client import YTDLPClient
from fuzzbin.common.config import APIClientConfig, YTDLPConfig


def _wait_for_job_completion(client: TestClient, job_id: str, timeout_seconds: float = 2.0) -> dict:
    deadline = time.time() + timeout_seconds
    last = None
    while time.time() < deadline:
        resp = client.get(f"/jobs/{job_id}")
        assert resp.status_code == 200
        last = resp.json()
        if last["status"] in ("completed", "failed", "cancelled", "timeout"):
            return last
        time.sleep(0.02)
    raise AssertionError(f"Job did not complete in time. Last: {last}")


class TestAddImportSingle:
    @pytest.fixture(autouse=True)
    def _enable_job_workers(self, monkeypatch):
        monkeypatch.setenv("FUZZBIN_TEST_JOB_WORKERS", "1")

    def test_add_import_imvdb_creates_video(self, test_app: TestClient, monkeypatch):
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

        resp = test_app.post(
            "/add/import",
            json={
                "source": "imvdb",
                "id": "123",
                "initial_status": "discovered",
                "skip_existing": True,
                "auto_download": False,
            },
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        job = _wait_for_job_completion(test_app, job_id)
        assert job["status"] == "completed"
        assert job["result"]["created"] is True
        assert job["result"]["skipped"] is False
        assert job["result"]["imvdb_video_id"] == "123"
        assert job["result"]["youtube_id"] == "dQw4w9WgXcQ"

        # Video now exists and can be retrieved
        created_video_id = job["result"]["video_id"]
        get_resp = test_app.get(f"/videos/{created_video_id}")
        assert get_resp.status_code == 200
        video_row = get_resp.json()
        assert video_row["title"] == "Smells Like Teen Spirit"
        assert video_row["artist"] == "Nirvana"
        assert video_row["imvdb_video_id"] == "123"
        assert video_row["youtube_id"] == "dQw4w9WgXcQ"

    def test_add_import_youtube_creates_video(self, test_app: TestClient, monkeypatch):
        config = fuzzbin.get_config()
        config.ytdlp = config.ytdlp or YTDLPConfig()

        yt = SimpleNamespace(
            id="dQw4w9WgXcQ",
            title="Video Title",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            channel="Uploader",
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

        resp = test_app.post(
            "/add/import",
            json={
                "source": "youtube",
                "id": "dQw4w9WgXcQ",
                "initial_status": "discovered",
                "skip_existing": True,
                "auto_download": False,
            },
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        job = _wait_for_job_completion(test_app, job_id)
        assert job["status"] == "completed"
        assert job["result"]["youtube_id"] == "dQw4w9WgXcQ"
        assert job["result"]["video_id"] is not None

        created_video_id = job["result"]["video_id"]
        get_resp = test_app.get(f"/videos/{created_video_id}")
        assert get_resp.status_code == 200
        row = get_resp.json()
        assert row["youtube_id"] == "dQw4w9WgXcQ"
        assert row["title"] == "Video Title"
        assert row["artist"] == "Uploader"
