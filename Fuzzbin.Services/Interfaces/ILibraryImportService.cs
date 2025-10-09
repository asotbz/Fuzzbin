using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services.Interfaces
{
    public interface ILibraryImportService
    {
        Task<LibraryImportSession> StartImportAsync(LibraryImportRequest request, CancellationToken cancellationToken = default);
        Task<LibraryImportSession?> GetSessionAsync(Guid sessionId, bool includeItems = false, CancellationToken cancellationToken = default);
        Task<IReadOnlyList<LibraryImportSession>> GetRecentSessionsAsync(int count = 5, CancellationToken cancellationToken = default);
        Task<IReadOnlyList<LibraryImportItem>> GetItemsAsync(Guid sessionId, CancellationToken cancellationToken = default);
        Task UpdateItemDecisionAsync(Guid sessionId, Guid itemId, LibraryImportDecision decision, CancellationToken cancellationToken = default);
        Task<LibraryImportSession> CommitAsync(Guid sessionId, CancellationToken cancellationToken = default);
        Task<LibraryImportSession> RollbackAsync(Guid sessionId, CancellationToken cancellationToken = default);
        Task<LibraryImportSession> RefreshSessionAsync(Guid sessionId, CancellationToken cancellationToken = default);
    }
}
