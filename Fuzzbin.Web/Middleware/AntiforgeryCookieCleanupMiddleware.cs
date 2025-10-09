using Microsoft.AspNetCore.Antiforgery;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Http.Extensions;
using Microsoft.Extensions.Logging;
using Fuzzbin.Web.Security;

namespace Fuzzbin.Web.Middleware
{
    /// <summary>
    /// Clears stale antiforgery cookies when the key ring changes (e.g. first run).
    /// </summary>
    public class AntiforgeryCookieCleanupMiddleware
    {
        private readonly RequestDelegate _next;
        private readonly ILogger<AntiforgeryCookieCleanupMiddleware> _logger;

        public AntiforgeryCookieCleanupMiddleware(RequestDelegate next, ILogger<AntiforgeryCookieCleanupMiddleware> logger)
        {
            _next = next;
            _logger = logger;
        }

        public async Task InvokeAsync(HttpContext context)
        {
            try
            {
                await _next(context);
            }
            catch (AntiforgeryValidationException ex)
            {
                _logger.LogWarning(ex, "Antiforgery token validation failed. Clearing cookie and retrying request.");

                context.Response.Cookies.Delete(AntiforgeryDefaults.CookieName);

                if (context.Response.HasStarted)
                {
                    _logger.LogWarning("Response already started. Unable to recover from antiforgery failure gracefully.");
                    throw;
                }

                if (HttpMethods.IsGet(context.Request.Method) || HttpMethods.IsHead(context.Request.Method))
                {
                    var redirectTarget = UriHelper.BuildRelative(context.Request.PathBase, context.Request.Path, context.Request.QueryString);
                    context.Response.Redirect(string.IsNullOrEmpty(redirectTarget) ? "/" : redirectTarget);
                    return;
                }
                else
                {
                    context.Response.StatusCode = StatusCodes.Status400BadRequest;
                    await context.Response.WriteAsync("Invalid antiforgery token. Please reload the page and try again.");
                    return;
                }
            }
        }
    }
}
