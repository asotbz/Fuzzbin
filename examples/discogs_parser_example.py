"""Example usage of Discogs response parser."""

import asyncio
import json
from pathlib import Path

from fuzzbin import (
    DiscogsClient,
    DiscogsParser,
    configure,
)


async def main():
    """Demonstrate Discogs parser usage."""
    # Configure fuzzbin
    config_path = Path(__file__).parent.parent / "config.yaml"
    configure(config_path=config_path)

    # Example 1: Parse search response from file
    print("=" * 70)
    print("Example 1: Parse Search Response")
    print("=" * 70)
    
    with open("examples/discogs_search_response.json") as f:
        search_data = json.load(f)
    
    search_results = DiscogsParser.parse_search_response(search_data)
    print(f"Total results: {search_results.pagination.items}")
    print(f"Results per page: {search_results.pagination.per_page}")
    print(f"\nFirst 3 results:")
    for i, result in enumerate(search_results.results[:3], 1):
        print(f"  {i}. {result.title}")
        print(f"     Type: {result.type}, Year: {result.year}, Master ID: {result.master_id}")
    
    # Example 2: Find earliest master
    print("\n" + "=" * 70)
    print("Example 2: Find Earliest Master Release")
    print("=" * 70)
    
    earliest = DiscogsParser.find_earliest_master(
        search_results, 
        artist="Nirvana", 
        track_title="Nevermind"
    )
    print(f"Earliest master: {earliest.title}")
    print(f"Master ID: {earliest.master_id}")
    print(f"Year: {earliest.year}")
    
    # Example 3: Parse master response with validation
    print("\n" + "=" * 70)
    print("Example 3: Parse Master Response with Validation")
    print("=" * 70)
    
    with open("examples/discogs_master_response.json") as f:
        master_data = json.load(f)
    
    # Valid artist and track
    master = DiscogsParser.parse_master_response(
        master_data,
        artist="Nirvana",
        track_title="Smells Like Teen Spirit"
    )
    print(f"Title: {master.title}")
    print(f"Year: {master.year}")
    print(f"Artists: {', '.join(a.name for a in master.artists)}")
    print(f"Genres: {', '.join(master.genres)}")
    print(f"Styles: {', '.join(master.styles)}")
    print(f"Tracks: {len(master.tracklist)}")
    print(f"Validation passed: {master.is_exact_match}")
    
    # Invalid artist
    master_invalid = DiscogsParser.parse_master_response(
        master_data,
        artist="Pearl Jam",
        track_title="Smells Like Teen Spirit"
    )
    print(f"\nValidation with wrong artist: {master_invalid.is_exact_match}")
    
    # Example 4: Filter music videos
    print("\n" + "=" * 70)
    print("Example 4: Filter Music Videos")
    print("=" * 70)
    
    print(f"Total videos: {len(master.videos)}")
    music_videos = DiscogsParser._filter_music_videos(master.videos)
    print(f"Music videos only: {len(music_videos)}")
    print(f"\nMusic video titles:")
    for i, video in enumerate(music_videos[:5], 1):
        print(f"  {i}. {video.title}")
    
    # Example 5: Parse release response
    print("\n" + "=" * 70)
    print("Example 5: Parse Release Response")
    print("=" * 70)
    
    with open("examples/discogs_release_response.json") as f:
        release_data = json.load(f)
    
    release = DiscogsParser.parse_release_response(
        release_data,
        artist="Nirvana",
        track_title="In Bloom"
    )
    print(f"Title: {release.title}")
    print(f"Year: {release.year}")
    print(f"Country: {release.country}")
    print(f"Labels: {', '.join(label.name for label in release.labels)}")
    print(f"Validation passed: {release.is_exact_match}")
    
    # Example 6: Parse artist releases (masters only)
    print("\n" + "=" * 70)
    print("Example 6: Parse Artist Releases (Masters Only)")
    print("=" * 70)
    
    with open("examples/discogs_artist_releases_response.json") as f:
        artist_releases_data = json.load(f)
    
    artist_releases = DiscogsParser.parse_artist_releases_response(artist_releases_data)
    print(f"Total items in response: {artist_releases.pagination.items}")
    print(f"Master releases returned: {len(artist_releases.releases)}")
    print(f"\nFirst 5 master releases:")
    for i, rel in enumerate(artist_releases.releases[:5], 1):
        print(f"  {i}. {rel.title} ({rel.year})")
        print(f"     Master ID: {rel.id}, Main Release: {rel.main_release}")
    
    # Example 7: Using with DiscogsClient (requires API credentials)
    print("\n" + "=" * 70)
    print("Example 7: Live API Usage (requires credentials)")
    print("=" * 70)
    
    try:
        from fuzzbin import get_config
        
        config = get_config()
        async with DiscogsClient.from_config(config.apis["discogs"]) as client:
            # Search for releases
            search_response = await client.search_releases("Nirvana", "Nevermind")
            results = DiscogsParser.parse_search_response(search_response)
            
            # Find earliest master
            earliest = DiscogsParser.find_earliest_master(
                results,
                artist="Nirvana",
                track_title="Nevermind"
            )
            
            # Get master details
            master_response = await client.get_master(earliest.master_id)
            master = DiscogsParser.parse_master_response(
                master_response,
                artist="Nirvana",
                track_title="Smells Like Teen Spirit"
            )
            
            # Filter to music videos only
            music_videos = DiscogsParser._filter_music_videos(master.videos)
            
            print(f"Found master: {master.title} ({master.year})")
            print(f"Genres: {', '.join(master.genres)}")
            print(f"Music videos: {len(music_videos)}")
            print(f"Validation passed: {master.is_exact_match}")
            
    except Exception as e:
        print(f"Note: API credentials required for live usage")
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
