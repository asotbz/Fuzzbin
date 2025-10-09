using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Videos;

public sealed class VideosByGenreSpecification : BaseSpecification<Video>
{
    public VideosByGenreSpecification(Guid genreId)
    {
        ApplyCriteria(v => v.IsActive);
        ApplyCriteria(v => v.Genres.Any(g => g.Id == genreId));

        AddInclude(v => v.Genres);
        AddInclude(v => v.FeaturedArtists);
        AddOrderBy(v => v.Title);
    }
}
