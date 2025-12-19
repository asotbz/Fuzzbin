"""Example: Import music video metadata from NFO files."""

import asyncio
from pathlib import Path

import fuzzbin


async def main():
    """Import NFO files from a directory into the database."""

    # Initialize fuzzbin with configuration
    await fuzzbin.configure(config_path=Path("config.yaml"))
    config = fuzzbin.get_config()

    print("NFO File Importer")
    print("=" * 50)

    # Get video repository
    repository = await fuzzbin.get_repository()

    # Create importer
    importer = fuzzbin.NFOImporter(
        video_repository=repository,
        initial_status="discovered",  # Mark videos as "discovered" status
        skip_existing=True,  # Skip videos that already exist in database
    )

    # Directory containing NFO files
    # This can be any directory with music video NFO files
    nfo_directory = Path("/path/to/music_videos")

    # You can also use a relative path:
    # nfo_directory = Path("./music_videos")

    print(f"\nImporting NFO files from: {nfo_directory}")
    print("This may take a moment...\n")

    try:
        # Import NFOs from directory
        result = await importer.import_from_directory(
            root_path=nfo_directory,
            recursive=True,  # Scan subdirectories
            update_file_paths=True,  # Store NFO file paths in database
        )

        # Print results
        print("\n" + "=" * 50)
        print("Import Results")
        print("=" * 50)
        print(f"Total NFO files: {result.total_tracks}")
        print(f"Imported: {result.imported_count}")
        print(f"Skipped: {result.skipped_count} (already in database)")
        print(f"Failed: {result.failed_count}")
        print(f"Duration: {result.duration_seconds:.2f} seconds")

        # Show failed imports if any
        if result.failed_tracks:
            print("\n" + "=" * 50)
            print("Failed Imports")
            print("=" * 50)
            for failed in result.failed_tracks:
                print(f"- {failed['name']}")
                print(f"  File: {failed['track_id']}")
                print(f"  Error: {failed['error']}")

        # Query some of the imported videos
        if result.imported_count > 0:
            print("\n" + "=" * 50)
            print("Sample of Imported Videos")
            print("=" * 50)

            # Query videos with status "discovered"
            query = repository.query().where_status("discovered").limit(5)
            videos = await query.execute()

            for video in videos:
                artist = video.get("artist", "Unknown")
                title = video.get("title", "Unknown")
                year = video.get("year", "N/A")
                director = video.get("director", "N/A")
                print(f"- {artist} - {title}")
                print(f"  Year: {year}, Director: {director}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Cleanup
        await repository.close()
        print("\nDone!")


if __name__ == "__main__":
    # Usage Instructions:
    #
    # 1. Create or organize music video NFO files in a directory
    # 2. Each NFO file should have the XML structure:
    #    <?xml version="1.0" encoding="UTF-8"?>
    #    <musicvideo>
    #        <title>Video Title</title>
    #        <artist>Artist Name</artist>
    #        <album>Album Name</album>
    #        <year>2020</year>
    #        <director>Director Name</director>
    #        <genre>Rock</genre>
    #        <studio>Label</studio>
    #    </musicvideo>
    #
    # 3. Update the nfo_directory path above to point to your directory
    # 4. Run this script: python examples/nfo_importer_example.py

    asyncio.run(main())
