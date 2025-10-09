using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Videos;

public sealed class VideoDuplicatesSpecification : BaseSpecification<Video>
{
    public VideoDuplicatesSpecification(string artist, string title, bool includeInactive = false)
    {
        if (string.IsNullOrWhiteSpace(artist))
        {
            throw new ArgumentException("Artist is required", nameof(artist));
        }

        if (string.IsNullOrWhiteSpace(title))
        {
            throw new ArgumentException("Title is required", nameof(title));
        }

        var normalizedArtist = artist.Trim().ToLower();
        var normalizedTitle = title.Trim().ToLower();

        if (!includeInactive)
        {
            ApplyCriteria(v => v.IsActive);
        }

        ApplyCriteria(v =>
            v.Title != null && v.Title.ToLower() == normalizedTitle &&
            (
                (v.Artist != null && v.Artist.ToLower() == normalizedArtist) ||
                v.FeaturedArtists.Any(f => f.Name != null && f.Name.ToLower() == normalizedArtist)
            ));

        AddInclude(v => v.FeaturedArtists);
    }
}
