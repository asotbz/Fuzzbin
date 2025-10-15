using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Core.Specifications.Queries;
using Fuzzbin.Services.Interfaces;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace Fuzzbin.Services;

public class TagService : ITagService
{
    private readonly IRepository<Tag> _tagRepository;
    private readonly IRepository<Video> _videoRepository;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<TagService> _logger;

    public TagService(
        IRepository<Tag> tagRepository,
        IRepository<Video> videoRepository,
        IUnitOfWork unitOfWork,
        ILogger<TagService> logger)
    {
        _tagRepository = tagRepository;
        _videoRepository = videoRepository;
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    public async Task<PagedResult<Tag>> GetTagsAsync(
        string? search,
        string? sortBy,
        string? sortDirection,
        int page,
        int pageSize,
        CancellationToken cancellationToken = default)
    {
        var query = _tagRepository.GetQueryable()
            .Include(t => t.Videos)
            .AsQueryable();

        // Apply search filter
        if (!string.IsNullOrWhiteSpace(search))
        {
            var searchLower = search.ToLower();
            query = query.Where(t => t.Name.ToLower().Contains(searchLower));
        }

        // Get total count before paging
        var totalCount = await query.CountAsync(cancellationToken);

        // Apply sorting
        var isDescending = string.Equals(sortDirection, "desc", StringComparison.OrdinalIgnoreCase);
        query = (sortBy?.ToLower()) switch
        {
            "name" => isDescending ? query.OrderByDescending(t => t.Name) : query.OrderBy(t => t.Name),
            "videocount" => isDescending
                ? query.OrderByDescending(t => t.Videos.Count)
                : query.OrderBy(t => t.Videos.Count),
            "createdat" => isDescending ? query.OrderByDescending(t => t.CreatedAt) : query.OrderBy(t => t.CreatedAt),
            _ => query.OrderBy(t => t.Name)
        };

        // Apply paging
        var items = await query
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync(cancellationToken);

        return new PagedResult<Tag>(items, totalCount, page, pageSize);
    }

    public async Task<Tag?> GetTagByIdAsync(Guid id, CancellationToken cancellationToken = default)
    {
        return await _tagRepository.GetByIdAsync(id);
    }

    public async Task<Tag> CreateTagAsync(string name, string? color, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            throw new ArgumentException("Tag name is required", nameof(name));
        }

        // Check for duplicate
        var existing = await _tagRepository.FirstOrDefaultAsync(t => t.Name.ToLower() == name.ToLower());
        if (existing != null)
        {
            throw new InvalidOperationException($"Tag with name '{name}' already exists");
        }

        var tag = new Tag
        {
            Name = name.Trim(),
            Color = color?.Trim()
        };

        await _tagRepository.AddAsync(tag);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Created tag {TagId} with name {TagName}", tag.Id, tag.Name);
        return tag;
    }

    public async Task<Tag> UpdateTagAsync(Tag tag, CancellationToken cancellationToken = default)
    {
        if (tag == null)
        {
            throw new ArgumentNullException(nameof(tag));
        }

        if (string.IsNullOrWhiteSpace(tag.Name))
        {
            throw new ArgumentException("Tag name is required");
        }

        // Check for duplicate name (excluding current tag)
        var existing = await _tagRepository
            .FirstOrDefaultAsync(t => t.Name.ToLower() == tag.Name.ToLower() && t.Id != tag.Id);
        if (existing != null)
        {
            throw new InvalidOperationException($"Tag with name '{tag.Name}' already exists");
        }

        await _tagRepository.UpdateAsync(tag);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Updated tag {TagId}", tag.Id);
        return tag;
    }

    public async Task<Tag> RenameTagAsync(Guid id, string newName, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(newName))
        {
            throw new ArgumentException("Tag name is required", nameof(newName));
        }

        var tag = await _tagRepository.GetByIdAsync(id);
        if (tag == null)
        {
            throw new InvalidOperationException("Tag not found");
        }

        // Check for duplicate name
        var existing = await _tagRepository
            .FirstOrDefaultAsync(t => t.Name.ToLower() == newName.ToLower() && t.Id != id);
        if (existing != null)
        {
            throw new InvalidOperationException($"Tag with name '{newName}' already exists");
        }

        tag.Name = newName.Trim();
        await _tagRepository.UpdateAsync(tag);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Renamed tag {TagId} to {NewName}", id, newName);
        return tag;
    }

    public async Task DeleteTagAsync(Guid id, CancellationToken cancellationToken = default)
    {
        var tag = await _tagRepository.GetByIdAsync(id);
        if (tag == null)
        {
            return;
        }

        // Remove tag associations from videos
        var videos = await _videoRepository
            .GetQueryable()
            .Include(v => v.Tags)
            .Where(v => v.Tags.Any(t => t.Id == id))
            .ToListAsync(cancellationToken);

        foreach (var video in videos)
        {
            video.Tags.Remove(tag);
        }

        await _tagRepository.DeleteAsync(tag);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Deleted tag {TagId} and removed from {VideoCount} videos", id, videos.Count);
    }

    public async Task DeleteTagsAsync(IEnumerable<Guid> ids, CancellationToken cancellationToken = default)
    {
        var idList = ids.ToList();
        if (idList.Count == 0)
        {
            return;
        }

        var tags = await _tagRepository
            .GetQueryable()
            .Where(t => idList.Contains(t.Id))
            .ToListAsync(cancellationToken);

        if (tags.Count == 0)
        {
            return;
        }

        // Remove tag associations from videos
        var videos = await _videoRepository
            .GetQueryable()
            .Include(v => v.Tags)
            .Where(v => v.Tags.Any(t => idList.Contains(t.Id)))
            .ToListAsync(cancellationToken);

        foreach (var video in videos)
        {
            var tagsToRemove = video.Tags.Where(t => idList.Contains(t.Id)).ToList();
            foreach (var tag in tagsToRemove)
            {
                video.Tags.Remove(tag);
            }
        }

        await _tagRepository.DeleteRangeAsync(tags);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Deleted {TagCount} tags and updated {VideoCount} videos", tags.Count, videos.Count);
    }

    public async Task<Dictionary<Guid, int>> GetTagVideoCountsAsync(
        IEnumerable<Guid> tagIds,
        CancellationToken cancellationToken = default)
    {
        var idList = tagIds.ToList();
        if (idList.Count == 0)
        {
            return new Dictionary<Guid, int>();
        }

        var counts = await _tagRepository
            .GetQueryable()
            .Where(t => idList.Contains(t.Id))
            .Select(t => new { t.Id, Count = t.Videos.Count })
            .ToDictionaryAsync(x => x.Id, x => x.Count, cancellationToken);

        return counts;
    }

    public async Task<List<Video>> GetVideosForTagAsync(Guid tagId, int maxCount, CancellationToken cancellationToken = default)
    {
        var videos = await _videoRepository
            .GetQueryable()
            .Include(v => v.Tags)
            .Where(v => v.Tags.Any(t => t.Id == tagId))
            .Take(maxCount)
            .Select(v => new Video
            {
                Id = v.Id,
                Title = v.Title,
                Artist = v.Artist
            })
            .ToListAsync(cancellationToken);

        return videos;
    }
}