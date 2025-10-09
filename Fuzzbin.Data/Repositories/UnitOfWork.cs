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
