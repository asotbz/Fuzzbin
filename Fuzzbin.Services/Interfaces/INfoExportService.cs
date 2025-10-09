using Fuzzbin.Core.Entities;

namespace Fuzzbin.Services.Interfaces
{
    public interface INfoExportService
    {
        Task<bool> ExportNfoAsync(Video video, string outputPath, CancellationToken cancellationToken = default);
        Task<int> BulkExportNfoAsync(
            IEnumerable<Video> videos,
            string outputDirectory,
            bool useVideoPath = false,
            CancellationToken cancellationToken = default);
        string GenerateNfoContent(Video video);

        Task<bool> ExportArtistNfoAsync(
            FeaturedArtist artist,
            IEnumerable<Video> artistVideos,
            string outputPath,
            CancellationToken cancellationToken = default);
        string GenerateArtistNfoContent(FeaturedArtist artist, IEnumerable<Video> artistVideos);
    }
}
