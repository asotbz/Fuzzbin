"""Example usage of the music video file organizer.

This example demonstrates how to use the build_media_paths function to generate
organized paths for music video files and their NFO metadata files.
"""

from pathlib import Path
from fuzzbin.parsers import MusicVideoNFO, MusicVideoNFOParser
from fuzzbin.core.organizer import build_media_paths


def basic_example():
    """Basic organizer usage without normalization."""
    print("=== Basic Organizer Example ===\n")

    # Create sample NFO data
    nfo = MusicVideoNFO(
        artist="Robin Thicke",
        title="Blurred Lines",
        year=2013,
        album="Blurred Lines",
        genre="R&B",
        director="Diane Martel",
    )

    # Build paths without normalization
    paths = build_media_paths(
        root_path=Path("/var/media/music_videos"),
        pattern="{artist}/{title}",
        nfo_data=nfo,
    )

    print(f"Video: {paths.video_path}")
    print(f"NFO:   {paths.nfo_path}")
    print()


def normalized_example():
    """Example with filename normalization."""
    print("=== Normalized Example ===\n")

    # Create NFO with special characters and diacritics
    nfo = MusicVideoNFO(
        artist="Björk",
        title="Humúríús - (Official Video)",
        year=1997,
        album="Homogenic",
    )

    # Build paths WITH normalization
    paths = build_media_paths(
        root_path=Path("/var/media/music_videos"),
        pattern="{artist}/{year}/{title}",
        nfo_data=nfo,
        video_extension=".mkv",
        normalize=True,  # Enable normalization
    )

    print(f"Video: {paths.video_path}")
    print(f"NFO:   {paths.nfo_path}")
    print("\nNote: Special chars removed, diacritics normalized, spaces -> underscores")
    print()


def complex_pattern_example():
    """Example with complex nested pattern."""
    print("=== Complex Pattern Example ===\n")

    nfo = MusicVideoNFO(
        genre="Rock",
        artist="AC/DC",
        year=1980,
        album="Back In Black",
        title="You Shook Me All Night Long",
        director="David Mallet",
    )

    # Build deeply nested paths
    paths = build_media_paths(
        root_path=Path("/var/media/music_videos"),
        pattern="{genre}/{artist}/{year}/{album}/{title}",
        nfo_data=nfo,
        normalize=True,
    )

    print(f"Video: {paths.video_path}")
    print(f"NFO:   {paths.nfo_path}")
    print()


def parse_and_organize_example():
    """Example integrating NFO parser with organizer."""
    print("=== Parse & Organize Example ===\n")

    # First, parse an existing NFO file
    parser = MusicVideoNFOParser()

    # Create a sample NFO for this example
    sample_nfo = MusicVideoNFO(
        artist="Nirvana",
        title="Smells Like Teen Spirit",
        year=1991,
        album="Nevermind",
        genre="Grunge",
    )

    # Write it to a temp file
    nfo_path = Path("temp_video.nfo")
    parser.write_file(sample_nfo, nfo_path)

    # Parse it back
    parsed_nfo = parser.parse_file(nfo_path)

    # Build organized paths from parsed data
    paths = build_media_paths(
        root_path=Path("/var/media/music_videos"),
        pattern="{genre}/{artist}/{year}/{title}",
        nfo_data=parsed_nfo,
        video_extension=".mp4",
        normalize=True,
    )

    print(f"Parsed NFO from: {nfo_path}")
    print(f"Target video:    {paths.video_path}")
    print(f"Target NFO:      {paths.nfo_path}")

    # Clean up temp file
    nfo_path.unlink()
    print()


def workflow_example():
    """Complete workflow: organize and prepare for file operations."""
    print("=== Complete Workflow Example ===\n")

    # Simulated scenario: You have a downloaded video file and NFO
    downloaded_video = Path("downloaded_video.mp4")
    downloaded_nfo = MusicVideoNFO(
        artist="Daft Punk",
        title="Get Lucky",
        year=2013,
        album="Random Access Memories",
        genre="Electronic",
    )

    library_root = Path("/var/media/music_videos")

    # Build target paths
    paths = build_media_paths(
        root_path=library_root,
        pattern="{genre}/{artist}/{album}/{title}",
        nfo_data=downloaded_nfo,
        video_extension=".mp4",
        normalize=True,
    )

    print(f"Source video (simulated): {downloaded_video}")
    print(f"Target video path:        {paths.video_path}")
    print(f"Target NFO path:          {paths.nfo_path}")
    print()

    # In a real scenario, you would now:
    # 1. Create the directory structure
    print("Next steps in real workflow:")
    print(f"1. Create directories:  {paths.video_path.parent}")
    print(f"   paths.video_path.parent.mkdir(parents=True, exist_ok=True)")
    print()
    print(f"2. Move video file:     {downloaded_video} -> {paths.video_path}")
    print(f"   shutil.move(str(downloaded_video), str(paths.video_path))")
    print()
    print(f"3. Write NFO file:      {paths.nfo_path}")
    print(f"   parser.write_file(downloaded_nfo, paths.nfo_path)")
    print()


def error_handling_example():
    """Example showing error handling."""
    print("=== Error Handling Example ===\n")

    from fuzzbin.core.exceptions import (
        MissingFieldError,
        InvalidPatternError,
        InvalidPathError,
    )

    # Example 1: Missing field
    print("1. Handling missing NFO field:")
    try:
        nfo = MusicVideoNFO(artist="Artist")  # title is missing
        paths = build_media_paths(
            root_path=Path("/var/media"),
            pattern="{artist}/{title}",  # title is required
            nfo_data=nfo,
        )
    except MissingFieldError as e:
        print(f"   Error: {e}")
        print(f"   Missing field: {e.field}")
    print()

    # Example 2: Invalid pattern field
    print("2. Handling invalid pattern field:")
    try:
        nfo = MusicVideoNFO(artist="Artist", title="Title")
        paths = build_media_paths(
            root_path=Path("/var/media"),
            pattern="{invalid_field}",  # doesn't exist in model
            nfo_data=nfo,
        )
    except InvalidPatternError as e:
        print(f"   Error: {e}")
        print(f"   Pattern: {e.pattern}")
    print()

    # Example 3: Invalid root path
    print("3. Handling invalid root path:")
    try:
        nfo = MusicVideoNFO(artist="Artist", title="Title")
        paths = build_media_paths(
            root_path=Path("/nonexistent/path"),
            pattern="{artist}/{title}",
            nfo_data=nfo,
        )
    except InvalidPathError as e:
        print(f"   Error: {e}")
        print(f"   Path: {e.path}")
    print()


if __name__ == "__main__":
    basic_example()
    normalized_example()
    complex_pattern_example()
    parse_and_organize_example()
    workflow_example()
    error_handling_example()

    print("=== Summary ===")
    print("The organizer supports:")
    print("- Flexible path patterns with {field} placeholders")
    print("- Optional filename normalization (diacritics, special chars, etc.)")
    print("- Custom video file extensions")
    print("- Integration with NFO parsers")
    print("- Comprehensive error handling")
    print("\nAvailable pattern fields:")
    print("  {artist}, {title}, {album}, {year}, {genre}, {director}, {studio}")


def config_based_example():
    """Example using configuration file for organizer settings."""
    from pathlib import Path
    from fuzzbin.common.config import Config, OrganizerConfig
    from fuzzbin.core import build_media_paths
    from fuzzbin.parsers.models import MusicVideoNFO

    print("\n=== Config-Based Organizer Example ===\n")

    # Load configuration from YAML file
    try:
        config = Config.from_yaml(Path("config.yaml"))
        print(f"✓ Loaded config from config.yaml")
        print(f"  Pattern: {config.organizer.path_pattern}")
        print(f"  Normalize: {config.organizer.normalize_filenames}")
    except Exception as e:
        print(f"Could not load config.yaml: {e}")
        print("Using programmatic config instead...")
        config = None
    
    # Or create OrganizerConfig programmatically
    organizer_config = OrganizerConfig(
        path_pattern="{genre}/{artist}/{year}/{title}",
        normalize_filenames=True
    )
    
    # Validate pattern on-demand (useful for hot-reload scenarios)
    try:
        organizer_config.validate_pattern()
        print("\n✓ Pattern validated successfully")
    except ValueError as e:
        print(f"\n✗ Pattern validation failed: {e}")
        return

    # Create sample NFO data
    nfo = MusicVideoNFO(
        artist="Daft Punk",
        title="Get Lucky",
        album="Random Access Memories",
        year=2013,
        genre="Electronic",
        featured_artists=["Pharrell Williams", "Nile Rodgers"]
    )

    # Use config to build paths
    paths = build_media_paths(
        root_path=Path("/var/media/music_videos"),
        nfo_data=nfo,
        config=organizer_config
    )

    print(f"\nConfig-based paths (normalized):")
    print(f"  Video: {paths.video_path}")
    print(f"  NFO:   {paths.nfo_path}")
    # Output:
    #   Video: /var/media/music_videos/electronic/daft_punk/2013/get_lucky.mp4
    #   NFO:   /var/media/music_videos/electronic/daft_punk/2013/get_lucky.nfo

    # Override config settings with explicit parameters
    paths_override = build_media_paths(
        root_path=Path("/var/media/music_videos"),
        nfo_data=nfo,
        pattern="{artist}/{title}",  # Override pattern
        normalize=False,              # Override normalization
        config=organizer_config       # Config provides fallback defaults
    )

    print(f"\nOverridden paths (not normalized):")
    print(f"  Video: {paths_override.video_path}")
    print(f"  NFO:   {paths_override.nfo_path}")
    # Output:
    #   Video: /var/media/music_videos/Daft Punk/Get Lucky.mp4
    #   NFO:   /var/media/music_videos/Daft Punk/Get Lucky.mp4


if __name__ == "__main__":
    main()
    
    print("\n" + "=" * 60)
    print("Config-Based Organizer Example")
    print("=" * 60)
    config_based_example()
