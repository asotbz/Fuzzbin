"""Example: Using Spotify OAuth Client Credentials flow."""

import asyncio
import os

from fuzzbin.api.spotify_client import SpotifyClient
from fuzzbin.api.spotify_auth import SpotifyTokenManager
from fuzzbin.common.config import HTTPConfig


async def main():
    """Demonstrate Spotify OAuth Client Credentials flow."""

    print("Spotify OAuth Example")
    print("=" * 50)

    # Get credentials from environment variables
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("\nError: Missing credentials!")
        print("\nPlease set environment variables:")
        print("  export SPOTIFY_CLIENT_ID='your_client_id'")
        print("  export SPOTIFY_CLIENT_SECRET='your_client_secret'")
        print("\nGet credentials from: https://developer.spotify.com/dashboard")
        return

    # Create token manager
    print("\nCreating token manager...")
    token_manager = SpotifyTokenManager(
        client_id=client_id,
        client_secret=client_secret,
    )

    # Get access token (this will obtain a new token if needed)
    print("Obtaining access token...")
    token = await token_manager.get_access_token()
    print(f"✓ Token obtained: {token[:20]}... (length: {len(token)})")

    # Create Spotify client with token manager
    print("\nCreating Spotify client with OAuth...")
    async with SpotifyClient(
        http_config=HTTPConfig(),
        base_url="https://api.spotify.com/v1",
        token_manager=token_manager,
    ) as client:
        # Test API call
        playlist_id = "50p2OQFPVWTZ55sHrLNTwO"
        print(f"\nFetching playlist: {playlist_id}")

        playlist = await client.get_playlist(playlist_id)
        print(f"✓ Playlist: {playlist.name}")
        print(f"  Description: {playlist.description}")
        print(f"  Public: {playlist.public}")

        # Get some tracks
        print(f"\nFetching tracks...")
        tracks_response = await client.get_playlist_tracks(playlist_id, limit=5)
        print(f"✓ Total tracks in playlist: {tracks_response.total}")
        print(f"  Fetched: {len(tracks_response.items)}")

        # Display tracks
        print("\nSample tracks:")
        for idx, item in enumerate(tracks_response.items, start=1):
            track = item.track
            artist = track.artists[0].name if track.artists else "Unknown"
            print(f"  {idx}. {artist} - {track.name}")

    # Get token again (should use cached token)
    print("\nGetting token again (should use cache)...")
    token2 = await token_manager.get_access_token()
    print(f"✓ Token retrieved from cache: {token == token2}")

    print("\n" + "=" * 50)
    print("OAuth flow complete!")
    print(f"Token cached at: {token_manager.token_cache_path}")
    print("Token will be automatically refreshed when it expires.")


if __name__ == "__main__":
    # Setup:
    # 1. Go to: https://developer.spotify.com/dashboard
    # 2. Click "Create App"
    # 3. Fill in app name and description
    # 4. Copy Client ID and Client Secret
    # 5. Set environment variables:
    #    export SPOTIFY_CLIENT_ID="your_client_id"
    #    export SPOTIFY_CLIENT_SECRET="your_client_secret"
    # 6. Run this script

    asyncio.run(main())
