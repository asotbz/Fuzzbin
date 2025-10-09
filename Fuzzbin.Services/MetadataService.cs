using System.Diagnostics;
using System.Globalization;
using System.Linq;
using System.Net.Http;
using System.Text.Json;
using System.Xml;
using System.Xml.Linq;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Refit;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.External.Imvdb;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services;

public class MetadataService : IMetadataService
{
    private readonly ILogger<MetadataService> _logger;
    private readonly IUnitOfWork _unitOfWork;
    private readonly HttpClient _httpClient;
    private readonly IMemoryCache _cache;
    private readonly IImvdbApi _imvdbApi;
    private readonly IOptionsMonitor<ImvdbOptions> _imvdbOptions;
    private readonly IImvdbApiKeyProvider _apiKeyProvider;
    private readonly JsonSerializerOptions _jsonOptions;

    public MetadataService(
        ILogger<MetadataService> logger,
        IUnitOfWork unitOfWork,
        IHttpClientFactory httpClientFactory,
        IMemoryCache cache,
        IImvdbApi imvdbApi,
        IOptionsMonitor<ImvdbOptions> imvdbOptions,
        IImvdbApiKeyProvider apiKeyProvider)
    {
        _logger = logger;
        _unitOfWork = unitOfWork;
        _cache = cache;
        _imvdbApi = imvdbApi;
        _imvdbOptions = imvdbOptions;
        _apiKeyProvider = apiKeyProvider;
        _httpClient = httpClientFactory.CreateClient();
        _jsonOptions = new JsonSerializerOptions 
        { 
            PropertyNameCaseInsensitive = true,
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase
        };
    }

    public async Task<VideoMetadata> ExtractMetadataAsync(string filePath, CancellationToken cancellationToken = default)
    {
        var metadata = new VideoMetadata();
        
        try
        {
            // Use ffprobe to extract metadata
            var startInfo = new ProcessStartInfo
            {
                FileName = "ffprobe",
                Arguments = $"-v quiet -print_format json -show_format -show_streams \"{filePath}\"",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var process = new Process { StartInfo = startInfo };
            process.Start();
            
            var output = await process.StandardOutput.ReadToEndAsync(cancellationToken);
            await process.WaitForExitAsync(cancellationToken);
            
            if (process.ExitCode == 0 && !string.IsNullOrEmpty(output))
            {
                var json = JsonDocument.Parse(output);
                
                // Parse format information
                if (json.RootElement.TryGetProperty("format", out var format))
                {
                    if (format.TryGetProperty("duration", out var duration))
                    {
                        if (double.TryParse(duration.GetString(), out var seconds))
                        {
                            metadata.Duration = TimeSpan.FromSeconds(seconds);
                        }
                    }
                    
                    if (format.TryGetProperty("size", out var size))
                    {
                        if (long.TryParse(size.GetString(), out var fileSize))
                        {
                            metadata.FileSize = fileSize;
                        }
                    }
                    
                    if (format.TryGetProperty("format_name", out var formatName))
                    {
                        metadata.Container = formatName.GetString();
                    }
                    
                    // Parse tags
                    if (format.TryGetProperty("tags", out var tags))
                    {
                        foreach (var tag in tags.EnumerateObject())
                        {
                            metadata.Tags[tag.Name] = tag.Value.GetString() ?? "";
                            
                            // Map common tags
                            switch (tag.Name.ToLowerInvariant())
                            {
                                case "title":
                                    metadata.Title = tag.Value.GetString();
                                    break;
                                case "artist":
                                    metadata.Artist = tag.Value.GetString();
                                    break;
                                case "album":
                                    metadata.Album = tag.Value.GetString();
                                    break;
                                case "date":
                                case "year":
                                    if (DateTime.TryParse(tag.Value.GetString(), out var date))
                                    {
                                        metadata.ReleaseDate = date;
                                    }
                                    break;
                            }
                        }
                    }
                }
                
                // Parse stream information
                if (json.RootElement.TryGetProperty("streams", out var streams))
                {
                    foreach (var stream in streams.EnumerateArray())
                    {
                        var codecType = stream.GetProperty("codec_type").GetString();
                        
                        if (codecType == "video")
                        {
                            metadata.VideoCodec = stream.GetProperty("codec_name").GetString();
                            
                            if (stream.TryGetProperty("width", out var width))
                                metadata.Width = width.GetInt32();
                                
                            if (stream.TryGetProperty("height", out var height))
                                metadata.Height = height.GetInt32();
                                
                            if (stream.TryGetProperty("r_frame_rate", out var frameRate))
                            {
                                var frParts = frameRate.GetString()?.Split('/');
                                if (frParts?.Length == 2 && 
                                    double.TryParse(frParts[0], out var num) && 
                                    double.TryParse(frParts[1], out var den) && 
                                    den > 0)
                                {
                                    metadata.FrameRate = num / den;
                                }
                            }
                            
                            if (stream.TryGetProperty("bit_rate", out var vBitrate))
                            {
                                if (int.TryParse(vBitrate.GetString(), out var bitrate))
                                {
                                    metadata.VideoBitrate = bitrate;
                                }
                            }
                        }
                        else if (codecType == "audio")
                        {
                            metadata.AudioCodec = stream.GetProperty("codec_name").GetString();
                            
                            if (stream.TryGetProperty("bit_rate", out var aBitrate))
                            {
                                if (int.TryParse(aBitrate.GetString(), out var bitrate))
                                {
                                    metadata.AudioBitrate = bitrate;
                                }
                            }
                            
                            if (stream.TryGetProperty("sample_rate", out var sampleRate))
                            {
                                if (int.TryParse(sampleRate.GetString(), out var rate))
                                {
                                    metadata.AudioSampleRate = rate;
                                }
                            }
                        }
                    }
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error extracting metadata from {FilePath}", filePath);
        }
        
        // Set file size if not already set
        if (metadata.FileSize == 0 && File.Exists(filePath))
        {
            metadata.FileSize = new FileInfo(filePath).Length;
        }
        
        return metadata;
    }

    public async Task<ImvdbMetadata?> GetImvdbMetadataAsync(string artist, string title, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(artist) || string.IsNullOrWhiteSpace(title))
        {
            _logger.LogWarning("Cannot query IMVDb with missing artist or title (Artist: '{Artist}', Title: '{Title}')", artist, title);
            return null;
        }

        var trimmedArtist = artist.Trim();
        var trimmedTitle = title.Trim();
        var cacheKey = ImvdbMapper.BuildCacheKey(trimmedArtist, trimmedTitle);

        if (_cache.TryGetValue<ImvdbMetadata>(cacheKey, out var cachedMetadata))
        {
            return cachedMetadata;
        }

        var apiKey = await _apiKeyProvider.GetApiKeyAsync(cancellationToken).ConfigureAwait(false);
        if (string.IsNullOrWhiteSpace(apiKey))
        {
            _logger.LogWarning("IMVDb API key not configured; skipping lookup for {Artist} - {Title}", trimmedArtist, trimmedTitle);
            return null;
        }

        try
        {
            var query = $"{trimmedArtist} {trimmedTitle}";
            var searchResponse = await _imvdbApi.SearchVideosAsync(
                query,
                perPage: 10,
                cancellationToken: cancellationToken).ConfigureAwait(false);

            if (searchResponse?.Results == null || searchResponse.Results.Count == 0)
            {
                _logger.LogInformation("IMVDb returned no results for {Artist} - {Title}", trimmedArtist, trimmedTitle);
                return null;
            }

            var bestMatch = ImvdbMapper.FindBestMatch(searchResponse.Results, trimmedArtist, trimmedTitle);
            if (bestMatch == null)
            {
                _logger.LogInformation("IMVDb search results did not contain a suitable match for {Artist} - {Title}", trimmedArtist, trimmedTitle);
                return null;
            }

            var videoResponse = await _imvdbApi.GetVideoAsync(
                bestMatch.Id.ToString(CultureInfo.InvariantCulture),
                cancellationToken).ConfigureAwait(false);

            if (videoResponse == null)
            {
                _logger.LogInformation("IMVDb did not return video details for ID {Id}", bestMatch.Id);
                return null;
            }

            var metadata = ImvdbMapper.MapToMetadata(videoResponse, bestMatch);

            var options = _imvdbOptions.CurrentValue;
            var expiration = options.CacheDuration <= TimeSpan.Zero
                ? TimeSpan.FromHours(24)
                : options.CacheDuration;

            _cache.Set(cacheKey, metadata, new MemoryCacheEntryOptions
            {
                SlidingExpiration = expiration
            });

            return metadata;
        }
        catch (ApiException apiException)
        {
            _logger.LogWarning(apiException, "IMVDb API request failed with status {StatusCode} for {Artist} - {Title}",
                apiException.StatusCode,
                trimmedArtist,
                trimmedTitle);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching IMVDb metadata for {Artist} - {Title}", trimmedArtist, trimmedTitle);
        }

        return null;
    }

    public async Task<MusicBrainzMetadata?> GetMusicBrainzMetadataAsync(string artist, string title, CancellationToken cancellationToken = default)
    {
        try
        {
            // MusicBrainz API endpoint
            var query = Uri.EscapeDataString($"artist:\"{artist}\" AND recording:\"{title}\"");
            var url = $"https://musicbrainz.org/ws/2/recording?query={query}&fmt=json&limit=1";
            
            // Add User-Agent header (required by MusicBrainz)
            _httpClient.DefaultRequestHeaders.UserAgent.Clear();
            _httpClient.DefaultRequestHeaders.UserAgent.ParseAdd("Fuzzbin/1.0 (https://github.com/videoJockey)");
            
            var response = await _httpClient.GetAsync(url, cancellationToken);
            
            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync(cancellationToken);
                var data = JsonDocument.Parse(json);
                
                if (data.RootElement.TryGetProperty("recordings", out var recordings))
                {
                    var recordingsArray = recordings.EnumerateArray().ToList();
                    if (recordingsArray.Any())
                    {
                        var recording = recordingsArray.First();
                        var metadata = new MusicBrainzMetadata();
                        
                        if (recording.TryGetProperty("id", out var id))
                            metadata.RecordingId = id.GetString();
                            
                        if (recording.TryGetProperty("title", out var recTitle))
                            metadata.Title = recTitle.GetString();
                            
                        if (recording.TryGetProperty("length", out var length))
                            metadata.Duration = length.GetInt32();
                            
                        // Parse artist credits
                        if (recording.TryGetProperty("artist-credit", out var artistCredit))
                        {
                            var artists = artistCredit.EnumerateArray().ToList();
                            if (artists.Any())
                            {
                                var firstArtist = artists.First();
                                if (firstArtist.TryGetProperty("artist", out var artistInfo))
                                {
                                    if (artistInfo.TryGetProperty("id", out var artistId))
                                        metadata.ArtistId = artistId.GetString();
                                        
                                    if (artistInfo.TryGetProperty("name", out var artistName))
                                        metadata.Artist = artistName.GetString();
                                        
                                    if (artistInfo.TryGetProperty("sort-name", out var sortName))
                                        metadata.ArtistSort = sortName.GetString();
                                }
                            }
                        }
                        
                        // Parse releases
                        if (recording.TryGetProperty("releases", out var releases))
                        {
                            var releasesArray = releases.EnumerateArray().ToList();
                            if (releasesArray.Any())
                            {
                                var release = releasesArray.First();
                                
                                if (release.TryGetProperty("id", out var releaseId))
                                    metadata.ReleaseId = releaseId.GetString();
                                    
                                if (release.TryGetProperty("title", out var albumTitle))
                                    metadata.Album = albumTitle.GetString();
                                    
                                if (release.TryGetProperty("date", out var date))
                                {
                                    if (DateTime.TryParse(date.GetString(), out var releaseDate))
                                        metadata.ReleaseDate = releaseDate;
                                }
                            }
                        }
                        
                        return metadata;
                    }
                }
            }
            
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching MusicBrainz metadata for {Artist} - {Title}", artist, title);
            return null;
        }
    }

    public async Task<string> GenerateNfoAsync(Video video, string outputPath, CancellationToken cancellationToken = default)
    {
        try
        {
            var nfoPath = string.IsNullOrEmpty(outputPath) 
                ? Path.ChangeExtension(video.FilePath, ".nfo")
                : outputPath;

            // Helper method to add XML element if value is not null
            void Add(XElement parent, string name, object? value)
            {
                if (value != null && !string.IsNullOrEmpty(value.ToString()))
                    parent.Add(new XElement(name, value));
            }
                
            var doc = new XDocument();
            var root = new XElement("musicvideo");
            doc.Add(root);

            Add(root, "title", video.Title);
            Add(root, "artist", video.Artist);
            Add(root, "album", video.Album);
            Add(root, "year", video.Year);
            Add(root, "aired", video.Year != null ? $"{video.Year}-01-01" : null);
            Add(root, "plot", video.Description);
            Add(root, "director", video.Director);
            Add(root, "studio", video.ProductionCompany);
            Add(root, "label", video.Publisher);
            Add(root, "runtime", video.Duration);
            Add(root, "rating", video.Rating?.ToString() ?? "0");
            Add(root, "imvdbid", video.ImvdbId);
            Add(root, "musicbrainzrecordingid", video.MusicBrainzRecordingId);
            Add(root, "thumb", video.ThumbnailPath);
            
            // Add genres
            foreach (var genre in video.Genres ?? Enumerable.Empty<Genre>())
            {
                Add(root, "genre", genre.Name);
            }
            
            // Add tags
            foreach (var tag in video.Tags ?? Enumerable.Empty<Tag>())
            {
                Add(root, "tag", tag.Name);
            }
            
            // Add featured artists
            if (video.FeaturedArtists?.Any() == true)
            {
                foreach (var artist in video.FeaturedArtists)
                {
                    Add(root, "actor", artist.Name);
                }
            }
            
            // Add video stream info
            var streamDetails = new XElement("streamdetails");
            var hasStreamDetails = false;
            
            // Parse resolution from Resolution string
            var resolutionParts = video.Resolution?.Split('x');
            if (resolutionParts?.Length == 2 && 
                int.TryParse(resolutionParts[0], out var width) && 
                int.TryParse(resolutionParts[1], out var height))
            {
                var videoElement = new XElement("video");
                streamDetails.Add(videoElement);
                Add(videoElement, "codec", video.VideoCodec);
                Add(videoElement, "width", width);
                Add(videoElement, "height", height);
                Add(videoElement, "aspect", $"{width}:{height}");
                Add(videoElement, "framerate", video.FrameRate);
                Add(videoElement, "bitrate", video.Bitrate);
                hasStreamDetails = true;
            }
            
            // Add audio stream info
            if (!string.IsNullOrEmpty(video.AudioCodec))
            {
                var audioElement = new XElement("audio");
                streamDetails.Add(audioElement);
                Add(audioElement, "codec", video.AudioCodec);
                Add(audioElement, "channels", 2); // Default stereo
                Add(audioElement, "samplerate", 48000); // Default sample rate
                Add(audioElement, "bitrate", 128000); // Default audio bitrate
                hasStreamDetails = true;
            }
            
            if (hasStreamDetails)
            {
                root.Add(streamDetails);
            }
            
            // Save the NFO file
            await Task.Run(() => doc.Save(nfoPath!), cancellationToken);
            
            _logger.LogInformation("Generated NFO file for video {VideoId} at {Path}", video.Id, nfoPath);
            return nfoPath!;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error generating NFO for video {VideoId}", video.Id);
            throw;
        }
    }

    public async Task<NfoData?> ReadNfoAsync(string nfoPath, CancellationToken cancellationToken = default)
    {
        try
        {
            if (!File.Exists(nfoPath))
                return null;
                
            var doc = await Task.Run(() => XDocument.Load(nfoPath), cancellationToken);
            var root = doc.Root;
            
            if (root == null || root.Name.LocalName != "musicvideo")
                return null;
                
            var nfoData = new NfoData
            {
                Title = root.Element("title")?.Value,
                Artist = root.Element("artist")?.Value,
                Album = root.Element("album")?.Value,
                Plot = root.Element("plot")?.Value,
                Director = root.Element("director")?.Value,
                Studio = root.Element("studio")?.Value,
                RecordLabel = root.Element("label")?.Value,
                ImvdbId = root.Element("imvdbid")?.Value,
                MusicBrainzId = root.Element("musicbrainzrecordingid")?.Value,
                Thumb = root.Element("thumb")?.Value,
                FanArt = root.Element("fanart")?.Value
            };
            
            // Parse year
            if (int.TryParse(root.Element("year")?.Value, out var year))
                nfoData.Year = year;
                
            // Parse runtime
            if (int.TryParse(root.Element("runtime")?.Value, out var runtime))
                nfoData.Runtime = runtime;
                
            // Parse release date
            if (DateTime.TryParse(root.Element("aired")?.Value, out var releaseDate))
                nfoData.ReleaseDate = releaseDate;
                
            // Parse genres
            nfoData.Genres = root.Elements("genre").Select(e => e.Value).ToList();
            
            // Parse tags
            nfoData.Tags = root.Elements("tag").Select(e => e.Value).ToList();
            
            // Parse stream details
            var streamDetails = root.Element("streamdetails");
            if (streamDetails != null)
            {
                var videoStream = streamDetails.Element("video");
                if (videoStream != null)
                {
                    nfoData.VideoStream = new VideoStreamInfo
                    {
                        Codec = videoStream.Element("codec")?.Value,
                        Width = int.TryParse(videoStream.Element("width")?.Value, out var w) ? w : null,
                        Height = int.TryParse(videoStream.Element("height")?.Value, out var h) ? h : null,
                        AspectRatio = double.TryParse(videoStream.Element("aspect")?.Value, out var ar) ? ar : null,
                        FrameRate = double.TryParse(videoStream.Element("framerate")?.Value, out var fr) ? fr : null,
                        Bitrate = long.TryParse(videoStream.Element("bitrate")?.Value, out var vb) ? vb : null
                    };
                }
                
                var audioStream = streamDetails.Element("audio");
                if (audioStream != null)
                {
                    nfoData.AudioStream = new AudioStreamInfo
                    {
                        Codec = audioStream.Element("codec")?.Value,
                        Channels = int.TryParse(audioStream.Element("channels")?.Value, out var ch) ? ch : null,
                        SampleRate = int.TryParse(audioStream.Element("samplerate")?.Value, out var sr) ? sr : null,
                        Bitrate = long.TryParse(audioStream.Element("bitrate")?.Value, out var ab) ? ab : null
                    };
                }
            }
            
            // Parse custom fields
            nfoData.CustomFields["customfield1"] = root.Element("customfield1")?.Value ?? "";
            nfoData.CustomFields["customfield2"] = root.Element("customfield2")?.Value ?? "";
            nfoData.CustomFields["customfield3"] = root.Element("customfield3")?.Value ?? "";
            
            return nfoData;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error reading NFO file from {Path}", nfoPath);
            return null;
        }
    }

    public async Task<Video> EnrichVideoMetadataAsync(Video video, bool fetchOnlineMetadata = true, CancellationToken cancellationToken = default)
    {
        try
        {
            // Extract metadata from file if available
            if (!string.IsNullOrWhiteSpace(video.FilePath) && File.Exists(video.FilePath))
            {
                var metadata = await ExtractMetadataAsync(video.FilePath, cancellationToken);

                if (metadata is not null)
                {
                    // Update video with file metadata
                    if (string.IsNullOrWhiteSpace(video.Title) && !string.IsNullOrWhiteSpace(metadata.Title))
                    {
                        video.Title = metadata.Title!;
                    }

                    if (string.IsNullOrWhiteSpace(video.Artist) && !string.IsNullOrWhiteSpace(metadata.Artist))
                    {
                        video.Artist = metadata.Artist!;
                    }

                    video.Album ??= metadata.Album;
                    video.Year ??= metadata.ReleaseDate?.Year;

                    // Convert TimeSpan to seconds
                    if (metadata.Duration != null && video.Duration == null)
                    {
                        video.Duration = (int)metadata.Duration.Value.TotalSeconds;
                    }

                    // Set resolution from width and height
                    if (metadata.Width != null && metadata.Height != null && string.IsNullOrEmpty(video.Resolution))
                    {
                        video.Resolution = $"{metadata.Width}x{metadata.Height}";
                    }

                    video.FrameRate ??= metadata.FrameRate;
                    video.VideoCodec ??= metadata.VideoCodec;
                    if (!video.Bitrate.HasValue && metadata.VideoBitrate.HasValue)
                    {
                        video.Bitrate = (int?)metadata.VideoBitrate.Value;
                    }
                    video.AudioCodec ??= metadata.AudioCodec;
                    video.FileSize = metadata.FileSize;
                }
            }
            
            // Fetch online metadata if enabled
            if (fetchOnlineMetadata && !string.IsNullOrWhiteSpace(video.Artist) && !string.IsNullOrWhiteSpace(video.Title))
            {
                // Try to get IMVDb metadata
                var imvdbMetadata = await GetImvdbMetadataAsync(video.Artist, video.Title, cancellationToken);
                if (imvdbMetadata != null)
                {
                    video.ImvdbId = imvdbMetadata.ImvdbId?.ToString();
                    video.Director ??= imvdbMetadata.Director;
                    video.ProductionCompany ??= imvdbMetadata.ProductionCompany;
                    video.Publisher ??= imvdbMetadata.RecordLabel;
                    video.Description ??= imvdbMetadata.Description;
                    video.Year ??= imvdbMetadata.Year;
                    
                    // Convert featured artists string to entities
                    if (!string.IsNullOrEmpty(imvdbMetadata.FeaturedArtists) && !video.FeaturedArtists.Any())
                    {
                        foreach (var artistName in imvdbMetadata.FeaturedArtists.Split(',', StringSplitOptions.RemoveEmptyEntries))
                        {
                            video.FeaturedArtists.Add(new FeaturedArtist { Name = artistName.Trim() });
                        }
                    }
                }
                
                // Try to get MusicBrainz metadata
                var mbMetadata = await GetMusicBrainzMetadataAsync(video.Artist, video.Title, cancellationToken);
                if (mbMetadata != null)
                {
                    video.MusicBrainzRecordingId ??= mbMetadata.RecordingId;
                    video.Album ??= mbMetadata.Album;
                    video.Publisher ??= mbMetadata.RecordLabel;
                }
            }
            
            // Update the video in the database
            video.UpdatedAt = DateTime.UtcNow;
            await _unitOfWork.Videos.UpdateAsync(video);
            await _unitOfWork.SaveChangesAsync();
            
            _logger.LogInformation("Enriched metadata for video {VideoId}", video.Id);
            return video;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error enriching metadata for video {VideoId}", video.Id);
            throw;
        }
    }

    public async Task<string?> DownloadThumbnailAsync(string thumbnailUrl, string outputPath, CancellationToken cancellationToken = default)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(thumbnailUrl))
                return null;
                
            var response = await _httpClient.GetAsync(thumbnailUrl, cancellationToken);
            if (response.IsSuccessStatusCode)
            {
                var bytes = await response.Content.ReadAsByteArrayAsync(cancellationToken);
                await File.WriteAllBytesAsync(outputPath, bytes, cancellationToken);
                
                _logger.LogInformation("Downloaded thumbnail from {Url} to {Path}", thumbnailUrl, outputPath);
                return outputPath;
            }
            
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error downloading thumbnail from {Url}", thumbnailUrl);
            return null;
        }
    }
}
