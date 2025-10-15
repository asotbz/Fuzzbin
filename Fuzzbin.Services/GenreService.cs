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

public class GenreService : IGenreService
{
    private readonly IRepository<Genre> _genreRepository;
    private readonly IRepository<Video> _videoRepository;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<GenreService> _logger;

    public GenreService(
        IRepository<Genre> genreRepository,
        IRepository<Video> videoRepository,
        IUnitOfWork unitOfWork,
        ILogger<GenreService> logger)
    {
        _genreRepository = genreRepository;
        _videoRepository = videoRepository;
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    public async Task<PagedResult<Genre>> GetGenresAsync(
        string? search,
        string? sortBy,
        string? sortDirection,
        int page,
        int pageSize,
        CancellationToken cancellationToken = default)
    {
        var query = _genreRepository.GetQueryable()
            .Include(g => g.Videos)
            .AsQueryable();

        // Apply search filter
        if (!string.IsNullOrWhiteSpace(search))
        {
            var searchLower = search.ToLower();
            query = query.Where(g => g.Name.ToLower().Contains(searchLower) ||
                                     (g.Description != null && g.Description.ToLower().Contains(searchLower)));
        }

        // Get total count before paging
        var totalCount = await query.CountAsync(cancellationToken);

        // Apply sorting
        var isDescending = string.Equals(sortDirection, "desc", StringComparison.OrdinalIgnoreCase);
        query = (sortBy?.ToLower()) switch
        {
            "name" => isDescending ? query.OrderByDescending(g => g.Name) : query.OrderBy(g => g.Name),
            "videocount" => isDescending
                ? query.OrderByDescending(g => g.Videos.Count)
                : query.OrderBy(g => g.Videos.Count),
            "createdat" => isDescending ? query.OrderByDescending(g => g.CreatedAt) : query.OrderBy(g => g.CreatedAt),
            _ => query.OrderBy(g => g.Name)
        };

        // Apply paging
        var items = await query
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync(cancellationToken);

        return new PagedResult<Genre>(items, totalCount, page, pageSize);
    }

    public async Task<Genre?> GetGenreByIdAsync(Guid id, CancellationToken cancellationToken = default)
    {
        return await _genreRepository.GetByIdAsync(id);
    }

    public async Task<Genre> CreateGenreAsync(string name, string? description, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            throw new ArgumentException("Genre name is required", nameof(name));
        }

        // Check for duplicate
        var existing = await _genreRepository.FirstOrDefaultAsync(g => g.Name.ToLower() == name.ToLower());
        if (existing != null)
        {
            throw new InvalidOperationException($"Genre with name '{name}' already exists");
        }

        var genre = new Genre
        {
            Name = name.Trim(),
            Description = description?.Trim()
        };

        await _genreRepository.AddAsync(genre);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Created genre {GenreId} with name {GenreName}", genre.Id, genre.Name);
        return genre;
    }

    public async Task<Genre> UpdateGenreAsync(Genre genre, CancellationToken cancellationToken = default)
    {
        if (genre == null)
        {
            throw new ArgumentNullException(nameof(genre));
        }

        if (string.IsNullOrWhiteSpace(genre.Name))
        {
            throw new ArgumentException("Genre name is required");
        }

        // Check for duplicate name (excluding current genre)
        var existing = await _genreRepository
            .FirstOrDefaultAsync(g => g.Name.ToLower() == genre.Name.ToLower() && g.Id != genre.Id);
        if (existing != null)
        {
            throw new InvalidOperationException($"Genre with name '{genre.Name}' already exists");
        }

        await _genreRepository.UpdateAsync(genre);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Updated genre {GenreId}", genre.Id);
        return genre;
    }

    public async Task DeleteGenreAsync(Guid id, CancellationToken cancellationToken = default)
    {
        var genre = await _genreRepository.GetByIdAsync(id);
        if (genre == null)
        {
            return;
        }

        // Remove genre associations from videos
        var videos = await _videoRepository
            .GetQueryable()
            .Include(v => v.Genres)
            .Where(v => v.Genres.Any(g => g.Id == id))
            .ToListAsync(cancellationToken);

        foreach (var video in videos)
        {
            video.Genres.Remove(genre);
        }

        await _genreRepository.DeleteAsync(genre);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Deleted genre {GenreId} and removed from {VideoCount} videos", id, videos.Count);
    }

    public async Task DeleteGenresAsync(IEnumerable<Guid> ids, CancellationToken cancellationToken = default)
    {
        var idList = ids.ToList();
        if (idList.Count == 0)
        {
            return;
        }

        var genres = await _genreRepository
            .GetQueryable()
            .Where(g => idList.Contains(g.Id))
            .ToListAsync(cancellationToken);

        if (genres.Count == 0)
        {
            return;
        }

        // Remove genre associations from videos
        var videos = await _videoRepository
            .GetQueryable()
            .Include(v => v.Genres)
            .Where(v => v.Genres.Any(g => idList.Contains(g.Id)))
            .ToListAsync(cancellationToken);

        foreach (var video in videos)
        {
            var genresToRemove = video.Genres.Where(g => idList.Contains(g.Id)).ToList();
            foreach (var genre in genresToRemove)
            {
                video.Genres.Remove(genre);
            }
        }

        await _genreRepository.DeleteRangeAsync(genres);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Deleted {GenreCount} genres and updated {VideoCount} videos", genres.Count, videos.Count);
    }

    public async Task<Dictionary<Guid, int>> GetGenreVideoCountsAsync(
        IEnumerable<Guid> genreIds,
        CancellationToken cancellationToken = default)
    {
        var idList = genreIds.ToList();
        if (idList.Count == 0)
        {
            return new Dictionary<Guid, int>();
        }

        var counts = await _genreRepository
            .GetQueryable()
            .Where(g => idList.Contains(g.Id))
            .Select(g => new { g.Id, Count = g.Videos.Count })
            .ToDictionaryAsync(x => x.Id, x => x.Count, cancellationToken);

        return counts;
    }

    public async Task GeneralizeGenresAsync(
        IEnumerable<Guid> sourceGenreIds,
        Guid targetGenreId,
        CancellationToken cancellationToken = default)
    {
        var sourceIds = sourceGenreIds.Where(id => id != targetGenreId).Distinct().ToList();
        if (sourceIds.Count == 0)
        {
            return;
        }

        var targetGenre = await _genreRepository
            .GetQueryable()
            .Include(g => g.Videos)
            .FirstOrDefaultAsync(g => g.Id == targetGenreId, cancellationToken);

        if (targetGenre == null)
        {
            throw new InvalidOperationException("Target genre not found");
        }

        // Get all videos that have any of the source genres
        var videos = await _videoRepository
            .GetQueryable()
            .Include(v => v.Genres)
            .Where(v => v.Genres.Any(g => sourceIds.Contains(g.Id)))
            .ToListAsync(cancellationToken);

        // Replace source genres with target genre
        foreach (var video in videos)
        {
            var videoSourceGenres = video.Genres.Where(g => sourceIds.Contains(g.Id)).ToList();
            foreach (var sourceGenre in videoSourceGenres)
            {
                video.Genres.Remove(sourceGenre);
            }

            // Add target genre if not already present
            if (!video.Genres.Any(g => g.Id == targetGenreId))
            {
                video.Genres.Add(targetGenre);
            }
        }

        // Delete source genres
        var sourceGenresToDelete = await _genreRepository
            .GetQueryable()
            .Where(g => sourceIds.Contains(g.Id))
            .ToListAsync(cancellationToken);

        await _genreRepository.DeleteRangeAsync(sourceGenresToDelete);
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation(
            "Generalized {SourceCount} genres to {TargetGenreName}, updated {VideoCount} videos",
            sourceIds.Count,
            targetGenre.Name,
            videos.Count);
    }
}