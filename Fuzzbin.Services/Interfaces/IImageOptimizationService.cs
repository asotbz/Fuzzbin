using System.Threading;
using System.Threading.Tasks;

namespace Fuzzbin.Services.Interfaces;

public interface IImageOptimizationService
{
    Task OptimizeImageAsync(string sourcePath, string destinationPath, CancellationToken cancellationToken = default);
    Task OptimizeInPlaceAsync(string imagePath, CancellationToken cancellationToken = default);
}
