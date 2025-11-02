# IMVDb response examples

## 1) Search Videos (title/artist query)

```json
{
  "page": 1,
  "per_page": 25,
  "total_results": 3,
  "results": [
    {
      "id": 186352742692,
      "url": "https://imvdb.com/video/robert-palmer/addicted-to-love",
      "song_title": "Addicted to Love",
      "video_title": "Addicted to Love",
      "release_date": "1986-01-01",
      "has_sources": true,
      "artists": [
        { "id": 12345, "name": "Robert Palmer", "role": "primary", "order": 0 }
      ],
      "thumbnail": {
        "url": "https://imvdb.img/186352742692/cover.jpg",
        "width": 640,
        "height": 360
      }
    },
    {
      "id": 186352700001,
      "url": "https://imvdb.com/video/robert-palmer/addicted-to-love-live",
      "song_title": "Addicted to Love (Live)",
      "video_title": "Addicted to Love (Live 1986)",
      "release_date": null,
      "has_sources": false,
      "artists": [
        { "id": 12345, "name": "Robert Palmer", "role": "primary", "order": 0 }
      ],
      "thumbnail": null
    },
    {
      "id": 186352799999,
      "url": "https://imvdb.com/video/various-artists/addicted-to-love-cover",
      "song_title": "Addicted to Love (Cover)",
      "video_title": "Addicted to Love (Cover)",
      "release_date": "2012-05-10",
      "has_sources": true,
      "artists": [
        { "id": 98765, "name": "Some Band", "role": "primary", "order": 0 }
      ],
      "thumbnail": {
        "url": "https://imvdb.img/186352799999/cover.jpg",
        "width": 640,
        "height": 360
      }
    }
  ]
}
```

**Parsing tips**

* `results[*].id` (numeric) is the canonical video id you’ll store.
* `song_title` vs `video_title` can differ; treat `song_title` as the track and `video_title` as the published MV title.
* `has_sources` is a quick boolean for whether IMVDb already lists YouTube/Vimeo links.
* `release_date` may be `null` or partial; don’t assume `YYYY-MM-DD` always present.
* `thumbnail` may be `null`.

Search endpoint & pagination behavior are documented in IMVDb’s “Searching” page. ([imvdb.com][1])

---

## 2) Video Detail (with includes: artists, directors, sources)

Typical follow-up:

```
GET https://imvdb.com/api/v1/video/{id}?include=artists,directors,sources
```

```json
{
  "id": 186352742692,
  "url": "https://imvdb.com/video/robert-palmer/addicted-to-love",
  "song_title": "Addicted to Love",
  "video_title": "Addicted to Love",
  "release_date": "1986-01-01",
  "runtime_seconds": 270,
  "thumbnail": {
    "url": "https://imvdb.img/186352742692/cover.jpg",
    "width": 640,
    "height": 360
  },

  "artists": [
    { "id": 12345, "name": "Robert Palmer", "role": "primary", "order": 0 },
    { "id": 23456, "name": "The Power Station", "role": "featured", "order": 1 }
  ],

  "directors": [
    { "id": 9001, "name": "Terence Donovan" }
  ],

  "sources": [
    {
      "source": "youtube",
      "external_id": "XcATvu5f9vE",
      "url": "https://www.youtube.com/watch?v=XcATvu5f9vE",
      "is_official": true
    },
    {
      "source": "vimeo",
      "external_id": "123456789",
      "url": "https://vimeo.com/123456789",
      "is_official": false
    }
  ]
}
```

**Parsing tips**

* The `include` list controls which nested arrays appear (`artists`, `directors`, `sources`, etc.). If you omit one, it may be missing entirely.
* `runtime_seconds` may be absent; don’t rely on it.
* In `artists`, `role` is typically `"primary"` or `"featured"` and may include an `order` for credit order.
* `sources[*].source` is `"youtube"` or `"vimeo"`; `external_id` is the video id you’ll store in your `imvdb_video_source`.
* `is_official` is your perfect hook for a scoring bonus.

Endpoint + includes are documented in IMVDb’s “Videos” page. ([imvdb.com][2])

---

## 3) Minimal Video Detail (no includes)

```json
{
  "id": 186352700001,
  "url": "https://imvdb.com/video/robert-palmer/addicted-to-love-live",
  "song_title": "Addicted to Love (Live)",
  "video_title": "Addicted to Love (Live 1986)",
  "release_date": null,
  "thumbnail": null
  // no artists/directors/sources arrays because they weren't requested
}
```

This is what you’ll see if you **don’t** pass `include=`—so make your parser resilient to absent arrays.

---

## 4) Artist entity (sometimes handy after detail fetch)

While most work centers on videos, you may fetch an artist to enrich local cache:

```
GET https://imvdb.com/api/v1/artist/{artistId}
```

```json
{
  "id": 12345,
  "name": "Robert Palmer",
  "url": "https://imvdb.com/n/robert-palmer"
}
```

Entity endpoints and id usage are noted in the developer reference. ([imvdb.com][3])

---

## Practical parser notes

* **Null-safety**: every string field can be `null` (or missing if not included). Use `TryGetProperty` and defaulting.
* **Numbers**: `id` fits in 64-bit; store as `INTEGER`.
* **Booleans**: `has_sources` and `is_official` map cleanly to `INTEGER NOT NULL DEFAULT 0`.
* **Dates**: don’t strictly parse to a `DateTime`; keep raw string + optional parsed year.
* **Includes**: your HTTP client should build `include=artists,directors,sources` as a comma list.
* **Pagination**: `page`, `per_page`, `total_results` let you page until `page * per_page >= total_results`.

[1]: https://imvdb.com/developers/api/searching?utm_source=chatgpt.com "Searching | Data API"
[2]: https://imvdb.com/developers/api/videos?utm_source=chatgpt.com "Videos | Data API"
[3]: https://imvdb.com/developers/api/entities?utm_source=chatgpt.com "Entities | Data API"
