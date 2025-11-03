using System;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore.Storage;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Data.Context;

namespace Fuzzbin.Data.Repositories
{
    public class UnitOfWork : IUnitOfWork
    {
        private readonly ApplicationDbContext _context;
        private IDbContextTransaction? _transaction;
        private bool _disposed;

        // Repository instances
        private IRepository<Video>? _videos;
        private IRepository<Genre>? _genres;
        private IRepository<Tag>? _tags;
        private IRepository<FeaturedArtist>? _featuredArtists;
        private IRepository<Configuration>? _configurations;
        private IRepository<DownloadQueueItem>? _downloadQueueItems;
        private ICollectionRepository? _collections;
        private IRepository<CollectionVideo>? _collectionVideos;
        private IRepository<UserPreference>? _userPreferences;
        private IRepository<BackgroundJob>? _backgroundJobs;
        private IRepository<VideoSourceVerification>? _videoSourceVerifications;
        private IRepository<RecycleBin>? _recycleBins;

        // Metadata cache repository instances
        private IRepository<Query>? _queries;
        private IRepository<QuerySourceCache>? _querySourceCaches;
        private IRepository<QueryResolution>? _queryResolutions;
        private IRepository<MbArtist>? _mbArtists;
        private IRepository<MbRecording>? _mbRecordings;
        private IRepository<MbRelease>? _mbReleases;
        private IRepository<MbReleaseGroup>? _mbReleaseGroups;
        private IRepository<MbRecordingCandidate>? _mbRecordingCandidates;
        private IRepository<ImvdbArtist>? _imvdbArtists;
        private IRepository<ImvdbVideo>? _imvdbVideos;
        private IRepository<ImvdbVideoCandidate>? _imvdbVideoCandidates;
        private IRepository<YtVideo>? _ytVideos;
        private IRepository<YtVideoCandidate>? _ytVideoCandidates;
        private IRepository<MvLink>? _mvLinks;
        
        // Join table repository instances
        private IRepository<MbRecordingArtist>? _mbRecordingArtists;
        private IRepository<MbRecordingRelease>? _mbRecordingReleases;
        private IRepository<MbReleaseToGroup>? _mbReleaseToGroups;
        private IRepository<MbTag>? _mbTags;
        private IRepository<ImvdbVideoArtist>? _imvdbVideoArtists;
        private IRepository<ImvdbVideoSource>? _imvdbVideoSources;

        public UnitOfWork(ApplicationDbContext context)
        {
            _context = context;
        }

        public IRepository<Video> Videos => _videos ??= new Repository<Video>(_context);
        public IRepository<Genre> Genres => _genres ??= new Repository<Genre>(_context);
        public IRepository<Tag> Tags => _tags ??= new Repository<Tag>(_context);
        public IRepository<FeaturedArtist> FeaturedArtists => _featuredArtists ??= new Repository<FeaturedArtist>(_context);
        public IRepository<Configuration> Configurations => _configurations ??= new Repository<Configuration>(_context);
        public IRepository<DownloadQueueItem> DownloadQueueItems => _downloadQueueItems ??= new Repository<DownloadQueueItem>(_context);
        public ICollectionRepository Collections => _collections ??= new CollectionRepository(_context);
        public IRepository<CollectionVideo> CollectionVideos => _collectionVideos ??= new Repository<CollectionVideo>(_context);
        public IRepository<UserPreference> UserPreferences => _userPreferences ??= new Repository<UserPreference>(_context);
        public IRepository<BackgroundJob> BackgroundJobs => _backgroundJobs ??= new Repository<BackgroundJob>(_context);
        public IRepository<VideoSourceVerification> VideoSourceVerifications => _videoSourceVerifications ??= new Repository<VideoSourceVerification>(_context);
        public IRepository<RecycleBin> RecycleBins => _recycleBins ??= new Repository<RecycleBin>(_context);

        // Metadata cache repositories
        public IRepository<Query> Queries => _queries ??= new Repository<Query>(_context);
        public IRepository<QuerySourceCache> QuerySourceCaches => _querySourceCaches ??= new Repository<QuerySourceCache>(_context);
        public IRepository<QueryResolution> QueryResolutions => _queryResolutions ??= new Repository<QueryResolution>(_context);
        public IRepository<MbArtist> MbArtists => _mbArtists ??= new Repository<MbArtist>(_context);
        public IRepository<MbRecording> MbRecordings => _mbRecordings ??= new Repository<MbRecording>(_context);
        public IRepository<MbRelease> MbReleases => _mbReleases ??= new Repository<MbRelease>(_context);
        public IRepository<MbReleaseGroup> MbReleaseGroups => _mbReleaseGroups ??= new Repository<MbReleaseGroup>(_context);
        public IRepository<MbRecordingCandidate> MbRecordingCandidates => _mbRecordingCandidates ??= new Repository<MbRecordingCandidate>(_context);
        public IRepository<ImvdbArtist> ImvdbArtists => _imvdbArtists ??= new Repository<ImvdbArtist>(_context);
        public IRepository<ImvdbVideo> ImvdbVideos => _imvdbVideos ??= new Repository<ImvdbVideo>(_context);
        public IRepository<ImvdbVideoCandidate> ImvdbVideoCandidates => _imvdbVideoCandidates ??= new Repository<ImvdbVideoCandidate>(_context);
        public IRepository<YtVideo> YtVideos => _ytVideos ??= new Repository<YtVideo>(_context);
        public IRepository<YtVideoCandidate> YtVideoCandidates => _ytVideoCandidates ??= new Repository<YtVideoCandidate>(_context);
        public IRepository<MvLink> MvLinks => _mvLinks ??= new Repository<MvLink>(_context);
        
        // Join table repositories
        public IRepository<MbRecordingArtist> MbRecordingArtists => _mbRecordingArtists ??= new Repository<MbRecordingArtist>(_context);
        public IRepository<MbRecordingRelease> MbRecordingReleases => _mbRecordingReleases ??= new Repository<MbRecordingRelease>(_context);
        public IRepository<MbReleaseToGroup> MbReleaseToGroups => _mbReleaseToGroups ??= new Repository<MbReleaseToGroup>(_context);
        public IRepository<MbTag> MbTags => _mbTags ??= new Repository<MbTag>(_context);
        public IRepository<ImvdbVideoArtist> ImvdbVideoArtists => _imvdbVideoArtists ??= new Repository<ImvdbVideoArtist>(_context);
        public IRepository<ImvdbVideoSource> ImvdbVideoSources => _imvdbVideoSources ??= new Repository<ImvdbVideoSource>(_context);

        public async Task<int> SaveChangesAsync()
        {
            return await _context.SaveChangesAsync();
        }

        public async Task BeginTransactionAsync()
        {
            if (_transaction != null)
            {
                throw new InvalidOperationException("A transaction is already in progress.");
            }

            _transaction = await _context.Database.BeginTransactionAsync();
        }

        public async Task CommitTransactionAsync()
        {
            if (_transaction == null)
            {
                throw new InvalidOperationException("No transaction in progress.");
            }

            try
            {
                await _context.SaveChangesAsync();
                await _transaction.CommitAsync();
            }
            catch
            {
                await RollbackTransactionAsync();
                throw;
            }
            finally
            {
                await _transaction.DisposeAsync();
                _transaction = null;
            }
        }

        public async Task RollbackTransactionAsync()
        {
            if (_transaction == null)
            {
                throw new InvalidOperationException("No transaction in progress.");
            }

            await _transaction.RollbackAsync();
            await _transaction.DisposeAsync();
            _transaction = null;
        }

        protected virtual void Dispose(bool disposing)
        {
            if (!_disposed)
            {
                if (disposing)
                {
                    _transaction?.Dispose();
                    _context.Dispose();
                }
                _disposed = true;
            }
        }

        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
        }
    }
}
