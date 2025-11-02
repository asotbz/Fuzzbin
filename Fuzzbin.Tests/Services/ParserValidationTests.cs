using System.Text.Json;
using Xunit;
using Fuzzbin.Services.External.Imvdb;
using Fuzzbin.Services.External.MusicBrainz;

namespace Fuzzbin.Tests.Services;

/// <summary>
/// Parser validation tests to ensure response models correctly parse API responses
/// based on examples from docs/cache/imvdb-examples.md and docs/cache/musicbrainz-examples.md
/// </summary>
public class ParserValidationTests
{
    private readonly JsonSerializerOptions _jsonOptions;

    public ParserValidationTests()
    {
        _jsonOptions = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        };
    }

    [Fact]
    public void ImvdbVideoResponse_ParsesSourcesArray()
    {
        // Arrange - JSON from docs/cache/imvdb-examples.md example 2
        var json = @"{
            ""id"": 186352742692,
            ""url"": ""https://imvdb.com/video/robert-palmer/addicted-to-love"",
            ""song_title"": ""Addicted to Love"",
            ""video_title"": ""Addicted to Love"",
            ""release_date"": ""1986-01-01"",
            ""runtime_seconds"": 270,
            ""thumbnail"": {
                ""url"": ""https://imvdb.img/186352742692/cover.jpg"",
                ""width"": 640,
                ""height"": 360
            },
            ""artists"": [
                { ""id"": 12345, ""name"": ""Robert Palmer"", ""role"": ""primary"", ""order"": 0 }
            ],
            ""directors"": [
                { ""id"": 9001, ""name"": ""Terence Donovan"" }
            ],
            ""sources"": [
                {
                    ""source"": ""youtube"",
                    ""external_id"": ""XcATvu5f9vE"",
                    ""url"": ""https://www.youtube.com/watch?v=XcATvu5f9vE"",
                    ""is_official"": true
                },
                {
                    ""source"": ""vimeo"",
                    ""external_id"": ""123456789"",
                    ""url"": ""https://vimeo.com/123456789"",
                    ""is_official"": false
                }
            ]
        }";

        // Act
        var response = JsonSerializer.Deserialize<ImvdbVideoResponse>(json, _jsonOptions);

        // Assert
        Assert.NotNull(response);
        Assert.Equal(186352742692L, response.Id);
        Assert.Equal("Addicted to Love", response.SongTitle);
        Assert.Equal("Addicted to Love", response.VideoTitle);
        Assert.Equal("1986-01-01", response.ReleaseDate);
        Assert.Equal(270, response.RuntimeSeconds);

        // Validate thumbnail parsing
        Assert.NotNull(response.Thumbnail);
        Assert.Equal("https://imvdb.img/186352742692/cover.jpg", response.Thumbnail.Url);
        Assert.Equal(640, response.Thumbnail.Width);
        Assert.Equal(360, response.Thumbnail.Height);

        // Validate artists array
        Assert.NotEmpty(response.Artists);
        Assert.Equal(12345, response.Artists[0].Id);
        Assert.Equal("Robert Palmer", response.Artists[0].Name);
        Assert.Equal("primary", response.Artists[0].Role);
        Assert.Equal(0, response.Artists[0].Order);

        // Validate directors array
        Assert.NotEmpty(response.Directors);
        Assert.Equal(9001, response.Directors[0].Id);
        Assert.Equal("Terence Donovan", response.Directors[0].Name);

        // CRITICAL: Validate sources array (required for cache strategy and scoring)
        Assert.NotEmpty(response.Sources);
        Assert.Equal(2, response.Sources.Count);
        
        var youtubeSource = response.Sources[0];
        Assert.Equal("youtube", youtubeSource.Source);
        Assert.Equal("XcATvu5f9vE", youtubeSource.ExternalId);
        Assert.Equal("https://www.youtube.com/watch?v=XcATvu5f9vE", youtubeSource.Url);
        Assert.True(youtubeSource.IsOfficial); // CRITICAL for scoring bonus
        
        var vimeoSource = response.Sources[1];
        Assert.Equal("vimeo", vimeoSource.Source);
        Assert.Equal("123456789", vimeoSource.ExternalId);
        Assert.False(vimeoSource.IsOfficial);
    }

    [Fact]
    public void ImvdbSearchResponse_ParsesHasSourcesField()
    {
        // Arrange - JSON from docs/cache/imvdb-examples.md example 1
        var json = @"{
            ""page"": 1,
            ""per_page"": 25,
            ""total_results"": 3,
            ""results"": [
                {
                    ""id"": 186352742692,
                    ""url"": ""https://imvdb.com/video/robert-palmer/addicted-to-love"",
                    ""song_title"": ""Addicted to Love"",
                    ""video_title"": ""Addicted to Love"",
                    ""release_date"": ""1986-01-01"",
                    ""has_sources"": true,
                    ""artists"": [
                        { ""id"": 12345, ""name"": ""Robert Palmer"", ""role"": ""primary"", ""order"": 0 }
                    ],
                    ""thumbnail"": {
                        ""url"": ""https://imvdb.img/186352742692/cover.jpg"",
                        ""width"": 640,
                        ""height"": 360
                    }
                },
                {
                    ""id"": 186352700001,
                    ""url"": ""https://imvdb.com/video/robert-palmer/addicted-to-love-live"",
                    ""song_title"": ""Addicted to Love (Live)"",
                    ""video_title"": ""Addicted to Love (Live 1986)"",
                    ""release_date"": null,
                    ""has_sources"": false,
                    ""artists"": [
                        { ""id"": 12345, ""name"": ""Robert Palmer"", ""role"": ""primary"", ""order"": 0 }
                    ],
                    ""thumbnail"": null
                }
            ]
        }";

        // Act
        var response = JsonSerializer.Deserialize<ImvdbSearchResponse>(json, _jsonOptions);

        // Assert
        Assert.NotNull(response);
        Assert.Equal(1, response.Page);
        Assert.Equal(25, response.PerPage);
        Assert.Equal(3, response.TotalResults);
        Assert.Equal(2, response.Results.Count);

        // Validate first result with sources
        var firstResult = response.Results[0];
        Assert.Equal(186352742692L, firstResult.Id);
        Assert.True(firstResult.HasSources); // CRITICAL: Indicates YouTube/Vimeo availability
        Assert.Equal("Addicted to Love", firstResult.SongTitle);
        Assert.Equal("Addicted to Love", firstResult.VideoTitle);
        Assert.Equal("1986-01-01", firstResult.ReleaseDate);

        // Validate second result without sources
        var secondResult = response.Results[1];
        Assert.Equal(186352700001L, secondResult.Id);
        Assert.False(secondResult.HasSources); // No YouTube/Vimeo links
        Assert.Null(secondResult.ReleaseDate);
        Assert.Null(secondResult.Thumbnail);
    }

    [Fact]
    public void MbRecording_ParsesReleaseGroupFirstReleaseDate()
    {
        // Arrange - JSON from docs/cache/musicbrainz-examples.md example 1
        var json = @"{
            ""created"": ""2025-11-01T00:00:00Z"",
            ""count"": 3,
            ""offset"": 0,
            ""recordings"": [
                {
                    ""id"": ""aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0001"",
                    ""title"": ""Still Fly"",
                    ""length"": 224000,
                    ""score"": 100,
                    ""artist-credit"": [
                        {
                            ""name"": ""Big Tymers"",
                            ""artist"": {
                                ""id"": ""11111111-2222-3333-4444-555555555555"",
                                ""name"": ""Big Tymers"",
                                ""sort-name"": ""Big Tymers""
                            }
                        }
                    ],
                    ""releases"": [
                        {
                            ""id"": ""99999999-aaaa-bbbb-cccc-dddddddddd01"",
                            ""title"": ""Hood Rich"",
                            ""date"": ""2002-04-30"",
                            ""country"": ""US"",
                            ""release-group"": {
                                ""id"": ""rg-00000000-1111-2222-3333-444444444444"",
                                ""title"": ""Hood Rich"",
                                ""first-release-date"": ""2002-04-30"",
                                ""primary-type"": ""Album""
                            }
                        }
                    ],
                    ""tags"": [
                        {""count"": 2, ""name"": ""hip hop""}
                    ],
                    ""genres"": [
                        {""count"": 2, ""name"": ""hip hop""}
                    ]
                }
            ]
        }";

        // Act
        var response = JsonSerializer.Deserialize<MbRecordingSearchResponse>(json, _jsonOptions);

        // Assert
        Assert.NotNull(response);
        Assert.Equal(3, response.Count);
        Assert.NotEmpty(response.Recordings);
        
        var recording = response.Recordings[0];
        Assert.Equal("aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0001", recording.Id);
        Assert.Equal("Still Fly", recording.Title);
        Assert.Equal(224000, recording.Length); // milliseconds
        Assert.Equal(100, recording.Score); // MusicBrainz relevance score

        // Validate artist-credit
        Assert.NotEmpty(recording.ArtistCredit);
        Assert.Equal("Big Tymers", recording.ArtistCredit[0].Name);
        Assert.Equal("Big Tymers", recording.ArtistCredit[0].Artist.Name);
        Assert.Equal("Big Tymers", recording.ArtistCredit[0].Artist.SortName);

        // CRITICAL: Validate release-group first-release-date (required for year scoring)
        Assert.NotEmpty(recording.Releases);
        var release = recording.Releases[0];
        Assert.NotNull(release.ReleaseGroup);
        Assert.Equal("2002-04-30", release.ReleaseGroup.FirstReleaseDate); // CRITICAL for year scoring
        Assert.Equal("Album", release.ReleaseGroup.PrimaryType);
        Assert.Equal("US", release.Country);

        // Validate tags/genres
        Assert.NotEmpty(recording.Tags);
        Assert.Equal("hip hop", recording.Tags[0].Name);
        Assert.Equal(2, recording.Tags[0].Count);
        
        Assert.NotEmpty(recording.Genres);
        Assert.Equal("hip hop", recording.Genres[0].Name);
    }

    [Fact]
    public void MbArtistCredit_ParsesJoinPhrase()
    {
        // Arrange - JSON with featured artist (joinphrase detection)
        var json = @"{
            ""id"": ""test-recording-id"",
            ""title"": ""Test Song"",
            ""length"": 200000,
            ""score"": 95,
            ""artist-credit"": [
                {
                    ""name"": ""Main Artist"",
                    ""joinphrase"": """",
                    ""artist"": {
                        ""id"": ""artist-1"",
                        ""name"": ""Main Artist"",
                        ""sort-name"": ""Artist, Main""
                    }
                },
                {
                    ""name"": ""Featured Artist"",
                    ""joinphrase"": "" feat. "",
                    ""artist"": {
                        ""id"": ""artist-2"",
                        ""name"": ""Featured Artist"",
                        ""sort-name"": ""Artist, Featured""
                    }
                }
            ],
            ""releases"": [],
            ""tags"": [],
            ""genres"": []
        }";

        // Act
        var recording = JsonSerializer.Deserialize<MbRecording>(json, _jsonOptions);

        // Assert
        Assert.NotNull(recording);
        Assert.Equal(2, recording.ArtistCredit.Count);
        
        // First artist (main)
        var mainArtist = recording.ArtistCredit[0];
        Assert.Equal("Main Artist", mainArtist.Name);
        Assert.Equal("", mainArtist.JoinPhrase); // Empty for main artist
        
        // Second artist (featured) - CRITICAL for IsJoinPhraseFeat detection
        var featuredArtist = recording.ArtistCredit[1];
        Assert.Equal("Featured Artist", featuredArtist.Name);
        Assert.NotNull(featuredArtist.JoinPhrase);
        Assert.Contains("feat", featuredArtist.JoinPhrase.ToLower()); // CRITICAL: detect featuring
    }

    [Fact]
    public void MbRecording_ParsesCompleteReleaseData()
    {
        // Arrange - JSON with complete release data including label info
        var json = @"{
            ""id"": ""recording-with-label"",
            ""title"": ""Test Track"",
            ""length"": 180000,
            ""score"": 90,
            ""artist-credit"": [
                {
                    ""name"": ""Test Artist"",
                    ""artist"": {
                        ""id"": ""artist-id"",
                        ""name"": ""Test Artist"",
                        ""sort-name"": ""Artist, Test"",
                        ""disambiguation"": ""rapper"",
                        ""country"": ""US""
                    }
                }
            ],
            ""releases"": [
                {
                    ""id"": ""release-id"",
                    ""title"": ""Test Album"",
                    ""date"": ""2020-01-15"",
                    ""country"": ""US"",
                    ""barcode"": ""123456789012"",
                    ""track-count"": 12,
                    ""label-info"": [
                        {
                            ""catalog-number"": ""ABC-123"",
                            ""label"": {
                                ""id"": ""label-id"",
                                ""name"": ""Test Records""
                            }
                        }
                    ],
                    ""release-group"": {
                        ""id"": ""rg-id"",
                        ""title"": ""Test Album"",
                        ""first-release-date"": ""2020-01-15"",
                        ""primary-type"": ""Album"",
                        ""tags"": [],
                        ""genres"": []
                    }
                }
            ],
            ""tags"": [],
            ""genres"": []
        }";

        // Act
        var recording = JsonSerializer.Deserialize<MbRecording>(json, _jsonOptions);

        // Assert
        Assert.NotNull(recording);
        
        // Validate artist with disambiguation and country
        var artist = recording.ArtistCredit[0].Artist;
        Assert.Equal("rapper", artist.Disambiguation);
        Assert.Equal("US", artist.Country);

        // Validate complete release data
        var release = recording.Releases[0];
        Assert.Equal("Test Album", release.Title);
        Assert.Equal("2020-01-15", release.Date);
        Assert.Equal("US", release.Country);
        Assert.Equal("123456789012", release.Barcode);
        Assert.Equal(12, release.TrackCount);

        // Validate label info
        Assert.NotNull(release.LabelInfo);
        Assert.NotEmpty(release.LabelInfo);
        var labelInfo = release.LabelInfo[0];
        Assert.Equal("ABC-123", labelInfo.CatalogNumber);
        Assert.NotNull(labelInfo.Label);
        Assert.Equal("Test Records", labelInfo.Label.Name);
    }

    [Fact]
    public void ImvdbVideoResponse_HandlesNullFields()
    {
        // Arrange - Minimal JSON with null fields
        var json = @"{
            ""id"": 123456,
            ""url"": ""https://imvdb.com/video/test"",
            ""song_title"": ""Test Song"",
            ""video_title"": null,
            ""release_date"": null,
            ""runtime_seconds"": null,
            ""thumbnail"": null,
            ""artists"": [],
            ""directors"": [],
            ""sources"": []
        }";

        // Act
        var response = JsonSerializer.Deserialize<ImvdbVideoResponse>(json, _jsonOptions);

        // Assert - Should handle nulls gracefully
        Assert.NotNull(response);
        Assert.Equal(123456L, response.Id);
        Assert.Equal("Test Song", response.SongTitle);
        Assert.Null(response.VideoTitle);
        Assert.Null(response.ReleaseDate);
        Assert.Null(response.RuntimeSeconds);
        Assert.Null(response.Thumbnail);
        Assert.Empty(response.Artists);
        Assert.Empty(response.Directors);
        Assert.Empty(response.Sources);
    }

    [Fact]
    public void MbRecording_HandlesEmptyArrays()
    {
        // Arrange - Minimal recording with empty arrays
        var json = @"{
            ""id"": ""minimal-recording"",
            ""title"": ""Minimal Track"",
            ""length"": null,
            ""score"": 50,
            ""artist-credit"": [],
            ""releases"": [],
            ""tags"": [],
            ""genres"": []
        }";

        // Act
        var recording = JsonSerializer.Deserialize<MbRecording>(json, _jsonOptions);

        // Assert - Should handle empty arrays gracefully
        Assert.NotNull(recording);
        Assert.Equal("minimal-recording", recording.Id);
        Assert.Equal("Minimal Track", recording.Title);
        Assert.Null(recording.Length);
        Assert.Equal(50, recording.Score);
        Assert.Empty(recording.ArtistCredit);
        Assert.Empty(recording.Releases);
        Assert.Empty(recording.Tags);
        Assert.Empty(recording.Genres);
    }
}