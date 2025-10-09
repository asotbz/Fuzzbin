using MudBlazor;

namespace Fuzzbin.Web.Services;

/// <summary>
/// Provides reusable skeleton configurations to keep loading states consistent.
/// </summary>
public sealed class LoadingStateService
{
    private static readonly IReadOnlyDictionary<LoadingProfile, IReadOnlyList<SkeletonDescriptor>> Profiles =
        new Dictionary<LoadingProfile, IReadOnlyList<SkeletonDescriptor>>
        {
            [LoadingProfile.VideoGrid] = new[]
            {
                new SkeletonDescriptor(8, "fz-skeleton-card", "100%", "260px", Animation.Wave),
            },
            [LoadingProfile.QueueList] = new[]
            {
                new SkeletonDescriptor(6, "fz-skeleton-row", "100%", "64px", Animation.Wave),
            },
            [LoadingProfile.FormSections] = new[]
            {
                new SkeletonDescriptor(3, "fz-skeleton-form", "100%", "48px", Animation.Pulse),
                new SkeletonDescriptor(2, "fz-skeleton-form", "75%", "36px", Animation.Pulse),
            },
        };

    public IReadOnlyList<SkeletonDescriptor> GetDescriptors(LoadingProfile profile)
    {
        return Profiles.TryGetValue(profile, out var descriptors)
            ? descriptors
            : Array.Empty<SkeletonDescriptor>();
    }
}

public enum LoadingProfile
{
    VideoGrid,
    QueueList,
    FormSections,
}

public sealed record SkeletonDescriptor(int Count, string CssClass, string Width, string Height, Animation Animation);
