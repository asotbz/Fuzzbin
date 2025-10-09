using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using FuzzySharp;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Core.Specifications.LibraryImport;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services
{
    public class LibraryImportService : ILibraryImportService
    {
        private static readonly Regex FilenameYearRegex = new("(?<!\\d)(19|20)\\d{2}(?!\\d)", RegexOptions.Compiled);
        private static readonly Regex CleanupRegex = new("[\\s._]+", RegexOptions.Compiled);
        private static readonly Regex NonAlphanumericRegex = new("[^a-z0-9]+", RegexOptions.Compiled);
        private static readonly string[] FallbackExtensions = { ".mp4", ".mkv", ".mov", ".avi", ".webm" };

        private readonly ILogger<LibraryImportService> _logger;
        private readonly IRepository<LibraryImportSession> _sessionRepository;
        private readonly IRepository<LibraryImportItem> _itemRepository;
        private readonly IRepository<Video> _videoRepository;
        private readonly IUnitOfWork _unitOfWork;
        private readonly IMetadataService _metadataService;
        private readonly ILibraryPathManager _libraryPathManager;

        public LibraryImportService(
            ILogger<LibraryImportService> logger,
            IRepository<LibraryImportSession> sessionRepository,
            IRepository<LibraryImportItem> itemRepository,
            IRepository<Video> videoRepository,
            IUnitOfWork unitOfWork,
            IMetadataService metadataService,
            ILibraryPathManager libraryPathManager)
        {
            _logger = logger;
            _sessionRepository = sessionRepository;
            _itemRepository = itemRepository;
            _videoRepository = videoRepository;
            _unitOfWork = unitOfWork;
            _metadataService = metadataService;
            _libraryPathManager = libraryPathManager;
        }

        public async Task<LibraryImportSession> StartImportAsync(LibraryImportRequest request, CancellationToken cancellationToken = default)
        {
            if (request == null)
            {
                throw new ArgumentNullException(nameof(request));
            }

            var rootPath = request.RootPath;
            if (string.IsNullOrWhiteSpace(rootPath))
            {
                rootPath = await _libraryPathManager.GetLibraryRootAsync(cancellationToken).ConfigureAwait(false);
            }

            if (string.IsNullOrWhiteSpace(rootPath) || !Directory.Exists(rootPath))
            {
                throw new DirectoryNotFoundException($"Library root path '{rootPath}' could not be resolved.");
            }

            var searchOption = request.IncludeSubdirectories ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly;
            var extensionSource = request.AllowedExtensions != null && request.AllowedExtensions.Count > 0
                ? request.AllowedExtensions
                : FallbackExtensions;
            var allowedExtensions = new HashSet<string>(extensionSource
                .Select(ext => NormalizeExtension(ext)), StringComparer.OrdinalIgnoreCase);

            var session = new LibraryImportSession
            {
                RootPath = rootPath,
                StartedByUserId = request.StartedByUserId,
                Status = LibraryImportStatus.Scanning,
                StartedAt = DateTime.UtcNow
            };

            await _sessionRepository.AddAsync(session).ConfigureAwait(false);
            await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);

            var existingVideos = (await _videoRepository.GetAllAsync().ConfigureAwait(false)).ToList();
            var existingVideoIndex = existingVideos.Select(video => new VideoMatchCandidate
            {
                Video = video,
                Key = BuildSearchKey(video.Artist, video.Title)
            }).ToList();

            var sessionHashes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var sessionPaths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            var importItems = new List<LibraryImportItem>();
            var files = Directory.EnumerateFiles(rootPath, "*.*", searchOption)
                .Where(path => allowedExtensions.Contains(NormalizeExtension(Path.GetExtension(path))))
                .ToList();

            foreach (var filePath in files)
            {
                cancellationToken.ThrowIfCancellationRequested();

                try
                {
                    var relativePath = Path.GetRelativePath(rootPath, filePath);
                    var item = await BuildImportItemAsync(
                        session,
                        filePath,
                        relativePath,
                        request,
                        existingVideoIndex,
                        existingVideos,
                        sessionHashes,
                        sessionPaths,
                        cancellationToken).ConfigureAwait(false);

                    importItems.Add(item);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to process file {FilePath} during import session {SessionId}", filePath, session.Id);
                }
            }

            if (importItems.Count > 0)
            {
                await _itemRepository.AddRangeAsync(importItems).ConfigureAwait(false);
            }

            session.Status = LibraryImportStatus.ReadyForReview;
            session.Items = importItems;
            await _sessionRepository.UpdateAsync(session).ConfigureAwait(false);
            await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);

            _logger.LogInformation("Library import session {SessionId} scanned {Count} files", session.Id, importItems.Count);

            return session;
        }

        public async Task<LibraryImportSession?> GetSessionAsync(Guid sessionId, bool includeItems = false, CancellationToken cancellationToken = default)
        {
            if (includeItems)
            {
                var specification = new LibraryImportSessionWithItemsSpecification(sessionId);
                return await _sessionRepository.FirstOrDefaultAsync(specification).ConfigureAwait(false);
            }

            return await _sessionRepository.GetByIdAsync(sessionId).ConfigureAwait(false);
        }

        public async Task<IReadOnlyList<LibraryImportSession>> GetRecentSessionsAsync(int count = 5, CancellationToken cancellationToken = default)
        {
            var queryable = _sessionRepository.GetQueryable()
                .OrderByDescending(s => s.StartedAt)
                .Take(Math.Max(1, count));

            return await queryable.ToListAsync(cancellationToken).ConfigureAwait(false);
        }

        public async Task<IReadOnlyList<LibraryImportItem>> GetItemsAsync(Guid sessionId, CancellationToken cancellationToken = default)
        {
            var items = await _itemRepository.GetAsync(item => item.SessionId == sessionId).ConfigureAwait(false);
            return items.OrderBy(item => item.FileName).ToList();
        }

        public async Task UpdateItemDecisionAsync(Guid sessionId, Guid itemId, LibraryImportDecision decision, CancellationToken cancellationToken = default)
        {
            if (decision == null)
            {
                throw new ArgumentNullException(nameof(decision));
            }

            var item = await _itemRepository.GetByIdAsync(itemId).ConfigureAwait(false);
            if (item == null || item.SessionId != sessionId)
            {
                throw new InvalidOperationException("Import item could not be found for the specified session.");
            }

            switch (decision.DecisionType)
            {
                case LibraryImportDecisionType.Approve:
                    item.Status = LibraryImportItemStatus.Approved;
                    item.ManualVideoId = decision.ManualVideoId;
                    break;
                case LibraryImportDecisionType.Reject:
                    item.Status = LibraryImportItemStatus.Rejected;
                    item.ManualVideoId = null;
                    break;
                case LibraryImportDecisionType.NeedsAttention:
                    item.Status = LibraryImportItemStatus.NeedsAttention;
                    break;
            }

            item.Notes = decision.Notes;
            item.ReviewedAt = DateTime.UtcNow;

            await _itemRepository.UpdateAsync(item).ConfigureAwait(false);
            await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);
        }

        public async Task<LibraryImportSession> CommitAsync(Guid sessionId, CancellationToken cancellationToken = default)
        {
            var session = await GetSessionAsync(sessionId, includeItems: true, cancellationToken).ConfigureAwait(false);
            if (session == null)
            {
                throw new InvalidOperationException("Import session could not be located.");
            }

            if (session.Status == LibraryImportStatus.Completed)
            {
                return session;
            }

            session.Status = LibraryImportStatus.Committing;
            await _sessionRepository.UpdateAsync(session).ConfigureAwait(false);
            await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);

            var createdVideoIds = new List<Guid>();

            foreach (var item in session.Items.Where(i => i.Status == LibraryImportItemStatus.Approved))
            {
                cancellationToken.ThrowIfCancellationRequested();

                try
                {
                    var video = await ResolveTargetVideoAsync(item, cancellationToken).ConfigureAwait(false);
                    if (video == null)
                    {
                        video = new Video
                        {
                            Title = item.Title ?? item.FileName,
                            Artist = item.Artist ?? "Unknown Artist"
                        };

                        await _videoRepository.AddAsync(video).ConfigureAwait(false);
                        createdVideoIds.Add(video.Id);
                    }

                    ApplyImportMetadata(video, session, item);
                    await _videoRepository.UpdateAsync(video).ConfigureAwait(false);

                    item.IsCommitted = true;
                    item.ReviewedAt = DateTime.UtcNow;
                    await _itemRepository.UpdateAsync(item).ConfigureAwait(false);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to commit import item {ItemId} in session {SessionId}", item.Id, session.Id);
                    item.Status = LibraryImportItemStatus.NeedsAttention;
                    item.Notes = AppendNote(item.Notes, $"Commit error: {ex.Message}");
                    await _itemRepository.UpdateAsync(item).ConfigureAwait(false);
                }
            }

            session.CreatedVideoIdsJson = JsonSerializer.Serialize(createdVideoIds);
            session.MarkCompleted(LibraryImportStatus.Completed);

            await _sessionRepository.UpdateAsync(session).ConfigureAwait(false);
            await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);

            _logger.LogInformation("Import session {SessionId} committed {Count} videos", session.Id, createdVideoIds.Count);

            return session;
        }

        public async Task<LibraryImportSession> RollbackAsync(Guid sessionId, CancellationToken cancellationToken = default)
        {
            var session = await GetSessionAsync(sessionId, includeItems: true, cancellationToken).ConfigureAwait(false);
            if (session == null)
            {
                throw new InvalidOperationException("Import session could not be located.");
            }

            var createdVideoIds = DeserializeCreatedIds(session.CreatedVideoIdsJson);
            foreach (var videoId in createdVideoIds)
            {
                cancellationToken.ThrowIfCancellationRequested();

                var video = await _videoRepository.GetByIdAsync(videoId).ConfigureAwait(false);
                if (video != null)
                {
                    await _videoRepository.DeleteAsync(video).ConfigureAwait(false);
                }
            }

            foreach (var item in session.Items)
            {
                item.IsCommitted = false;
                await _itemRepository.UpdateAsync(item).ConfigureAwait(false);
            }

            session.MarkCompleted(LibraryImportStatus.RolledBack);
            await _sessionRepository.UpdateAsync(session).ConfigureAwait(false);
            await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);

            _logger.LogInformation("Import session {SessionId} rolled back {Count} videos", session.Id, createdVideoIds.Count);

            return session;
        }

        public async Task<LibraryImportSession> RefreshSessionAsync(Guid sessionId, CancellationToken cancellationToken = default)
        {
            var session = await GetSessionAsync(sessionId, includeItems: true, cancellationToken).ConfigureAwait(false);
            if (session == null)
            {
                throw new InvalidOperationException("Import session could not be located.");
            }

            var summary = LibraryImportSummary.FromItems(session.Items);
            session.Notes = $"Pending: {summary.PendingReview}, Approved: {summary.Approved}, Duplicates: {summary.PotentialDuplicates + summary.ConfirmedDuplicates}";
            await _sessionRepository.UpdateAsync(session).ConfigureAwait(false);
            await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);
            return session;
        }

        private async Task<LibraryImportItem> BuildImportItemAsync(
            LibraryImportSession session,
            string filePath,
            string relativePath,
            LibraryImportRequest request,
            List<VideoMatchCandidate> existingVideoIndex,
            List<Video> existingVideos,
            HashSet<string> sessionHashes,
            HashSet<string> sessionPaths,
            CancellationToken cancellationToken)
        {
            var fileInfo = new FileInfo(filePath);
            var item = new LibraryImportItem
            {
                SessionId = session.Id,
                FilePath = filePath,
                RelativePath = relativePath,
                FileName = fileInfo.Name,
                Extension = fileInfo.Extension,
                FileSize = fileInfo.Exists ? fileInfo.Length : 0,
                Status = LibraryImportItemStatus.PendingReview
            };

            if (request.ComputeHashes && fileInfo.Exists)
            {
                item.FileHash = await ComputeHashAsync(filePath, cancellationToken).ConfigureAwait(false);
                if (!string.IsNullOrEmpty(item.FileHash))
                {
                    if (!sessionHashes.Add(item.FileHash))
                    {
                        item.DuplicateStatus = LibraryImportDuplicateStatus.ConfirmedDuplicate;
                        item.Notes = AppendNote(item.Notes, "Duplicate detected in current session (matching hash)");
                    }
                }
            }

            if (!string.IsNullOrEmpty(relativePath))
            {
                var normalized = NormalizePath(relativePath);
                if (!sessionPaths.Add(normalized))
                {
                    item.DuplicateStatus = LibraryImportDuplicateStatus.PotentialDuplicate;
                    item.Notes = AppendNote(item.Notes, "Duplicate detected in current session (matching relative path)");
                }
            }

            var metadata = request.RefreshMetadata ? await TryExtractMetadataAsync(filePath, cancellationToken).ConfigureAwait(false) : null;
            if (metadata != null)
            {
                item.DurationSeconds = metadata.Duration?.TotalSeconds;
                item.Resolution = metadata.Width.HasValue && metadata.Height.HasValue
                    ? $"{metadata.Width.Value}x{metadata.Height.Value}"
                    : null;
                item.VideoCodec = metadata.VideoCodec;
                item.AudioCodec = metadata.AudioCodec;
                item.FrameRate = metadata.FrameRate;
                item.BitrateKbps = metadata.VideoBitrate.HasValue ? (int?)(metadata.VideoBitrate.Value / 1000) : null;
                item.Title = metadata.Title;
                item.Artist = metadata.Artist;
                item.Album = metadata.Album;
                item.Year = metadata.ReleaseDate?.Year;
            }

            if (string.IsNullOrWhiteSpace(item.Title) || string.IsNullOrWhiteSpace(item.Artist))
            {
                var inferred = InferFromFilename(fileInfo.Name);
                item.Artist ??= inferred.Artist;
                item.Title ??= inferred.Title;
                item.Year ??= inferred.Year;
            }

            var searchKey = BuildSearchKey(item.Artist, item.Title);
            if (!string.IsNullOrWhiteSpace(searchKey))
            {
                var matches = BuildMatchCandidates(searchKey, existingVideoIndex);
                item.CandidateMatchesJson = LibraryImportMatchCandidate.SerializeList(matches);

                if (matches.Count > 0)
                {
                    item.SuggestedVideoId = matches[0].VideoId;
                    item.Confidence = matches[0].Confidence;
                }

                var duplicate = EvaluateDuplicate(item, matches, existingVideos);
                if (duplicate != null)
                {
                    item.DuplicateStatus = duplicate.Value.Status;
                    item.DuplicateVideoId = duplicate.Value.VideoId;
                }
            }

            return item;
        }

        private async Task<Video?> ResolveTargetVideoAsync(LibraryImportItem item, CancellationToken cancellationToken)
        {
            if (item.ManualVideoId.HasValue)
            {
                return await _videoRepository.GetByIdAsync(item.ManualVideoId.Value).ConfigureAwait(false);
            }

            if (item.SuggestedVideoId.HasValue && item.Confidence.HasValue && item.Confidence.Value >= 0.9)
            {
                return await _videoRepository.GetByIdAsync(item.SuggestedVideoId.Value).ConfigureAwait(false);
            }

            if (item.DuplicateStatus == LibraryImportDuplicateStatus.ConfirmedDuplicate && item.DuplicateVideoId.HasValue)
            {
                return await _videoRepository.GetByIdAsync(item.DuplicateVideoId.Value).ConfigureAwait(false);
            }

            return null;
        }

        private void ApplyImportMetadata(Video video, LibraryImportSession session, LibraryImportItem item)
        {
            video.Title = string.IsNullOrWhiteSpace(item.Title) ? video.Title : item.Title;
            video.Artist = string.IsNullOrWhiteSpace(item.Artist) ? video.Artist : item.Artist;
            video.Album = item.Album ?? video.Album;
            video.Year = item.Year ?? video.Year;
            video.Duration = item.DurationSeconds.HasValue ? (int?)Math.Round(item.DurationSeconds.Value) : video.Duration;
            video.FilePath = item.RelativePath ?? item.FilePath;
            video.FileSize = item.FileSize;
            video.FileHash = item.FileHash ?? video.FileHash;
            video.VideoCodec = item.VideoCodec ?? video.VideoCodec;
            video.AudioCodec = item.AudioCodec ?? video.AudioCodec;
            video.Bitrate = item.BitrateKbps ?? video.Bitrate;
            video.FrameRate = item.FrameRate ?? video.FrameRate;
            video.Resolution = item.Resolution ?? video.Resolution;
            video.ImportedAt ??= DateTime.UtcNow;
        }

        private static string NormalizePath(string path)
        {
            return path
                .Replace('\n', ' ')
                .Replace('\r', ' ')
                .Replace('\t', ' ')
                .Replace('\\', '/')
                .Trim()
                .Trim('/')
                .ToLowerInvariant();
        }

        private static string AppendNote(string? existing, string note)
        {
            if (string.IsNullOrWhiteSpace(existing))
            {
                return note;
            }

            return $"{existing} | {note}";
        }

        private static List<Guid> DeserializeCreatedIds(string? json)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                return new List<Guid>();
            }

            try
            {
                var ids = JsonSerializer.Deserialize<List<Guid>>(json);
                return ids ?? new List<Guid>();
            }
            catch
            {
                return new List<Guid>();
            }
        }

        private async Task<VideoMetadata?> TryExtractMetadataAsync(string filePath, CancellationToken cancellationToken)
        {
            try
            {
                return await _metadataService.ExtractMetadataAsync(filePath, cancellationToken).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Metadata extraction failed for {FilePath}", filePath);
                return null;
            }
        }

        private static string BuildSearchKey(string? artist, string? title)
        {
            var parts = new List<string>();
            if (!string.IsNullOrWhiteSpace(artist))
            {
                parts.Add(artist);
            }
            if (!string.IsNullOrWhiteSpace(title))
            {
                parts.Add(title);
            }

            if (parts.Count == 0)
            {
                return string.Empty;
            }

            var combined = string.Join(" ", parts.Select(p => p.ToLowerInvariant()));
            var cleaned = NonAlphanumericRegex.Replace(combined, " ");
            cleaned = CleanupRegex.Replace(cleaned, " ");
            return cleaned.Trim();
        }

        private static (string? Artist, string? Title, int? Year) InferFromFilename(string fileName)
        {
            var nameWithoutExt = Path.GetFileNameWithoutExtension(fileName);
            var normalized = nameWithoutExt.Replace('_', ' ');

            int? year = null;
            var yearMatch = FilenameYearRegex.Match(normalized);
            if (yearMatch.Success && int.TryParse(yearMatch.Value, out var parsedYear))
            {
                year = parsedYear;
                normalized = normalized.Replace(yearMatch.Value, string.Empty, StringComparison.OrdinalIgnoreCase);
            }

            var separators = new[] { " - ", " – ", " — " };
            foreach (var separator in separators)
            {
                var parts = normalized.Split(separator, StringSplitOptions.TrimEntries);
                if (parts.Length >= 2)
                {
                    return (parts[0], string.Join(" - ", parts.Skip(1)), year);
                }
            }

            return (null, normalized, year);
        }

        private IReadOnlyList<LibraryImportMatchCandidate> BuildMatchCandidates(
            string searchKey,
            List<VideoMatchCandidate> existingVideos,
            int limit = 5)
        {
            if (existingVideos.Count == 0 || string.IsNullOrWhiteSpace(searchKey))
            {
                return Array.Empty<LibraryImportMatchCandidate>();
            }

            var scored = existingVideos
                .Select(candidate => new
                {
                    Candidate = candidate,
                    Score = Fuzz.WeightedRatio(searchKey, candidate.Key)
                })
                .Where(entry => entry.Score > 0)
                .OrderByDescending(entry => entry.Score)
                .Take(Math.Max(1, limit))
                .ToList();

            return scored
                .Select(entry => new LibraryImportMatchCandidate
                {
                    VideoId = entry.Candidate.Video.Id,
                    DisplayName = $"{entry.Candidate.Video.Artist} - {entry.Candidate.Video.Title}",
                    Confidence = Math.Round(entry.Score / 100.0, 4),
                    Notes = BuildMatchNotes(entry.Candidate.Video)
                })
                .ToList();
        }

        private static string? BuildMatchNotes(Video video)
        {
            var parts = new List<string>();
            if (video.Year.HasValue)
            {
                parts.Add(video.Year.Value.ToString(CultureInfo.InvariantCulture));
            }

            if (!string.IsNullOrWhiteSpace(video.Resolution))
            {
                parts.Add(video.Resolution);
            }

            if (video.Duration.HasValue)
            {
                parts.Add($"{video.Duration.Value / 60}m");
            }

            return parts.Count == 0 ? null : string.Join(" · ", parts);
        }

        private (LibraryImportDuplicateStatus Status, Guid VideoId)? EvaluateDuplicate(
            LibraryImportItem item,
            IReadOnlyList<LibraryImportMatchCandidate> matches,
            List<Video> existingVideos)
        {
            if (!string.IsNullOrEmpty(item.FileHash))
            {
                var hashMatch = existingVideos.FirstOrDefault(v => !string.IsNullOrEmpty(v.FileHash) && string.Equals(v.FileHash, item.FileHash, StringComparison.OrdinalIgnoreCase));
                if (hashMatch != null)
                {
                    return (LibraryImportDuplicateStatus.ConfirmedDuplicate, hashMatch.Id);
                }
            }

            if (!string.IsNullOrEmpty(item.RelativePath))
            {
                var normalizedItemPath = NormalizePath(item.RelativePath);
                var pathMatch = existingVideos.FirstOrDefault(v => string.Equals(NormalizePath(v.FilePath ?? string.Empty), normalizedItemPath, StringComparison.OrdinalIgnoreCase));
                if (pathMatch != null)
                {
                    return (LibraryImportDuplicateStatus.ConfirmedDuplicate, pathMatch.Id);
                }
            }

            if (matches.Count > 0 && matches[0].Confidence >= 0.9 && item.DurationSeconds.HasValue)
            {
                var video = existingVideos.FirstOrDefault(v => v.Id == matches[0].VideoId);
                if (video != null && video.Duration.HasValue)
                {
                    var durationDelta = Math.Abs(video.Duration.Value - item.DurationSeconds.Value);
                    if (durationDelta <= 3)
                    {
                        return (LibraryImportDuplicateStatus.PotentialDuplicate, video.Id);
                    }
                }
            }

            return null;
        }

        private static async Task<string?> ComputeHashAsync(string filePath, CancellationToken cancellationToken)
        {
            try
            {
                await using var stream = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.Read, bufferSize: 1 << 20, useAsync: true);
                using var sha256 = SHA256.Create();

                var buffer = new byte[8192];
                int bytesRead;
                while ((bytesRead = await stream.ReadAsync(buffer, 0, buffer.Length, cancellationToken).ConfigureAwait(false)) > 0)
                {
                    sha256.TransformBlock(buffer, 0, bytesRead, null, 0);
                }

                sha256.TransformFinalBlock(Array.Empty<byte>(), 0, 0);
                return BitConverter.ToString(sha256.Hash ?? Array.Empty<byte>()).Replace("-", string.Empty).ToLowerInvariant();
            }
            catch (Exception)
            {
                return null;
            }
        }

        private sealed class VideoMatchCandidate
        {
            public required Video Video { get; init; }
            public required string Key { get; init; }
        }

        private static string NormalizeExtension(string extension)
        {
            if (string.IsNullOrWhiteSpace(extension))
            {
                return string.Empty;
            }

            var trimmed = extension.Trim();
            if (!trimmed.StartsWith('.'))
            {
                trimmed = $".{trimmed}";
            }

            return trimmed.ToLowerInvariant();
        }
    }
}
