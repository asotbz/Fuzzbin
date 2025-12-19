"""Example usage of NFO parsers."""

from pathlib import Path

from fuzzbin.parsers import (
    ArtistNFO,
    ArtistNFOParser,
    MusicVideoNFO,
    MusicVideoNFOParser,
)


def artist_example():
    """Demonstrate artist NFO parsing."""
    print("=== Artist NFO Example ===\n")

    parser = ArtistNFOParser()

    # Parse from file
    nfo_path = Path("examples/artist.nfo")
    if nfo_path.exists():
        artist = parser.parse_file(nfo_path)
        print(f"Loaded artist: {artist.name}")

    # Create new artist NFO
    artist = ArtistNFO(name="Pearl Jam")
    print(f"\nCreated: {artist.name}")

    # Update field
    artist = parser.update_field(artist, "name", "Pearl Jam (Seattle)")
    print(f"Updated: {artist.name}")

    # Write to file
    output_path = Path("output_artist.nfo")
    parser.write_file(artist, output_path)
    print(f"\nWrote to: {output_path}")

    # Show XML
    xml = parser.to_xml_string(artist)
    print(f"\nGenerated XML:\n{xml}")


def musicvideo_example():
    """Demonstrate music video NFO parsing."""
    print("\n=== Music Video NFO Example ===\n")

    parser = MusicVideoNFOParser()

    # Parse from file
    nfo_path = Path("examples/musicvideo.nfo")
    if nfo_path.exists():
        video = parser.parse_file(nfo_path)
        print(f"Loaded video: {video.title}")
        print(f"Artist: {video.artist}")
        print(f"Year: {video.year}")
        print(f"Tags: {', '.join(video.tags)}")

    # Create new music video NFO
    video = MusicVideoNFO(
        title="Smells Like Teen Spirit",
        album="Nevermind",
        studio="DGC",
        year=1991,
        director="Samuel Bayer",
        genre="Rock",
        artist="Nirvana",
        tags=["90s", "grunge"],
    )

    print(f"\n\nCreated new video:")
    print(f"Title: {video.title}")
    print(f"Artist: {video.artist}")
    print(f"Year: {video.year}")
    print(f"Tags: {', '.join(video.tags)}")

    # Add tag
    video = parser.add_tag(video, "alternative")
    print(f"\nAfter adding tag: {', '.join(video.tags)}")

    # Remove tag
    video = parser.remove_tag(video, "grunge")
    print(f"After removing 'grunge': {', '.join(video.tags)}")

    # Update field
    video = parser.update_field(video, "director", "Samuel Benjamin Bayer")
    print(f"\nUpdated director: {video.director}")

    # Write to file
    output_path = Path("output_musicvideo.nfo")
    parser.write_file(video, output_path)
    print(f"\nWrote to: {output_path}")

    # Parse it back
    parsed = parser.parse_file(output_path)
    print(f"\nRe-parsed title: {parsed.title}")

    # Show XML
    xml = parser.to_xml_string(video)
    print(f"\nGenerated XML:\n{xml}")


def config_based_parser_example():
    """Example using configuration for featured artist handling."""
    from pathlib import Path
    from fuzzbin.common.config import Config
    from fuzzbin.parsers import MusicVideoNFOParser, MusicVideoNFO

    print("\n=== Config-Based NFO Parser Example ===\n")

    # Load configuration from YAML file
    try:
        config = Config.from_yaml(Path("config.yaml"))
        print(f"✓ Loaded config from config.yaml")
        print(f"  Featured artists enabled: {config.nfo.featured_artists.enabled}")
        print(f"  Append to field: {config.nfo.featured_artists.append_to_field}")
    except Exception as e:
        print(f"Could not load config.yaml: {e}")
        print("Using default config...")
        config = Config()
    
    # Create parser with config-based featured artist settings
    parser = MusicVideoNFOParser(
        featured_config=config.nfo.featured_artists
    )

    # Create NFO data with featured artists
    nfo = MusicVideoNFO(
        artist="Robin Thicke",
        title="Blurred Lines",
        year=2013,
        genre="R&B",
        featured_artists=["T.I.", "Pharrell Williams"]
    )

    # Generate XML - behavior depends on config.nfo.featured_artists settings
    xml_string = parser.to_xml_string(nfo)
    
    print("\nGenerated XML with config-based featured artist handling:")
    print(xml_string)
    
    print("\nBehavior explanation:")
    if config.nfo.featured_artists.enabled:
        print(f"  Featured artists are appended to '{config.nfo.featured_artists.append_to_field}' field")
        print(f"  No separate <featured_artists> tag in XML")
    else:
        print(f"  Featured artists are omitted from XML output")


if __name__ == "__main__":
    artist_example()
    musicvideo_example()
    
    print("\n" + "=" * 60)
    print("Config-Based NFO Parser Example")
    print("=" * 60)
    config_based_parser_example()
