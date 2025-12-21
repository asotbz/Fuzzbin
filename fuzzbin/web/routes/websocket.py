"""WebSocket endpoints for real-time updates."""

import asyncio

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from fuzzbin.tasks import get_job_queue
from fuzzbin.web.schemas.jobs import JobProgressUpdate

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/jobs/{job_id}")
async def job_progress_websocket(websocket: WebSocket, job_id: str) -> None:
    """WebSocket endpoint for real-time job progress updates.

    Connects to a specific job and streams progress updates until the job
    reaches a terminal state (completed, failed, or cancelled).

    Args:
        websocket: WebSocket connection
        job_id: Job ID to monitor

    Protocol:
        1. Client connects to /ws/jobs/{job_id}
        2. Server accepts and sends initial job state
        3. Server polls job status every 500ms and sends updates
        4. Server closes connection when job reaches terminal state
        5. Client can disconnect at any time

    Message Format (JSON):
        {
            "job_id": "uuid",
            "status": "running",
            "progress": 0.45,
            "current_step": "Processing file.nfo...",
            "processed_items": 45,
            "total_items": 100,
            "error": null,
            "result": null
        }
    """
    await websocket.accept()
    logger.info("websocket_connected", job_id=job_id)

    try:
        queue = get_job_queue()
    except RuntimeError:
        await websocket.send_json({"error": "Job queue not initialized"})
        await websocket.close(code=1011, reason="Job queue not initialized")
        return

    try:
        # Send initial job state
        job = await queue.get_job(job_id)
        if not job:
            await websocket.send_json({"error": "Job not found"})
            await websocket.close(code=1008, reason="Job not found")
            return

        # Send initial state
        update = JobProgressUpdate(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            current_step=job.current_step,
            processed_items=job.processed_items,
            total_items=job.total_items,
            error=job.error,
            result=job.result,
        )
        await websocket.send_json(update.model_dump(mode="json"))

        # Poll for updates every 500ms
        last_progress = job.progress
        last_step = job.current_step

        while True:
            await asyncio.sleep(0.5)

            job = await queue.get_job(job_id)
            if not job:
                logger.warning("job_disappeared", job_id=job_id)
                break

            # Only send update if something changed
            if (
                job.progress != last_progress
                or job.current_step != last_step
                or job.is_terminal
            ):
                update = JobProgressUpdate(
                    job_id=job.id,
                    status=job.status,
                    progress=job.progress,
                    current_step=job.current_step,
                    processed_items=job.processed_items,
                    total_items=job.total_items,
                    error=job.error,
                    result=job.result,
                )
                await websocket.send_json(update.model_dump(mode="json"))
                last_progress = job.progress
                last_step = job.current_step

            # Exit if job is terminal
            if job.is_terminal:
                logger.info(
                    "job_terminal_state",
                    job_id=job_id,
                    status=job.status.value,
                )
                break

    except WebSocketDisconnect:
        logger.info("websocket_disconnected", job_id=job_id)
    except Exception as e:
        logger.error("websocket_error", job_id=job_id, error=str(e), exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass  # Connection may already be closed
    finally:
        logger.info("websocket_closed", job_id=job_id)
