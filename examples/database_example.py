"""
Example demonstrating database functionality.

This example shows how to:
1. Initialize the database
2. Create videos and artists
3. Link videos to artists
4. Query videos using fluent API
5. Perform full-text search
6. Soft delete and restore
7. Export to NFO files
8. Backup and restore database
"""

import asyncio
from pathlib import Path

import fuzzbin


async def main():
    """Run database example."""
    print("=" * 70)
    print("Database Example")
    print("=" * 70)

    # Initialize fuzzbin with database
    print("\n1. Initializing fuzzbin with database...")
    await fuzzbin.configure()
    repo = await fuzzbin.get_repository()
    print(f"   Database initialized at: {repo.db_path}")

    # Create artists
    print("\n2. Creating artists...")
    nirvana_id = await repo.upsert_artist(
        name="Nirvana",
        imvdb_entity_id="12345",
        discogs_artist_id=67890,
    )
    print(f"   Created artist: Nirvana (ID: {nirvana_id})")

    dave_grohl_id = await repo.upsert_artist(
        name="Dave Grohl",
        imvdb_entity_id="54321",
    )
    print(f"   Created artist: Dave Grohl (ID: {dave_grohl_id})")

    # Create videos
    print("\n3. Creating videos...")
    video1_id = await repo.create_video(
        title="Smells Like Teen Spirit",
        artist="Nirvana",
        album="Nevermind",
        year=1991,
        director="Samuel Bayer",
        genre="Grunge",
        studio="DGC Records",
        imvdb_video_id="nv001",
        youtube_id="hTWKbfoikeg",
    )
    print(f"   Created video: Smells Like Teen Spirit (ID: {video1_id})")

    video2_id = await repo.create_video(
        title="Come As You Are",
        artist="Nirvana",
        album="Nevermind",
        year=1992,
        director="Kevin Kerslake",
        genre="Grunge",
        studio="DGC Records",
        imvdb_video_id="nv002",
        youtube_id="vabnZ9-ex7o",
    )
    print(f"   Created video: Come As You Are (ID: {video2_id})")

    video3_id = await repo.create_video(
        title="In Bloom",
        artist="Nirvana",
        album="Nevermind",
        year=1992,
        director="Kevin Kerslake",
        genre="Grunge",
        studio="DGC Records",
        imvdb_video_id="nv003",
        youtube_id="PbgKEjNBHqM",
    )
    print(f"   Created video: In Bloom (ID: {video3_id})")

    # Link videos to artists
    print("\n4. Linking videos to artists...")
    await repo.bulk_link_artists(
        video_id=video1_id,
        artist_links=[
            {"artist_id": nirvana_id, "role": "primary", "position": 0},
        ],
    )
    await repo.bulk_link_artists(
        video_id=video2_id,
        artist_links=[
            {"artist_id": nirvana_id, "role": "primary", "position": 0},
        ],
    )
    await repo.bulk_link_artists(
        video_id=video3_id,
        artist_links=[
            {"artist_id": nirvana_id, "role": "primary", "position": 0},
            {"artist_id": dave_grohl_id, "role": "featured", "position": 1},
        ],
    )
    print("   Artists linked to videos")

    # Query videos using fluent API
    print("\n5. Querying videos...")
    
    # Query by artist
    nirvana_videos = await repo.query().where_artist("Nirvana").execute()
    print(f"   Found {len(nirvana_videos)} videos by Nirvana")
    for video in nirvana_videos:
        print(f"     - {video['title']} ({video['year']})")

    # Query by year range
    print("\n   Filtering by year range (1991-1991)...")
    early_videos = await repo.query().where_year_range(1991, 1991).execute()
    print(f"   Found {len(early_videos)} videos from 1991:")
    for video in early_videos:
        print(f"     - {video['title']} ({video['year']})")

    # Query by director
    print("\n   Finding videos directed by Kevin Kerslake...")
    kerslake_videos = await repo.query().where_director("Kerslake").execute()
    print(f"   Found {len(kerslake_videos)} videos:")
    for video in kerslake_videos:
        print(f"     - {video['title']} (dir: {video['director']})")

    # Full-text search using FTS5
    print("\n6. Full-text search with FTS5...")
    search_results = await repo.search_videos("Grunge AND Nevermind")
    print(f"   Search for 'Grunge AND Nevermind': {len(search_results)} results")
    for video in search_results:
        print(f"     - {video['title']} ({video['genre']}, {video['album']})")

    # Complex query with chaining
    print("\n7. Complex query with method chaining...")
    results = await (
        repo.query()
        .where_artist("Nirvana")
        .where_year_range(1990, 1992)
        .order_by("year")
        .limit(2)
        .execute()
    )
    print(f"   First 2 Nirvana videos (1990-1992), ordered by year:")
    for video in results:
        print(f"     - {video['title']} ({video['year']})")

    # Get video by external ID
    print("\n8. Retrieving video by YouTube ID...")
    video = await repo.get_video_by_youtube_id("hTWKbfoikeg")
    print(f"   Found: {video['title']} by {video['artist']}")

    # Get video artists
    print("\n9. Getting artists for 'In Bloom'...")
    video_artists = await repo.get_video_artists(video3_id)
    print(f"   Artists for 'In Bloom':")
    for artist in video_artists:
        print(f"     - {artist['name']} ({artist['role']}, pos: {artist['position']})")

    # Soft delete demonstration
    print("\n10. Demonstrating soft delete...")
    await repo.delete_video(video3_id)
    print(f"   Soft deleted video ID {video3_id}")

    # Query without deleted
    active_videos = await repo.query().where_artist("Nirvana").execute()
    print(f"   Active Nirvana videos: {len(active_videos)}")

    # Query including deleted
    all_videos = await repo.query().where_artist("Nirvana").include_deleted().execute()
    print(f"   All Nirvana videos (including deleted): {len(all_videos)}")

    # Restore video
    print("\n   Restoring deleted video...")
    await repo.restore_video(video3_id)
    print(f"   Video ID {video3_id} restored")

    # Update video
    print("\n11. Updating video metadata...")
    await repo.update_video(
        video1_id,
        year=1991,
        studio="DGC Records / Geffen",
    )
    updated_video = await repo.get_video_by_id(video1_id)
    print(f"   Updated studio: {updated_video['studio']}")

    # Export to NFO
    print("\n12. Exporting video to NFO file...")
    exporter = fuzzbin.NFOExporter(repo)
    nfo_path = Path("/tmp/test_video.nfo")
    await exporter.export_video_to_nfo(video1_id, nfo_path)
    print(f"   Exported to: {nfo_path}")
    if nfo_path.exists():
        print(f"   NFO file size: {nfo_path.stat().st_size} bytes")

    # Backup database
    print("\n13. Creating database backup...")
    backup_path = Path("/tmp/fuzzbin_backup.db")
    await fuzzbin.DatabaseBackup.backup(repo.db_path, backup_path)
    print(f"   Backup created: {backup_path}")
    print(f"   Backup size: {backup_path.stat().st_size} bytes")

    # Verify backup
    print("\n14. Verifying backup integrity...")
    is_valid = await fuzzbin.DatabaseBackup.verify_backup(backup_path)
    print(f"   Backup valid: {is_valid}")

    # Transaction example
    print("\n15. Using explicit transaction...")
    async with repo.transaction():
        video4_id = await repo.create_video(
            title="Heart-Shaped Box",
            artist="Nirvana",
            album="In Utero",
            year=1993,
            director="Anton Corbijn",
            genre="Grunge",
        )
        await repo.link_video_artist(video4_id, nirvana_id, role="primary")
        print(f"   Created and linked video in transaction (ID: {video4_id})")

    # Count query
    print("\n16. Counting videos...")
    total_count = await repo.query().count()
    nirvana_count = await repo.query().where_artist("Nirvana").count()
    print(f"   Total videos: {total_count}")
    print(f"   Nirvana videos: {nirvana_count}")

    # Context manager usage
    print("\n17. Using repository as context manager...")
    async with await fuzzbin.get_repository() as repo:
        videos = await repo.query().limit(5).execute()
        print(f"   Retrieved {len(videos)} videos using context manager")

    # ==================== STATUS TRACKING EXAMPLES ====================
    print("\n" + "=" * 70)
    print("STATUS TRACKING")
    print("=" * 70)

    # Create video with initial status
    print("\n18. Creating video with status 'discovered'...")
    video5_id = await repo.create_video(
        title="Black Hole Sun",
        artist="Soundgarden",
        album="Superunknown",
        year=1994,
        status="discovered",
        download_source="youtube",
    )
    print(f"   Created video ID: {video5_id}")

    # Query videos by status
    print("\n19. Querying videos by status...")
    discovered = await repo.query().where_status("discovered").execute()
    print(f"   Found {len(discovered)} videos with status 'discovered'")

    # Update status through workflow
    print("\n20. Simulating download workflow...")
    print("   discovered → queued")
    await repo.update_status(
        video5_id,
        "queued",
        reason="Added to download queue",
        changed_by="download_manager",
    )

    print("   queued → downloading")
    await repo.update_status(
        video5_id,
        "downloading",
        reason="Download started",
        changed_by="download_worker",
    )

    # Simulate successful download
    print("   downloading → downloaded")
    await repo.mark_as_downloaded(
        video5_id,
        file_path=str(Path("/tmp/soundgarden_black_hole_sun.mp4")),
        file_size=45678901,
        file_checksum="def456789abc",
        download_source="youtube",
    )

    video5 = await repo.get_video_by_id(video5_id)
    print(f"   Final status: {video5['status']}")
    print(f"   File path: {video5['video_file_path']}")
    print(f"   File size: {video5['file_size']:,} bytes")

    # View status history
    print("\n21. Viewing status history...")
    history = await repo.get_status_history(video5_id)
    print(f"   Status transitions ({len(history)} changes):")
    for i, entry in enumerate(reversed(history), 1):
        old = entry["old_status"] or "None"
        new = entry["new_status"]
        reason = entry.get("reason", "")
        changed_by = entry.get("changed_by", "system")
        print(f"     {i}. {old} → {new}")
        print(f"        Reason: {reason}")
        print(f"        Changed by: {changed_by}")

    # Simulate failed download
    print("\n22. Simulating failed download...")
    video6_id = await repo.create_video(
        title="Man in the Box",
        artist="Alice in Chains",
        status="downloading",
    )
    await repo.mark_download_failed(
        video6_id,
        error_message="Network timeout after 3 retries",
    )
    video6 = await repo.get_video_by_id(video6_id)
    print(f"   Status: {video6['status']}")
    print(f"   Error: {video6['last_download_error']}")
    print(f"   Attempts: {video6['download_attempts']}")

    # Query by download source
    print("\n23. Querying by download source...")
    youtube_vids = await repo.query().where_download_source("youtube").execute()
    print(f"   Found {len(youtube_vids)} videos from YouTube")

    print("\n" + "=" * 70)
    print("Database example complete!")
    print("=" * 70)
    
    # Cleanup
    await repo.close()


if __name__ == "__main__":
    asyncio.run(main())
