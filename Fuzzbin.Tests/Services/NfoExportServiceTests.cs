using System;
using System.Collections.Generic;
using System.Linq;
using System.Xml.Linq;
using Fuzzbin.Core.Entities;
using Fuzzbin.Services;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using Xunit;

namespace Fuzzbin.Tests.Services;

    public class NfoExportServiceTests
    {
        [Fact]
        public void GenerateNfoContent_UsesGeneralizedGenresWhenEnabled()
        {
            var settings = new MetadataSettings
            {
                GeneralizeGenres = true,
                GenreMappings = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                {
                    ["Grunge"] = "Rock"
                }
            };

            var provider = new StubMetadataSettingsProvider(settings);
            var service = new NfoExportService(provider);

            var video = new Video
            {
                Title = "Smells Like Teen Spirit",
                Artist = "Nirvana",
                Genres = new List<Genre>
                {
                    new() { Name = "Grunge" }
                }
            };

            var nfoContent = service.GenerateNfoContent(video);
            var document = XDocument.Parse(nfoContent);
            var genres = document.Root?
                .Elements("genre")
                .Select(element => element.Value)
                .ToList() ?? new List<string>();

            Assert.Contains("Rock", genres);
            Assert.DoesNotContain("Grunge", genres);
        }

        [Fact]
        public void GenerateNfoContent_AddsSpecificGenreTagWhenEnabled()
        {
            var settings = new MetadataSettings
            {
                GeneralizeGenres = true,
                WriteExternalGenreAsTag = true,
                GenreMappings = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                {
                    ["Grunge"] = "Rock"
                }
            };

            var provider = new StubMetadataSettingsProvider(settings);
            var service = new NfoExportService(provider);

            var video = new Video
            {
                Title = "Smells Like Teen Spirit",
                Artist = "Nirvana",
                Genres = new List<Genre>
                {
                    new() { Name = "Grunge" }
                },
                Tags = new List<Tag>
                {
                    new() { Name = "1990s" }
                }
            };

            var nfoContent = service.GenerateNfoContent(video);
            var document = XDocument.Parse(nfoContent);

            var genres = document.Root?
                .Elements("genre")
                .Select(element => element.Value)
                .ToList() ?? new List<string>();

            Assert.Contains("Rock", genres);
            Assert.DoesNotContain("Grunge", genres);

            var tags = document.Root?
                .Elements("tag")
                .Select(element => element.Value)
                .ToList() ?? new List<string>();

            Assert.Contains("1990s", tags);
            Assert.Contains("Grunge", tags);
            Assert.Equal(1, tags.Count(tag => string.Equals(tag, "Grunge", StringComparison.OrdinalIgnoreCase)));
        }

        [Fact]
        public void GenerateNfoContent_UsePrimaryArtistTrue_ExcludesFeaturedArtists()
    {
        // Arrange
        var settings = new MetadataSettings
        {
            UsePrimaryArtistForNfo = true,
            AppendFeaturedArtistsToTitle = false
        };

        var provider = new StubMetadataSettingsProvider(settings);
        var service = new NfoExportService(provider);

        var video = new Video
        {
            Title = "End Game",
            Artist = "Taylor Swift",
            FeaturedArtists = new List<FeaturedArtist>
            {
                new() { Name = "Ed Sheeran" },
                new() { Name = "Future" }
            }
        };

        // Act
        var nfoContent = service.GenerateNfoContent(video);
        var document = XDocument.Parse(nfoContent);

        // Assert
        var artists = document.Root?
            .Elements("artist")
            .Select(element => element.Value)
            .ToList() ?? new List<string>();

        Assert.Contains("Taylor Swift", artists);
        Assert.DoesNotContain("Ed Sheeran", artists);
        Assert.DoesNotContain("Future", artists);
            Assert.Single(artists); // Only the main artist
        }

        [Fact]
        public void GenerateNfoContent_UsePrimaryArtistFalse_IncludesFeaturedArtists()
    {
        // Arrange
        var settings = new MetadataSettings
        {
            UsePrimaryArtistForNfo = false,
            AppendFeaturedArtistsToTitle = false
        };

        var provider = new StubMetadataSettingsProvider(settings);
        var service = new NfoExportService(provider);

        var video = new Video
        {
            Title = "End Game",
            Artist = "Taylor Swift",
            FeaturedArtists = new List<FeaturedArtist>
            {
                new() { Name = "Ed Sheeran" },
                new() { Name = "Future" }
            }
        };

        // Act
        var nfoContent = service.GenerateNfoContent(video);
        var document = XDocument.Parse(nfoContent);

        // Assert
        var artists = document.Root?
            .Elements("artist")
            .Select(element => element.Value)
            .ToList() ?? new List<string>();

        Assert.Contains("Taylor Swift", artists);
        Assert.Contains("Ed Sheeran", artists);
        Assert.Contains("Future", artists);
            Assert.Equal(3, artists.Count);
        }

        [Fact]
        public void GenerateNfoContent_AppendFeaturedTrue_AppendsToTitle()
    {
        // Arrange
        var settings = new MetadataSettings
        {
            UsePrimaryArtistForNfo = true,
            AppendFeaturedArtistsToTitle = true
        };

        var provider = new StubMetadataSettingsProvider(settings);
        var service = new NfoExportService(provider);

        var video = new Video
        {
            Title = "Work",
            Artist = "Rihanna",
            FeaturedArtists = new List<FeaturedArtist>
            {
                new() { Name = "Drake" }
            }
        };

        // Act
        var nfoContent = service.GenerateNfoContent(video);
        var document = XDocument.Parse(nfoContent);

        // Assert
        var title = document.Root?.Element("title")?.Value;
        Assert.NotNull(title);
        Assert.Contains("feat.", title, StringComparison.OrdinalIgnoreCase);
            Assert.Contains("Drake", title);
        }

        [Fact]
        public void GenerateNfoContent_AppendFeaturedFalse_LeavesTitleUnchanged()
    {
        // Arrange
        var settings = new MetadataSettings
        {
            UsePrimaryArtistForNfo = true,
            AppendFeaturedArtistsToTitle = false
        };

        var provider = new StubMetadataSettingsProvider(settings);
        var service = new NfoExportService(provider);

        var video = new Video
        {
            Title = "Work",
            Artist = "Rihanna",
            FeaturedArtists = new List<FeaturedArtist>
            {
                new() { Name = "Drake" }
            }
        };

        // Act
        var nfoContent = service.GenerateNfoContent(video);
        var document = XDocument.Parse(nfoContent);

        // Assert
        var title = document.Root?.Element("title")?.Value;
        Assert.NotNull(title);
        Assert.Equal("Work", title);
        Assert.DoesNotContain("feat.", title, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("Drake", title);
        }

        [Fact]
        public void GenerateNfoContent_WriteCollectionsTagsTrue_IncludesCollectionNames()
    {
        // Arrange
        var settings = new MetadataSettings
        {
            WriteCollectionsAsNfoTags = true
        };

        var provider = new StubMetadataSettingsProvider(settings);
        var service = new NfoExportService(provider);

        var video = new Video
        {
            Title = "Thriller",
            Artist = "Michael Jackson",
            CollectionVideos = new List<CollectionVideo>
            {
                new() { Collection = new Collection { Name = "80s Classics" } },
                new() { Collection = new Collection { Name = "Best Of MJ" } }
            },
            Tags = new List<Tag>
            {
                new() { Name = "Pop" }
            }
        };

        // Act
        var nfoContent = service.GenerateNfoContent(video);
        var document = XDocument.Parse(nfoContent);

        // Assert
        var tags = document.Root?
            .Elements("tag")
            .Select(element => element.Value)
            .ToList() ?? new List<string>();

        Assert.Contains("Pop", tags);
        Assert.Contains("80s Classics", tags);
        Assert.Contains("Best Of MJ", tags);
            Assert.Equal(3, tags.Count);
        }

        [Fact]
        public void GenerateNfoContent_WriteCollectionsTagsFalse_ExcludesCollections()
    {
        // Arrange
        var settings = new MetadataSettings
        {
            WriteCollectionsAsNfoTags = false
        };

        var provider = new StubMetadataSettingsProvider(settings);
        var service = new NfoExportService(provider);

        var video = new Video
        {
            Title = "Thriller",
            Artist = "Michael Jackson",
            CollectionVideos = new List<CollectionVideo>
            {
                new() { Collection = new Collection { Name = "80s Classics" } },
                new() { Collection = new Collection { Name = "Best Of MJ" } }
            },
            Tags = new List<Tag>
            {
                new() { Name = "Pop" }
            }
        };

        // Act
        var nfoContent = service.GenerateNfoContent(video);
        var document = XDocument.Parse(nfoContent);

        // Assert
        var tags = document.Root?
            .Elements("tag")
            .Select(element => element.Value)
            .ToList() ?? new List<string>();

        Assert.Contains("Pop", tags);
        Assert.DoesNotContain("80s Classics", tags);
        Assert.DoesNotContain("Best Of MJ", tags);
            Assert.Single(tags);
        }

        [Fact]
        public void GenerateNfoContent_WithNoFeaturedArtists_DoesNotCrash()
    {
        // Arrange
        var settings = new MetadataSettings
        {
            UsePrimaryArtistForNfo = true,
            AppendFeaturedArtistsToTitle = true
        };

        var provider = new StubMetadataSettingsProvider(settings);
        var service = new NfoExportService(provider);

        var video = new Video
        {
            Title = "Billie Jean",
            Artist = "Michael Jackson",
            FeaturedArtists = null!
        };

        // Act
        var nfoContent = service.GenerateNfoContent(video);
        var document = XDocument.Parse(nfoContent);

        // Assert
        var title = document.Root?.Element("title")?.Value;
        Assert.NotNull(title);
            Assert.Equal("Billie Jean", title);
        }

        [Fact]
        public void GenerateNfoContent_WithEmptyCollections_DoesNotCrash()
    {
        // Arrange
        var settings = new MetadataSettings
        {
            WriteCollectionsAsNfoTags = true
        };

        var provider = new StubMetadataSettingsProvider(settings);
        var service = new NfoExportService(provider);

        var video = new Video
        {
            Title = "Song",
            Artist = "Artist",
            CollectionVideos = new List<CollectionVideo>(),
            Tags = new List<Tag>()
        };

        // Act
        var nfoContent = service.GenerateNfoContent(video);

        // Assert
        Assert.NotNull(nfoContent);
            Assert.Contains("<musicvideo>", nfoContent);
        }

        private sealed class StubMetadataSettingsProvider : IMetadataSettingsProvider
        {
            private readonly MetadataSettings _settings;

            public StubMetadataSettingsProvider(MetadataSettings settings)
        {
            _settings = settings ?? throw new ArgumentNullException(nameof(settings));
        }

        public MetadataSettings GetSettings() => _settings;

        public void Invalidate()
        {
            // no-op for tests
        }
    }
}
