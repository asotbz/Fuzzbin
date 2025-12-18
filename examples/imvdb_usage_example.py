"""
Example usage of the IMVDb API client.

This example demonstrates how to:
1. Search for entities (artists) by name
2. Get entity details with video counts
3. Search for videos by artist and track
4. Get video details with director, sources, and featured artists

Before running:
1. Set your IMVDb API key in the IMVDB_APP_KEY environment variable, or
2. Update the config.yaml file with your API key in the apis.imvdb.custom.app_key field

Run with:
    python examples/imvdb_usage_example.py
"""

import asyncio
from pathlib import Path

import httpx

import fuzzbin
from fuzzbin.api.imvdb_client import IMVDbClient


async def search_artist_entity(client: IMVDbClient, artist_name: str) -> dict:
    """
    Search for an artist entity by name.

    Args:
        client: IMVDbClient instance
        artist_name: Name of the artist to search for

    Returns:
        Entity data for the first matching result
    """
    print(f"\n{'='*60}")
    print(f"Searching for entity: {artist_name}")
    print(f"{'='*60}")

    try:
        results = await client.search_entities(artist_name)
        print(f"Found {results['total_results']} entities")
        print(f"Page {results['current_page']} of {results['total_pages']}")

        if not results["results"]:
            print("No entities found!")
            return None

        # Display first few results
        print(f"\nTop {min(5, len(results['results']))} results:")
        for i, entity in enumerate(results["results"][:5], 1):
            print(f"  {i}. {entity['slug']} (ID: {entity['id']})")
            print(f"     Videos: {entity['artist_video_count']} as artist, "
                  f"{entity['featured_video_count']} featured")

        # Return the first result that matches our search
        first_match = results["results"][0]
        return first_match

    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code} - {e.response.text}")
        return None


async def get_entity_details(client: IMVDbClient, entity_id: int) -> dict:
    """
    Get detailed information about an entity.

    Args:
        client: IMVDbClient instance
        entity_id: IMVDb entity ID

    Returns:
        Detailed entity data
    """
    print(f"\n{'='*60}")
    print(f"Getting entity details for ID: {entity_id}")
    print(f"{'='*60}")

    try:
        entity = await client.get_entity(entity_id)
        
        print(f"\nEntity: {entity['slug']}")
        print(f"Artist Video Count: {entity['artist_video_count']}")
        print(f"Featured Video Count: {entity['featured_video_count']}")

        # Display artist videos
        if entity.get("artist_videos") and entity["artist_videos"]["videos"]:
            print(f"\nArtist Videos (showing first 10 of "
                  f"{entity['artist_videos']['total_videos']}):")
            for i, video in enumerate(entity["artist_videos"]["videos"][:10], 1):
                print(f"  {i}. {video['song_title']} ({video.get('year', 'N/A')})")

        # Display featured videos
        if entity.get("featured_artist_videos") and entity["featured_artist_videos"]["videos"]:
            print(f"\nFeatured Videos (showing first 5):")
            for i, video in enumerate(entity["featured_artist_videos"]["videos"][:5], 1):
                print(f"  {i}. {video['song_title']} ({video.get('year', 'N/A')})")

        return entity

    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code} - {e.response.text}")
        return None


async def search_videos(client: IMVDbClient, artist: str, track_title: str) -> dict:
    """
    Search for videos by artist and track title.

    Args:
        client: IMVDbClient instance
        artist: Artist name
        track_title: Track title

    Returns:
        Search results with video list
    """
    print(f"\n{'='*60}")
    print(f"Searching for videos: {artist} - {track_title}")
    print(f"{'='*60}")

    try:
        results = await client.search_videos(artist, track_title)
        print(f"Found {results['total_results']} videos")
        print(f"Page {results['current_page']} of {results['total_pages']}")

        if not results["results"]:
            print("No videos found!")
            return None

        # Display results
        print(f"\nTop {min(10, len(results['results']))} results:")
        for i, video in enumerate(results["results"][:10], 1):
            print(f"  {i}. {video['song_title']} ({video.get('year', 'N/A')})")
            print(f"     ID: {video['id']}")
            print(f"     URL: {video['url']}")

        return results

    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code} - {e.response.text}")
        return None


async def get_video_details(client: IMVDbClient, video_id: int) -> dict:
    """
    Get detailed information about a video.

    Args:
        client: IMVDbClient instance
        video_id: IMVDb video ID

    Returns:
        Detailed video data
    """
    print(f"\n{'='*60}")
    print(f"Getting video details for ID: {video_id}")
    print(f"{'='*60}")

    try:
        video = await client.get_video(video_id)
        
        print(f"\nVideo: {video['song_title']}")
        print(f"Year: {video.get('year', 'N/A')}")
        print(f"URL: {video['url']}")

        # Display artists
        if video.get("artists"):
            print(f"\nArtists:")
            for artist in video["artists"]:
                print(f"  - {artist['name']}")

        # Display featured artists
        if video.get("featured_artists"):
            print(f"\nFeatured Artists:")
            for artist in video["featured_artists"]:
                print(f"  - {artist['name']}")

        # Display directors
        if video.get("directors"):
            print(f"\nDirectors:")
            for director in video["directors"]:
                print(f"  - {director['entity_name']}")

        # Display sources
        if video.get("sources"):
            print(f"\nVideo Sources:")
            for source in video["sources"]:
                primary = " (PRIMARY)" if source.get("is_primary") else ""
                print(f"  - {source['source']}: {source['source_data']}{primary}")

        # Display credits summary
        if video.get("credits"):
            crew_count = len(video["credits"].get("crew", []))
            cast_count = len(video["credits"].get("cast", []))
            print(f"\nCredits: {crew_count} crew, {cast_count} cast")
            
            # Show some crew roles
            if video["credits"].get("crew"):
                print("  Sample crew:")
                for credit in video["credits"]["crew"][:5]:
                    print(f"    - {credit['position_name']}: {credit['entity_name']}")

        return video

    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code} - {e.response.text}")
        return None


async def main():
    """Main example workflow."""
    print("\n" + "="*60)
    print("IMVDb API Client Example")
    print("="*60)

    # Configure fuzzbin
    config_path = Path(__file__).parent.parent / "config.yaml"
    fuzzbin.configure(config_path=config_path)

    # Get configuration
    config = fuzzbin.get_config()
    imvdb_config = config.apis.get("imvdb")

    if not imvdb_config:
        print("\nError: IMVDb configuration not found in config.yaml")
        print("Please add the 'imvdb' section to your config.yaml file.")
        return

    # Create IMVDb client
    async with IMVDbClient.from_config(imvdb_config) as client:
        print("\nIMVDb client initialized successfully!")
        print(f"Base URL: {client.base_url}")
        print(f"Rate Limit: {imvdb_config.rate_limit.requests_per_minute} req/min")
        print(f"Max Concurrency: {imvdb_config.concurrency.max_concurrent_requests}")

        # Example 1: Search for an artist entity
        artist_name = "Robin Thicke"
        entity = await search_artist_entity(client, artist_name)
        
        if entity:
            # Example 2: Get detailed entity information
            await get_entity_details(client, entity["id"])

        # Example 3: Search for a specific video
        artist = "Robin Thicke"
        track = "Blurred Lines"
        video_results = await search_videos(client, artist, track)

        if video_results and video_results["results"]:
            # Example 4: Get detailed video information
            first_video = video_results["results"][0]
            await get_video_details(client, first_video["id"])

        # Example 5: Demonstrate pagination
        print(f"\n{'='*60}")
        print("Pagination Example")
        print(f"{'='*60}")
        print("\nFetching page 2 with 10 results per page...")
        
        try:
            page2_results = await client.search_entities(artist_name, page=2, per_page=10)
            print(f"Page {page2_results['current_page']} of "
                  f"{page2_results['total_pages']}")
            print(f"Results on this page: {len(page2_results['results'])}")
        except httpx.HTTPStatusError as e:
            print(f"Error: HTTP {e.response.status_code} - {e.response.text}")

        print(f"\n{'='*60}")
        print("Example completed!")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
