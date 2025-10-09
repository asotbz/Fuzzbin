using Fuzzbin.Core.Interfaces;

namespace Fuzzbin.Web.Middleware
{
    public class SetupCheckMiddleware
    {
        private readonly RequestDelegate _next;
        private readonly ILogger<SetupCheckMiddleware> _logger;

        public SetupCheckMiddleware(RequestDelegate next, ILogger<SetupCheckMiddleware> logger)
        {
            _next = next;
            _logger = logger;
        }

        public async Task InvokeAsync(HttpContext context, IServiceProvider serviceProvider)
        {
            // Skip check for setup page, static files, and health endpoints
            var path = context.Request.Path.Value?.ToLower() ?? "";
            if (path == "/setup" || 
                path.StartsWith("/_") || 
                path.StartsWith("/css") || 
                path.StartsWith("/js") || 
                path.StartsWith("/health") ||
                path.Contains(".css") ||
                path.Contains(".js"))
            {
                await _next(context);
                return;
            }

            // Check if setup is complete
            using (var scope = serviceProvider.CreateScope())
            {
                var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();
                var setupComplete = await unitOfWork.Configurations
                    .FirstOrDefaultAsync(c => c.Key == "SetupComplete" && c.Category == "System");

                if (setupComplete?.Value != "true")
                {
                    _logger.LogInformation("Setup not complete, redirecting to /setup");
                    context.Response.Redirect("/setup");
                    return;
                }
            }

            await _next(context);
        }
    }

    public static class SetupCheckMiddlewareExtensions
    {
        public static IApplicationBuilder UseSetupCheck(this IApplicationBuilder builder)
        {
            return builder.UseMiddleware<SetupCheckMiddleware>();
        }
    }
}