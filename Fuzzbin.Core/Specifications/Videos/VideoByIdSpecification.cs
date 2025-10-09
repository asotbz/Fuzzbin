using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Videos;

public sealed class VideoByIdSpecification : BaseSpecification<Video>
{
    public VideoByIdSpecification(Guid id, bool includeRelations = true, bool trackForUpdate = false)
        : base(v => v.Id == id)
    {
        if (trackForUpdate)
        {
            EnableTracking();
        }

        if (!includeRelations)
        {
            return;
        }

        AddInclude(v => v.Genres);
        AddInclude(v => v.Tags);
        AddInclude(v => v.FeaturedArtists);
        AddInclude(v => v.CollectionVideos);
        AddInclude($"{nameof(Video.CollectionVideos)}.{nameof(CollectionVideo.Collection)}");
    }
}
