"""Library scanning and import routes.

Provides endpoints for scanning directories for music videos and importing
them into the library database. Supports two modes:

- **Full Import**: Import all metadata from NFO files
- **Discovery Mode**: Import only title/artist for follow-on workflow processing
"""

from pathlib import Path
from typing import Annotated, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from fuzzbin.auth.schemas import UserInfo
from fuzzbin.tasks import Job, JobType, get_job_queue
from fuzzbin.web.dependencies import get_current_user
from fuzzbin.web.schemas.common import AUTH_ERROR_RESPONSES, COMMON_ERROR_RESPONSES
from fuzzbin.web.schemas.scan import (
    ImportMode,
    ScanJobResponse,
    ScanPreviewItem,
    ScanPreviewResponse,
    ScanRequest,
)
from fuzzbin.workflows.nfo_importer import NFOImporter

import fuzzbin as fuzzbin_module

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/scan", tags=["Library Scan"])


def _get_initial_status(mode: ImportMode) -> str:
    """Map import mode to initial video status.

    Args:
        mode: Import mode

    Returns:
        Status string for new videos
    """
    if mode == ImportMode.FULL:
        return "imported"
    else:  # DISCOVERY
        return "discovered"


@router.post(
    "/preview",
    response_model=ScanPreviewResponse,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Preview directory scan",
    description="Scan a directory and preview what would be imported without making changes.",
)
async def preview_scan(
    request: ScanRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> ScanPreviewResponse:
    """
    Preview a directory scan without importing.

    This endpoint performs a dry-run scan to show:
    - How many NFO files were found
    - Which are music video NFOs vs artist NFOs
    - Which videos would be imported vs skipped
    - Preview of video metadata

    Use this to verify scan parameters before running the actual import.
    """
    directory = Path(request.directory)

    # Validate directory exists
    if not directory.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Directory does not exist: {request.directory}",
        )
    if not directory.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {request.directory}",
        )

    logger.info(
        "scan_preview_starting",
        directory=str(directory),
        mode=request.mode.value,
        recursive=request.recursive,
        user=current_user.username if current_user else "anonymous",
    )

    # Get repository for existence checks
    repository = await fuzzbin_module.get_repository()

    # Create importer just for scanning (we won't actually import)
    from fuzzbin.parsers.musicvideo_parser import MusicVideoNFOParser

    parser = MusicVideoNFOParser()

    # Discover NFO files
    if request.recursive:
        nfo_files = list(directory.rglob("*.nfo"))
    else:
        nfo_files = list(directory.glob("*.nfo"))

    # Filter and analyze
    preview_items: List[ScanPreviewItem] = []
    musicvideo_count = 0
    would_import = 0
    would_skip = 0

    import xml.etree.ElementTree as ET

    for nfo_path in nfo_files:
        # Identify NFO type
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            if root.tag != "musicvideo":
                continue
            musicvideo_count += 1
        except Exception:
            continue

        # Parse NFO for preview
        try:
            nfo = parser.parse_file(nfo_path)
            if not nfo.title or not nfo.artist:
                continue

            # Check if exists
            query = repository.query()
            query = query.where_title(nfo.title)
            query = query.where_artist(nfo.artist)
            results = await query.execute()
            already_exists = len(results) > 0

            if already_exists and request.skip_existing:
                would_skip += 1
            else:
                would_import += 1

            # Only include first 100 items in preview
            if len(preview_items) < 100:
                preview_items.append(
                    ScanPreviewItem(
                        nfo_path=str(nfo_path),
                        title=nfo.title,
                        artist=nfo.artist,
                        album=nfo.album,
                        year=nfo.year,
                        already_exists=already_exists,
                    )
                )

        except Exception as e:
            logger.debug(
                "scan_preview_parse_error",
                nfo_path=str(nfo_path),
                error=str(e),
            )
            continue

    logger.info(
        "scan_preview_complete",
        directory=str(directory),
        total_nfos=len(nfo_files),
        musicvideo_count=musicvideo_count,
        would_import=would_import,
        would_skip=would_skip,
    )

    return ScanPreviewResponse(
        directory=str(directory),
        total_nfo_files=len(nfo_files),
        musicvideo_nfos=musicvideo_count,
        would_import=would_import,
        would_skip=would_skip,
        items=preview_items,
        mode=request.mode,
    )


@router.post(
    "",
    response_model=ScanJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Scan and import music videos",
    description="""Scan a directory for music videos and import them into the library.

**Import Modes:**
- `full`: Import all metadata from NFO files, set status to 'imported'
- `discovery`: Only import title/artist, set status to 'discovered' for follow-on workflows

The scan runs as a background job. Track progress via:
- `GET /jobs/{job_id}` for status polling
- `WebSocket /ws/jobs/{job_id}` for real-time updates
""",
)
async def start_scan(
    request: ScanRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> ScanJobResponse:
    """
    Start a directory scan and import job.

    The scan runs as a background job with progress tracking. After submission,
    use the returned job_id to monitor progress via the jobs API or WebSocket.

    **Option A - Full Import (mode='full'):**
    - Imports all available metadata from NFO files
    - Sets video status to 'imported'
    - Suitable when NFO files have complete, accurate metadata

    **Option B - Discovery Only (mode='discovery'):**
    - Only imports title and artist
    - Sets video status to 'discovered'
    - Designed for follow-on workflows to:
      - Enrich metadata from external APIs (IMVDb, Discogs)
      - Organize files into proper directory structure
      - Download higher quality versions if needed
    """
    directory = Path(request.directory)

    # Validate directory
    if not directory.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Directory does not exist: {request.directory}",
        )
    if not directory.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {request.directory}",
        )

    # Map mode to initial status
    initial_status = _get_initial_status(request.mode)

    logger.info(
        "scan_job_submitting",
        directory=str(directory),
        mode=request.mode.value,
        initial_status=initial_status,
        recursive=request.recursive,
        skip_existing=request.skip_existing,
        user=current_user.username if current_user else "anonymous",
    )

    # Create job with parameters
    job = Job(
        type=JobType.IMPORT_NFO,
        metadata={
            "directory": str(directory.resolve()),
            "recursive": request.recursive,
            "skip_existing": request.skip_existing,
            "initial_status": initial_status,
            "update_file_paths": request.update_file_paths,
            "import_mode": request.mode.value,
        },
    )

    # Submit to queue
    queue = get_job_queue()
    await queue.submit(job)

    logger.info(
        "scan_job_submitted",
        job_id=job.id,
        directory=str(directory),
        mode=request.mode.value,
    )

    return ScanJobResponse(
        job_id=job.id,
        message=f"Scan job submitted. Track progress at /jobs/{job.id}",
        directory=str(directory),
        mode=request.mode,
        initial_status=initial_status,
    )


@router.get(
    "/statuses",
    response_model=dict,
    summary="Get video status definitions",
    description="Get the list of video statuses and their meanings for workflow planning.",
)
async def get_status_definitions(
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> dict:
    """
    Get video status definitions for workflow planning.

    Returns the available video statuses and their typical use cases,
    helping users understand how to structure their import workflows.
    """
    return {
        "statuses": {
            "discovered": {
                "description": "Video identified but not yet processed",
                "typical_use": "Initial discovery, pending metadata enrichment",
                "next_steps": ["Enrich metadata", "Search for downloads"],
            },
            "queued": {
                "description": "Queued for download or processing",
                "typical_use": "Waiting in download queue",
                "next_steps": ["Wait for download to start"],
            },
            "downloading": {
                "description": "Currently being downloaded",
                "typical_use": "Active download in progress",
                "next_steps": ["Wait for completion"],
            },
            "downloaded": {
                "description": "Download complete, pending organization",
                "typical_use": "File exists but not yet organized",
                "next_steps": ["Organize into library structure"],
            },
            "imported": {
                "description": "Fully imported with all metadata",
                "typical_use": "Complete library entry from NFO import",
                "next_steps": ["Review", "Add to collections"],
            },
            "organized": {
                "description": "File organized into library structure",
                "typical_use": "Final state for complete videos",
                "next_steps": ["Enjoy!"],
            },
            "missing": {
                "description": "Expected file not found",
                "typical_use": "File was moved, deleted, or never downloaded",
                "next_steps": ["Re-download", "Update path"],
            },
            "failed": {
                "description": "Processing failed",
                "typical_use": "Download or import error",
                "next_steps": ["Review error", "Retry"],
            },
            "archived": {
                "description": "Archived/hidden from main library",
                "typical_use": "Old versions, duplicates, or hidden items",
                "next_steps": ["Restore if needed"],
            },
        },
        "import_modes": {
            "full": {
                "initial_status": "imported",
                "description": "Import all metadata from NFO files",
                "use_case": "Existing libraries with complete NFO metadata",
            },
            "discovery": {
                "initial_status": "discovered",
                "description": "Import only title and artist",
                "use_case": "New imports requiring metadata enrichment workflow",
            },
        },
    }
