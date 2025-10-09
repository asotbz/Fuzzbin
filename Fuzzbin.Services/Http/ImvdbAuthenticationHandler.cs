using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services.Http;

/// <summary>
/// Adds the IMVDb API key header to outgoing requests.
/// </summary>
public class ImvdbAuthenticationHandler : DelegatingHandler
{
    private readonly IImvdbApiKeyProvider _apiKeyProvider;
    private readonly ILogger<ImvdbAuthenticationHandler> _logger;

    public ImvdbAuthenticationHandler(IImvdbApiKeyProvider apiKeyProvider, ILogger<ImvdbAuthenticationHandler> logger)
    {
        _apiKeyProvider = apiKeyProvider;
        _logger = logger;
    }

    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        var apiKey = await _apiKeyProvider.GetApiKeyAsync(cancellationToken).ConfigureAwait(false);
        if (!string.IsNullOrWhiteSpace(apiKey))
        {
            if (request.Headers.Contains("IMVDB-APP-KEY"))
            {
                request.Headers.Remove("IMVDB-APP-KEY");
            }

            request.Headers.Add("IMVDB-APP-KEY", apiKey);
        }
        else
        {
            _logger.LogWarning("IMVDb API key is missing; request to {Url} may fail", request.RequestUri);
        }

        return await base.SendAsync(request, cancellationToken).ConfigureAwait(false);
    }
}
