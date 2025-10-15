using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Specifications.Queries;

namespace Fuzzbin.Services.Interfaces;

public interface IGenreService
{
    Task<PagedResult<Genre>> GetGenresAsync(string? search, string? sortBy, string? sortDirection, int page, int pageSize, CancellationToken cancellationToken = default);
    Task<Genre?> GetGenreByIdAsync(Guid id, CancellationToken cancellationToken = default);
    Task<Genre> CreateGenreAsync(string name, string? description, CancellationToken cancellationToken = default);
    Task<Genre> UpdateGenreAsync(Genre genre, CancellationToken cancellationToken = default);
    Task DeleteGenreAsync(Guid id, CancellationToken cancellationToken = default);
    Task DeleteGenresAsync(IEnumerable<Guid> ids, CancellationToken cancellationToken = default);
    Task<Dictionary<Guid, int>> GetGenreVideoCountsAsync(IEnumerable<Guid> genreIds, CancellationToken cancellationToken = default);
    Task GeneralizeGenresAsync(IEnumerable<Guid> sourceGenreIds, Guid targetGenreId, CancellationToken cancellationToken = default);
}