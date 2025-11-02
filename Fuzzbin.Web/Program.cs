using System;
using System.Collections.Generic;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Security.Claims;
using Microsoft.AspNetCore.Antiforgery;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.OutputCaching;
using Microsoft.AspNetCore.ResponseCompression;
using Microsoft.AspNetCore.StaticFiles;
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
using Fuzzbin.Services.External.MusicBrainz;
using Fuzzbin.Services.Http;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using HeaderNames = Microsoft.Net.Http.Headers.HeaderNames;

// Configure Serilog - will be reconfigured with proper paths after service provider is built
Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Debug()
    .MinimumLevel.Override("Microsoft", LogEventLevel.Information)
    .MinimumLevel.Override("Microsoft.AspNetCore", LogEventLevel.Warning)
    .MinimumLevel.Override("Microsoft.EntityFrameworkCore", LogEventLevel.Warning)
    .Enrich.FromLogContext()
    .WriteTo.Console(
        outputTemplate: "[{Timestamp:HH:mm:ss} {Level:u3}] {Message:lj}{NewLine}{Exception}")
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

    // Register configuration path service first (required by other services)
    builder.Services.AddSingleton<IConfigurationPathService, ConfigurationPathService>();

    // Build a temporary service provider to resolve the configuration path service
    // This is necessary to configure paths before the main application starts
#pragma warning disable ASP0000 // BuildServiceProvider is intentionally used here to configure paths early
    using (var tempProvider = builder.Services.BuildServiceProvider())
#pragma warning restore ASP0000
    {
        var configPathService = tempProvider.GetRequiredService<IConfigurationPathService>();
        
        // Configure SQLite with Entity Framework Core using new path structure
        var databasePath = configPathService.GetDatabasePath();
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

        // Configure Data Protection for encryption using new path structure
        var keysDirectory = Path.Combine(configPathService.GetDataDirectory(), "keys");
        configPathService.EnsureDirectoryExists(keysDirectory);
        builder.Services.AddDataProtection()
            .PersistKeysToFileSystem(new DirectoryInfo(keysDirectory))
            .SetApplicationName("Fuzzbin");
        
        // Reconfigure Serilog to use proper logs directory
        var logsPath = Path.Combine(configPathService.GetLogsDirectory(), "fuzzbin-.txt");
        Log.Logger = new LoggerConfiguration()
            .MinimumLevel.Debug()
            .MinimumLevel.Override("Microsoft", LogEventLevel.Information)
            .MinimumLevel.Override("Microsoft.AspNetCore", LogEventLevel.Warning)
            .MinimumLevel.Override("Microsoft.EntityFrameworkCore", LogEventLevel.Warning)
            .Enrich.FromLogContext()
            .WriteTo.Console(
                outputTemplate: "[{Timestamp:HH:mm:ss} {Level:u3}] {Message:lj}{NewLine}{Exception}")
            .WriteTo.File(
                logsPath,
                rollingInterval: RollingInterval.Day,
                rollOnFileSizeLimit: true,
                fileSizeLimitBytes: 10485760, // 10MB
                retainedFileCountLimit: 30,
                outputTemplate: "[{Timestamp:yyyy-MM-dd HH:mm:ss.fff zzz}] [{Level:u3}] {Message:lj}{NewLine}{Exception}")
            .CreateLogger();

        Log.Information("Configuration directory: {ConfigDir}", configPathService.GetConfigDirectory());
        Log.Information("Database path: {DatabasePath}", databasePath);
        Log.Information("Logs directory: {LogsDir}", configPathService.GetLogsDirectory());
    }

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
    builder.Services.AddSingleton<IGenreMappingDefaultsProvider, GenreMappingDefaultsProvider>();
    builder.Services.AddSingleton<IMetadataSettingsProvider, MetadataSettingsProvider>();
    builder.Services.AddSingleton<IExternalCacheSettingsProvider, ExternalCacheSettingsProvider>();

    // Register Services
    builder.Services.AddScoped<IYtDlpService, YtDlpService>();
    builder.Services.AddScoped<Fuzzbin.Services.Interfaces.IDownloadQueueService, DownloadQueueService>();
    builder.Services.AddScoped<ILibraryPathManager, LibraryPathManager>();
    builder.Services.AddScoped<IFileOrganizationService, FileOrganizationService>();
    builder.Services.AddScoped<IMetadataCacheService, MetadataCacheService>();
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
    builder.Services.AddScoped<IBackgroundJobService, BackgroundJobService>();
    builder.Services.AddSingleton<IJobProgressNotifier, Fuzzbin.Web.Services.SignalRJobProgressNotifier>();
    builder.Services.AddScoped<IGenreService, GenreService>();
    builder.Services.AddScoped<ITagService, TagService>();
    
    // Add HttpContextAccessor for ActivityLogService
    builder.Services.AddHttpContextAccessor();
    
    // Register Background Services
    builder.Services.AddHostedService<DownloadBackgroundService>();
    builder.Services.AddHostedService<ThumbnailBackgroundService>();
    builder.Services.AddHostedService<BackgroundJobProcessorService>();

    // Add health checks
    builder.Services.AddHealthChecks()
        .AddDbContextCheck<ApplicationDbContext>("database");

    // Add memory cache
    builder.Services.AddMemoryCache();

    // Register HTTP infrastructure for external APIs with retry and rate limiting
    builder.Services.AddSingleton<MusicBrainzRateLimiter>();
    builder.Services.AddTransient<MusicBrainzHttpMessageHandler>();
    
    // Register MusicBrainz client
    builder.Services.AddScoped<IMusicBrainzClient, MusicBrainzClient>();

    // Configure MusicBrainz HTTP client with rate limiting and retry policy
    builder.Services.AddHttpClient("MusicBrainz", (sp, client) =>
    {
        var settingsProvider = sp.GetRequiredService<IExternalCacheSettingsProvider>();
        var settings = settingsProvider.GetSettings();
        client.BaseAddress = new Uri("https://musicbrainz.org/ws/2/");
        client.Timeout = TimeSpan.FromSeconds(30);
        client.DefaultRequestHeaders.UserAgent.ParseAdd(settings.MusicBrainzUserAgent);
    })
    .AddHttpMessageHandler<MusicBrainzHttpMessageHandler>()
    .AddPolicyHandler(RetryPolicyFactory.CreateExternalApiRetryPolicy());

    // Configure IMVDb HTTP client with retry policy (no rate limiting needed)
    builder.Services.AddHttpClient("ImvdbEnriched")
        .AddPolicyHandler(RetryPolicyFactory.CreateExternalApiRetryPolicy());

    // Configure YouTube/yt-dlp HTTP client with retry policy
    builder.Services.AddHttpClient("YouTubeDlp")
        .AddPolicyHandler(RetryPolicyFactory.CreateExternalApiRetryPolicy());

    // Add generic HttpClient for other external API calls
    builder.Services.AddHttpClient();

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

    app.MapPost("/api/account/login", async (
        LoginRequest request,
        SignInManager<ApplicationUser> signInManager,
        UserManager<ApplicationUser> userManager,
        ILogger<Program> logger) =>
    {
        if (request is null || string.IsNullOrWhiteSpace(request.Email) || string.IsNullOrWhiteSpace(request.Password))
        {
            return Results.BadRequest(new { message = "Email and password are required." });
        }

        var user = await userManager.FindByNameAsync(request.Email);
        if (user is null)
        {
            logger.LogWarning("Login attempt with unknown email {Email}", request.Email);
            return Results.Unauthorized();
        }

        if (!user.IsActive)
        {
            logger.LogWarning("Inactive user {UserId} attempted to sign in.", user.Id);
            return Results.Unauthorized();
        }

        var result = await signInManager.PasswordSignInAsync(user.UserName!, request.Password, request.RememberMe, lockoutOnFailure: true);

        if (result.Succeeded)
        {
            user.LastLoginAt = DateTime.UtcNow;
            await userManager.UpdateAsync(user);
            logger.LogInformation("User {UserId} signed in via API.", user.Id);
            return Results.Ok(new { message = "Login successful." });
        }

        if (result.IsLockedOut)
        {
            logger.LogWarning("User {UserId} locked out.", user.Id);
            return Results.Unauthorized();
        }

        if (result.IsNotAllowed)
        {
            logger.LogWarning("User {UserId} not allowed to sign in.", user.Id);
            return Results.Unauthorized();
        }

        logger.LogWarning("Invalid credentials provided for user {UserId}.", user.Id);
        return Results.Unauthorized();
    }).AllowAnonymous();

    app.MapPost("/api/account/logout", async (
        SignInManager<ApplicationUser> signInManager,
        ILogger<Program> logger) =>
    {
        try
        {
            await signInManager.SignOutAsync();
            logger.LogInformation("User signed out via API");
            return Results.Ok(new { message = "Logout successful." });
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Error during API sign-out");
            return Results.Problem("An error occurred during logout.");
        }
    }).AllowAnonymous();

    app.MapPost("/api/account/change-password", async (
        HttpContext httpContext,
        ChangePasswordRequest request,
        UserManager<ApplicationUser> userManager,
        SignInManager<ApplicationUser> signInManager,
        ILogger<Program> logger) =>
    {
        // Check authentication first
        if (!httpContext.User.Identity?.IsAuthenticated ?? true)
        {
            return Results.Unauthorized();
        }

        if (request is null ||
            string.IsNullOrWhiteSpace(request.CurrentPassword) ||
            string.IsNullOrWhiteSpace(request.NewPassword) ||
            string.IsNullOrWhiteSpace(request.ConfirmPassword))
        {
            return Results.BadRequest(new { message = "All password fields are required." });
        }

        if (!string.Equals(request.NewPassword, request.ConfirmPassword, StringComparison.Ordinal))
        {
            return Results.BadRequest(new { errors = new[] { "New password and confirmation do not match." } });
        }

        var user = await userManager.GetUserAsync(httpContext.User);
        if (user is null)
        {
            return Results.Unauthorized();
        }

        var result = await userManager.ChangePasswordAsync(user, request.CurrentPassword, request.NewPassword);
        if (!result.Succeeded)
        {
            var errors = result.Errors
                .Select(e =>
                {
                    // Make error messages more consistent with test expectations
                    if (e.Code == "PasswordMismatch")
                    {
                        return "The current password is incorrect.";
                    }
                    return e.Description;
                })
                .Where(description => !string.IsNullOrWhiteSpace(description))
                .ToArray();

            if (errors.Length == 0)
            {
                errors = new[] { "Unable to change password." };
            }

            logger.LogWarning("Failed password change for user {UserId}: {Errors}", user.Id, string.Join("; ", errors));
            return Results.BadRequest(new { errors });
        }

        await signInManager.RefreshSignInAsync(user);
        logger.LogInformation("User {UserId} updated their password via settings.", user.Id);
        return Results.Ok(new { message = "Password updated successfully." });
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
    app.MapHub<JobProgressHub>("/hubs/jobprogress").AllowAnonymous();

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

    // Background Job API Endpoints
    // GET /api/jobs?status=Running&limit=50
    app.MapGet("/api/jobs", async (IBackgroundJobService jobService, string? status, int? limit, CancellationToken ct) =>
    {
        BackgroundJobStatus? parsedStatus = null;
        if (!string.IsNullOrWhiteSpace(status))
        {
            if (Enum.TryParse<BackgroundJobStatus>(status, true, out var st))
            {
                parsedStatus = st;
            }
            else
            {
                return Results.BadRequest(new { message = $"Invalid status value '{status}'." });
            }
        }
        var jobs = await jobService.GetJobsAsync(parsedStatus, limit, ct);
        return Results.Ok(jobs);
    })
    .WithName("ListJobs");

    // GET /api/jobs/{jobId}
    app.MapGet("/api/jobs/{jobId:guid}", async (IBackgroundJobService jobService, Guid jobId, CancellationToken ct) =>
    {
        var job = await jobService.GetJobAsync(jobId, ct);
        return job is null ? Results.NotFound() : Results.Ok(job);
    })
    .WithName("GetJob");

    // POST /api/jobs/{type}  (singleton enqueue)
    app.MapPost("/api/jobs/{type}", async (IBackgroundJobService jobService, string type, CancellationToken ct) =>
    {
        if (!Enum.TryParse<BackgroundJobType>(type, true, out var jobType))
        {
            return Results.BadRequest(new { message = $"Unknown job type '{type}'." });
        }

        var (created, job) = await jobService.TryEnqueueSingletonJobAsync(jobType, null, ct);
        if (created)
        {
            return Results.Accepted($"/api/jobs/{job.Id}", job);
        }
        return Results.Ok(new
        {
            message = "Job of this type is already active (singleton).",
            existingJobId = job.Id,
            job.Status,
            job.Progress
        });
    })
    .WithName("EnqueueSingletonJob");

    // POST /api/jobs/{jobId}/cancel
    app.MapPost("/api/jobs/{jobId:guid}/cancel", async (IBackgroundJobService jobService, Guid jobId, CancellationToken ct) =>
    {
        await jobService.CancelJobAsync(jobId, ct);
        return Results.Accepted();
    })
    .WithName("CancelJob");

    // Genre Management API Endpoints
    app.MapGet("/api/genres", async (
        IGenreService genreService,
        string? search,
        string? sortBy,
        string? sortDirection,
        int page = 1,
        int pageSize = 50,
        CancellationToken ct = default) =>
    {
        var result = await genreService.GetGenresAsync(search, sortBy, sortDirection, page, pageSize, ct);
        return Results.Ok(result);
    })
    .WithName("GetGenres")
    .RequireAuthorization();

    app.MapPost("/api/genres", async (
        IGenreService genreService,
        GenreCreateRequest request,
        CancellationToken ct = default) =>
    {
        try
        {
            var genre = await genreService.CreateGenreAsync(request.Name, request.Description, ct);
            return Results.Created($"/api/genres/{genre.Id}", genre);
        }
        catch (InvalidOperationException ex)
        {
            return Results.Conflict(new { message = ex.Message });
        }
    })
    .WithName("CreateGenre")
    .RequireAuthorization();

    app.MapPost("/api/genres/generalize", async (
        IGenreService genreService,
        GeneralizeGenresRequest request,
        CancellationToken ct = default) =>
    {
        try
        {
            await genreService.GeneralizeGenresAsync(request.SourceGenreIds, request.TargetGenreId, ct);
            return Results.Ok(new { message = "Genres generalized successfully" });
        }
        catch (InvalidOperationException ex)
        {
            return Results.BadRequest(new { message = ex.Message });
        }
    })
    .WithName("GeneralizeGenres")
    .RequireAuthorization();

    app.MapDelete("/api/genres/{id:guid}", async (
        IGenreService genreService,
        Guid id,
        CancellationToken ct = default) =>
    {
        await genreService.DeleteGenreAsync(id, ct);
        return Results.NoContent();
    })
    .WithName("DeleteGenre")
    .RequireAuthorization();

    app.MapPost("/api/genres/bulk-delete", async (
        IGenreService genreService,
        BulkDeleteRequest request,
        CancellationToken ct = default) =>
    {
        await genreService.DeleteGenresAsync(request.Ids, ct);
        return Results.Ok(new { message = $"Deleted {request.Ids.Count()} genres" });
    })
    .WithName("BulkDeleteGenres")
    .RequireAuthorization();

    // Tag Management API Endpoints
    app.MapGet("/api/tags", async (
        ITagService tagService,
        string? search,
        string? sortBy,
        string? sortDirection,
        int page = 1,
        int pageSize = 50,
        CancellationToken ct = default) =>
    {
        var result = await tagService.GetTagsAsync(search, sortBy, sortDirection, page, pageSize, ct);
        return Results.Ok(result);
    })
    .WithName("GetTags")
    .RequireAuthorization();

    app.MapGet("/api/tags/{id:guid}/videos", async (
        ITagService tagService,
        Guid id,
        int maxCount = 5,
        CancellationToken ct = default) =>
    {
        var videos = await tagService.GetVideosForTagAsync(id, maxCount, ct);
        return Results.Ok(videos);
    })
    .WithName("GetTagVideos")
    .RequireAuthorization();

    app.MapPost("/api/tags", async (
        ITagService tagService,
        TagCreateRequest request,
        CancellationToken ct = default) =>
    {
        try
        {
            var tag = await tagService.CreateTagAsync(request.Name, request.Color, ct);
            return Results.Created($"/api/tags/{tag.Id}", tag);
        }
        catch (InvalidOperationException ex)
        {
            return Results.Conflict(new { message = ex.Message });
        }
    })
    .WithName("CreateTag")
    .RequireAuthorization();

    app.MapPut("/api/tags/{id:guid}", async (
        ITagService tagService,
        Guid id,
        TagUpdateRequest request,
        CancellationToken ct = default) =>
    {
        try
        {
            var tag = await tagService.RenameTagAsync(id, request.Name, ct);
            return Results.Ok(tag);
        }
        catch (InvalidOperationException ex)
        {
            return Results.BadRequest(new { message = ex.Message });
        }
    })
    .WithName("UpdateTag")
    .RequireAuthorization();

    app.MapDelete("/api/tags/{id:guid}", async (
        ITagService tagService,
        Guid id,
        CancellationToken ct = default) =>
    {
        await tagService.DeleteTagAsync(id, ct);
        return Results.NoContent();
    })
    .WithName("DeleteTag")
    .RequireAuthorization();

    app.MapPost("/api/tags/bulk-delete", async (
        ITagService tagService,
        BulkDeleteRequest request,
        CancellationToken ct = default) =>
    {
        await tagService.DeleteTagsAsync(request.Ids, ct);
        return Results.Ok(new { message = $"Deleted {request.Ids.Count()} tags" });
    })
    .WithName("BulkDeleteTags")
    .RequireAuthorization();

    app.MapGet("/api/videos/stream", async (
        string? path,
        ILibraryPathManager libraryPathManager,
        ILogger<Program> logger,
        CancellationToken cancellationToken) =>
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            logger.LogWarning("Stream endpoint called with empty or missing path");
            return Results.BadRequest(new {
                message = "File path is required.",
                errorCode = "MISSING_PATH"
            });
        }

        try
        {
            var normalized = libraryPathManager.NormalizePath(path);
            var candidates = new List<string>();

            if (Path.IsPathRooted(normalized))
            {
                candidates.Add(normalized);
            }

            var videoRoot = await libraryPathManager.GetVideoRootAsync(cancellationToken).ConfigureAwait(false);
            candidates.Add(Path.Combine(videoRoot, normalized));

            logger.LogDebug("Attempting to stream video. Original path: {OriginalPath}, Normalized: {Normalized}, Video root: {VideoRoot}, Candidates: {CandidateCount}",
                path, normalized, videoRoot, candidates.Count);

            string? fullPath = null;
            foreach (var candidate in candidates)
            {
                try
                {
                    var resolved = Path.GetFullPath(candidate);
                    logger.LogDebug("Checking candidate path: {Candidate} -> {Resolved}, Exists: {Exists}",
                        candidate, resolved, File.Exists(resolved));
                    
                    if (File.Exists(resolved))
                    {
                        fullPath = resolved;
                        break;
                    }
                }
                catch (Exception ex)
                {
                    logger.LogDebug(ex, "Invalid path candidate: {Candidate}", candidate);
                }
            }

            if (fullPath is null)
            {
                logger.LogWarning("Stream requested for missing file. Path: {FilePath}, Normalized: {Normalized}, VideoRoot: {VideoRoot}, Checked {Count} candidates",
                    path, normalized, videoRoot, candidates.Count);
                return Results.NotFound(new {
                    message = "Video file not found. The file may have been moved or deleted.",
                    errorCode = "FILE_NOT_FOUND",
                    requestedPath = path
                });
            }

            var provider = new FileExtensionContentTypeProvider();
            
            // Add support for additional video formats not in the default provider
            provider.Mappings[".mkv"] = "video/x-matroska";
            provider.Mappings[".webm"] = "video/webm";
            
            if (!provider.TryGetContentType(fullPath, out var contentType))
            {
                contentType = "application/octet-stream";
            }

            logger.LogDebug("Streaming video file: {FullPath}, ContentType: {ContentType}", fullPath, contentType);
            var stream = new FileStream(fullPath, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 16, useAsync: true);
            return Results.File(stream, contentType, enableRangeProcessing: true);
        }
        catch (UnauthorizedAccessException ex)
        {
            logger.LogError(ex, "Access denied when streaming video {FilePath}", path);
            return Results.Problem(
                detail: "Access to the video file was denied. Please check file permissions.",
                statusCode: 403,
                title: "Access Denied");
        }
        catch (IOException ex)
        {
            logger.LogError(ex, "IO error when streaming video {FilePath}", path);
            return Results.Problem(
                detail: "Unable to read the video file. The file may be in use or corrupted.",
                statusCode: 500,
                title: "File Read Error");
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Unexpected error when streaming video {FilePath}", path);
            return Results.Problem(
                detail: "An unexpected error occurred while streaming the video.",
                statusCode: 500,
                title: "Stream Error");
        }
    })
    .WithName("StreamVideo")
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

    // Apply database migrations and check first run (skip in Testing environment)
    if (!app.Environment.IsEnvironment("Testing"))
    {
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

// Helper functions
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

// Request/Response DTOs for API endpoints
record GenreCreateRequest(string Name, string? Description);
record GeneralizeGenresRequest(IEnumerable<Guid> SourceGenreIds, Guid TargetGenreId);
record TagCreateRequest(string Name, string? Color);
record TagUpdateRequest(string Name);
record BulkDeleteRequest(IEnumerable<Guid> Ids);
record LoginRequest(string Email, string Password, bool RememberMe);
record ChangePasswordRequest(string CurrentPassword, string NewPassword, string ConfirmPassword);

// Make the implicit Program class public so test projects can access it
public partial class Program { }
