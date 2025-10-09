using System;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Threading;
using Microsoft.AspNetCore.Antiforgery;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.OutputCaching;
using Microsoft.AspNetCore.ResponseCompression;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Fuzzbin.Web.Hubs;
using MudBlazor.Services;
using Serilog;
using Serilog.Events;
using Fuzzbin.Core.Entities;
using Fuzzbin.Web.Identity;
using Fuzzbin.Web.Middleware;
using Fuzzbin.Web.Security;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Fuzzbin.Services;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using HeaderNames = Microsoft.Net.Http.Headers.HeaderNames;

// Configure Serilog
Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Debug()
    .MinimumLevel.Override("Microsoft", LogEventLevel.Information)
    .MinimumLevel.Override("Microsoft.AspNetCore", LogEventLevel.Warning)
    .MinimumLevel.Override("Microsoft.EntityFrameworkCore", LogEventLevel.Warning)
    .Enrich.FromLogContext()
    .WriteTo.Console(
        outputTemplate: "[{Timestamp:HH:mm:ss} {Level:u3}] {Message:lj}{NewLine}{Exception}")
    .WriteTo.File(
        "logs/fuzzbin-.txt",
        rollingInterval: RollingInterval.Day,
        rollOnFileSizeLimit: true,
        fileSizeLimitBytes: 10485760, // 10MB
        retainedFileCountLimit: 30,
        outputTemplate: "[{Timestamp:yyyy-MM-dd HH:mm:ss.fff zzz}] [{Level:u3}] {Message:lj}{NewLine}{Exception}")
    .CreateLogger();

try
{
    Log.Information("Starting Fuzzbin application");

    var builder = WebApplication.CreateBuilder(args);

    // Add Serilog
    builder.Host.UseSerilog();

    // Add services to the container
    builder.Services.AddRazorComponents()
        .AddInteractiveServerComponents();

    builder.Services.AddHttpContextAccessor();

    builder.Services.AddResponseCompression(options =>
    {
        options.EnableForHttps = true;
        options.Providers.Add<BrotliCompressionProvider>();
        options.Providers.Add<GzipCompressionProvider>();
        options.MimeTypes = ResponseCompressionDefaults.MimeTypes.Concat(new[]
        {
            "application/json",
            "application/xml",
            "application/javascript",
            "image/svg+xml"
        });
    });

    builder.Services.Configure<BrotliCompressionProviderOptions>(options => options.Level = CompressionLevel.Optimal);
    builder.Services.Configure<GzipCompressionProviderOptions>(options => options.Level = CompressionLevel.SmallestSize);

    builder.Services.AddOutputCache(options =>
    {
        options.AddBasePolicy(policy => policy.NoCache());

        options.AddPolicy("StaticAssets", policy =>
        {
            policy.Cache();
            policy.Expire(TimeSpan.FromHours(1));
            policy.SetCacheKeyPrefix("fz-assets");
            policy.SetVaryByHeader(HeaderNames.AcceptEncoding);
        });

        options.AddPolicy("SystemMetrics", policy =>
        {
            policy.Cache();
            policy.Expire(TimeSpan.FromSeconds(5));
            policy.SetCacheKeyPrefix("fz-metrics");
            policy.SetVaryByHeader(HeaderNames.AcceptEncoding);
        });
    });

    // Add MudBlazor services
    builder.Services.AddMudServices();

    // SignalR for real-time updates
    builder.Services.AddSignalR();

    // Configure SQLite with Entity Framework Core
    var dataDirectory = Path.Combine(builder.Environment.ContentRootPath, "data");
    Directory.CreateDirectory(dataDirectory);
    var databasePath = Path.Combine(dataDirectory, "fuzzbin.db");
    var connectionStringBuilder = new SqliteConnectionStringBuilder
    {
        DataSource = databasePath,
        Pooling = true,
        Cache = SqliteCacheMode.Shared,
        Mode = SqliteOpenMode.ReadWriteCreate
    };

    var connectionString = connectionStringBuilder.ToString();

    builder.Services.AddDbContextPool<ApplicationDbContext>(options =>
    {
        options.UseSqlite(connectionString);
        options.EnableSensitiveDataLogging(builder.Environment.IsDevelopment());
        options.EnableDetailedErrors(builder.Environment.IsDevelopment());
    });

    // Configure Data Protection for encryption
    var keysDirectory = Path.Combine(dataDirectory, "keys");
    Directory.CreateDirectory(keysDirectory);
    builder.Services.AddDataProtection()
        .PersistKeysToFileSystem(new DirectoryInfo(keysDirectory))
        .SetApplicationName("Fuzzbin");

    builder.Services.AddAntiforgery(options =>
    {
        options.Cookie.Name = AntiforgeryDefaults.CookieName;
        options.Cookie.HttpOnly = true;
        options.Cookie.SameSite = SameSiteMode.Strict;
        options.Cookie.SecurePolicy = CookieSecurePolicy.SameAsRequest;
        options.HeaderName = AntiforgeryDefaults.HeaderName;
    });

    var identityCoreBuilder = builder.Services.AddIdentityCore<ApplicationUser>(options =>
    {
        options.Password.RequireDigit = false;
        options.Password.RequireNonAlphanumeric = false;
        options.Password.RequireUppercase = false;
        options.Password.RequiredLength = 8;
        options.User.RequireUniqueEmail = false;
        options.Lockout.MaxFailedAccessAttempts = 5;
        options.Lockout.DefaultLockoutTimeSpan = TimeSpan.FromMinutes(5);
    });

    identityCoreBuilder = identityCoreBuilder.AddRoles<IdentityRole<Guid>>();
    identityCoreBuilder.AddEntityFrameworkStores<ApplicationDbContext>();
    identityCoreBuilder.AddSignInManager();
    identityCoreBuilder.AddDefaultTokenProviders();

    builder.Services.AddScoped<IUserClaimsPrincipalFactory<ApplicationUser>, ApplicationUserClaimsPrincipalFactory>();

    builder.Services.AddAuthentication(options =>
    {
        options.DefaultScheme = IdentityConstants.ApplicationScheme;
        options.DefaultAuthenticateScheme = IdentityConstants.ApplicationScheme;
        options.DefaultChallengeScheme = IdentityConstants.ApplicationScheme;
    })
    .AddCookie(IdentityConstants.ApplicationScheme, options =>
    {
        options.LoginPath = "/auth/signin";
        options.LogoutPath = "/auth/logout";
        options.AccessDeniedPath = "/auth/access-denied";
        options.SlidingExpiration = true;
        options.ExpireTimeSpan = TimeSpan.FromDays(14);
    });

    builder.Services.AddAuthorizationBuilder()
        .AddPolicy("ActiveUser", policy => policy.RequireAuthenticatedUser())
        .AddPolicy("AdminOnly", policy => policy.RequireRole("Admin"));


    // Register repositories and Unit of Work
    builder.Services.AddScoped(typeof(IRepository<>), typeof(Repository<>));
    builder.Services.AddScoped<IUnitOfWork, UnitOfWork>();
    builder.Services.AddScoped<IActivityLogRepository, ActivityLogRepository>();

    // Shared services
    builder.Services.AddSingleton<IDownloadTaskQueue, DownloadTaskQueue>();
    builder.Services.AddSingleton<IDownloadSettingsProvider, DownloadSettingsProvider>();

    // Register Services
    builder.Services.AddScoped<IYtDlpService, YtDlpService>();
    builder.Services.AddScoped<Fuzzbin.Services.Interfaces.IDownloadQueueService, DownloadQueueService>();
    builder.Services.AddScoped<ILibraryPathManager, LibraryPathManager>();
    builder.Services.AddScoped<IFileOrganizationService, FileOrganizationService>();
    builder.Services.AddScoped<IMetadataService, MetadataService>();
    builder.Services.AddScoped<IMetadataExportService, MetadataExportService>();
    builder.Services.AddScoped<Fuzzbin.Services.Interfaces.ICollectionService, Fuzzbin.Services.CollectionService>();
    builder.Services.AddScoped<IBulkOrganizeService, BulkOrganizeService>();
    builder.Services.AddScoped<INfoExportService, NfoExportService>();
    builder.Services.AddScoped<IVideoService, VideoService>();
    builder.Services.AddScoped<ISearchService, SearchService>();
    builder.Services.AddScoped<IExternalSearchService, ExternalSearchService>();
    builder.Services.AddSingleton<IImageOptimizationService, ImageOptimizationService>();
    builder.Services.AddScoped<IMetricsService, MetricsService>();
    builder.Services.AddScoped<IThumbnailService, ThumbnailService>();
    builder.Services.AddScoped<IPlaylistService, PlaylistService>();
    builder.Services.AddScoped<IActivityLogService, ActivityLogService>();
    builder.Services.AddScoped<ILibraryImportService, LibraryImportService>();
    builder.Services.AddScoped<ISourceVerificationService, SourceVerificationService>();
    builder.Services.AddSingleton<IVideoUpdateNotifier, Fuzzbin.Web.Services.SignalRVideoUpdateNotifier>();
    builder.Services.AddScoped<IBackupService, BackupService>();
    
    // Add HttpContextAccessor for ActivityLogService
    builder.Services.AddHttpContextAccessor();
    
    // Register Background Services
    builder.Services.AddHostedService<DownloadBackgroundService>();
    builder.Services.AddHostedService<ThumbnailBackgroundService>();

    // Add health checks
    builder.Services.AddHealthChecks()
        .AddDbContextCheck<ApplicationDbContext>("database");

    // Add HttpClient for external API calls
    builder.Services.AddHttpClient();

    // Add memory cache
    builder.Services.AddMemoryCache();

    builder.Services.AddOptions<ImvdbOptions>()
        .Bind(builder.Configuration.GetSection("Imvdb"))
        .Configure(options =>
        {
            options.ApiKey ??= builder.Configuration["ApiKeys:ImvdbApiKey"];
        });

    builder.Services.AddImvdbIntegration();
    
    // Add web-specific services
    builder.Services.AddScoped<Fuzzbin.Web.Services.KeyboardShortcutService>();
    builder.Services.AddScoped<Fuzzbin.Web.Services.LoadingStateService>();
    builder.Services.AddScoped<Fuzzbin.Web.Services.ThemeService>();
    builder.Services.AddScoped<Fuzzbin.Web.Services.OnboardingService>();

    // Configure CORS (if needed for API access)
    builder.Services.AddCors(options =>
    {
        options.AddPolicy("AllowAll", policy =>
        {
            policy.AllowAnyOrigin()
                  .AllowAnyMethod()
                  .AllowAnyHeader();
        });
    });

    var app = builder.Build();

    // Configure the HTTP request pipeline
    if (!app.Environment.IsDevelopment())
    {
        app.UseExceptionHandler("/Error", createScopeForErrors: true);
        // The default HSTS value is 30 days
        app.UseHsts();
    }

    // Use Serilog request logging
    app.UseSerilogRequestLogging(options =>
    {
        options.MessageTemplate = "HTTP {RequestMethod} {RequestPath} responded {StatusCode} in {Elapsed:0.0000} ms";
        options.GetLevel = (httpContext, elapsed, ex) => LogEventLevel.Debug;
        options.EnrichDiagnosticContext = (diagnosticContext, httpContext) =>
        {
            diagnosticContext.Set("RequestHost", httpContext.Request.Host.Value ?? "unknown");
            diagnosticContext.Set("RequestScheme", httpContext.Request.Scheme);
        };
    });

    app.UseHttpsRedirection();
    app.UseResponseCompression();
    app.UseOutputCache();

    app.UseStaticFiles(new StaticFileOptions
    {
        OnPrepareResponse = context =>
        {
            var headers = context.Context.Response.Headers;
            headers[HeaderNames.CacheControl] = "public,max-age=3600";
            headers[HeaderNames.Vary] = HeaderNames.AcceptEncoding;
        }
    });
    app.UseMiddleware<AntiforgeryCookieCleanupMiddleware>();
    app.UseAntiforgery();

    app.UseAuthentication();
    app.UseAuthorization();
    
    // Enforce single-user mode
    app.UseSingleUserEnforcement();
    
    // Use setup check middleware to redirect to setup if not configured
    app.UseSetupCheck();

    // Map health check endpoints
    app.MapHealthChecks("/health");
    app.MapHealthChecks("/health/ready", new Microsoft.AspNetCore.Diagnostics.HealthChecks.HealthCheckOptions
    {
        Predicate = check => check.Tags.Contains("ready")
    });
    app.MapHealthChecks("/health/live", new Microsoft.AspNetCore.Diagnostics.HealthChecks.HealthCheckOptions
    {
        Predicate = _ => false
    });

    app.MapPost("/auth/login", async (
        HttpContext httpContext,
        SignInManager<ApplicationUser> signInManager,
        UserManager<ApplicationUser> userManager,
        ILogger<Program> logger) =>
    {
        var form = await httpContext.Request.ReadFormAsync();

        var identifier = form["EmailOrUsername"].ToString().Trim();
        var password = form["Password"].ToString();
        var rememberMe = ParseCheckboxValue(form["RememberMe"].ToString());
        var returnUrlRaw = form["ReturnUrl"].ToString();

        if (string.IsNullOrWhiteSpace(identifier) || string.IsNullOrWhiteSpace(password))
        {
            logger.LogInformation("Fallback login attempt rejected due to missing credentials.");
            return Results.Redirect(BuildLoginRedirect(returnUrlRaw, "missingcredentials", identifier));
        }

        logger.LogInformation("Fallback login attempt submitted for {Identifier}", identifier);

        var user = await userManager.FindByNameAsync(identifier);
        if (user is null)
        {
            logger.LogWarning("Fallback login attempt with unknown identifier {Identifier}", identifier);
            return Results.Redirect(BuildLoginRedirect(returnUrlRaw, "invalidcredentials", identifier));
        }

        if (!user.IsActive)
        {
            logger.LogWarning("Inactive user {UserId} attempted to sign in via fallback login.", user.Id);
            return Results.Redirect(BuildLoginRedirect(returnUrlRaw, "disabled", identifier));
        }

        var result = await signInManager.PasswordSignInAsync(user.UserName!, password, rememberMe, lockoutOnFailure: true);

        if (result.Succeeded)
        {
            user.LastLoginAt = DateTime.UtcNow;
            await userManager.UpdateAsync(user);
            logger.LogInformation("User {UserId} signed in via fallback login POST.", user.Id);
            return Results.LocalRedirect(NormalizeReturnUrl(returnUrlRaw));
        }

        if (result.IsLockedOut)
        {
            logger.LogWarning("User {UserId} locked out via fallback login POST.", user.Id);
            return Results.Redirect(BuildLoginRedirect(returnUrlRaw, "lockedout", identifier));
        }

        if (result.IsNotAllowed)
        {
            logger.LogWarning("User {UserId} not allowed to sign in via fallback login POST.", user.Id);
            return Results.Redirect(BuildLoginRedirect(returnUrlRaw, "notallowed", identifier));
        }

        logger.LogWarning("Invalid credentials provided for user {UserId} via fallback login POST.", user.Id);
        return Results.Redirect(BuildLoginRedirect(returnUrlRaw, "invalidcredentials", identifier));
    }).AllowAnonymous();

    app.MapGet("/auth/logout", async (
        HttpContext httpContext,
        SignInManager<ApplicationUser> signInManager,
        ILogger<Program> logger) =>
    {
        try
        {
            var userName = httpContext.User.Identity?.Name;
            await signInManager.SignOutAsync();
            logger.LogInformation("User {UserName} signed out successfully", userName ?? "Unknown");
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Error during sign-out");
        }
        
        return Results.Redirect("/auth/signin");
    }).AllowAnonymous();

    app.MapGet("/antiforgery/token", (IAntiforgery antiforgery, HttpContext context) =>
    {
        var tokens = antiforgery.GetAndStoreTokens(context);
        context.Response.Headers.CacheControl = "no-cache, no-store";
        context.Response.Headers.Pragma = "no-cache";
        return Results.Json(new { fieldName = tokens.FormFieldName, requestToken = tokens.RequestToken });
    }).AllowAnonymous();

    app.MapRazorComponents<Fuzzbin.Web.Components.App>()
        .AddInteractiveServerRenderMode();

app.MapHub<VideoUpdatesHub>("/hubs/updates");

    app.MapGet("/api/system/build-info", () =>
    {
        var assembly = Assembly.GetExecutingAssembly();
        var informationalVersion = assembly
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?
            .InformationalVersion;

        var version = informationalVersion ?? assembly.GetName().Version?.ToString() ?? "unknown";

        var payload = new
        {
            Name = assembly.GetName().Name ?? "Fuzzbin.Web",
            Version = version,
            Build = Environment.GetEnvironmentVariable("BUILD_NUMBER") ?? "local",
            Environment = app.Environment.EnvironmentName
        };

        return Results.Ok(payload);
    })
    .CacheOutput("StaticAssets")
    .WithName("GetBuildInfo")
    .AllowAnonymous();

    app.MapGet("/api/system/metrics", async (IMetricsService metricsService, CancellationToken cancellationToken) =>
        Results.Ok(await metricsService.CaptureAsync(cancellationToken)))
        .CacheOutput("SystemMetrics")
        .WithName("GetSystemMetrics")
        .AllowAnonymous();

    app.MapGet("/auth/setup-complete", async (
        HttpContext httpContext,
        string? token,
        SignInManager<ApplicationUser> signInManager,
        IUnitOfWork unitOfWork,
        ILogger<Program> logger) =>
    {
        if (string.IsNullOrWhiteSpace(token))
        {
            logger.LogWarning("Setup sign-in attempted without a token.");
            return Results.Redirect("/auth/signin");
        }

        var storedTokenConfig = await unitOfWork.Configurations
            .FirstOrDefaultAsync(c => c.Key == "SetupSignInToken" && c.Category == "System" && c.IsActive);

        if (storedTokenConfig?.Value is null)
        {
            logger.LogWarning("Setup sign-in token not found or already used.");
            return Results.Redirect("/auth/signin");
        }

        var tokenParts = storedTokenConfig.Value.Split('|', 2, StringSplitOptions.TrimEntries);
        if (tokenParts.Length != 2 || !string.Equals(tokenParts[0], token, StringComparison.Ordinal))
        {
            logger.LogWarning("Setup sign-in token mismatch.");
            return Results.Redirect("/auth/signin");
        }

        var userId = tokenParts[1];
        var user = await signInManager.UserManager.FindByIdAsync(userId);
        if (user is null)
        {
            logger.LogWarning("Setup sign-in user not found for token.");
            return Results.Redirect("/auth/signin");
        }

        user.LockoutEnabled = false;
        user.LockoutEnd = null;
        await signInManager.UserManager.UpdateAsync(user);
        await signInManager.UserManager.ResetAccessFailedCountAsync(user);

        await signInManager.SignInAsync(user, isPersistent: true);
        logger.LogInformation("Administrator {AdminEmail} signed in via setup completion endpoint.", user.Email);

        storedTokenConfig.IsActive = false;
        storedTokenConfig.Value = string.Empty;
        await unitOfWork.Configurations.UpdateAsync(storedTokenConfig);
        await unitOfWork.SaveChangesAsync();

        return Results.Redirect("/dashboard");
    }).AllowAnonymous();

    // Apply database migrations and check first run
    using (var scope = app.Services.CreateScope())
    {
        var dbContext = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var logger = scope.ServiceProvider.GetRequiredService<ILogger<Program>>();

        try
        {
            logger.LogInformation("Applying database migrations...");
            dbContext.Database.Migrate();
            logger.LogInformation("Database migrations applied successfully");

            // Check if this is the first run
            var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();
            var firstRunConfig = await unitOfWork.Configurations
                .FirstOrDefaultAsync(c => c.Key == "IsFirstRun" && c.Category == "System");

            if (firstRunConfig != null && firstRunConfig.Value == "true")
            {
                logger.LogInformation("First run detected - setup wizard will be shown");
            }
}
catch (Exception ex)
{
    logger.LogError(ex, "An error occurred while migrating the database");
    throw;
}
}
static string NormalizeReturnUrl(string? returnUrl)
{
    if (string.IsNullOrWhiteSpace(returnUrl))
    {
        return "/";
    }

    if (Uri.TryCreate(returnUrl, UriKind.Absolute, out _))
    {
        return "/";
    }

    return returnUrl.StartsWith('/') ? returnUrl : $"/{returnUrl}";
}

static string BuildLoginRedirect(string? returnUrl, string errorCode, string? identifier = null)
{
    var query = QueryString.Empty;

    if (!string.IsNullOrWhiteSpace(errorCode))
    {
        query = query.Add("error", errorCode);
    }

    if (!string.IsNullOrWhiteSpace(identifier))
    {
        query = query.Add("identifier", identifier);
    }

    var safeReturnUrl = NormalizeReturnUrl(returnUrl);
    if (!string.Equals(safeReturnUrl, "/", StringComparison.Ordinal))
    {
        query = query.Add("returnUrl", safeReturnUrl);
    }

    return $"/auth/signin{query}";
}

static bool ParseCheckboxValue(string? value)
{
    if (string.IsNullOrWhiteSpace(value))
    {
        return false;
    }

    return value.Equals("true", StringComparison.OrdinalIgnoreCase) ||
           value.Equals("on", StringComparison.OrdinalIgnoreCase) ||
           value.Equals("1", StringComparison.OrdinalIgnoreCase);
}

    Log.Information("Fuzzbin application started successfully");
    app.Run();
}
catch (Exception ex)
{
    Log.Fatal(ex, "Fuzzbin application terminated unexpectedly");
}
finally
{
    Log.CloseAndFlush();
}

// Make the implicit Program class public so test projects can access it
public partial class Program { }
