using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services.Interfaces;

public interface IMetricsService
{
    Task<SystemMetrics> CaptureAsync(CancellationToken cancellationToken = default);
}
