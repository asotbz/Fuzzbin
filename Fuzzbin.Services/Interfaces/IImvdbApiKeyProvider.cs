using System.Threading;
using System.Threading.Tasks;

namespace Fuzzbin.Services.Interfaces;

public interface IImvdbApiKeyProvider
{
    Task<string?> GetApiKeyAsync(CancellationToken cancellationToken = default);
}
