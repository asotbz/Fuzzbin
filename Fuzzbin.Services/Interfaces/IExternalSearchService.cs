using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services.Interfaces;

public interface IExternalSearchService
{
    Task<ExternalSearchResult> SearchAsync(ExternalSearchQuery query, CancellationToken cancellationToken = default);
}
