using System.Linq.Expressions;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Core.Specifications;
using Fuzzbin.Services;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Tests.Services;

public class ImvdbApiKeyProviderTests
{
    [Fact]
    public async Task ReturnsOptionValueWithoutQueryingRepository()
    {
        var repository = new FakeConfigurationRepository();
        var scopeFactory = BuildScopeFactory(repository);
        using var cache = new MemoryCache(new MemoryCacheOptions());
        var options = Options.Create(new ImvdbOptions { ApiKey = "option-key" });
        IImvdbApiKeyProvider provider = new ImvdbApiKeyProvider(scopeFactory, cache, options, NullLogger<ImvdbApiKeyProvider>.Instance);

        var key = await provider.GetApiKeyAsync();

        Assert.Equal("option-key", key);
        Assert.Equal(0, repository.QueryCount);
    }

    [Fact]
    public async Task ReadsFromRepositoryAndCachesResult()
    {
        var repository = new FakeConfigurationRepository(
            new Configuration
            {
                Key = "ImvdbApiKey",
                Category = "API",
                Value = "db-key",
                IsActive = true
            });

        var scopeFactory = BuildScopeFactory(repository);
        using var cache = new MemoryCache(new MemoryCacheOptions());
        var options = Options.Create(new ImvdbOptions { ApiKey = null });
        IImvdbApiKeyProvider provider = new ImvdbApiKeyProvider(scopeFactory, cache, options, NullLogger<ImvdbApiKeyProvider>.Instance);

        var first = await provider.GetApiKeyAsync();
        var second = await provider.GetApiKeyAsync();

        Assert.Equal("db-key", first);
        Assert.Equal("db-key", second);
        Assert.Equal(1, repository.QueryCount);
    }

    [Fact]
    public async Task ReturnsNullWhenNoKeyIsConfigured()
    {
        var repository = new FakeConfigurationRepository();
        var scopeFactory = BuildScopeFactory(repository);
        using var cache = new MemoryCache(new MemoryCacheOptions());
        var options = Options.Create(new ImvdbOptions());
        IImvdbApiKeyProvider provider = new ImvdbApiKeyProvider(scopeFactory, cache, options, NullLogger<ImvdbApiKeyProvider>.Instance);

        var key = await provider.GetApiKeyAsync();

        Assert.Null(key);
        Assert.Equal(1, repository.QueryCount);
    }

    private static IServiceScopeFactory BuildScopeFactory(FakeConfigurationRepository repository)
    {
        var services = new ServiceCollection();
        services.AddScoped<IUnitOfWork>(_ => new FakeUnitOfWork(repository));
        return services.BuildServiceProvider().GetRequiredService<IServiceScopeFactory>();
    }

    private sealed class FakeUnitOfWork : IUnitOfWork
    {
        private readonly FakeConfigurationRepository _repository;

        public FakeUnitOfWork(FakeConfigurationRepository repository)
        {
            _repository = repository;
        }

        public IRepository<Video> Videos => throw new NotSupportedException();
        public IRepository<Genre> Genres => throw new NotSupportedException();
        public IRepository<Tag> Tags => throw new NotSupportedException();
        public IRepository<FeaturedArtist> FeaturedArtists => throw new NotSupportedException();
        public IRepository<Configuration> Configurations => _repository;
        public IRepository<DownloadQueueItem> DownloadQueueItems => throw new NotSupportedException();
        public ICollectionRepository Collections => throw new NotSupportedException();
        public IRepository<CollectionVideo> CollectionVideos => throw new NotSupportedException();
        public IRepository<UserPreference> UserPreferences => throw new NotSupportedException();

        public Task<int> SaveChangesAsync() => Task.FromResult(0);
        public Task BeginTransactionAsync() => Task.CompletedTask;
        public Task CommitTransactionAsync() => Task.CompletedTask;
        public Task RollbackTransactionAsync() => Task.CompletedTask;
        public void Dispose() { }
    }

    private sealed class FakeConfigurationRepository : IRepository<Configuration>
    {
        private readonly List<Configuration> _configurations;

        public FakeConfigurationRepository(params Configuration[] configurations)
        {
            _configurations = configurations?.ToList() ?? new List<Configuration>();
        }

        public int QueryCount { get; private set; }

        public Task<Configuration?> FirstOrDefaultAsync(Expression<Func<Configuration, bool>> predicate)
        {
            QueryCount++;
            var matcher = predicate.Compile();
            var match = _configurations.FirstOrDefault(matcher);
            return Task.FromResult(match);
        }

        public Task<IEnumerable<Configuration>> GetAllAsync() => Task.FromResult<IEnumerable<Configuration>>(_configurations);
        public Task<IEnumerable<Configuration>> GetAllAsync(bool includeDeleted) => GetAllAsync();
        public Task<IEnumerable<Configuration>> GetAsync(Expression<Func<Configuration, bool>> predicate)
            => Task.FromResult<IEnumerable<Configuration>>(_configurations.Where(predicate.Compile()));

        public IQueryable<Configuration> GetQueryable() => _configurations.AsQueryable();
        public Task<IReadOnlyList<Configuration>> ListAsync(ISpecification<Configuration> specification) => throw new NotSupportedException();
        public Task<Configuration?> FirstOrDefaultAsync(ISpecification<Configuration> specification) => throw new NotSupportedException();
        public Task<int> CountAsync(ISpecification<Configuration> specification) => throw new NotSupportedException();
        public Task<Configuration> AddAsync(Configuration entity)
        {
            _configurations.Add(entity);
            return Task.FromResult(entity);
        }

        public Task<IEnumerable<Configuration>> AddRangeAsync(IEnumerable<Configuration> entities)
        {
            _configurations.AddRange(entities);
            return Task.FromResult(entities);
        }

        public Task UpdateAsync(Configuration entity) => Task.CompletedTask;
        public Task UpdateRangeAsync(IEnumerable<Configuration> entities) => Task.CompletedTask;
        public Task DeleteAsync(Configuration entity)
        {
            _configurations.Remove(entity);
            return Task.CompletedTask;
        }

        public Task DeleteRangeAsync(IEnumerable<Configuration> entities)
        {
            foreach (var entity in entities)
            {
                _configurations.Remove(entity);
            }
            return Task.CompletedTask;
        }

        public Task DeleteByIdAsync(Guid id)
        {
            _configurations.RemoveAll(c => c.Id == id);
            return Task.CompletedTask;
        }

        public Task<bool> ExistsAsync(Expression<Func<Configuration, bool>> predicate)
            => Task.FromResult(_configurations.Any(predicate.Compile()));

        public Task<int> CountAsync(Expression<Func<Configuration, bool>>? predicate = null)
        {
            return Task.FromResult(predicate == null ? _configurations.Count : _configurations.Count(predicate.Compile()));
        }

        public Task<Configuration?> GetByIdAsync(Guid id)
        {
            return Task.FromResult(_configurations.FirstOrDefault(c => c.Id == id));
        }

        public Task<int> SaveChangesAsync() => Task.FromResult(0);
    }
}
