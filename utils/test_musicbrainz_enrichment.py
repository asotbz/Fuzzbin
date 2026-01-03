#!/usr/bin/env python3
"""Test script for MusicBrainz enrichment using Spotify playlist tracks.

This script:
1. Accepts a Spotify playlist URL as input
2. Uses Fuzzbin configuration to derive Spotify API credentials
3. Fetches all tracks from the playlist
4. For each track with an ISRC, enriches using MusicBrainz to find:
   - Earliest official studio album the track appears on
   - Release year for that album
   - Genre (top MusicBrainz tag by vote count)
   - Record label for the album

Example usage:
    python utils/test_musicbrainz_enrichment.py "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
    
    # Output as JSON
    python utils/test_musicbrainz_enrichment.py --json "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
    
    # Limit number of tracks
    python utils/test_musicbrainz_enrichment.py --limit 10 "https://open.spotify.com/playlist/..."
"""

import argparse
import asyncio
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class EnrichedTrack:
    """Result of enriching a Spotify track with MusicBrainz data."""
    
    # Spotify data
    spotify_track_name: str
    spotify_artist: str
    spotify_album: Optional[str]
    isrc: Optional[str]
    
    # MusicBrainz enrichment
    mb_album: Optional[str] = None
    mb_year: Optional[int] = None
    mb_genre: Optional[str] = None  # Raw MusicBrainz genre tag
    mb_classified_genre: Optional[str] = None  # Classified bucket (Metal, Rock, etc.)
    mb_label: Optional[str] = None
    mb_recording_mbid: Optional[str] = None
    mb_release_mbid: Optional[str] = None
    
    # Canonical (normalized) metadata from MusicBrainz
    canonical_title: Optional[str] = None
    canonical_artist: Optional[str] = None
    
    # IMVDb enrichment
    imvdb_video_id: Optional[int] = None
    imvdb_year: Optional[int] = None
    imvdb_director: Optional[str] = None
    imvdb_url: Optional[str] = None
    imvdb_found: bool = False
    
    # Match details
    match_method: str = "none"
    match_score: float = 0.0
    confident_match: bool = False


def extract_playlist_id(url_or_id: str) -> str:
    """Extract playlist ID from Spotify URL or return as-is if already an ID.
    
    Supported URL formats:
    - https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
    - https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=xxx
    - spotify:playlist:37i9dQZF1DXcBWIGoYBM5M
    - 37i9dQZF1DXcBWIGoYBM5M (plain ID)
    
    Args:
        url_or_id: Spotify playlist URL or ID
        
    Returns:
        Playlist ID
    """
    # Spotify URI format
    uri_match = re.match(r"spotify:playlist:([a-zA-Z0-9]+)", url_or_id)
    if uri_match:
        return uri_match.group(1)
    
    # Web URL format
    url_match = re.match(r"https?://open\.spotify\.com/playlist/([a-zA-Z0-9]+)", url_or_id)
    if url_match:
        return url_match.group(1)
    
    # Assume it's already an ID if it looks like one (22 chars, alphanumeric)
    if re.match(r"^[a-zA-Z0-9]{22}$", url_or_id):
        return url_or_id
    
    raise ValueError(f"Could not extract playlist ID from: {url_or_id}")


async def run_enrichment(
    playlist_url: str,
    limit: Optional[int] = None,
    output_json: bool = False,
) -> List[EnrichedTrack]:
    """Run MusicBrainz enrichment on Spotify playlist tracks.
    
    Args:
        playlist_url: Spotify playlist URL or ID
        limit: Maximum number of tracks to process (None for all)
        output_json: Whether output will be JSON (affects progress output)
        
    Returns:
        List of EnrichedTrack results
    """
    import fuzzbin
    from fuzzbin.api.spotify_client import SpotifyClient
    from fuzzbin.api.imvdb_client import IMVDbClient
    from fuzzbin.common.config import APIClientConfig
    from fuzzbin.services.musicbrainz_enrichment import MusicBrainzEnrichmentService
    
    # Extract playlist ID
    playlist_id = extract_playlist_id(playlist_url)
    
    # Initialize Fuzzbin configuration
    config = fuzzbin.get_config()
    config_dir = config.config_dir
    
    # Get Spotify config - fall back to empty config (env vars checked in from_config)
    spotify_config = (config.apis.get("spotify") if config.apis else None) or APIClientConfig(name="spotify")
    
    # Check if we have credentials (either in config or env vars)
    import os
    has_credentials = bool(
        os.environ.get("SPOTIFY_CLIENT_ID") 
        or os.environ.get("SPOTIFY_ACCESS_TOKEN")
        or (spotify_config.auth and (spotify_config.auth.get("client_id") or spotify_config.auth.get("access_token")))
    )
    if not has_credentials:
        print("Error: No Spotify credentials found.", file=sys.stderr)
        print("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables,", file=sys.stderr)
        print("or configure apis.spotify in config.yaml", file=sys.stderr)
        sys.exit(1)
    
    results: List[EnrichedTrack] = []
    
    # Create MusicBrainz enrichment service
    musicbrainz_config = config.apis.get("musicbrainz") if config.apis else None  # Optional, MusicBrainz has defaults
    enrichment_service = MusicBrainzEnrichmentService(
        config=musicbrainz_config,
        config_dir=config_dir,
    )
    
    # Create IMVDb client config
    imvdb_config = config.apis.get("imvdb") if config.apis else None
    if not imvdb_config:
        imvdb_config = APIClientConfig(name="imvdb")
    
    async with SpotifyClient.from_config(spotify_config, config_dir=config_dir) as spotify_client, \
               IMVDbClient.from_config(imvdb_config, config_dir=config_dir) as imvdb_client:
        # Get playlist metadata
        playlist = await spotify_client.get_playlist(playlist_id)
        if not output_json:
            print(f"\nPlaylist: {playlist.name}", file=sys.stderr)
            if playlist.description:
                print(f"Description: {playlist.description[:100]}...", file=sys.stderr)
        
        # Fetch all tracks
        if not output_json:
            print(f"\nFetching tracks from playlist...", file=sys.stderr)
        tracks = await spotify_client.get_all_playlist_tracks(playlist_id)
        
        total_tracks = len(tracks)
        if limit:
            tracks = tracks[:limit]
        
        if not output_json:
            print(f"Processing {len(tracks)} of {total_tracks} tracks\n", file=sys.stderr)
        
        # Process each track
        for i, track in enumerate(tracks, 1):
            # Get artist name
            artist_name = track.artists[0].name if track.artists else "Unknown"
            spotify_album = track.album.name if track.album else None
            
            # Get ISRC from track
            isrc = track.isrc
            
            if not output_json:
                print(
                    f"[{i}/{len(tracks)}] {track.name} - {artist_name} "
                    f"(ISRC: {isrc or 'N/A'})",
                    file=sys.stderr,
                )
            
            # Create base result
            enriched = EnrichedTrack(
                spotify_track_name=track.name,
                spotify_artist=artist_name,
                spotify_album=spotify_album,
                isrc=isrc,
            )
            
            # Enrich using MusicBrainz
            if isrc or (artist_name and track.name):
                mb_result = await enrichment_service.enrich(
                    isrc=isrc,
                    artist=artist_name,
                    title=track.name,
                )
                
                enriched.mb_album = mb_result.album
                enriched.mb_year = mb_result.year
                enriched.mb_genre = mb_result.genre
                enriched.mb_classified_genre = mb_result.classified_genre
                enriched.mb_label = mb_result.label
                enriched.mb_recording_mbid = mb_result.recording_mbid
                enriched.mb_release_mbid = mb_result.release_mbid
                enriched.canonical_title = mb_result.canonical_title
                enriched.canonical_artist = mb_result.canonical_artist
                enriched.match_method = mb_result.match_method
                enriched.match_score = mb_result.match_score
                enriched.confident_match = mb_result.confident_match
                
                if not output_json:
                    if mb_result.confident_match:
                        # Show title normalization if different
                        if mb_result.canonical_title and mb_result.canonical_title != track.name:
                            print(
                                f"    → Title: \"{track.name}\" → \"{mb_result.canonical_title}\"",
                                file=sys.stderr,
                            )
                        print(
                            f"    → Album: {mb_result.album} ({mb_result.year})",
                            file=sys.stderr,
                        )
                        print(
                            f"    → Genre: {mb_result.genre}, Label: {mb_result.label}",
                            file=sys.stderr,
                        )
                    else:
                        print(f"    → No confident match found", file=sys.stderr)
                
                # Enrich with IMVDb using canonical artist/title if available
                search_artist = mb_result.canonical_artist or artist_name
                search_title = mb_result.canonical_title or track.name
                
                if not output_json:
                    print(f"    → Searching IMVDb for: {search_artist} - {search_title}", file=sys.stderr)
                
                try:
                    imvdb_results = await imvdb_client.search_videos(
                        artist=search_artist,
                        track_title=search_title,
                        per_page=5,
                    )
                    
                    if imvdb_results.results:
                        # Take the first result
                        video = imvdb_results.results[0]
                        enriched.imvdb_video_id = video.id
                        enriched.imvdb_year = video.year
                        enriched.imvdb_url = video.url
                        enriched.imvdb_found = True
                        
                        # Get director from first artist's name if available
                        if video.artists and len(video.artists) > 0:
                            # Note: IMVDb artists in search results don't include directors
                            # Would need to call get_video() for full details
                            pass
                        
                        if not output_json:
                            print(
                                f"    → IMVDb: Found video (ID: {video.id}, Year: {video.year or 'N/A'})",
                                file=sys.stderr,
                            )
                    else:
                        if not output_json:
                            print(f"    → IMVDb: No videos found", file=sys.stderr)
                except Exception as e:
                    if not output_json:
                        print(f"    → IMVDb: Search failed: {e}", file=sys.stderr)
            else:
                if not output_json:
                    print(f"    → Skipped (no ISRC or artist/title)", file=sys.stderr)
            
            results.append(enriched)
    
    return results


def format_table(results: List[EnrichedTrack]) -> str:
    """Format results as a readable table.
    
    Args:
        results: List of enrichment results
        
    Returns:
        Formatted table string
    """
    lines = []
    lines.append("\n" + "=" * 180)
    lines.append("ENRICHMENT RESULTS")
    lines.append("=" * 180)
    
    # Summary stats
    total = len(results)
    matched = sum(1 for r in results if r.confident_match)
    isrc_matches = sum(1 for r in results if r.match_method == "isrc_search")
    search_matches = sum(1 for r in results if r.match_method == "search")
    imvdb_found = sum(1 for r in results if r.imvdb_found)
    
    lines.append(f"\nTotal tracks: {total}")
    lines.append(f"MusicBrainz matched: {matched} ({100*matched/total:.1f}%)" if total > 0 else "Matched: 0")
    lines.append(f"  - ISRC search: {isrc_matches}")
    lines.append(f"  - Search: {search_matches}")
    lines.append(f"IMVDb found: {imvdb_found} ({100*imvdb_found/total:.1f}%)" if total > 0 else "IMVDb: 0")
    lines.append("")
    
    # Table header
    lines.append("-" * 180)
    lines.append(
        f"{'Track':<30} {'Artist':<20} {'MB Album':<25} {'Year':<6} {'Label':<18} {'Genre':<15} {'Bucket':<12} {'IMVDb':<8}"
    )
    lines.append("-" * 180)
    
    for r in results:
        track = r.canonical_title or r.spotify_track_name
        track = track[:28] + ".." if len(track) > 30 else track
        artist = r.canonical_artist or r.spotify_artist
        artist = artist[:18] + ".." if len(artist) > 20 else artist
        album = (r.mb_album[:23] + "..") if r.mb_album and len(r.mb_album) > 25 else (r.mb_album or "-")
        year = str(r.mb_year) if r.mb_year else "-"
        label = (r.mb_label[:16] + "..") if r.mb_label and len(r.mb_label) > 18 else (r.mb_label or "-")
        genre = (r.mb_genre[:13] + "..") if r.mb_genre and len(r.mb_genre) > 15 else (r.mb_genre or "-")
        bucket = (r.mb_classified_genre[:10] + "..") if r.mb_classified_genre and len(r.mb_classified_genre) > 12 else (r.mb_classified_genre or "-")
        imvdb_status = "✓" if r.imvdb_found else "-"
        
        lines.append(f"{track:<30} {artist:<20} {album:<25} {year:<6} {label:<18} {genre:<15} {bucket:<12} {imvdb_status:<8}")
    
    lines.append("-" * 180)
    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test MusicBrainz enrichment using Spotify playlist tracks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "playlist_url",
        help="Spotify playlist URL or ID",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of tracks to process (default: all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output results as JSON",
    )
    
    args = parser.parse_args()
    
    try:
        results = asyncio.run(
            run_enrichment(
                playlist_url=args.playlist_url,
                limit=args.limit,
                output_json=args.output_json,
            )
        )
        
        if args.output_json:
            # Output as JSON
            output = [asdict(r) for r in results]
            print(json.dumps(output, indent=2))
        else:
            # Output as table
            print(format_table(results))
            
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
