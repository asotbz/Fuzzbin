using Fuzzbin.Services.Models;

namespace Fuzzbin.Services.Interfaces;

public interface IDownloadSettingsProvider
{
    DownloadWorkerOptions GetOptions();
    string GetFfmpegPath();
    string GetFfprobePath();
    void Invalidate();
}
