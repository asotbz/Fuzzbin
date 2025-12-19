"""Example: Import tracks from a Spotify playlist into the database."""

import asyncio
from pathlib import Path

import fuzzbin


async def main():
    """Import a Spotify playlist into the database."""

    # Initialize fuzzbin with configuration
    await fuzzbin.configure(config_path=Path("config.yaml"))
    config = fuzzbin.get_config()

    print("Spotify Playlist Importer")
    print("=" * 50)

    # Create Spotify client from config
    spotify_client = fuzzbin.SpotifyClient.from_config(config.apis["spotify"])

    # Get video repository
    repository = await fuzzbin.get_repository()

    # Create importer
    importer = fuzzbin.SpotifyPlaylistImporter(
        spotify_client=spotify_client,
        video_repository=repository,
        initial_status="discovered",  # Mark tracks as "discovered" status
        skip_existing=True,  # Skip tracks that already exist in database
    )

    # Spotify playlist ID to import
    # You can get this from the Spotify URL:
    # https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
    #                                 ^^^^^^^^^^^^^^^^^^^^^^^^
    playlist_id = "3cEYpjA9oz9GiPac4AsH4n"

    # You can also use your own playlist ID
    # Uncomment the line below and replace with your playlist ID:
    # playlist_id = "YOUR_PLAYLIST_ID_HERE"

    print(f"\nImporting playlist: {playlist_id}")
    print("This may take a moment...\n")

    try:
        # Import the playlist
        result = await importer.import_playlist(playlist_id)

        # Print results
        print("\n" + "=" * 50)
        print("Import Results")
        print("=" * 50)
        print(f"Playlist: {result.playlist_name}")
        print(f"Total tracks: {result.total_tracks}")
        print(f"Imported: {result.imported_count}")
        print(f"Skipped: {result.skipped_count} (already in database)")
        print(f"Failed: {result.failed_count}")
        print(f"Duration: {result.duration_seconds:.2f} seconds")

        # Show failed tracks if any
        if result.failed_tracks:
            print("\n" + "=" * 50)
            print("Failed Tracks")
            print("=" * 50)
            for failed in result.failed_tracks:
                print(f"- {failed['name']}")
                print(f"  Error: {failed['error']}")

        # Query some of the imported tracks
        if result.imported_count > 0:
            print("\n" + "=" * 50)
            print("Sample of Imported Tracks")
            print("=" * 50)

            # Query tracks with status "discovered"
            query = repository.query().where_status("discovered").limit(5)
            tracks = await query.execute()

            for track in tracks:
                artist = track.get('artist', 'Unknown')
                title = track.get('title', 'Unknown')
                year = track.get('year', 'N/A')
                album = track.get('album', 'N/A')
                print(f"- {artist} - {title}")
                print(f"  Album: {album}, Year: {year}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        await spotify_client.aclose()
        await repository.close()
        print("\nDone!")


if __name__ == "__main__":
    # Setup Instructions:
    #
    # Method 1: OAuth Client Credentials (RECOMMENDED - tokens auto-refresh)
    # -----------------------------------------------------------------------
    # 1. Go to: https://developer.spotify.com/dashboard
    # 2. Click "Create App" and fill in the details
    # 3. Copy your Client ID and Client Secret
    # 4. Either:
    #    a) Set environment variables:
    #       export SPOTIFY_CLIENT_ID="your_client_id"
    #       export SPOTIFY_CLIENT_SECRET="your_client_secret"
    #    b) Or update config.yaml with your credentials
    #
    # Method 2: Manual Access Token (for testing only - expires in 1 hour)
    # ---------------------------------------------------------------------
    # 1. Go to: https://developer.spotify.com/console/get-playlist-tracks/
    # 2. Click "Get Token" and copy the access token
    # 3. Set environment variable:
    #    export SPOTIFY_ACCESS_TOKEN="your_token_here"

    asyncio.run(main())
