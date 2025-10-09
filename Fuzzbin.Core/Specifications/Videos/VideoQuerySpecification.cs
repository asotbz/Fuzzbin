using System;
using System.Linq;
using Microsoft.EntityFrameworkCore;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Specifications.Queries;

namespace Fuzzbin.Core.Specifications.Videos;

public sealed class VideoQuerySpecification : BaseSpecification<Video>
{
    public VideoQuerySpecification(
        VideoQuery query,
        bool includeGenres = true,
        bool includeTags = true,
        bool includeFeaturedArtists = true,
        bool includeCollections = false,
        bool applyPaging = true)
    {
        if (query == null)
        {
            throw new ArgumentNullException(nameof(query));
        }

        query.Normalize();

        if (!query.IncludeInactive)
        {
            ApplyCriteria(v => v.IsActive);
        }

        if (!string.IsNullOrEmpty(query.Search))
        {
            foreach (var term in query.SearchTerms)
            {
                var likeTerm = $"%{term}%";
                ApplyCriteria(v =>
                    EF.Functions.Like(v.Title, likeTerm) ||
                    EF.Functions.Like(v.Artist, likeTerm) ||
                    (v.Album != null && EF.Functions.Like(v.Album, likeTerm)) ||
                    v.FeaturedArtists.Any(f => EF.Functions.Like(f.Name, likeTerm)) ||
                    v.Tags.Any(t => EF.Functions.Like(t.Name, likeTerm)) ||
                    v.Genres.Any(g => EF.Functions.Like(g.Name, likeTerm)));
            }
        }

        if (query.GenreIds.Count > 0)
        {
            foreach (var genreId in query.GenreIds)
            {
                ApplyCriteria(v => v.Genres.Any(g => g.Id == genreId));
            }
        }

        if (query.GenreNames.Count > 0)
        {
            var genreNames = query.GenreNames
                .Select(name => name.ToLowerInvariant())
                .ToList();

            ApplyCriteria(v => v.Genres.Any(g => genreNames.Contains(g.Name.ToLower())));
        }

        if (query.TagIds.Count > 0)
        {
            foreach (var tagId in query.TagIds)
            {
                ApplyCriteria(v => v.Tags.Any(t => t.Id == tagId));
            }
        }

        if (query.CollectionIds.Count > 0)
        {
            foreach (var collectionId in query.CollectionIds)
            {
                ApplyCriteria(v => v.CollectionVideos.Any(cv => cv.CollectionId == collectionId));
            }
        }

        if (query.ArtistNames.Count > 0)
        {
            var artists = query.ArtistNames
                .Select(a => a.ToLowerInvariant())
                .ToList();

            ApplyCriteria(v =>
                (v.Artist != null && artists.Contains(v.Artist.ToLower())) ||
                v.FeaturedArtists.Any(f => f.Name != null && artists.Contains(f.Name.ToLower())));
        }

        if (query.Formats.Count > 0)
        {
            var formats = query.Formats.Select(f => f.ToLowerInvariant()).ToList();
            ApplyCriteria(v => v.Format != null && formats.Contains(v.Format.ToLower()));
        }

        if (query.Resolutions.Count > 0)
        {
            var resolutions = query.Resolutions.Select(r => r.ToLowerInvariant()).ToList();
            ApplyCriteria(v => v.Resolution != null && resolutions.Contains(v.Resolution.ToLower()));
        }

        if (query.Years.Count > 0)
        {
            var years = query.Years.ToList();
            ApplyCriteria(v => v.Year.HasValue && years.Contains(v.Year.Value));
        }

        if (query.YearFrom.HasValue)
        {
            ApplyCriteria(v => v.Year.HasValue && v.Year.Value >= query.YearFrom.Value);
        }

        if (query.YearTo.HasValue)
        {
            ApplyCriteria(v => v.Year.HasValue && v.Year.Value <= query.YearTo.Value);
        }

        if (query.DurationFrom.HasValue)
        {
            ApplyCriteria(v => v.Duration.HasValue && v.Duration.Value >= query.DurationFrom.Value);
        }

        if (query.DurationTo.HasValue)
        {
            ApplyCriteria(v => v.Duration.HasValue && v.Duration.Value <= query.DurationTo.Value);
        }

        if (query.MinRating.HasValue)
        {
            ApplyCriteria(v => v.Rating.HasValue && v.Rating.Value >= query.MinRating.Value);
        }

        if (query.HasFile.HasValue)
        {
            if (query.HasFile.Value)
            {
                ApplyCriteria(v => v.FilePath != null && v.FileSize.HasValue && v.FileSize.Value > 0);
            }
            else
            {
                ApplyCriteria(v => v.FilePath == null || !v.FileSize.HasValue || v.FileSize.Value == 0);
            }
        }

        if (query.MissingMetadata.HasValue && query.MissingMetadata.Value)
        {
            ApplyCriteria(v =>
                string.IsNullOrEmpty(v.ImvdbId) ||
                string.IsNullOrEmpty(v.ThumbnailPath) ||
                string.IsNullOrEmpty(v.Description));
        }

        if (query.HasCollections.HasValue)
        {
            if (query.HasCollections.Value)
            {
                ApplyCriteria(v => v.CollectionVideos.Any());
            }
            else
            {
                ApplyCriteria(v => !v.CollectionVideos.Any());
            }
        }

        if (query.HasYouTubeId.HasValue)
        {
            if (query.HasYouTubeId.Value)
            {
                ApplyCriteria(v => !string.IsNullOrEmpty(v.YouTubeId));
            }
            else
            {
                ApplyCriteria(v => string.IsNullOrEmpty(v.YouTubeId));
            }
        }

        if (query.HasImvdbId.HasValue)
        {
            if (query.HasImvdbId.Value)
            {
                ApplyCriteria(v => !string.IsNullOrEmpty(v.ImvdbId));
            }
            else
            {
                ApplyCriteria(v => string.IsNullOrEmpty(v.ImvdbId));
            }
        }

        if (query.AddedAfter.HasValue)
        {
            var after = query.AddedAfter.Value;
            ApplyCriteria(v => v.CreatedAt >= after);
        }

        if (query.AddedBefore.HasValue)
        {
            var before = query.AddedBefore.Value;
            ApplyCriteria(v => v.CreatedAt <= before);
        }

        ConfigureIncludes(includeGenres, includeTags, includeFeaturedArtists, includeCollections);
        ConfigureSorting(query);

        if (applyPaging)
        {
            ApplyPaging(query.Skip, query.PageSize);
        }
    }

    private void ConfigureIncludes(bool includeGenres, bool includeTags, bool includeFeaturedArtists, bool includeCollections)
    {
        if (includeGenres)
        {
            AddInclude(v => v.Genres);
        }

        if (includeTags)
        {
            AddInclude(v => v.Tags);
        }

        if (includeFeaturedArtists)
        {
            AddInclude(v => v.FeaturedArtists);
        }

        if (includeCollections)
        {
            AddInclude(v => v.CollectionVideos);
            AddInclude($"{nameof(Video.CollectionVideos)}.{nameof(CollectionVideo.Collection)}");
            EnableSplitQuery();
        }
    }

    private void ConfigureSorting(VideoQuery query)
    {
        switch (query.SortBy)
        {
            case VideoSortOption.Artist:
                if (query.SortDirection == SortDirection.Descending)
                {
                    AddOrderByDescending(v => v.Artist);
                }
                else
                {
                    AddOrderBy(v => v.Artist);
                }
                break;
            case VideoSortOption.CreatedAt:
                if (query.SortDirection == SortDirection.Descending)
                {
                    AddOrderByDescending(v => v.CreatedAt);
                }
                else
                {
                    AddOrderBy(v => v.CreatedAt);
                }
                break;
            case VideoSortOption.UpdatedAt:
                if (query.SortDirection == SortDirection.Descending)
                {
                    AddOrderByDescending(v => v.UpdatedAt);
                }
                else
                {
                    AddOrderBy(v => v.UpdatedAt);
                }
                break;
            case VideoSortOption.LastPlayedAt:
                if (query.SortDirection == SortDirection.Descending)
                {
                    AddOrderByDescending(v => v.LastPlayedAt ?? DateTime.MinValue);
                }
                else
                {
                    AddOrderBy(v => v.LastPlayedAt ?? DateTime.MinValue);
                }
                break;
            case VideoSortOption.PlayCount:
                if (query.SortDirection == SortDirection.Descending)
                {
                    AddOrderByDescending(v => v.PlayCount);
                }
                else
                {
                    AddOrderBy(v => v.PlayCount);
                }
                break;
            case VideoSortOption.Rating:
                if (query.SortDirection == SortDirection.Descending)
                {
                    AddOrderByDescending(v => v.Rating ?? 0);
                }
                else
                {
                    AddOrderBy(v => v.Rating ?? 0);
                }
                break;
            case VideoSortOption.Year:
                if (query.SortDirection == SortDirection.Descending)
                {
                    AddOrderByDescending(v => v.Year ?? 0);
                }
                else
                {
                    AddOrderBy(v => v.Year ?? 0);
                }
                break;
            case VideoSortOption.Duration:
                if (query.SortDirection == SortDirection.Descending)
                {
                    AddOrderByDescending(v => v.Duration ?? 0);
                }
                else
                {
                    AddOrderBy(v => v.Duration ?? 0);
                }
                break;
            case VideoSortOption.Random:
                AddOrderBy(_ => EF.Functions.Random());
                break;
            case VideoSortOption.Title:
            default:
                if (query.SortDirection == SortDirection.Descending)
                {
                    AddOrderByDescending(v => v.Title);
                }
                else
                {
                    AddOrderBy(v => v.Title);
                }
                break;
        }

        // Deterministic secondary ordering ensures predictable results.
        AddOrderBy(v => v.Title);
    }
}
