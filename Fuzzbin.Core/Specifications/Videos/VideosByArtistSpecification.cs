using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Videos;

public sealed class VideosByArtistSpecification : BaseSpecification<Video>
{
    public VideosByArtistSpecification(string artist)
    {
        if (string.IsNullOrWhiteSpace(artist))
        {
            throw new ArgumentException("Artist is required", nameof(artist));
        }

        var normalizedArtist = artist.Trim().ToLower();

        ApplyCriteria(v => v.IsActive && (
            (v.Artist != null && v.Artist.ToLower() == normalizedArtist) ||
            v.FeaturedArtists.Any(f => f.Name != null && f.Name.ToLower() == normalizedArtist)));

        AddInclude(v => v.FeaturedArtists);
        AddInclude(v => v.Genres);
        AddOrderBy(v => v.Title);
    }
}
