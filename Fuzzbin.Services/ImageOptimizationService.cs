using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.Formats;
using SixLabors.ImageSharp.Formats.Jpeg;
using SixLabors.ImageSharp.Formats.Png;
using SixLabors.ImageSharp.Processing;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services;

public class ImageOptimizationService : IImageOptimizationService
{
    private readonly ILogger<ImageOptimizationService> _logger;
    private const int MaxImageDimension = 1280;

    public ImageOptimizationService(ILogger<ImageOptimizationService> logger)
    {
        _logger = logger;
    }

    public async Task OptimizeImageAsync(string sourcePath, string destinationPath, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(sourcePath))
        {
            throw new ArgumentException("Source path is required", nameof(sourcePath));
        }

        if (!File.Exists(sourcePath))
        {
            _logger.LogWarning("Source image not found for optimization: {SourcePath}", sourcePath);
            return;
        }

        var destinationDirectory = Path.GetDirectoryName(destinationPath);
        if (!string.IsNullOrEmpty(destinationDirectory))
        {
            Directory.CreateDirectory(destinationDirectory);
        }

        try
        {
            await using var sourceStream = File.OpenRead(sourcePath);
            using var image = await Image.LoadAsync(sourceStream, cancellationToken).ConfigureAwait(false);

            ResizeIfNeeded(image);
            StripMetadata(image);

            var encoder = SelectEncoder(destinationPath);
            await using var destinationStream = File.Create(destinationPath);
            await image.SaveAsync(destinationStream, encoder, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to optimize image {SourcePath}", sourcePath);
            if (!File.Exists(destinationPath))
            {
                File.Copy(sourcePath, destinationPath, overwrite: true);
            }
        }
    }

    public async Task OptimizeInPlaceAsync(string imagePath, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(imagePath) || !File.Exists(imagePath))
        {
            return;
        }

        var tempFile = Path.Combine(Path.GetDirectoryName(imagePath)!,
            $"{Path.GetFileNameWithoutExtension(imagePath)}.opt{Path.GetExtension(imagePath)}");

        await OptimizeImageAsync(imagePath, tempFile, cancellationToken).ConfigureAwait(false);

        if (File.Exists(tempFile))
        {
            File.Copy(tempFile, imagePath, overwrite: true);
            File.Delete(tempFile);
        }
    }

    private static void ResizeIfNeeded(Image image)
    {
        if (image.Width <= MaxImageDimension && image.Height <= MaxImageDimension)
        {
            return;
        }

        var resizeOptions = new ResizeOptions
        {
            Mode = ResizeMode.Max,
            Size = new Size(MaxImageDimension, MaxImageDimension)
        };

        image.Mutate(operation => operation.Resize(resizeOptions));
    }

    private static void StripMetadata(Image image)
    {
        if (image.Metadata != null)
        {
            image.Metadata.ExifProfile = null;
            image.Metadata.IptcProfile = null;
            image.Metadata.XmpProfile = null;
        }
    }

    private static IImageEncoder SelectEncoder(string destinationPath)
    {
        var extension = Path.GetExtension(destinationPath)?.ToLowerInvariant();
        return extension switch
        {
            ".png" => new PngEncoder
            {
                CompressionLevel = PngCompressionLevel.Level9,
                TransparentColorMode = PngTransparentColorMode.Preserve
            },
            _ => new JpegEncoder
            {
                Quality = 82
            }
        };
    }
}
