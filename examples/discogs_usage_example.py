"""
Example usage of the Discogs API client.

This example demonstrates how to:
1. Search for releases by artist and track
2. Get master release details
3. Get specific release details
4. Get artist releases with pagination

Before running:
1. Set your Discogs API credentials in environment variables:
   export DISCOGS_API_KEY="your_key_here"
   export DISCOGS_API_SECRET="your_secret_here"
   OR
2. Update the config.yaml file with your credentials in:
   apis.discogs.custom.api_key and apis.discogs.custom.api_secret

Run with:
    python examples/discogs_usage_example.py
"""

import asyncio
from pathlib import Path

import httpx

import fuzzbin
from fuzzbin.api.discogs_client import DiscogsClient


async def search_releases(client: DiscogsClient, artist: str, track: str) -> dict:
    """
    Search for master releases by artist and track.

    Args:
        client: DiscogsClient instance
        artist: Artist name to search for
        track: Track title to search for

    Returns:
        Search results data
    """
    print(f"\n{'='*60}")
    print(f"Searching for: {artist} - {track}")
    print(f"{'='*60}")

    try:
        results = await client.search(artist, track)
        
        print(f"Found {results['pagination']['items']} results")
        print(f"Page {results['pagination']['page']} of {results['pagination']['pages']}")

        if not results["results"]:
            print("No results found!")
            return None

        # Display first few results
        print(f"\nTop {min(5, len(results['results']))} results:")
        for i, result in enumerate(results["results"][:5], 1):
            result_type = result.get('type', 'unknown')
            title = result.get('title', 'Unknown Title')
            year = result.get('year', 'Unknown')
            result_id = result.get('id', 'Unknown')
            
            print(f"  {i}. [{result_type.upper()}] {title} ({year})")
            print(f"     ID: {result_id}")
            
            if result_type == 'master':
                print(f"     Master ID: {result_id}")
                if 'master_url' in result:
                    print(f"     URL: {result['master_url']}")

        return results

    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code} - {e.response.text}")
        return None


async def get_master_details(client: DiscogsClient, master_id: int) -> dict:
    """
    Get detailed information about a master release.

    Args:
        client: DiscogsClient instance
        master_id: Discogs master release ID

    Returns:
        Master release details
    """
    print(f"\n{'='*60}")
    print(f"Getting master release details for ID: {master_id}")
    print(f"{'='*60}")

    try:
        master = await client.get_master(master_id)
        
        print(f"\nTitle: {master['title']}")
        print(f"Year: {master['year']}")
        
        # Artists
        if master.get('artists'):
            artists = ', '.join([a['name'] for a in master['artists']])
            print(f"Artists: {artists}")
        
        # Genres and styles
        if master.get('genres'):
            print(f"Genres: {', '.join(master['genres'])}")
        if master.get('styles'):
            print(f"Styles: {', '.join(master['styles'])}")
        
        # Main release info
        if 'main_release' in master:
            print(f"\nMain Release ID: {master['main_release']}")
            print(f"Main Release URL: {master.get('main_release_url', 'N/A')}")
        
        # Tracklist
        if master.get('tracklist'):
            print(f"\nTracklist ({len(master['tracklist'])} tracks):")
            for track in master['tracklist'][:5]:  # Show first 5 tracks
                position = track.get('position', '?')
                title = track.get('title', 'Unknown')
                duration = track.get('duration', 'N/A')
                print(f"  {position}. {title} ({duration})")
            if len(master['tracklist']) > 5:
                print(f"  ... and {len(master['tracklist']) - 5} more tracks")
        
        # Videos
        if master.get('videos'):
            print(f"\nVideos available: {len(master['videos'])}")
            for video in master['videos'][:3]:  # Show first 3 videos
                print(f"  - {video.get('title', 'Unknown')}")
                print(f"    {video.get('uri', 'N/A')}")
        
        return master

    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code} - {e.response.text}")
        return None


async def get_release_details(client: DiscogsClient, release_id: int) -> dict:
    """
    Get detailed information about a specific release.

    Args:
        client: DiscogsClient instance
        release_id: Discogs release ID

    Returns:
        Release details
    """
    print(f"\n{'='*60}")
    print(f"Getting release details for ID: {release_id}")
    print(f"{'='*60}")

    try:
        release = await client.get_release(release_id)
        
        print(f"\nTitle: {release['title']}")
        print(f"Year: {release['year']}")
        print(f"Country: {release.get('country', 'Unknown')}")
        
        # Artists
        if release.get('artists'):
            artists = ', '.join([a['name'] for a in release['artists']])
            print(f"Artists: {artists}")
        
        # Labels
        if release.get('labels'):
            labels = ', '.join([l['name'] for l in release['labels']])
            print(f"Labels: {labels}")
        
        # Formats
        if release.get('formats'):
            for fmt in release['formats']:
                name = fmt.get('name', 'Unknown')
                descriptions = fmt.get('descriptions', [])
                qty = fmt.get('qty', '1')
                print(f"Format: {qty}x {name}")
                if descriptions:
                    print(f"  Details: {', '.join(descriptions)}")
        
        # Master release link
        if 'master_id' in release:
            print(f"\nMaster Release ID: {release['master_id']}")
            print(f"Master URL: {release.get('master_url', 'N/A')}")
        
        # Identifiers (barcodes, matrix numbers, etc.)
        if release.get('identifiers'):
            print(f"\nIdentifiers:")
            for identifier in release['identifiers'][:5]:
                id_type = identifier.get('type', 'Unknown')
                value = identifier.get('value', 'N/A')
                description = identifier.get('description', '')
                print(f"  {id_type}: {value}")
                if description:
                    print(f"    ({description})")
        
        return release

    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code} - {e.response.text}")
        return None


async def get_artist_releases(client: DiscogsClient, artist_id: int, max_pages: int = 2) -> list:
    """
    Get releases by an artist, demonstrating pagination.

    Args:
        client: DiscogsClient instance
        artist_id: Discogs artist ID
        max_pages: Maximum number of pages to fetch

    Returns:
        List of all releases fetched
    """
    print(f"\n{'='*60}")
    print(f"Getting releases for artist ID: {artist_id}")
    print(f"{'='*60}")

    all_releases = []
    page = 1

    try:
        while page <= max_pages:
            print(f"\nFetching page {page}...")
            result = await client.get_artist_releases(artist_id, page=page, per_page=50)
            
            pagination = result['pagination']
            releases = result['releases']
            
            print(f"Page {pagination['page']} of {pagination['pages']}")
            print(f"Total releases: {pagination['items']}")
            print(f"Releases on this page: {len(releases)}")
            
            all_releases.extend(releases)
            
            # Display some releases from this page
            print(f"\nSample releases from page {page}:")
            for release in releases[:5]:
                title = release.get('title', 'Unknown')
                year = release.get('year', 'N/A')
                rel_type = release.get('type', 'unknown')
                role = release.get('role', 'N/A')
                print(f"  - {title} ({year}) [{rel_type}] - Role: {role}")
            
            # Check if there are more pages
            if page >= pagination['pages']:
                print(f"\nReached last page ({pagination['pages']})")
                break
            
            page += 1

        print(f"\n{'='*60}")
        print(f"Total releases fetched: {len(all_releases)}")
        print(f"{'='*60}")
        
        return all_releases

    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP {e.response.status_code} - {e.response.text}")
        return all_releases


async def main():
    """Main example function demonstrating Discogs API client usage."""
    print("\n" + "="*60)
    print("Discogs API Client Example")
    print("="*60)

    # Load configuration
    config_path = Path(__file__).parent.parent / "config.yaml"
    
    try:
        config = fuzzbin.Config.from_yaml(str(config_path))
        api_config = config.apis.get("discogs")
        
        if not api_config:
            print("\nError: 'discogs' configuration not found in config.yaml")
            print("Please add Discogs API configuration to config.yaml")
            return
        
        # Create client from configuration
        async with DiscogsClient.from_config(api_config) as client:
            print(f"Connected to: {client.base_url}")
            print(f"Rate limit: {api_config.rate_limit.requests_per_minute} req/min")
            
            # Example 1: Search for releases
            search_results = await search_releases(client, "nirvana", "smells like teen spirit")
            
            if search_results and search_results['results']:
                # Find the first master release
                master_result = next(
                    (r for r in search_results['results'] if r.get('type') == 'master'),
                    None
                )
                
                if master_result:
                    master_id = master_result['id']
                    
                    # Example 2: Get master details
                    master = await get_master_details(client, master_id)
                    
                    if master and 'main_release' in master:
                        # Example 3: Get specific release details
                        release_id = master['main_release']
                        await get_release_details(client, release_id)
                    
                    # Example 4: Get artist releases with pagination
                    if master and master.get('artists'):
                        artist_id = master['artists'][0]['id']
                        await get_artist_releases(client, artist_id, max_pages=2)
            
            print("\n" + "="*60)
            print("Example completed successfully!")
            print("="*60)

    except FileNotFoundError:
        print(f"\nError: Configuration file not found at {config_path}")
        print("Please ensure config.yaml exists in the project root")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
