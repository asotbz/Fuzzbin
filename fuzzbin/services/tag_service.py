"""Tag service for managing video tags with NFO synchronization.

This service wraps all tag mutation operations to ensure NFO files
stay in sync with database tag changes. Single-video operations
trigger inline NFO export; bulk operations submit background jobs.
"""

from typing import Any, Dict, List, Optional

import structlog

from fuzzbin.core.db.repository import VideoRepository

from .base import BaseService, ServiceCallback

logger = structlog.get_logger(__name__)


class TagService(BaseService):
    """Service for tag operations with NFO sync side-effects.

    All tag mutation methods check ``config.nfo.write_musicvideo_nfo``
    and, when enabled, re-export the affected video's NFO file so that
    on-disk tags stay consistent with the database.

    For bulk operations the NFO export is offloaded to a background
    ``EXPORT_NFO_SELECTIVE`` job to avoid blocking the API response.
    """

    def __init__(
        self,
        repository: VideoRepository,
        callback: Optional[ServiceCallback] = None,
    ):
        super().__init__(repository, callback)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _export_nfo_for_video(self, video_id: int) -> None:
        """Re-export a single video's NFO file if auto-export is enabled."""
        config = self._get_config()
        if not config.nfo.write_musicvideo_nfo:
            return

        from fuzzbin.core.db.exporter import NFOExporter

        try:
            exporter = NFOExporter(self.repository)
            await exporter.export_video_to_nfo(video_id)
            self.logger.debug("nfo_exported_after_tag_change", video_id=video_id)
        except Exception as e:
            # NFO export failure should not break tag operations
            self.logger.warning(
                "nfo_export_failed_after_tag_change",
                video_id=video_id,
                error=str(e),
            )

    async def _submit_selective_nfo_export(self, video_ids: List[int]) -> Optional[str]:
        """Submit a background job to re-export NFO files for specific videos.

        Returns:
            The job ID if submitted, None if NFO export is disabled or no videos.
        """
        config = self._get_config()
        if not config.nfo.write_musicvideo_nfo or not video_ids:
            return None

        from fuzzbin.tasks.models import Job, JobPriority, JobType
        from fuzzbin.tasks.queue import get_job_queue

        try:
            queue = get_job_queue()
            job = Job(
                type=JobType.EXPORT_NFO_SELECTIVE,
                metadata={"video_ids": video_ids},
                priority=JobPriority.LOW,
            )
            await queue.submit(job)
            self.logger.info(
                "selective_nfo_export_queued",
                job_id=job.id,
                video_count=len(video_ids),
            )
            return job.id
        except Exception as e:
            self.logger.warning(
                "selective_nfo_export_queue_failed",
                video_count=len(video_ids),
                error=str(e),
            )
            return None

    async def _emit_tags_changed(self, video_id: int) -> None:
        """Emit a video_updated WebSocket event for tag changes."""
        from fuzzbin.core.event_bus import get_event_bus

        try:
            event_bus = get_event_bus()
            await event_bus.emit_video_updated(
                video_id=video_id,
                fields_changed=["tags"],
            )
        except RuntimeError:
            pass  # Event bus not initialized (e.g. tests)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def set_video_tags(
        self,
        video_id: int,
        tags: List[str],
        source: str = "manual",
        replace_existing: bool = True,
    ) -> List[Dict[str, Any]]:
        """Set tags on a video, then sync NFO.

        Args:
            video_id: Video ID
            tags: Tag name strings to set
            source: Tag source ('manual' or 'auto')
            replace_existing: If True, replaces all tags; if False, adds to existing

        Returns:
            Updated list of tag dicts for the video
        """
        await self.repository.set_video_tags(
            video_id,
            tags,
            source=source,
            replace_existing=replace_existing,
        )
        self.logger.info(
            "video_tags_set",
            video_id=video_id,
            tag_count=len(tags),
            replace=replace_existing,
        )

        await self._export_nfo_for_video(video_id)
        await self._emit_tags_changed(video_id)

        return await self.repository.get_video_tags(video_id)

    async def add_video_tag(self, video_id: int, tag_id: int) -> None:
        """Add a single tag to a video by tag ID, then sync NFO.

        Args:
            video_id: Video ID
            tag_id: Tag ID to add
        """
        await self.repository.add_video_tag(video_id, tag_id)
        self.logger.info("video_tag_added", video_id=video_id, tag_id=tag_id)

        await self._export_nfo_for_video(video_id)
        await self._emit_tags_changed(video_id)

    async def remove_video_tag(self, video_id: int, tag_id: int) -> None:
        """Remove a single tag from a video by tag ID, then sync NFO.

        Args:
            video_id: Video ID
            tag_id: Tag ID to remove
        """
        await self.repository.remove_video_tag(video_id, tag_id)
        self.logger.info("video_tag_removed", video_id=video_id, tag_id=tag_id)

        await self._export_nfo_for_video(video_id)
        await self._emit_tags_changed(video_id)

    async def bulk_apply_tags(
        self,
        video_ids: List[int],
        tag_names: List[str],
        replace: bool = False,
    ) -> Dict[str, Any]:
        """Bulk apply tags to multiple videos, then queue NFO export.

        The tag mutation happens synchronously; NFO re-export is queued
        as a background ``EXPORT_NFO_SELECTIVE`` job for the affected IDs.

        Args:
            video_ids: List of video IDs
            tag_names: Tag name strings to apply
            replace: If True, replaces existing tags; if False, adds

        Returns:
            Repo result dict with success_ids, failed_ids, errors
        """
        result = await self.repository.bulk_apply_tags(
            video_ids=video_ids,
            tag_names=tag_names,
            replace=replace,
        )

        # Queue NFO export for successfully tagged videos
        success_ids = result.get("success_ids", [])
        if success_ids:
            await self._submit_selective_nfo_export(success_ids)

        self.logger.info(
            "bulk_tags_applied",
            total=len(video_ids),
            success=len(success_ids),
            failed=len(result.get("failed_ids", [])),
            tags=tag_names,
            replace=replace,
        )

        return result
