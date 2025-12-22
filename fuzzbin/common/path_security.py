"""Path security utilities for validating and containing file paths.

This module provides functions to prevent path traversal attacks by ensuring
that user-provided paths stay within allowed directories (library_dir, config_dir).
"""

from pathlib import Path
from typing import List, Optional, Union

import structlog

logger = structlog.get_logger(__name__)


class PathSecurityError(ValueError):
    """Raised when a path fails security validation."""

    def __init__(self, message: str, path: str, allowed_roots: List[str]):
        self.path = path
        self.allowed_roots = allowed_roots
        super().__init__(message)


def validate_contained_path(
    user_path: Union[str, Path],
    allowed_roots: List[Union[str, Path]],
    must_exist: bool = False,
) -> Path:
    """Validate that a path is contained within allowed root directories.
    
    This function prevents path traversal attacks by ensuring the resolved
    absolute path stays within one of the allowed root directories. It handles
    symlinks, relative paths, and various escape attempts (../, etc.).
    
    Args:
        user_path: User-provided path (absolute or relative)
        allowed_roots: List of allowed root directories
        must_exist: If True, also verify the path exists
        
    Returns:
        Resolved absolute Path object
        
    Raises:
        PathSecurityError: If path escapes allowed roots or validation fails
        
    Example:
        >>> library_dir = Path("/data/videos")
        >>> validate_contained_path("movie.mp4", [library_dir])
        PosixPath('/data/videos/movie.mp4')
        
        >>> validate_contained_path("../etc/passwd", [library_dir])
        PathSecurityError: Path escapes allowed directories
    """
    if not allowed_roots:
        raise PathSecurityError(
            "No allowed roots specified",
            str(user_path),
            [],
        )
    
    # Normalize allowed roots to resolved Paths
    resolved_roots = []
    for root in allowed_roots:
        root_path = Path(root).resolve()
        if not root_path.exists():
            logger.warning(
                "path_security_root_missing",
                root=str(root_path),
            )
        resolved_roots.append(root_path)
    
    # Convert user path to Path object
    user_path = Path(user_path)
    
    # Handle relative paths - try each root
    if not user_path.is_absolute():
        for root in resolved_roots:
            candidate = (root / user_path).resolve()
            if _is_path_under_roots(candidate, resolved_roots):
                if must_exist and not candidate.exists():
                    continue
                return candidate
        
        # No valid root found
        raise PathSecurityError(
            f"Relative path '{user_path}' could not be resolved under allowed directories",
            str(user_path),
            [str(r) for r in resolved_roots],
        )
    
    # Handle absolute paths
    resolved_path = user_path.resolve()
    
    if not _is_path_under_roots(resolved_path, resolved_roots):
        raise PathSecurityError(
            f"Path '{resolved_path}' is outside allowed directories",
            str(user_path),
            [str(r) for r in resolved_roots],
        )
    
    if must_exist and not resolved_path.exists():
        raise PathSecurityError(
            f"Path '{resolved_path}' does not exist",
            str(user_path),
            [str(r) for r in resolved_roots],
        )
    
    return resolved_path


def _is_path_under_roots(path: Path, roots: List[Path]) -> bool:
    """Check if a resolved path is under any of the root directories."""
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def make_relative_path(
    absolute_path: Union[str, Path],
    root: Union[str, Path],
) -> Path:
    """Convert an absolute path to a path relative to the given root.
    
    Args:
        absolute_path: Absolute path to convert
        root: Root directory to make path relative to
        
    Returns:
        Relative Path object
        
    Raises:
        PathSecurityError: If path is not under the root
    """
    abs_path = Path(absolute_path).resolve()
    root_path = Path(root).resolve()
    
    try:
        return abs_path.relative_to(root_path)
    except ValueError:
        raise PathSecurityError(
            f"Path '{abs_path}' is not under root '{root_path}'",
            str(absolute_path),
            [str(root_path)],
        )


def safe_join(
    root: Union[str, Path],
    *parts: str,
) -> Path:
    """Safely join path parts to a root directory.
    
    Prevents path traversal by validating the result stays under root.
    
    Args:
        root: Root directory
        *parts: Path parts to join
        
    Returns:
        Resolved absolute Path under root
        
    Raises:
        PathSecurityError: If resulting path escapes root
    """
    root_path = Path(root).resolve()
    result = root_path.joinpath(*parts).resolve()
    
    if not _is_path_under_roots(result, [root_path]):
        raise PathSecurityError(
            f"Path traversal detected: {'/'.join(parts)} escapes {root_path}",
            "/".join(parts),
            [str(root_path)],
        )
    
    return result


def validate_media_path(
    path: Union[str, Path],
    library_dir: Union[str, Path],
    allowed_extensions: Optional[List[str]] = None,
) -> Path:
    """Validate a media file path for storage or access.
    
    Args:
        path: Path to validate
        library_dir: Library root directory
        allowed_extensions: Optional list of allowed extensions (e.g., ['.mp4', '.mkv'])
        
    Returns:
        Validated absolute Path
        
    Raises:
        PathSecurityError: If validation fails
    """
    validated_path = validate_contained_path(path, [library_dir])
    
    if allowed_extensions:
        ext = validated_path.suffix.lower()
        if ext not in [e.lower() for e in allowed_extensions]:
            raise PathSecurityError(
                f"File extension '{ext}' not allowed. Allowed: {allowed_extensions}",
                str(path),
                [str(library_dir)],
            )
    
    return validated_path


def validate_nfo_path(
    path: Union[str, Path],
    library_dir: Union[str, Path],
) -> Path:
    """Validate an NFO metadata file path.
    
    Args:
        path: Path to validate
        library_dir: Library root directory
        
    Returns:
        Validated absolute Path
        
    Raises:
        PathSecurityError: If validation fails
    """
    return validate_media_path(path, library_dir, allowed_extensions=[".nfo"])


def validate_export_path(
    path: Union[str, Path],
    allowed_roots: List[Union[str, Path]],
    allowed_extensions: Optional[List[str]] = None,
) -> Path:
    """Validate an export output path.
    
    Ensures exports can only be written to allowed directories.
    
    Args:
        path: Export destination path
        allowed_roots: List of allowed output directories
        allowed_extensions: Optional list of allowed extensions
        
    Returns:
        Validated absolute Path
        
    Raises:
        PathSecurityError: If validation fails
    """
    validated_path = validate_contained_path(path, allowed_roots)
    
    if allowed_extensions:
        ext = validated_path.suffix.lower()
        if ext not in [e.lower() for e in allowed_extensions]:
            raise PathSecurityError(
                f"Export extension '{ext}' not allowed. Allowed: {allowed_extensions}",
                str(path),
                [str(r) for r in allowed_roots],
            )
    
    return validated_path
