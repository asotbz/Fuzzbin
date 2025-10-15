using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Specifications.Queries;

namespace Fuzzbin.Services.Interfaces;

public interface ITagService
{
    Task<PagedResult<Tag>> GetTagsAsync(string? search, string? sortBy, string? sortDirection, int page, int pageSize, CancellationToken cancellationToken = default);
    Task<Tag?> GetTagByIdAsync(Guid id, CancellationToken cancellationToken = default);
    Task<Tag> CreateTagAsync(string name, string? color, CancellationToken cancellationToken = default);
    Task<Tag> UpdateTagAsync(Tag tag, CancellationToken cancellationToken = default);
    Task<Tag> RenameTagAsync(Guid id, string newName, CancellationToken cancellationToken = default);
    Task DeleteTagAsync(Guid id, CancellationToken cancellationToken = default);
    Task DeleteTagsAsync(IEnumerable<Guid> ids, CancellationToken cancellationToken = default);
    Task<Dictionary<Guid, int>> GetTagVideoCountsAsync(IEnumerable<Guid> tagIds, CancellationToken cancellationToken = default);
    Task<List<Video>> GetVideosForTagAsync(Guid tagId, int maxCount, CancellationToken cancellationToken = default);
}