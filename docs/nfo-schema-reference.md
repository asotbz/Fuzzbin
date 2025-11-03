# Fuzzbin NFO Schema Reference

## Quick Reference for Music Video NFO Files

Fuzzbin supports Kodi-compatible `<musicvideo>` NFO files with some custom extensions for enhanced functionality.

## Standard Kodi Elements (Supported)

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<musicvideo>
    <!-- Required Fields -->
    <title>Song Title</title>
    <artist>Primary Artist Name</artist>
    
    <!-- Highly Recommended -->
    <year>2023</year>
    <album>Album Name</album>
    <genre>Pop</genre>
    <genre>Electronic</genre>
    
    <!-- Optional Metadata -->
    <director>Director Name</director>
    <studio>Production Company</studio>
    <label>Record Label Name</label>
    <plot>Video description or synopsis</plot>
    <runtime>240</runtime> <!-- seconds -->
    
    <!-- Tags/Keywords -->
    <tag>keyword1</tag>
    <tag>keyword2</tag>
    
    <!-- External IDs -->
    <imvdbid>12345</imvdbid>
    <musicbrainzrecordingid>abc-123-def-456</musicbrainzrecordingid>
    
    <!-- Media Info -->
    <thumb>path/to/thumbnail.jpg</thumb>
    <fanart>path/to/fanart.jpg</fanart>
</musicvideo>
```

## Fuzzbin Extensions (Non-Kodi)

### 1. Source URLs (Video Sources)

Store one or more source URLs for the music video (YouTube, Vimeo, etc.):

```xml
<sources>
    <url>https://www.youtube.com/watch?v=dQw4w9WgXcQ</url>
    <url>https://vimeo.com/123456789</url>
</sources>
```

**Note:** These URLs point to where the video can be found online, NOT to metadata sources.

### ⚠️ Deprecated: Custom Fields (No Longer Supported)

**BREAKING CHANGE:** As of this version, URLs in custom fields are NO LONGER recognized:

```xml
<!-- ❌ NO LONGER WORKS -->
<customfield1>https://www.youtube.com/watch?v=dQw4w9WgXcQ</customfield1>
<customfield2>https://vimeo.com/123456789</customfield2>
<customfield3>https://example.com/video</customfield3>
```

**You must migrate to the `<sources>` format:**

```xml
<!-- ✅ CORRECT FORMAT -->
<sources>
    <url>https://www.youtube.com/watch?v=dQw4w9WgXcQ</url>
    <url>https://vimeo.com/123456789</url>
</sources>
```

## Featured Artist Handling

Fuzzbin automatically extracts featured artists from two sources:

### From Artist Field

```xml
<artist>Taylor Swift feat. Ed Sheeran</artist>
<!-- OR -->
<artist>Taylor Swift ft. Ed Sheeran</artist>
<!-- OR -->
<artist>Taylor Swift featuring Ed Sheeran</artist>
<!-- OR -->
<artist>Taylor Swift with Ed Sheeran</artist>
<!-- OR -->
<artist>Taylor Swift x Ed Sheeran</artist>
```

**Result:**
- Primary Artist: "Taylor Swift"
- Featured Artists: ["Ed Sheeran"]

### From Title Field

```xml
<title>End Game (feat. Ed Sheeran)</title>
<!-- OR -->
<title>End Game [feat. Ed Sheeran]</title>
<!-- OR -->
<title>End Game (ft. Ed Sheeran)</title>
```

**Result:**
- Clean Title: "End Game"
- Featured Artists: ["Ed Sheeran"]

### Multiple Featured Artists

```xml
<artist>Artist Name feat. Guest 1 & Guest 2</artist>
<!-- OR -->
<artist>Artist Name feat. Guest 1, Guest 2</artist>
<!-- OR -->
<artist>Artist Name feat. Guest 1 and Guest 2</artist>
```

**Result:**
- Primary Artist: "Artist Name"
- Featured Artists: ["Guest 1", "Guest 2"]

### Combined (Artist + Title)

```xml
<artist>Taylor Swift feat. Future</artist>
<title>End Game (feat. Ed Sheeran)</title>
```

**Result:**
- Primary Artist: "Taylor Swift"
- Featured Artists: ["Future", "Ed Sheeran"]
- Clean Title: "End Game"

## Multiple Artists (Alternative Format)

You can also use multiple `<artist>` elements:

```xml
<artist>Primary Artist</artist>
<artist>Featured Artist 1</artist>
<artist>Featured Artist 2</artist>
```

**Note:** First `<artist>` element is treated as primary artist.

## Complete Example

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<musicvideo>
    <!-- Core Metadata -->
    <title>End Game (feat. Ed Sheeran)</title>
    <artist>Taylor Swift feat. Future</artist>
    <album>Reputation</album>
    <year>2017</year>
    
    <!-- Genres (multiple allowed) -->
    <genre>Pop</genre>
    <genre>Electropop</genre>
    <genre>Hip Hop</genre>
    
    <!-- Tags/Keywords -->
    <tag>party</tag>
    <tag>upbeat</tag>
    <tag>collaboration</tag>
    
    <!-- Production Details -->
    <director>Joseph Kahn</director>
    <studio>Taylor Swift Productions</studio>
    <label>Big Machine Records</label>
    <plot>Official music video for "End Game" from the album Reputation. Features Future and Ed Sheeran in various international locations.</plot>
    
    <!-- Technical -->
    <runtime>240</runtime>
    
    <!-- External IDs -->
    <imvdbid>206879</imvdbid>
    <musicbrainzrecordingid>d8cc5926-27d8-4662-b269-bd68dcb16bf8</musicbrainzrecordingid>
    
    <!-- Source URLs (Fuzzbin Extension - REQUIRED format) -->
    <sources>
        <url>https://www.youtube.com/watch?v=dfnCAmr569k</url>
        <url>https://vimeo.com/987654321</url>
    </sources>
    
    <!-- Note: customfield1/2/3 are no longer parsed for URLs -->
    
    <!-- Artwork -->
    <thumb>poster.jpg</thumb>
    <fanart>fanart.jpg</fanart>
</musicvideo>
```

**Parsing Result:**
- Primary Artist: "Taylor Swift"
- Title: "End Game"
- Featured Artists: ["Future", "Ed Sheeran"]
- Year: 2017
- Album: "Reputation"
- Genres: ["Pop", "Electropop", "Hip Hop"]
- Tags: ["party", "upbeat", "collaboration"]
- Director: "Joseph Kahn"
- Record Label: "Big Machine Records"
- Source URLs: 2 URLs stored for verification
- Complete metadata: ✅ Yes

## Import Behavior

### NFO Priority Rules

1. **NFO ALWAYS takes precedence** over filename parsing
2. If NFO is incomplete, metadata cache is queried for missing fields
3. If no NFO exists, filename parsing is used + metadata cache query

### Required for "Complete" Status

For an NFO to be considered "complete" (green checkmark in import UI):

- ✅ `<title>` present
- ✅ `<artist>` present
- ✅ `<year>` present
- ✅ At least one `<genre>` present

Missing any of these triggers a metadata cache query to fill gaps.

## File Naming Conventions

NFO files should be named to match the video file:

```
# Same basename (recommended)
Artist - Title.mp4
Artist - Title.nfo

# Kodi pattern (supported)
Artist - Title.mp4
Artist - Title-nfo.nfo

# Directory-level (only if single video in directory)
Artist - Title.mp4
movie.nfo
```

## Stream Details (Optional)

While Fuzzbin extracts this from the video file directly, you can include it in NFO:

```xml
<streamdetails>
    <video>
        <codec>h264</codec>
        <width>1920</width>
        <height>1080</height>
        <aspect>1.78</aspect>
        <framerate>23.976024</framerate>
        <bitrate>5000</bitrate>
    </video>
    <audio>
        <codec>aac</codec>
        <channels>2</channels>
        <samplerate>48000</samplerate>
        <bitrate>256</bitrate>
    </audio>
</streamdetails>
```

## Best Practices

1. **Always include:** title, artist, year, and at least one genre
2. **Use multiple genres** to improve organization and searchability
3. **Add meaningful tags** for better discovery
4. **Include source URLs** in `<sources>` element for verification
5. **Use proper XML encoding** (UTF-8) for special characters
6. **Validate XML** before use to ensure proper parsing
7. **Store NFO next to video** with matching filename
8. **Include IMVDb/MusicBrainz IDs** when known for better metadata linking

## Validation

Your NFO file should:
- ✅ Be valid XML (well-formed)
- ✅ Have `<musicvideo>` as root element
- ✅ Include at minimum: `<title>` and `<artist>`
- ✅ Use UTF-8 encoding
- ✅ Match video filename (for auto-discovery)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| NFO not detected | Check filename matches video exactly |
| Parsing fails | Validate XML structure |
| Featured artists missing | Use supported feat. patterns |
| Status shows "needs review" | Add required fields: title, artist, year, genres |
| Source URLs not saved | Use `<sources><url>` format (customfields no longer supported) |

## Tools

**Recommended NFO Editors:**
- [TinyMediaManager](https://www.tinymediamanager.org/) - Cross-platform media manager
- [MediaElch](https://www.kvibes.de/mediaelch/) - Free NFO editor
- Any text editor (VS Code, Notepad++, etc.) with XML validation

**XML Validators:**
- [XMLValidator.com](https://www.xmlvalidation.com/)
- VS Code with XML extension
- xmllint command-line tool

---

📄 **Related Documentation:**
- `video-import-refactoring-plan.md` - Full technical implementation details
- `video-import-refactoring-summary.md` - Executive summary

💡 **Questions?** Check the main refactoring plan or open an issue on GitHub.
