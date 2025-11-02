# 1) Recording Search (title + artist)

**Request**

```
GET https://musicbrainz.org/ws/2/recording
  ?query=recording:"Still Fly" AND artist:"Big Tymers"
  &limit=5
  &inc=artist-credits+releases+release-groups+tags+genres
  &fmt=json
Headers:
  User-Agent: YourApp/1.0 (you@example.com)
```

(WS/2 base, search syntax, and `inc` usage per docs.) ([musicbrainz.org][1])

**Representative JSON**

```json
{
  "created": "2025-11-01T00:00:00Z",
  "count": 3,
  "offset": 0,
  "recordings": [
    {
      "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0001",
      "title": "Still Fly",
      "length": 224000,
      "artist-credit": [
        {
          "name": "Big Tymers",
          "artist": {
            "id": "11111111-2222-3333-4444-555555555555",
            "name": "Big Tymers",
            "sort-name": "Big Tymers"
          }
        }
      ],
      "releases": [
        {
          "id": "99999999-aaaa-bbbb-cccc-dddddddddd01",
          "title": "Hood Rich",
          "date": "2002-04-30",
          "country": "US",
          "release-group": {
            "id": "rg-00000000-1111-2222-3333-444444444444",
            "title": "Hood Rich",
            "first-release-date": "2002-04-30",
            "primary-type": "Album"
          }
        }
      ],
      "tags": [
        {"count": 2, "name": "hip hop"}
      ],
      "genres": [
        {"count": 2, "name": "hip hop"}
      ],
      "score": 100
    },
    {
      "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0002",
      "title": "Still Fly (Radio Edit)",
      "length": 210000,
      "artist-credit": [
        {
          "name": "Big Tymers",
          "artist": { "id": "11111111-2222-3333-4444-555555555555", "name": "Big Tymers", "sort-name": "Big Tymers" }
        }
      ],
      "releases": [],
      "tags": [],
      "genres": [],
      "score": 92
    }
  ]
}
```

**Parsing notes**

* Prefer `release-group.first-release-date` for “earliest year”; fall back to min of `releases[*].date` if needed. ([musicbrainz.org][2])
* `artist-credit` gives you credited names/join phrases; use for primary vs featured heuristics. ([musicbrainz.org][3])
* `tags` vs `genres`: genres are implemented via tags behind the scenes; both may appear. ([musicbrainz.org][4])

---

# 2) Recording Lookup (enrich a chosen candidate)

**Request**

```
GET https://musicbrainz.org/ws/2/recording/{recording_mbid}
  ?inc=artist-credits+releases+release-groups+genres+tags
  &fmt=json
```

(`inc` options for lookups are documented under WS/2 “Lookups”.) ([musicbrainz.org][1])

**Representative JSON**

```json
{
  "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0001",
  "title": "Still Fly",
  "length": 224000,
  "artist-credit": [
    { "name": "Big Tymers",
      "artist": { "id": "11111111-2222-3333-4444-555555555555", "name": "Big Tymers", "sort-name": "Big Tymers" }
    }
  ],
  "releases": [
    { "id": "99999999-aaaa-bbbb-cccc-dddddddddd01", "title": "Hood Rich", "date": "2002-04-30",
      "release-group": {
        "id": "rg-00000000-1111-2222-3333-444444444444",
        "title": "Hood Rich",
        "first-release-date": "2002-04-30",
        "primary-type": "Album"
      }
    }
  ],
  "genres": [{ "name": "hip hop", "count": 2 }],
  "tags":   [{ "name": "hip hop", "count": 2 }]
}
```

---

# 3) Release Group Lookup (sometimes useful for year/genre)

**Request**

```
GET https://musicbrainz.org/ws/2/release-group/{rg_mbid}
  ?inc=genres+tags
  &fmt=json
```

(Release-group concept + fields.) ([musicbrainz.org][2])

**Representative JSON**

```json
{
  "id": "rg-00000000-1111-2222-3333-444444444444",
  "title": "Hood Rich",
  "first-release-date": "2002-04-30",
  "primary-type": "Album",
  "genres": [{ "name": "hip hop", "count": 2 }],
  "tags":   [{ "name": "hip hop", "count": 2 }]
}
```

---

# 4) Artist Lookup (for supplemental tags/genres)

**Request**

```
GET https://musicbrainz.org/ws/2/artist/{artist_mbid}
  ?inc=aliases+genres+tags
  &fmt=json
```

(Official example shows `inc=aliases+genres+tags+ratings`.) ([musicbrainz.org][4])

**Representative JSON**

```json
{
  "id": "11111111-2222-3333-4444-555555555555",
  "name": "Big Tymers",
  "sort-name": "Big Tymers",
  "country": "US",
  "aliases": [
    { "name": "Big Tymers", "sort-name": "Big Tymers", "type": null }
  ],
  "genres": [{ "name": "hip hop", "count": 2 }],
  "tags":   [{ "name": "hip hop", "count": 2 }]
}
```

---

# 5) Helpful patterns & gotchas

* **Rate-limiting & headers**: Be polite—~1 req/sec and set a real `User-Agent`. (WS overview.) ([musicbrainz.org][5])
* **Search syntax**: `query=recording:"…" AND artist:"…"`; use `limit`, `offset`. (Search docs.) ([musicbrainz.org][6])
* **Inc parameters**: `artist-credits`, `releases`, `release-groups`, `genres`, `tags`, `recordings` (for release lookups). ([musicbrainz.org][1])
* **Earliest year**: prefer `release-group.first-release-date`. (Concept doc.) ([musicbrainz.org][2])
* **Genres vs tags**: genres are implemented via tags under the hood; treat both. ([blog.metabrainz.org][7])

---

## How this maps to your DDL & scorer

* Insert/UPSERT `mb_recording`, `mb_artist`, `mb_release`, `mb_release_group`, and `mb_tag` (for both `genres` and `tags`).
* For each search hit, compute `textScore` (normalized title/artist), `yearScore` (vs `first-release-date`), and `durationScore` (vs `length`), then persist into `mb_recording_candidate` with `overall_score` and `rank`.
* Keep `query_source_cache` updated for `musicbrainz` after each run so you skip unnecessary calls next time.

[1]: https://musicbrainz.org/doc/Web_Service?utm_source=chatgpt.com "Web Service"
[2]: https://musicbrainz.org/doc/Release_Group?utm_source=chatgpt.com "Release Group"
[3]: https://musicbrainz.org/doc/Artist_Credits?utm_source=chatgpt.com "Artist Credits"
[4]: https://musicbrainz.org/doc/MusicBrainz_API/Examples?utm_source=chatgpt.com "MusicBrainz API / Examples"
[5]: https://musicbrainz.org/doc/MusicBrainz_API?utm_source=chatgpt.com "MusicBrainz API"
[6]: https://musicbrainz.org/doc/MusicBrainz_API/Search?utm_source=chatgpt.com "MusicBrainz API / Search"
[7]: https://blog.metabrainz.org/2018/11/02/musicbrainz-introducing-genres/?utm_source=chatgpt.com "MusicBrainz introducing: Genres! - MetaBrainz Blog"
