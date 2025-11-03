using System;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Interfaces
{
    /// <summary>
    /// Unit of Work pattern interface for managing transactions
    /// </summary>
    public interface IUnitOfWork : IDisposable
    {
        /// <summary>
        /// Repository for Video entities
        /// </summary>
        IRepository<Video> Videos { get; }

        /// <summary>
        /// Repository for Genre entities
        /// </summary>
        IRepository<Genre> Genres { get; }

        /// <summary>
        /// Repository for Tag entities
        /// </summary>
        IRepository<Tag> Tags { get; }

        /// <summary>
        /// Repository for FeaturedArtist entities
        /// </summary>
        IRepository<FeaturedArtist> FeaturedArtists { get; }

        /// <summary>
        /// Repository for Configuration entities
        /// </summary>
        IRepository<Configuration> Configurations { get; }

        /// <summary>
        /// Repository for DownloadQueueItem entities
        /// </summary>
        IRepository<DownloadQueueItem> DownloadQueueItems { get; }

        /// <summary>
        /// Repository for Collection entities with specialized operations
        /// </summary>
        ICollectionRepository Collections { get; }

        /// <summary>
        /// Repository for CollectionVideo entities (join table)
        /// </summary>
        IRepository<CollectionVideo> CollectionVideos { get; }

        /// <summary>
        /// Repository for user preference key/value pairs
        /// </summary>
        IRepository<UserPreference> UserPreferences { get; }

        /// <summary>
        /// Repository for BackgroundJob entities
        /// </summary>
        IRepository<BackgroundJob> BackgroundJobs { get; }

        /// <summary>
        /// Repository for VideoSourceVerification entities
        /// </summary>
        IRepository<VideoSourceVerification> VideoSourceVerifications { get; }

        /// <summary>
        /// Repository for RecycleBin entities
        /// </summary>
        IRepository<RecycleBin> RecycleBins { get; }

        /// <summary>
        /// Repository for MaintenanceExecution entities
        /// </summary>
        IRepository<MaintenanceExecution> MaintenanceExecutions { get; }

        /// <summary>
        /// Repository for CacheStatSnapshot entities
        /// </summary>
        IRepository<CacheStatSnapshot> CacheStatSnapshots { get; }

        // Metadata Cache repositories

        /// <summary>
        /// Repository for Query entities
        /// </summary>
        IRepository<Query> Queries { get; }

        /// <summary>
        /// Repository for QuerySourceCache entities
        /// </summary>
        IRepository<QuerySourceCache> QuerySourceCaches { get; }

        /// <summary>
        /// Repository for QueryResolution entities
        /// </summary>
        IRepository<QueryResolution> QueryResolutions { get; }

        /// <summary>
        /// Repository for MusicBrainz Artist entities
        /// </summary>
        IRepository<MbArtist> MbArtists { get; }

        /// <summary>
        /// Repository for MusicBrainz Recording entities
        /// </summary>
        IRepository<MbRecording> MbRecordings { get; }

        /// <summary>
        /// Repository for MusicBrainz Release entities
        /// </summary>
        IRepository<MbRelease> MbReleases { get; }

        /// <summary>
        /// Repository for MusicBrainz ReleaseGroup entities
        /// </summary>
        IRepository<MbReleaseGroup> MbReleaseGroups { get; }

        /// <summary>
        /// Repository for MusicBrainz Recording Candidate entities
        /// </summary>
        IRepository<MbRecordingCandidate> MbRecordingCandidates { get; }

        /// <summary>
        /// Repository for IMVDb Artist entities
        /// </summary>
        IRepository<ImvdbArtist> ImvdbArtists { get; }

        /// <summary>
        /// Repository for IMVDb Video entities
        /// </summary>
        IRepository<ImvdbVideo> ImvdbVideos { get; }

        /// <summary>
        /// Repository for IMVDb Video Candidate entities
        /// </summary>
        IRepository<ImvdbVideoCandidate> ImvdbVideoCandidates { get; }

        /// <summary>
        /// Repository for YouTube Video entities
        /// </summary>
        IRepository<YtVideo> YtVideos { get; }

        /// <summary>
        /// Repository for YouTube Video Candidate entities
        /// </summary>
        IRepository<YtVideoCandidate> YtVideoCandidates { get; }

        /// <summary>
        /// Repository for MvLink entities (cross-source linking)
        /// </summary>
        IRepository<MvLink> MvLinks { get; }

        // Join table repositories for metadata relationships

        /// <summary>
        /// Repository for MusicBrainz Recording-Artist relationships
        /// </summary>
        IRepository<MbRecordingArtist> MbRecordingArtists { get; }

        /// <summary>
        /// Repository for MusicBrainz Recording-Release relationships
        /// </summary>
        IRepository<MbRecordingRelease> MbRecordingReleases { get; }

        /// <summary>
        /// Repository for MusicBrainz Release-ReleaseGroup relationships
        /// </summary>
        IRepository<MbReleaseToGroup> MbReleaseToGroups { get; }

        /// <summary>
        /// Repository for MusicBrainz Tags
        /// </summary>
        IRepository<MbTag> MbTags { get; }

        /// <summary>
        /// Repository for IMVDb Video-Artist relationships
        /// </summary>
        IRepository<ImvdbVideoArtist> ImvdbVideoArtists { get; }

        /// <summary>
        /// Repository for IMVDb Video Sources
        /// </summary>
        IRepository<ImvdbVideoSource> ImvdbVideoSources { get; }

        /// <summary>
        /// Save all changes to the database
        /// </summary>
        Task<int> SaveChangesAsync();

        /// <summary>
        /// Begin a database transaction
        /// </summary>
        Task BeginTransactionAsync();

        /// <summary>
        /// Commit the current transaction
        /// </summary>
        Task CommitTransactionAsync();

        /// <summary>
        /// Rollback the current transaction
        /// </summary>
        Task RollbackTransactionAsync();
    }
}
