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
