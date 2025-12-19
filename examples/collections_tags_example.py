"""Example usage of collections and tags functionality."""

import asyncio
from pathlib import Path

from fuzzbin import configure, get_repository
from fuzzbin.common.config import Config


async def main():
    """Demonstrate collections and tags usage."""
    
    # Initialize Fuzzbin with configuration
    config = Config.from_yaml(Path("config.yaml"))
    await configure(config=config)
    
    # Get repository instance
    repo = await get_repository()
    
    # ============================================================
    # COLLECTIONS EXAMPLES
    # ============================================================
    
    # Create a collection
    collection_id = await repo.upsert_collection(
        name="90s Rock Classics",
        description="The best rock videos from the 1990s"
    )
    print(f"Created collection: {collection_id}")
    
    # Create some videos
    video_id1 = await repo.create_video(
        title="Smells Like Teen Spirit",
        artist="Nirvana",
        year=1991,
        genre="Grunge"
    )
    
    video_id2 = await repo.create_video(
        title="Black Hole Sun",
        artist="Soundgarden",
        year=1994,
        genre="Alternative Rock"
    )
    
    # Add videos to collection
    await repo.link_video_collection(video_id1, collection_id, position=0)
    await repo.link_video_collection(video_id2, collection_id, position=1)
    
    # Get all videos in the collection (ordered by position)
    collection_videos = await repo.get_collection_videos(collection_id)
    print(f"\nVideos in '90s Rock Classics' collection:")
    for video in collection_videos:
        print(f"  {video['position']}: {video['artist']} - {video['title']}")
    
    # List all collections
    all_collections = await repo.list_collections()
    print(f"\nAll collections: {[c['name'] for c in all_collections]}")
    
    # ============================================================
    # TAGS EXAMPLES
    # ============================================================
    
    # Add tags manually to a video
    await repo.bulk_add_video_tags(
        video_id1,
        ["rock", "grunge", "alternative"],
        source="manual"
    )
    
    # Auto-generate decade tag based on year
    if config.tags.auto_decade.enabled:
        await repo.auto_add_decade_tag(
            video_id1,
            year=1991,
            tag_format=config.tags.auto_decade.format
        )
    
    # Get all tags for a video
    video_tags = await repo.get_video_tags(video_id1)
    print(f"\nTags for 'Smells Like Teen Spirit':")
    for tag in video_tags:
        print(f"  - {tag['name']} (source: {tag['source']}, usage: {tag['usage_count']})")
    
    # Replace all tags for a video
    await repo.replace_video_tags(
        video_id2,
        ["rock", "alternative", "90s"],
        source="manual"
    )
    
    # List all tags sorted by usage
    popular_tags = await repo.list_tags(min_usage_count=1, order_by="usage_count")
    print(f"\nMost popular tags:")
    for tag in popular_tags[:5]:
        print(f"  {tag['name']}: {tag['usage_count']} videos")
    
    # ============================================================
    # QUERYING WITH FILTERS
    # ============================================================
    
    # Find all rock videos
    rock_videos = await repo.query().where_tag("rock").execute()
    print(f"\nFound {len(rock_videos)} rock videos")
    
    # Find videos with ANY of these tags
    genre_videos = await repo.query().where_any_tags(["grunge", "alternative"]).execute()
    print(f"Found {len(genre_videos)} videos tagged grunge OR alternative")
    
    # Find videos with ALL of these tags
    specific_videos = await repo.query().where_all_tags(["rock", "90s"]).execute()
    print(f"Found {len(specific_videos)} videos tagged rock AND 90s")
    
    # Find videos in a specific collection
    collection_query = await repo.query().where_collection("90s Rock").execute()
    print(f"Found {len(collection_query)} videos in '90s Rock' collection")
    
    # Combine filters: collection + tag + year range
    filtered_videos = await repo.query()\
        .where_collection("90s Rock")\
        .where_tag("grunge")\
        .where_year_range(1990, 1995)\
        .execute()
    print(f"Found {len(filtered_videos)} grunge videos from 1990-1995 in collection")
    
    # ============================================================
    # NFO FILE EXPORT (Tags are written to NFO files)
    # ============================================================
    
    from fuzzbin.core.db.exporter import NFOExporter
    
    exporter = NFOExporter(repo)
    nfo_path = Path("examples/exported_musicvideo.nfo")
    
    # Export video with tags to NFO file
    await exporter.export_video_to_nfo(video_id1, nfo_path)
    print(f"\nExported video to {nfo_path}")
    print("NFO file will include tags from database")
    
    # Read the NFO back
    from fuzzbin.parsers.musicvideo_parser import MusicVideoNFOParser
    parser = MusicVideoNFOParser()
    nfo = parser.parse_file(nfo_path)
    print(f"NFO tags: {nfo.tags}")
    
    # ============================================================
    # TAG MANAGEMENT
    # ============================================================
    
    # Remove a tag from a video
    rock_tag = await repo.get_tag_by_name("rock")
    if rock_tag:
        await repo.remove_video_tag(video_id2, rock_tag["id"])
        print(f"\nRemoved 'rock' tag from video {video_id2}")
    
    # Tags with zero usage are automatically deleted
    unused_tags = await repo.list_tags(min_usage_count=0)
    print(f"Active tags (including unused): {len(unused_tags)}")
    
    # Get all videos with a specific tag
    tag = await repo.get_tag_by_name("90s")
    if tag:
        tagged_videos = await repo.get_tag_videos(tag["id"])
        print(f"\nVideos tagged with '90s': {len(tagged_videos)}")
    
    # ============================================================
    # COLLECTION MANAGEMENT
    # ============================================================
    
    # Remove a video from collection
    await repo.unlink_video_collection(video_id1, collection_id)
    print(f"\nRemoved video {video_id1} from collection")
    
    # Get collections for a specific video
    video_collections = await repo.get_video_collections(video_id2)
    print(f"Video {video_id2} is in {len(video_collections)} collections")
    
    # Soft delete a collection (videos remain, links are removed via CASCADE)
    # await repo.delete_collection(collection_id)
    
    # Close repository connection
    await repo.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
