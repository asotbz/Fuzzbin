using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services;

public sealed class GenreMappingDefaultsProvider : IGenreMappingDefaultsProvider
{
    private readonly string _contentRootPath;
    private readonly ILogger<GenreMappingDefaultsProvider> _logger;
    private readonly object _syncRoot = new();
    private IReadOnlyList<GenreMappingEntry>? _cached;

    public GenreMappingDefaultsProvider(
        IHostEnvironment hostEnvironment,
        ILogger<GenreMappingDefaultsProvider> logger)
    {
        ArgumentNullException.ThrowIfNull(hostEnvironment);
        ArgumentNullException.ThrowIfNull(logger);

        _logger = logger;
        _contentRootPath = hostEnvironment.ContentRootPath;
    }

    public IReadOnlyList<GenreMappingEntry> GetDefaultMappings()
    {
        if (_cached is not null)
        {
            return _cached;
        }

        lock (_syncRoot)
        {
            if (_cached is null)
            {
                _cached = LoadMappings();
            }
        }

        return _cached;
    }

    private IReadOnlyList<GenreMappingEntry> LoadMappings()
    {
        try
        {
            var csvPath = ResolveCsvPath();
            if (csvPath is null)
            {
                _logger.LogWarning(
                    "Genre mapping defaults CSV could not be located. Checked {ContentRoot} and {BaseDirectory}",
                    _contentRootPath,
                    AppContext.BaseDirectory);
                return Array.Empty<GenreMappingEntry>();
            }

            using var stream = new FileStream(csvPath, FileMode.Open, FileAccess.Read, FileShare.Read);
            using var reader = new StreamReader(stream, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);

            var entries = new List<GenreMappingEntry>();
            string? line;
            var lineNumber = 0;
            while ((line = reader.ReadLine()) is not null)
            {
                lineNumber++;
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }

                if (lineNumber == 1 && line.Contains("Specific", StringComparison.OrdinalIgnoreCase))
                {
                    // Skip header row
                    continue;
                }

                var parts = line.Split(',', StringSplitOptions.TrimEntries);
                if (parts.Length < 2)
                {
                    _logger.LogWarning("Skipping invalid genre mapping row at line {LineNumber}: {Line}", lineNumber, line);
                    continue;
                }

                var general = parts[0];
                var specific = parts[1];

                if (string.IsNullOrWhiteSpace(general) || string.IsNullOrWhiteSpace(specific))
                {
                    continue;
                }

                entries.Add(new GenreMappingEntry(specific, general));
            }

            if (entries.Count == 0)
            {
                _logger.LogWarning("Genre mapping defaults CSV at {CsvPath} did not produce any entries", csvPath);
            }

            // Remove duplicates (case-insensitive) while preserving order
            var distinctEntries = entries
                .Where(entry => !string.IsNullOrWhiteSpace(entry.SpecificGenre))
                .DistinctBy(entry => entry.SpecificGenre, StringComparer.OrdinalIgnoreCase)
                .ToList();

            return distinctEntries;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to load default genre mappings");
            return Array.Empty<GenreMappingEntry>();
        }
    }

    private string? ResolveCsvPath()
    {
        var candidates = new[]
        {
            Path.Combine(_contentRootPath, "genre_mapping.csv"),
            Path.Combine(AppContext.BaseDirectory, "genre_mapping.csv")
        };

        foreach (var candidate in candidates)
        {
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return null;
    }
}
