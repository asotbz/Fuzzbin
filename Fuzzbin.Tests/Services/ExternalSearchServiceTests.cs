using System.Linq;
using Microsoft.Extensions.Logging.Abstractions;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services;
using Fuzzbin.Services.External.Imvdb;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using YtSearchResult = Fuzzbin.Core.Interfaces.SearchResult;
using ApiImvdbCredit = Fuzzbin.Services.External.Imvdb.ImvdbCredit;
using ApiImvdbPerson = Fuzzbin.Services.External.Imvdb.ImvdbPerson;

namespace Fuzzbin.Tests.Services;

public class ExternalSearchServiceTests
{
    [Fact]
    public async Task SearchAsync_WithMatchingSources_ReturnsCombinedResult()
    {
        var imvdbApi = new FakeImvdbApi
        {
            SearchResponse = new ImvdbSearchResponse
            {
                Results =
                {
                    new ImvdbVideoSummary
                    {
                        Id = 101,
                        Artist = "Daft Punk",
                        SongTitle = "Around the World",
                        Title = "Around the World",
                        ImageUrl = "https://imvdb.test/thumb",
                        Url = "https://imvdb.test/video"
                    }
                }
            },
            VideoResponses =
            {
                ["101"] = new ImvdbVideoResponse
                {
                    Id = 101,
                    Artist = "Daft Punk",
                    SongTitle = "Around the World",
                    ReleaseDate = "1997-03-17",
                    ThumbnailUrl = "https://imvdb.test/detail-thumb",
                    ImvdbUrl = "https://imvdb.test/video",
                    Genres = new List<ImvdbGenre> { new() { Name = "Electronic" } },
                    Credits = new List<ApiImvdbCredit>
                    {
                        new ApiImvdbCredit
                        {
                            Role = "Director",
                            Person = new ApiImvdbPerson { Name = "Michel Gondry" }
                        }
                    }
                }
            }
        };

        var youtubeService = new FakeYtDlpService
        {
            Results =
            {
                new YtSearchResult
                {
                    Title = "Daft Punk - Around the World (Official Music Video)",
                    Url = "https://youtube.test/watch?v=123",
                    ThumbnailUrl = "https://youtube.test/thumb",
                    Duration = TimeSpan.FromMinutes(4)
                }
            }
        };

        var apiKeyProvider = new FakeApiKeyProvider(() => "key");
        var service = new ExternalSearchService(imvdbApi, youtubeService, apiKeyProvider, NullLogger<ExternalSearchService>.Instance);

        var query = new ExternalSearchQuery
        {
            Artist = "Daft Punk",
            Title = "Around the World",
            SearchText = "Daft Punk Around the World",
            MaxResults = 5
        };

        var result = await service.SearchAsync(query);

        Assert.NotNull(result);
        var item = Assert.Single(result.Items);
        Assert.Equal(ExternalSearchSource.Combined, item.Source);
        Assert.NotNull(item.Imvdb);
        Assert.Equal(101, item.Imvdb!.ImvdbId);
        Assert.NotNull(item.YtDlp);
        Assert.Equal("https://youtube.test/watch?v=123", item.YtDlp!.Url);
        Assert.True(item.Confidence > 0.5);
        Assert.Empty(result.Warnings);
    }

    [Fact]
    public async Task SearchAsync_WithEmptyQuery_ReturnsWarning()
    {
        var service = new ExternalSearchService(new FakeImvdbApi(), new FakeYtDlpService(), new FakeApiKeyProvider(() => null), NullLogger<ExternalSearchService>.Instance);

        var result = await service.SearchAsync(new ExternalSearchQuery());

        Assert.NotNull(result);
        Assert.Empty(result.Items);
        Assert.Contains(result.Warnings, warning => warning.Contains("Provide a song"));
    }

    [Fact]
    public async Task SearchAsync_WithoutImvdbKey_AddsWarning()
    {
        var service = new ExternalSearchService(new FakeImvdbApi(), new FakeYtDlpService(), new FakeApiKeyProvider(() => null), NullLogger<ExternalSearchService>.Instance);

        var query = new ExternalSearchQuery
        {
            Artist = "Test",
            Title = "Song",
            SearchText = "Test Song"
        };

        var result = await service.SearchAsync(query);

        Assert.Contains(result.Warnings, warning => warning.Contains("IMVDb API key not configured"));
        Assert.Empty(result.Items);
    }

    [Fact]
    public async Task SearchAsync_WithDefaultToggles_IncludesBothSources()
    {
        // Arrange
        var imvdbApi = new FakeImvdbApi
        {
            SearchResponse = new ImvdbSearchResponse
            {
                Results =
                {
                    new ImvdbVideoSummary
                    {
                        Id = 102,
                        Artist = "Test Artist",
                        SongTitle = "Test Song",
                        Title = "Test Song",
                        ImageUrl = "https://imvdb.test/thumb",
                        Url = "https://imvdb.test/video"
                    }
                }
            }
        };

        var youtubeService = new FakeYtDlpService
        {
            Results =
            {
                new YtSearchResult
                {
                    Title = "Test Artist - Test Song",
                    Url = "https://youtube.test/watch?v=456",
                    ThumbnailUrl = "https://youtube.test/thumb",
                    Duration = TimeSpan.FromMinutes(3)
                }
            }
        };

        var apiKeyProvider = new FakeApiKeyProvider(() => "test-key");
        var service = new ExternalSearchService(imvdbApi, youtubeService, apiKeyProvider, NullLogger<ExternalSearchService>.Instance);

        // Act - Query with default toggles (both true)
        var query = new ExternalSearchQuery
        {
            SearchText = "Test Artist Test Song",
            MaxResults = 10,
            IncludeImvdb = true,
            IncludeYtDlp = true
        };

        var result = await service.SearchAsync(query);

        // Assert
        Assert.NotNull(result);
        Assert.True(result.ImvdbEnabled);
        Assert.True(result.YtDlpEnabled);
        Assert.NotEmpty(result.Items);
    }

    [Fact]
    public async Task SearchAsync_WithImvdbDisabled_OnlyReturnsYtDlpResults()
    {
        // Arrange
        var imvdbApi = new FakeImvdbApi();
        var youtubeService = new FakeYtDlpService
        {
            Results =
            {
                new YtSearchResult
                {
                    Title = "Test Video",
                    Url = "https://youtube.test/watch?v=789",
                    ThumbnailUrl = "https://youtube.test/thumb"
                }
            }
        };

        var apiKeyProvider = new FakeApiKeyProvider(() => "test-key");
        var service = new ExternalSearchService(imvdbApi, youtubeService, apiKeyProvider, NullLogger<ExternalSearchService>.Instance);

        // Act
        var query = new ExternalSearchQuery
        {
            SearchText = "Test Video",
            MaxResults = 10,
            IncludeImvdb = false,
            IncludeYtDlp = true
        };

        var result = await service.SearchAsync(query);

        // Assert
        Assert.NotNull(result);
        Assert.False(result.ImvdbEnabled);
        Assert.True(result.YtDlpEnabled);
        Assert.NotEmpty(result.Items);
        Assert.All(result.Items, item => Assert.True(item.Source == ExternalSearchSource.YtDlp));
    }

    [Fact]
    public async Task SearchAsync_WithYtDlpDisabled_OnlyReturnsImvdbResults()
    {
        // Arrange
        var imvdbApi = new FakeImvdbApi
        {
            SearchResponse = new ImvdbSearchResponse
            {
                Results =
                {
                    new ImvdbVideoSummary
                    {
                        Id = 103,
                        Artist = "Artist Name",
                        SongTitle = "Song Title",
                        Title = "Song Title",
                        ImageUrl = "https://imvdb.test/thumb",
                        Url = "https://imvdb.test/video"
                    }
                }
            },
            VideoResponses =
            {
                ["103"] = new ImvdbVideoResponse
                {
                    Id = 103,
                    Artist = "Artist Name",
                    SongTitle = "Song Title",
                    ReleaseDate = "2020-01-01",
                    ThumbnailUrl = "https://imvdb.test/detail-thumb",
                    ImvdbUrl = "https://imvdb.test/video",
                    Genres = new List<ImvdbGenre> { new() { Name = "Pop" } }
                }
            }
        };

        var youtubeService = new FakeYtDlpService();
        var apiKeyProvider = new FakeApiKeyProvider(() => "test-key");
        var service = new ExternalSearchService(imvdbApi, youtubeService, apiKeyProvider, NullLogger<ExternalSearchService>.Instance);

        // Act
        var query = new ExternalSearchQuery
        {
            SearchText = "Artist Name Song Title",
            MaxResults = 10,
            IncludeImvdb = true,
            IncludeYtDlp = false
        };

        var result = await service.SearchAsync(query);

        // Assert
        Assert.NotNull(result);
        Assert.True(result.ImvdbEnabled);
        Assert.False(result.YtDlpEnabled);
        Assert.NotEmpty(result.Items);
        Assert.All(result.Items, item => Assert.True(item.Source == ExternalSearchSource.Imvdb));
    }

    private sealed class FakeImvdbApi : IImvdbApi
    {
        public ImvdbSearchResponse SearchResponse { get; set; } = new();
        public Dictionary<string, ImvdbVideoResponse> VideoResponses { get; } = new();

        public Task<ImvdbVideoResponse> GetVideoAsync(string id, CancellationToken cancellationToken = default)
        {
            if (VideoResponses.TryGetValue(id, out var response))
            {
                return Task.FromResult(response);
            }

            throw new InvalidOperationException($"No test response configured for video id {id}");
        }

        public Task<ImvdbSearchResponse> SearchVideosAsync(string query, int page = 1, int perPage = 20, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(SearchResponse);
        }
    }

    private sealed class FakeYtDlpService : IYtDlpService
    {
        public List<YtSearchResult> Results { get; } = new();

        public Task<List<YtSearchResult>> SearchVideosAsync(string query, int maxResults = 10, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(Results.Take(maxResults).ToList());
        }

        public Task<DownloadResult> DownloadVideoAsync(string url, string outputPath, IProgress<DownloadProgress>? progress = null, CancellationToken cancellationToken = default)
        {
            throw new NotImplementedException();
        }

        public Task<YtDlpVideoMetadata> GetVideoMetadataAsync(string url, CancellationToken cancellationToken = default)
        {
            throw new NotImplementedException();
        }

        public Task<bool> ValidateInstallationAsync()
        {
            throw new NotImplementedException();
        }

        public Task<string> GetVersionAsync()
        {
            throw new NotImplementedException();
        }
    }

    private sealed class FakeApiKeyProvider : IImvdbApiKeyProvider
    {
        private readonly Func<string?> _resolver;

        public FakeApiKeyProvider(Func<string?> resolver)
        {
            _resolver = resolver;
        }

        public Task<string?> GetApiKeyAsync(CancellationToken cancellationToken = default)
        {
            return Task.FromResult(_resolver());
        }
    }
}
