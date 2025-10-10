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
