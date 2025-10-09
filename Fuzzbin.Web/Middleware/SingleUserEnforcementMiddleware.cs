using System;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Web.Middleware;

/// <summary>
/// Middleware that enforces single-user mode by blocking user creation endpoints
/// after the initial setup user has been created.
/// </summary>
public class SingleUserEnforcementMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<SingleUserEnforcementMiddleware> _logger;

    public SingleUserEnforcementMiddleware(
        RequestDelegate next,
        ILogger<SingleUserEnforcementMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context, UserManager<ApplicationUser> userManager)
    {
        var path = context.Request.Path.Value?.ToLowerInvariant() ?? string.Empty;

        // Block any endpoints that might create users
        if (IsUserCreationEndpoint(path))
        {
            var userCount = await userManager.Users.CountAsync();
            
            if (userCount >= 1)
            {
                _logger.LogWarning(
                    "Single-user mode: Blocked attempt to create additional user via {Path}",
                    context.Request.Path);

                context.Response.StatusCode = 403;
                context.Response.ContentType = "application/json";
                
                await context.Response.WriteAsJsonAsync(new
                {
                    error = "Forbidden",
                    message = "Fuzzbin is configured for single-user mode. Only one user account is allowed.",
                    statusCode = 403
                });
                
                return;
            }
        }

        await _next(context);
    }

    private static bool IsUserCreationEndpoint(string path)
    {
        // List of potential user creation endpoints to block
        var blockedPaths = new[]
        {
            "/api/users/create",
            "/api/users/register",
            "/api/users/add",
            "/api/admin/users/create",
            "/api/admin/users/add",
            "/api/account/register",
            "/admin/users/create",
            "/admin/users/add",
            "/users/create",
            "/users/register",
            "/register",
            "/signup"
        };

        foreach (var blockedPath in blockedPaths)
        {
            if (path.Equals(blockedPath, StringComparison.OrdinalIgnoreCase) ||
                path.StartsWith(blockedPath + "/", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }
}

/// <summary>
/// Extension methods for registering the single-user enforcement middleware.
/// </summary>
public static class SingleUserEnforcementMiddlewareExtensions
{
    public static IApplicationBuilder UseSingleUserEnforcement(this IApplicationBuilder builder)
    {
        return builder.UseMiddleware<SingleUserEnforcementMiddleware>();
    }
}