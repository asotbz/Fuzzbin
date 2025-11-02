# API / CLI Calling Patterns & Ranking Inputs

## A) MusicBrainz (courtesy rate ≈ 1 req/sec; always set a real User-Agent)

**Primary search (recording by title + artist):**

```
GET https://musicbrainz.org/ws/2/recording
  ?query=recording:"{raw title}" AND artist:"{raw artist}"
  &limit=25
  &inc=artist-credits+releases+release-groups+tags
  &fmt=json
Headers:
  User-Agent: Fuzzbin/1.0 # configurable in UI
```

**Follow-ups for strong candidates (if needed to enrich/confirm):**

```
GET /ws/2/recording/{recording_mbid}?inc=artist-credits+releases+release-groups+tags&fmt=json
GET /ws/2/release-group/{rg_mbid}?inc=tags&fmt=json
GET /ws/2/artist/{artist_mbid}?inc=tags+genres&fmt=json
```

**Cache**

* Insert/UPSERT into `mb_*` tables.
* Earliest year: prefer `release-group.first-release-date` (fallback: min(release.date)).
* Populate `mb_recording_candidate` with:

  * `text_score`: compare (`query.norm_*`) vs normalized MB `recording.title` + primary artist credit.
  * `year_score`: distance to earliest year.
  * `duration_score`: distance to known `length_ms`.
  * `overall_score`: weighted sum; keep `rank` by DESC score.
* Mark `query_source_cache(source='musicbrainz')`.

## B) IMVDb (v1—API key required)

**Search (title+artist or either):**

```
GET https://imvdb.com/api/v1/search/videos
  ?q={artist and/or title}
  &per_page=25
Headers:
  Authorization: Bearer {IMVDB_API_KEY}
```

**Details for each candidate:**

```
GET https://imvdb.com/api/v1/video/{imvdb_video_id}
  (often includes artists, directors, release_date, and possibly sources)
```

**Cache & branch**

* Upsert `imvdb_video`, `imvdb_artist`, `imvdb_video_artist`, and `imvdb_video_source` if present.
* If any row in `imvdb_video_source` exists → `has_sources=1` and you can mark **MV exists** immediately and create an `mv_link (imvdb_to_yt or triad later)**.
* If **no sources** but strong IMVDb match: keep the candidate and proceed to YouTube pairing (next section).
* Populate `imvdb_video_candidate` with `text_score`, plus a `source_bonus` (e.g., +0.2 if IMVDb reports sources).
* Mark `query_source_cache(source='imvdb')`.

## C) YouTube (via yt-dlp, no API quota, robust search)

**Use YoutubeDLSharp to facilitate the below:**

**Search when IMVDb fails to produce a suitable candidate or lacks sources**
Use a few queries; store all `video_id` candidates and metadata:

```bash
# General relevance
yt-dlp -J "ytsearch15:${ARTIST} ${TITLE} official video" > out1.json

# Sometimes titles differ; try artist-only/title-only fallbacks:
yt-dlp -J "ytsearch15:${ARTIST} ${TITLE}"          > out2.json
yt-dlp -J "ytsearch15:${ARTIST}"                   > out3.json
yt-dlp -J "ytsearch15:${TITLE}"                    > out4.json
```

**For each result item (JSON):**

* Insert into `yt_video`:

  * `id` → `video_id`
  * `title`, `channel`, `channel_id`, `duration`, `width`/`height` (from formats), `view_count`, `upload_date`, `thumbnails[0].url`.
* Save thumbnail file (optional but recommended):

```bash
yt-dlp --write-thumbnail --skip-download -o "%(id)s.%(ext)s" "https://www.youtube.com/watch?v=${VIDEO_ID}"
# Move the resulting file into your thumbnails folder and record the path in yt_video.thumbnail_path
```

**Candidates & ranking**

* Insert into `yt_video_candidate` with:

  * `text_score`: normalized title/artist similarity.
  * `channel_bonus`: + if channel looks official (heuristics: matches artist name, VEVO, artist-VEVO, verified badge if you pre-computed).
  * `duration_score`: match to MB length_ms (if known).
  * Compute `overall_score`, assign `rank`.
* If chosen, create/link `mv_link (mb_to_yt or imvdb_to_yt or triad)` and set `query_resolution(chosen_source='youtube', mv_exists=1)`.

---

## Resolution Flow (end-to-end)

1. Insert/find `query` using the C# normalizer → `norm_title`, `norm_artist`, `norm_combo_key`.
2. If `query_source_cache` shows fresh IMVDb results and a selected IMVDb candidate with sources → **done** (populate `mv_link` + `query_resolution`).
3. Else call IMVDb. If strong candidate without sources → continue to YouTube pair.
4. If IMVDb has no suitable candidate → run yt-dlp searches, score `yt_video_candidate`, choose best.
5. Enrich with MusicBrainz regardless (for year/album/genre). Create `mv_link` rows to connect the worlds.
6. Record `query_resolution` with `mv_exists` and `chosen_source`.

**Confidence signals to combine in all “*_candidate.overall_score”**

* Exact token match on title and primary artist (big weight)
* Year proximity to MB earliest year (medium)
* Duration proximity to MB length (medium)
* Channel heuristic (YouTube) or source presence (IMVDb) (significant bonus)
* Penalty if “[Lyric Video]”, “[Live]”, “[Audio]”, “Cover”, “Remix” unless present in source query intent

