# Fuzzbin C# - Implementation Guide

## Overview

This guide provides a step-by-step approach to implementing Fuzzbin using C# with ASP.NET Core 8.0, Blazor Server, and SQLite with database-driven configuration.

## Key Architecture Decisions

### Why This Stack?

1. **Single Language**: C# throughout
2. **Single Container**: Everything in one ~180MB Docker image
3. **Zero Configuration**: All settings in database, managed via UI
4. **Self-Contained**: No external services or environment variables required
5. **Resource Efficient**: 150MB idle memory (vs 800MB for Python/Node.js)

### Technology Choices

- **ASP.NET Core 8.0**: Modern, performant web framework
- **Blazor Server**: Real-time UI with minimal JavaScript
- **SQLite + EF Core**: Embedded database with ORM
- **SignalR**: WebSocket-based real-time updates
- **Data Protection API**: Built-in encryption for sensitive data

## Project Structure

```
Fuzzbin/
├── Fuzzbin.csproj
├── Program.cs                      # Application entry point
├── Startup/
│   ├── DatabaseInitializer.cs     # First-run setup
│   └── ConfigurationSetup.cs      # Configuration services
├── Models/
│   ├── Entities/
│   │   ├── User.cs
│   │   ├── Video.cs
│   │   ├── QueueItem.cs
│   │   └── SystemConfiguration.cs # DB-stored config
│   └── DTOs/
│       ├── VideoDto.cs
│       └── QueueItemDto.cs
├── Data/
│   ├── FuzzbinDbContext.cs    # EF Core context
│   ├── Migrations/                # Database migrations
│   └── Repositories/
│       ├── VideoRepository.cs
│       └── QueueRepository.cs
├── Services/
│   ├── ConfigurationService.cs    # DB config management
│   ├── VideoService.cs
│   ├── DownloadService.cs
│   ├── MetadataService.cs
│   └── BackgroundServices/
│       └── DownloadWorker.cs
├── Components/                     # Blazor components
│   ├── App.razor
│   ├── Routes.razor
│   ├── Layout/
│   │   ├── MainLayout.razor
│   │   └── NavMenu.razor
│   ├── Pages/
│   │   ├── Index.razor
│   │   ├── Setup.razor            # First-run wizard
│   │   ├── Settings.razor         # Admin settings
│   │   ├── Videos.razor
│   │   └── Queue.razor
│   └── Shared/
│       ├── VideoCard.razor
│       └── DownloadProgress.razor
├── Hubs/
│   └── DownloadHub.cs             # SignalR hub
├── wwwroot/
│   ├── css/
│   └── js/
├── Dockerfile
└── appsettings.json               # Minimal config
```

## Implementation Steps

### Phase 1: Core Setup (Week 1)

#### 1.1 Create Project

```bash
# Create new Blazor Server project
dotnet new blazorserver -n Fuzzbin
cd Fuzzbin

# Add required packages
dotnet add package Microsoft.EntityFrameworkCore.Sqlite
dotnet add package Microsoft.AspNetCore.DataProtection.EntityFrameworkCore
dotnet add package MudBlazor
dotnet add package Serilog.AspNetCore
```

#### 1.2 Define Data Models

```csharp
// Models/Entities/SystemConfiguration.cs
public class SystemConfiguration
{
    public int Id { get; set; } = 1;
    public DateTime LastModified { get; set; }
    
    [Encrypted]
    public string ImvdbApiKey { get; set; }
    [Encrypted]
    public string JwtSecret { get; set; }
    
    public string MediaPath { get; set; } = "/media";
    public long MaxStorageBytes { get; set; } = 536_870_912_000;
    public bool IsInitialized { get; set; } = false;
    public string AdminEmail { get; set; }
}

// Models/Entities/User.cs
public class User
{
    public Guid Id { get; set; }
    public string Email { get; set; }
    public string Username { get; set; }
    public string PasswordHash { get; set; }
    public bool IsAdmin { get; set; }
    public DateTime CreatedAt { get; set; }
}
```

#### 1.3 Setup Database Context

```csharp
// Data/FuzzbinDbContext.cs
public class FuzzbinDbContext : DbContext
{
    private readonly IDataProtectionProvider _dataProtection;
    
    public FuzzbinDbContext(
        DbContextOptions<FuzzbinDbContext> options,
        IDataProtectionProvider dataProtection)
        : base(options)
    {
        _dataProtection = dataProtection;
    }
    
    public DbSet<User> Users { get; set; }
    public DbSet<Video> Videos { get; set; }
    public DbSet<QueueItem> QueueItems { get; set; }
    public DbSet<SystemConfiguration> Configuration { get; set; }
    
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        // Configure encryption for sensitive fields
        var protector = _dataProtection.CreateProtector("Fuzzbin.Encryption");
        
        foreach (var entityType in modelBuilder.Model.GetEntityTypes())
        {
            foreach (var property in entityType.GetProperties())
            {
                var attributes = property.PropertyInfo?.GetCustomAttributes(
                    typeof(EncryptedAttribute), false);
                    
                if (attributes?.Any() == true)
                {
                    property.SetValueConverter(
                        new EncryptedStringConverter(protector));
                }
            }
        }
        
        // Seed initial configuration
        modelBuilder.Entity<SystemConfiguration>().HasData(
            new SystemConfiguration 
            { 
                Id = 1,
                LastModified = DateTime.UtcNow,
                JwtSecret = GenerateSecureKey()
            });
    }
}
```

#### 1.4 Configuration Service

```csharp
// Services/ConfigurationService.cs
public interface IConfigurationService
{
    Task<SystemConfiguration> GetConfigurationAsync();
    Task UpdateConfigurationAsync(SystemConfiguration config);
    Task<bool> IsSystemInitializedAsync();
    Task InitializeSystemAsync(SystemInitDto initDto);
}

public class ConfigurationService : IConfigurationService
{
    private readonly FuzzbinDbContext _context;
    private readonly IMemoryCache _cache;
    
    public async Task<SystemConfiguration> GetConfigurationAsync()
    {
        return await _cache.GetOrCreateAsync("system_config", async entry =>
        {
            entry.SlidingExpiration = TimeSpan.FromMinutes(5);
            return await _context.Configuration
                .FirstOrDefaultAsync(c => c.Id == 1);
        });
    }
    
    public async Task UpdateConfigurationAsync(SystemConfiguration config)
    {
        config.LastModified = DateTime.UtcNow;
        _context.Configuration.Update(config);
        await _context.SaveChangesAsync();
        _cache.Remove("system_config");
    }
}
```

### Phase 2: First-Run Setup (Week 1)

#### 2.1 Setup Wizard Component

```razor
@* Components/Pages/Setup.razor *@
@page "/setup"
@layout EmptyLayout
@inject IConfigurationService ConfigService
@inject NavigationManager NavigationManager

@if (!IsInitialized)
{
    <MudContainer MaxWidth="MaxWidth.Small" Class="mt-8">
        <MudCard>
            <MudCardContent>
                <MudText Typo="Typo.h4">Welcome to Fuzzbin</MudText>
                
                <MudStepper @ref="stepper">
                    <MudStep Title="Admin Account">
                        <MudTextField Label="Admin Email" 
                                    @bind-Value="InitData.AdminEmail"
                                    Required="true"
                                    InputType="InputType.Email" />
                        <MudTextField Label="Admin Password" 
                                    @bind-Value="InitData.AdminPassword"
                                    Required="true"
                                    InputType="InputType.Password" />
                    </MudStep>
                    
                    <MudStep Title="Storage">
                        <MudTextField Label="Media Path" 
                                    @bind-Value="InitData.MediaPath"
                                    HelperText="Where videos are stored" />
                        <MudNumericField Label="Max Storage (GB)" 
                                       @bind-Value="MaxStorageGB"
                                       Min="10" Max="10000" />
                    </MudStep>
                    
                    <MudStep Title="API Keys (Optional)">
                        <MudAlert Severity="Severity.Info">
                            You can add these later in Settings
                        </MudAlert>
                        <MudTextField Label="IMVDb API Key"
                                    @bind-Value="InitData.ImvdbApiKey"
                                    InputType="InputType.Password" />
                    </MudStep>
                    
                    <MudStep Title="Complete">
                        <MudButton Color="Color.Primary" 
                                 Variant="Variant.Filled"
                                 OnClick="CompleteSetup">
                            Initialize System
                        </MudButton>
                    </MudStep>
                </MudStepper>
            </MudCardContent>
        </MudCard>
    </MudContainer>
}

@code {
    private SystemInitDto InitData = new();
    private int MaxStorageGB = 500;
    
    protected override async Task OnInitializedAsync()
    {
        IsInitialized = await ConfigService.IsSystemInitializedAsync();
        if (IsInitialized)
        {
            NavigationManager.NavigateTo("/");
        }
    }
    
    private async Task CompleteSetup()
    {
        InitData.MaxStorageBytes = MaxStorageGB * 1_073_741_824L;
        await ConfigService.InitializeSystemAsync(InitData);
        NavigationManager.NavigateTo("/");
    }
}
```

#### 2.2 Program.cs Setup

```csharp
// Program.cs
var builder = WebApplication.CreateBuilder(args);

// Configure SQLite
var dataPath = Path.Combine(
    Environment.GetEnvironmentVariable("DATA_PATH") ?? "/data",
    "fuzzbin.db");
    
builder.Services.AddDbContext<FuzzbinDbContext>(options =>
    options.UseSqlite($"Data Source={dataPath}"));

// Add Data Protection
builder.Services.AddDataProtection()
    .PersistKeysToFileSystem(new DirectoryInfo("/data/keys"))
    .SetApplicationName("Fuzzbin");

// Add services
builder.Services.AddScoped<IConfigurationService, ConfigurationService>();
builder.Services.AddMemoryCache();

// Add Blazor and SignalR
builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();
builder.Services.AddSignalR();

// Add MudBlazor
builder.Services.AddMudServices();

var app = builder.Build();

// Ensure database exists
using (var scope = app.Services.CreateScope())
{
    var context = scope.ServiceProvider
        .GetRequiredService<FuzzbinDbContext>();
    await context.Database.MigrateAsync();
}

// Redirect to setup if not initialized
app.Use(async (context, next) =>
{
    var configService = context.RequestServices
        .GetRequiredService<IConfigurationService>();
        
    if (!await configService.IsSystemInitializedAsync() 
        && !context.Request.Path.StartsWithSegments("/setup"))
    {
        context.Response.Redirect("/setup");
        return;
    }
    
    await next();
});

app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();
app.MapHub<DownloadHub>("/hubs/download");

await app.RunAsync();
```

### Phase 3: Core Features (Week 2)

#### 3.1 NFO Generation and File Organization

```csharp
// Services/NfoGeneratorService.cs
public class NfoGeneratorService
{
    private readonly IConfigurationService _configService;
    
    public async Task<XDocument> GenerateVideoNfoAsync(Video video)
    {
        var config = await _configService.GetConfigurationAsync();
        
        // Build artist string based on configuration
        var artistString = video.Artist;
        if (video.FeaturedArtists?.Any() == true && config.IncludeFeaturedArtistsInArtist)
        {
            artistString += config.FeaturedArtistSeparator +
                string.Join(", ", video.FeaturedArtists);
        }
        
        // Build title string based on configuration
        var titleString = video.Title;
        if (video.FeaturedArtists?.Any() == true && config.IncludeFeaturedArtistsInTitle)
        {
            titleString += config.FeaturedArtistSeparator +
                string.Join(", ", video.FeaturedArtists);
        }
        
        // Select genre based on configuration
        var genreValue = config.GenreSpecificity == GenreSpecificity.Specific
            ? video.SpecificGenre ?? video.Genre
            : video.BroadGenre ?? video.Genre;
            
        // Select label based on configuration
        var labelValue = config.LabelDisplay == LabelDisplay.Direct
            ? video.Label
            : video.ParentLabel ?? video.Label;
        
        return new XDocument(
            new XDeclaration("1.0", "UTF-8", "yes"),
            new XElement("musicvideo",
                new XElement("title", titleString),
                new XElement("artist", artistString),
                new XElement("album", video.Album),
                new XElement("year", video.Year),
                new XElement("genre", genreValue),
                new XElement("director", video.Director),
                new XElement("studio", video.Studio),
                new XElement("label", labelValue),
                new XElement("runtime", video.Duration?.TotalSeconds)
            ));
    }
}

// Services/FileOrganizationService.cs
public class FileOrganizationService
{
    private readonly IConfigurationService _configService;
    
    public async Task<string> GenerateFilePathAsync(Video video)
    {
        var config = await _configService.GetConfigurationAsync();
        
        // Process patterns with variable substitution
        var directoryPath = await ProcessPatternAsync(
            config.DirectoryNamingPattern, video);
        var filename = await ProcessPatternAsync(
            config.FileNamingPattern, video);
        
        // Add extension and sanitize
        var extension = Path.GetExtension(video.FilePath) ?? ".mp4";
        filename = Path.ChangeExtension(filename, extension);
        
        if (config.SanitizeFilenames)
        {
            directoryPath = SanitizePath(directoryPath, config.InvalidCharacterReplacement);
            filename = SanitizeFilename(filename, config.InvalidCharacterReplacement);
        }
        
        return Path.Combine(config.MediaPath, directoryPath, filename);
    }
    
    private async Task<string> ProcessPatternAsync(string pattern, Video video)
    {
        var config = await _configService.GetConfigurationAsync();
        
        // Available metadata variables
        var replacements = new Dictionary<string, string>
        {
            {"{artist}", video.Artist},
            {"{title}", video.Title},
            {"{album}", video.Album ?? ""},
            {"{year}", video.Year?.ToString() ?? ""},
            {"{genre}", video.Genre ?? ""},
            {"{director}", video.Director ?? ""},
            {"{studio}", video.Studio ?? ""},
            {"{label}", video.Label ?? ""},
            {"{featured}", string.Join(", ", video.FeaturedArtists ?? new List<string>())},
            {"{artist_full}", GetFullArtistString(video, config)},
            {"{quality}", video.Metadata?["quality"]?.ToString() ?? "HD"}
        };
        
        // Replace all variables in pattern
        foreach (var kvp in replacements)
        {
            pattern = pattern.Replace(kvp.Key, kvp.Value);
        }
        
        return pattern.Trim();
    }
    
    private string GetFullArtistString(Video video, SystemConfiguration config)
    {
        if (video.FeaturedArtists?.Any() == true && config.IncludeFeaturedArtistsInArtist)
        {
            return video.Artist + config.FeaturedArtistSeparator +
                string.Join(", ", video.FeaturedArtists);
        }
        return video.Artist;
    }
    
    private string SanitizePath(string path, string replacement)
    {
        var invalidChars = Path.GetInvalidPathChars();
        foreach (var c in invalidChars)
        {
            path = path.Replace(c.ToString(), replacement);
        }
        return path;
    }
    
    private string SanitizeFilename(string filename, string replacement)
    {
        var invalidChars = Path.GetInvalidFileNameChars();
        foreach (var c in invalidChars)
        {
            filename = filename.Replace(c.ToString(), replacement);
        }
        
        // Ensure filename isn't too long
        if (filename.Length > 255)
        {
            var ext = Path.GetExtension(filename);
            var name = Path.GetFileNameWithoutExtension(filename);
            filename = name.Substring(0, 255 - ext.Length) + ext;
        }
        
        return filename;
    }
}
```

#### 3.2 Collection Import Service

```csharp
// Services/CollectionImportService.cs
public class CollectionImportService
{
    private readonly IVideoService _videoService;
    private readonly IMetadataService _metadataService;
    private readonly ILogger<CollectionImportService> _logger;
    
    public async Task<ImportResult> ImportCollectionAsync(string basePath)
    {
        var result = new ImportResult();
        var videoExtensions = new[] { ".mp4", ".mkv", ".avi", ".mov", ".webm" };
        
        // Scan for video files
        var videoFiles = Directory.GetFiles(basePath, "*.*", SearchOption.AllDirectories)
            .Where(f => videoExtensions.Contains(Path.GetExtension(f).ToLower()));
            
        foreach (var videoFile in videoFiles)
        {
            try
            {
                // Check for existing NFO file
                var nfoPath = Path.ChangeExtension(videoFile, ".nfo");
                Video video = null;
                
                if (File.Exists(nfoPath))

#### 3.2 Metadata Services Integration

```csharp
// Services/ImvdbService.cs
public class ImvdbService : IImvdbService
{
    private readonly HttpClient _httpClient;
    private readonly IConfigurationService _configService;
    private readonly ILogger<ImvdbService> _logger;
    
    public ImvdbService(HttpClient httpClient, 
        IConfigurationService configService,
        ILogger<ImvdbService> logger)
    {
        _httpClient = httpClient;
        _configService = configService;
        _logger = logger;
    }
    
    public async Task<ImvdbSearchResult> SearchVideosAsync(string artist, string title)
    {
        try
        {
            var config = await _configService.GetConfigurationAsync();
            if (string.IsNullOrEmpty(config.ImvdbApiKey))
            {
                _logger.LogWarning("IMVDb API key not configured");
                return null;
            }
            
            _httpClient.DefaultRequestHeaders.Clear();
            _httpClient.DefaultRequestHeaders.Add("IMVDB-APP-KEY", config.ImvdbApiKey);
            
            var query = Uri.EscapeDataString($"{artist} {title}");
            var response = await _httpClient.GetAsync(
                $"https://imvdb.com/api/v1/search/videos?q={query}");
                
            if (response.IsSuccessStatusCode)
            {
                return await response.Content.ReadFromJsonAsync<ImvdbSearchResult>();
            }
            
            _logger.LogWarning("IMVDb search failed: {Status}", response.StatusCode);
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error searching IMVDb for {Artist} - {Title}", artist, title);
            return null;
        }
    }
}

// Services/MusicBrainzService.cs
public class MusicBrainzService : IMusicBrainzService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<MusicBrainzService> _logger;
    private readonly SemaphoreSlim _rateLimiter;
    
    public MusicBrainzService(HttpClient httpClient, ILogger<MusicBrainzService> logger)
    {
        _httpClient = httpClient;
        _httpClient.DefaultRequestHeaders.Add("User-Agent", 
            "Fuzzbin/1.0 (https://github.com/fuzzbin/fuzzbin)");
        _logger = logger;
        _rateLimiter = new SemaphoreSlim(1, 1); // MusicBrainz requires 1 req/sec
    }
    
    public async Task<MusicBrainzRecording> SearchRecordingAsync(string artist, string title)
    {
        await _rateLimiter.WaitAsync();
        try
        {
            await Task.Delay(1000); // Rate limiting
            
            var query = Uri.EscapeDataString($"artist:\"{artist}\" AND recording:\"{title}\"");
            var url = $"https://musicbrainz.org/ws/2/recording?" +
                     $"query={query}&fmt=json&inc=artist-credits+releases+genres+labels";
            
            var response = await _httpClient.GetAsync(url);
            if (response.IsSuccessStatusCode)
            {
                var result = await response.Content.ReadFromJsonAsync<MusicBrainzSearchResult>();
                return result?.Recordings?.FirstOrDefault();
            }
            
            _logger.LogWarning("MusicBrainz search failed: {Status}", response.StatusCode);
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error searching MusicBrainz for {Artist} - {Title}", 
                artist, title);
            return null;
        }
        finally
        {
            _rateLimiter.Release();
        }
    }
}

// Services/MetadataService.cs - Unified service
public class MetadataService : IMetadataService
{
    private readonly IImvdbService _imvdbService;
    private readonly IMusicBrainzService _musicBrainzService;
    private readonly ILogger<MetadataService> _logger;
    
    public MetadataService(
        IImvdbService imvdbService,
        IMusicBrainzService musicBrainzService,
        ILogger<MetadataService> logger)
    {
        _imvdbService = imvdbService;
        _musicBrainzService = musicBrainzService;
        _logger = logger;
    }
    
    public async Task<VideoMetadata> GetCompleteMetadataAsync(string artist, string title)
    {
        var metadata = new VideoMetadata
        {
            SearchArtist = artist,
            SearchTitle = title
        };
        
        // Get video metadata from IMVDb (year, artist, title, director, sources)
        var imvdbTask = GetImvdbMetadataAsync(artist, title);
        
        // Get audio metadata from MusicBrainz (featured artists, album, genre, label)
        var musicBrainzTask = GetMusicBrainzMetadataAsync(artist, title);
        
        // Run both API calls in parallel
        await Task.WhenAll(imvdbTask, musicBrainzTask);
        
        // Merge results
        var imvdbData = await imvdbTask;
        var mbData = await musicBrainzTask;
        
        // IMVDb provides primary video metadata
        if (imvdbData != null)
        {
            metadata.Year = imvdbData.Year;
            metadata.PrimaryArtist = imvdbData.PrimaryArtist;
            metadata.Title = imvdbData.Title;
            metadata.Directors = imvdbData.Directors;
            metadata.VideoSources = imvdbData.VideoSources;
            metadata.ImvdbId = imvdbData.ImvdbId;
            metadata.ImvdbUrl = imvdbData.ImvdbUrl;
            metadata.ThumbnailUrl = imvdbData.ThumbnailUrl;
        }
        
        // MusicBrainz provides audio metadata
        if (mbData != null)
        {
            metadata.FeaturedArtists = mbData.FeaturedArtists;
            metadata.Album = mbData.Album;
            metadata.Genres = mbData.Genres;
            metadata.SpecificGenre = mbData.SpecificGenre;
            metadata.BroadGenre = mbData.BroadGenre;
            metadata.Label = mbData.Label;
            metadata.ParentLabel = mbData.ParentLabel;
        }
        
        return metadata;
    }
    
    private async Task<VideoMetadata> GetImvdbMetadataAsync(string artist, string title)
    {
        try
        {
            var result = await _imvdbService.SearchVideosAsync(artist, title);
            if (result?.Results?.Any() == true)
            {
                var video = result.Results.First();
                return new VideoMetadata
                {
                    Year = video.Year,
                    PrimaryArtist = video.Artists?.FirstOrDefault()?.Name ?? artist,
                    Title = video.Title ?? title,
                    Directors = video.Directors?.Select(d => d.Name).ToList(),
                    ImvdbId = video.Id,
                    ImvdbUrl = video.ImvdbUrl,
                    ThumbnailUrl = video.Image?.Url
                };
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get IMVDb metadata");
        }
        
        return null;
    }
    
    private async Task<VideoMetadata> GetMusicBrainzMetadataAsync(string artist, string title)
    {
        try
        {
            var recording = await _musicBrainzService.SearchRecordingAsync(artist, title);
            if (recording != null)
            {
                var metadata = new VideoMetadata();
                
                // Extract featured artists
                if (recording.ArtistCredits?.Count > 1)
                {
                    metadata.FeaturedArtists = recording.ArtistCredits
                        .Skip(1)
                        .Select(ac => ac.Name)
                        .ToList();
                }
                
                // Get album and label from releases
                if (recording.Releases?.Any() == true)
                {
                    var release = recording.Releases.First();
                    metadata.Album = release.Title;
                    
                    if (release.LabelInfo?.Any() == true)
                    {
                        metadata.Label = release.LabelInfo.First().Label?.Name;
                    }
                }
                
                // Extract genres
                if (recording.Tags?.Any() == true)
                {
                    metadata.Genres = recording.Tags
                        .OrderByDescending(t => t.Count)
                        .Select(t => t.Name)
                        .ToList();
                    metadata.SpecificGenre = metadata.Genres.FirstOrDefault();
                    metadata.BroadGenre = MapToBroadGenre(metadata.SpecificGenre);
                }
                
                return metadata;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get MusicBrainz metadata");
        }
        
        return null;
    }
    
    private string MapToBroadGenre(string specificGenre)
    {
        if (string.IsNullOrEmpty(specificGenre))
            return "Unknown";
            
        var genreMap = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["crunk"] = "Hip Hop/R&B",
            ["trap"] = "Hip Hop/R&B",
            ["hip hop"] = "Hip Hop/R&B",
            ["post-grunge"] = "Rock",
            ["indie rock"] = "Rock",
            ["house"] = "Electronic",
            ["techno"] = "Electronic",
            ["k-pop"] = "Pop",
            ["j-pop"] = "Pop"
        };
        
        foreach (var mapping in genreMap)
        {
            if (specificGenre.Contains(mapping.Key, StringComparison.OrdinalIgnoreCase))
            {
                return mapping.Value;
            }

#### 3.3 NFO Generation with Featured Artists

```csharp
// Services/NfoService.cs
public class NfoService : INfoService
{
    private readonly ILogger<NfoService> _logger;
    
    public NfoService(ILogger<NfoService> logger)
    {
        _logger = logger;
    }
    
    public async Task<string> GenerateNfoAsync(Video video)
    {
        var doc = new XDocument(
            new XElement("musicvideo",
                // Basic metadata
                new XElement("title", video.Title),
                new XElement("year", video.Year?.ToString() ?? ""),
                new XElement("premiered", video.Year?.ToString() ?? ""),
                
                // Primary artist
                new XElement("artist", video.PrimaryArtist),
                
                // Featured artists as separate artist tags
                video.FeaturedArtists?.Select(fa => new XElement("artist", fa)) ?? Enumerable.Empty<XElement>(),
                
                // Album information
                new XElement("album", video.Album ?? ""),
                
                // Directors
                video.Directors?.Select(d => new XElement("director", d)) ?? Enumerable.Empty<XElement>(),
                
                // Genre tags
                new XElement("genre", video.BroadGenre ?? "Unknown"),
                video.SpecificGenre != null ? new XElement("tag", video.SpecificGenre) : null,
                video.Genres?.Select(g => new XElement("tag", g)) ?? Enumerable.Empty<XElement>(),
                
                // Label information
                new XElement("studio", video.Label ?? ""),
                video.ParentLabel != null ? new XElement("studio", video.ParentLabel) : null,
                
                // Sources
                video.VideoSources?.Select(s => new XElement("source", s)) ?? Enumerable.Empty<XElement>(),
                
                // External IDs
                video.ImvdbId != null ? new XElement("imvdbid", video.ImvdbId) : null,
                video.ImvdbUrl != null ? new XElement("imvdburl", video.ImvdbUrl) : null,
                
                // File information
                new XElement("fileinfo",
                    new XElement("duration", video.Duration?.ToString(@"mm\:ss") ?? ""),
                    new XElement("videocodec", video.VideoCodec ?? ""),
                    new XElement("audiocodec", video.AudioCodec ?? ""),
                    new XElement("width", video.Width?.ToString() ?? ""),
                    new XElement("height", video.Height?.ToString() ?? ""),
                    new XElement("aspectratio", video.AspectRatio ?? "")
                ),
                
                // Thumbnail
                video.ThumbnailUrl != null ? new XElement("thumb", video.ThumbnailUrl) : null,
                
                // Custom tags
                video.Tags?.Select(t => new XElement("tag", t)) ?? Enumerable.Empty<XElement>(),
                
                // Date added
                new XElement("dateadded", video.DateAdded.ToString("yyyy-MM-dd HH:mm:ss"))
            )
        );
        
        // Remove null elements
        doc.Descendants()
            .Where(e => e.IsEmpty && !e.HasAttributes)
            .Remove();
        
        return doc.ToString();
    }
    
    public async Task<Video> ParseNfoAsync(string nfoContent)
    {
        try
        {
            var doc = XDocument.Parse(nfoContent);
            var root = doc.Root;
            
            if (root?.Name.LocalName != "musicvideo")
            {
                _logger.LogWarning("Invalid NFO format: root element is not 'musicvideo'");
                return null;
            }
            
            var video = new Video
            {
                Title = root.Element("title")?.Value,
                PrimaryArtist = root.Elements("artist").FirstOrDefault()?.Value,
                Album = root.Element("album")?.Value,
                BroadGenre = root.Element("genre")?.Value,
                Label = root.Elements("studio").FirstOrDefault()?.Value,
                ImvdbId = root.Element("imvdbid")?.Value,
                ImvdbUrl = root.Element("imvdburl")?.Value,
                ThumbnailUrl = root.Element("thumb")?.Value
            };
            
            // Parse year
            if (int.TryParse(root.Element("year")?.Value, out var year))
            {
                video.Year = year;
            }
            
            // Parse featured artists (all artist tags except the first)
            var allArtists = root.Elements("artist").Select(e => e.Value).ToList();
            if (allArtists.Count > 1)
            {
                video.FeaturedArtists = allArtists.Skip(1).ToList();
            }
            
            // Parse directors
            var directors = root.Elements("director").Select(e => e.Value).ToList();
            if (directors.Any())
            {
                video.Directors = directors;
            }
            
            // Parse tags (includes specific genre)
            var tags = root.Elements("tag").Select(e => e.Value).ToList();
            if (tags.Any())
            {
                video.Tags = tags;
                video.SpecificGenre = tags.FirstOrDefault();
            }
            
            // Parse all genres
            var genres = root.Elements("tag")
                .Union(root.Elements("genre"))
                .Select(e => e.Value)
                .Distinct()
                .ToList();
            if (genres.Any())
            {
                video.Genres = genres;
            }
            
            // Parse studios (label and parent label)
            var studios = root.Elements("studio").Select(e => e.Value).ToList();
            if (studios.Count > 1)
            {
                video.ParentLabel = studios[1];
            }
            
            // Parse sources
            var sources = root.Elements("source").Select(e => e.Value).ToList();
            if (sources.Any())
            {
                video.VideoSources = sources;
            }
            
            // Parse file information
            var fileInfo = root.Element("fileinfo");
            if (fileInfo != null)
            {
                if (TimeSpan.TryParse(fileInfo.Element("duration")?.Value, out var duration))
                {
                    video.Duration = duration;
                }
                
                video.VideoCodec = fileInfo.Element("videocodec")?.Value;
                video.AudioCodec = fileInfo.Element("audiocodec")?.Value;
                
                if (int.TryParse(fileInfo.Element("width")?.Value, out var width))
                {
                    video.Width = width;
                }
                
                if (int.TryParse(fileInfo.Element("height")?.Value, out var height))
                {
                    video.Height = height;
                }
                
                video.AspectRatio = fileInfo.Element("aspectratio")?.Value;
            }
            
            // Parse date added
            if (DateTime.TryParse(root.Element("dateadded")?.Value, out var dateAdded))
            {
                video.DateAdded = dateAdded;
            }
            
            return video;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to parse NFO content");
            return null;
        }
    }
    
    public async Task SaveNfoAsync(Video video)
    {
        try
        {
            var nfoContent = await GenerateNfoAsync(video);
            var nfoPath = Path.ChangeExtension(video.FilePath, ".nfo");
            await File.WriteAllTextAsync(nfoPath, nfoContent);
            _logger.LogInformation("Saved NFO for {Title} to {Path}", video.Title, nfoPath);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to save NFO for video {Id}", video.Id);
            throw;
        }
    }
    
    public async Task<bool> LoadNfoAsync(Video video)
    {
        try
        {
            var nfoPath = Path.ChangeExtension(video.FilePath, ".nfo");
            if (!File.Exists(nfoPath))
            {
                _logger.LogDebug("No NFO file found for {Path}", video.FilePath);
                return false;
            }
            
            var nfoContent = await File.ReadAllTextAsync(nfoPath);
            var parsedVideo = await ParseNfoAsync(nfoContent);
            
            if (parsedVideo == null)
            {
                _logger.LogWarning("Failed to parse NFO for {Path}", nfoPath);
                return false;
            }
            
            // Update video with parsed data
            video.Title = parsedVideo.Title ?? video.Title;
            video.PrimaryArtist = parsedVideo.PrimaryArtist ?? video.PrimaryArtist;
            video.FeaturedArtists = parsedVideo.FeaturedArtists ?? video.FeaturedArtists;
            video.Album = parsedVideo.Album ?? video.Album;
            video.Year = parsedVideo.Year ?? video.Year;
            video.Directors = parsedVideo.Directors ?? video.Directors;
            video.BroadGenre = parsedVideo.BroadGenre ?? video.BroadGenre;
            video.SpecificGenre = parsedVideo.SpecificGenre ?? video.SpecificGenre;
            video.Genres = parsedVideo.Genres ?? video.Genres;
            video.Label = parsedVideo.Label ?? video.Label;
            video.ParentLabel = parsedVideo.ParentLabel ?? video.ParentLabel;
            video.VideoSources = parsedVideo.VideoSources ?? video.VideoSources;
            video.ImvdbId = parsedVideo.ImvdbId ?? video.ImvdbId;
            video.ImvdbUrl = parsedVideo.ImvdbUrl ?? video.ImvdbUrl;
            video.ThumbnailUrl = parsedVideo.ThumbnailUrl ?? video.ThumbnailUrl;
            video.Tags = parsedVideo.Tags ?? video.Tags;
            
            // Update file info if available
            if (parsedVideo.Duration.HasValue)
                video.Duration = parsedVideo.Duration;
            if (!string.IsNullOrEmpty(parsedVideo.VideoCodec))
                video.VideoCodec = parsedVideo.VideoCodec;
            if (!string.IsNullOrEmpty(parsedVideo.AudioCodec))
                video.AudioCodec = parsedVideo.AudioCodec;
            if (parsedVideo.Width.HasValue)
                video.Width = parsedVideo.Width;
            if (parsedVideo.Height.HasValue)
                video.Height = parsedVideo.Height;
            if (!string.IsNullOrEmpty(parsedVideo.AspectRatio))
                video.AspectRatio = parsedVideo.AspectRatio;
            
            _logger.LogInformation("Loaded NFO data for {Title}", video.Title);
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to load NFO for video {Id}", video.Id);
            return false;
        }
    }
}
```
        }
        
        return specificGenre;
    }
}

// Program.cs - Register services
builder.Services.AddHttpClient<IImvdbService, ImvdbService>();
builder.Services.AddHttpClient<IMusicBrainzService, MusicBrainzService>();
builder.Services.AddScoped<IMetadataService, MetadataService>();
```
                {
                    // Parse existing NFO
                    video = await ParseNfoFileAsync(nfoPath);
                    video.FilePath = videoFile;
                }
                else
                {
                    // Parse from filename
                    video = ParseFromFilename(videoFile);
                }
                
                // Try to get complete metadata from IMVDb + MusicBrainz
                var metadata = await _metadataService.GetCompleteMetadataAsync(
                    video.Artist, video.Title);
                    
                if (metadata != null && (metadata.ImvdbId.HasValue || !string.IsNullOrEmpty(metadata.Album)))
                {
                    // Merge enriched metadata into video
                    video = await _metadataService.MergeMetadataIntoVideo(video, metadata);
                    result.MatchedCount++;
                }
                else
                {
                    result.UnmatchedVideos.Add(video);
                }
                
                await _videoService.CreateVideoAsync(video);
                result.ImportedCount++;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to import {File}", videoFile);
                result.Errors.Add($"{videoFile}: {ex.Message}");
            }
        }
        
        return result;
    }
    
    public async Task<Video> ParseNfoFileAsync(string nfoPath)
    {
        var doc = XDocument.Load(nfoPath);
        var root = doc.Root;
        
        return new Video
        {
            Title = root.Element("title")?.Value,
            Artist = root.Element("artist")?.Value,
            Album = root.Element("album")?.Value,
            Year = int.TryParse(root.Element("year")?.Value, out var year) ? year : null,
            Genre = root.Element("genre")?.Value,
            Director = root.Element("director")?.Value,
            Studio = root.Element("studio")?.Value,
            Label = root.Element("label")?.Value
        };
    }
    
    public Video ParseFromFilename(string filepath)
    {
        var filename = Path.GetFileNameWithoutExtension(filepath);
        var video = new Video { FilePath = filepath };
        
        // Common patterns to try
        var patterns = new[]
        {
            @"^(?<artist>[^-]+)\s*-\s*(?<title>[^(]+)(?:\((?<year>\d{4})\))?",
            @"^(?<artist>[^-]+)\s*-\s*(?<title>.+)",
            @"^(?<title>.+)$"
        };
        
        foreach (var pattern in patterns)
        {
            var match = Regex.Match(filename, pattern);
            if (match.Success)
            {
                video.Artist = match.Groups["artist"]?.Value?.Trim() ?? "Unknown Artist";
                video.Title = match.Groups["title"]?.Value?.Trim() ?? filename;
                if (int.TryParse(match.Groups["year"]?.Value, out var year))
                {
                    video.Year = year;
                }
                break;
            }
        }
        
        return video;
    }
    
}
```

#### 3.3 File Reorganization Service

```csharp
// Services/FileReorganizationService.cs
public class FileReorganizationService
{
    private readonly IFileOrganizationService _fileOrgService;
    private readonly IVideoService _videoService;
    private readonly INfoGeneratorService _nfoService;
    private readonly ILogger<FileReorganizationService> _logger;
    
    public async Task<ReorganizeResult> ReorganizeCollectionAsync(bool preview = false)
    {
        var result = new ReorganizeResult();
        var videos = await _videoService.GetAllVideosAsync();
        
        foreach (var video in videos)
        {
            try
            {
                var currentPath = video.FilePath;
                var newPath = await _fileOrgService.GenerateFilePathAsync(video);
                
                if (currentPath != newPath)
                {
                    result.Changes.Add(new FileChange
                    {
                        VideoId = video.Id,
                        OldPath = currentPath,
                        NewPath = newPath
                    });
                    
                    if (!preview)
                    {
                        // Create directory if needed
                        var newDir = Path.GetDirectoryName(newPath);
                        Directory.CreateDirectory(newDir);
                        
                        // Move video file
                        File.Move(currentPath, newPath);
                        
                        // Generate and save NFO
                        var nfo = await _nfoService.GenerateVideoNfoAsync(video);
                        var nfoPath = Path.ChangeExtension(newPath, ".nfo");
                        nfo.Save(nfoPath);
                        
                        // Move thumbnail if exists
                        if (!string.IsNullOrEmpty(video.ThumbnailPath) && File.Exists(video.ThumbnailPath))
                        {
                            var newThumbPath = Path.ChangeExtension(newPath, ".jpg");

### Phase 6: Collection Management UI (Week 3)

#### 6.1 Collection Import Page

```razor
@* Components/Pages/Collection/Import.razor *@
@page "/collection/import"
@attribute [Authorize]
@inject ICollectionImportService ImportService
@inject ISnackbar Snackbar

<MudContainer>
    <MudText Typo="Typo.h4" Class="mb-4">Import Collection</MudText>
    
    <MudCard>
        <MudCardContent>
            <MudTextField @bind-Value="ImportPath" 
                Label="Collection Path" 
                HelperText="Path to your existing video collection"
                Variant="Variant.Outlined" />
                
            <MudButton Color="Color.Primary" 
                OnClick="ScanCollection"
                StartIcon="@Icons.Material.Filled.Search"
                Class="mt-3">
                Scan Collection
            </MudButton>
        </MudCardContent>
    </MudCard>
    
    @if (ScanResults != null)
    {
        <MudCard Class="mt-4">
            <MudCardContent>
                <MudText Typo="Typo.h6">Scan Results</MudText>
                <MudText Typo="Typo.body2" Class="mb-3">
                    Found @ScanResults.Count videos. @MatchedCount matched with IMVDb.
                </MudText>
                
                <MudDataGrid T="ImportPreviewItem" 
                    Items="@ScanResults"
                    MultiSelection="true"
                    @bind-SelectedItems="SelectedItems">
                    <Columns>
                        <SelectColumn T="ImportPreviewItem" />
                        <PropertyColumn Property="x => x.FileName" Title="File" />
                        <TemplateColumn Title="Artist">
                            <CellTemplate>
                                <MudTextField @bind-Value="context.Item.Artist" 
                                    Variant="Variant.Text" Margin="Margin.Dense" />
                            </CellTemplate>
                        </TemplateColumn>
                        <TemplateColumn Title="Title">
                            <CellTemplate>
                                <MudTextField @bind-Value="context.Item.Title" 
                                    Variant="Variant.Text" Margin="Margin.Dense" />
                            </CellTemplate>
                        </TemplateColumn>
                        <TemplateColumn Title="IMVDb Match">
                            <CellTemplate>
                                @if (context.Item.ImvdbMatch != null)
                                {
                                    <MudChip Color="Color.Success" Size="Size.Small">
                                        Matched
                                    </MudChip>
                                }
                                else
                                {
                                    <MudChip Color="Color.Warning" Size="Size.Small">
                                        No Match
                                    </MudChip>
                                }
                            </CellTemplate>
                        </TemplateColumn>
                        <TemplateColumn Title="Actions">
                            <CellTemplate>
                                <MudIconButton Icon="@Icons.Material.Filled.Search"
                                    Size="Size.Small"
                                    OnClick="() => SearchImvdb(context.Item)" />
                            </CellTemplate>
                        </TemplateColumn>
                    </Columns>
                </MudDataGrid>
                
                <MudButton Color="Color.Primary" 
                    OnClick="ImportSelected"
                    StartIcon="@Icons.Material.Filled.Download"
                    Class="mt-4"
                    Disabled="!SelectedItems.Any()">
                    Import @SelectedItems.Count Selected Videos
                </MudButton>
            </MudCardContent>
        </MudCard>
    }
</MudContainer>

@code {
    private string ImportPath = "";
    private List<ImportPreviewItem> ScanResults;
    private HashSet<ImportPreviewItem> SelectedItems = new();
    private int MatchedCount => ScanResults?.Count(x => x.ImvdbMatch != null) ?? 0;
    
    private async Task ScanCollection()
    {
        var preview = await ImportService.PreviewImportAsync(ImportPath);
        ScanResults = preview.Items;
        SelectedItems = new HashSet<ImportPreviewItem>(ScanResults);
    }
    
    private async Task ImportSelected()
    {
        var result = await ImportService.ImportSelectedAsync(SelectedItems.ToList());
        Snackbar.Add($"Imported {result.ImportedCount} videos", Severity.Success);
        NavigationManager.NavigateTo("/collection");
    }
    
    private async Task SearchImvdb(ImportPreviewItem item)
    {
        // Open IMVDb search dialog
        var parameters = new DialogParameters
        {
            ["Artist"] = item.Artist,
            ["Title"] = item.Title
        };
        
        var dialog = await DialogService.ShowAsync<ImvdbSearchDialog>(
            "Search IMVDb", parameters);
        var result = await dialog.Result;
        
        if (!result.Cancelled && result.Data != null)
        {
            item.ImvdbMatch = result.Data as ImvdbMatch;
        }
    }
}
```

#### 6.2 Collection Management Page

```razor
@* Components/Pages/Collection/Index.razor *@
@page "/collection"
@attribute [Authorize]
@inject IVideoService VideoService
@inject ITagManagementService TagService

<MudContainer>
    <MudGrid>
        <MudItem xs="12">
            <MudCard>
                <MudCardContent>
                    <!-- Real-time search -->
                    <MudTextField @bind-Value="SearchQuery"
                        Label="Search Collection"
                        Placeholder="Search by artist or title..."
                        Adornment="Adornment.Start"
                        AdornmentIcon="@Icons.Material.Filled.Search"
                        Immediate="true"
                        DebounceInterval="300"
                        ValueChanged="OnSearchChanged" />
                        
                    <!-- Bulk actions toolbar -->
                    <MudToolBar Class="px-0">
                        <MudCheckBox @bind-Checked="SelectAll" 
                            Label="Select All"
                            CheckedChanged="OnSelectAllChanged" />
                        <MudSpacer />
                        <MudButton Color="Color.Primary"
                            OnClick="ShowBulkTagDialog"
                            StartIcon="@Icons.Material.Filled.Label"
                            Disabled="!HasSelection">
                            Manage Tags
                        </MudButton>
                        <MudButton Color="Color.Secondary"
                            OnClick="ShowReorganizeDialog"
                            StartIcon="@Icons.Material.Filled.DriveFileMove"
                            Disabled="!HasSelection"
                            Class="ml-2">
                            Reorganize Files
                        </MudButton>
                        <MudButton Color="Color.Info"
                            OnClick="RegenerateNfos"
                            StartIcon="@Icons.Material.Filled.Description"
                            Disabled="!HasSelection"
                            Class="ml-2">
                            Regenerate NFOs
                        </MudButton>
                    </MudToolBar>
                </MudCardContent>
            </MudCard>
        </MudItem>
        
        <MudItem xs="12">
            <MudDataGrid T="Video" 
                Items="@FilteredVideos"
                MultiSelection="true"
                @bind-SelectedItems="SelectedVideos"
                Virtualize="true"
                RowsPerPage="50"
                Dense="true">
                <Columns>
                    <SelectColumn T="Video" />
                    <PropertyColumn Property="x => x.Artist" Title="Artist" />
                    <PropertyColumn Property="x => x.Title" Title="Title" />
                    <PropertyColumn Property="x => x.Album" Title="Album" />
                    <PropertyColumn Property="x => x.Year" Title="Year" />
                    <TemplateColumn Title="Genre">
                        <CellTemplate>
                            <MudTooltip Text="@($"Specific: {context.Item.SpecificGenre ?? "N/A"}")">
                                <MudText>@context.Item.Genre</MudText>
                            </MudTooltip>
                        </CellTemplate>
                    </TemplateColumn>
                    <TemplateColumn Title="Tags">
                        <CellTemplate>
                            @if (context.Item.Tags?.Any() == true)
                            {
                                @foreach (var tag in context.Item.Tags)
                                {
                                    <MudChip Size="Size.Small" Class="ma-1">@tag</MudChip>
                                }
                            }
                        </CellTemplate>
                    </TemplateColumn>
                    <TemplateColumn Title="Actions">
                        <CellTemplate>
                            <MudIconButton Icon="@Icons.Material.Filled.Edit"
                                Size="Size.Small"
                                OnClick="() => EditVideo(context.Item)" />
                            <MudIconButton Icon="@Icons.Material.Filled.PlayArrow"
                                Size="Size.Small"
                                OnClick="() => PlayVideo(context.Item)" />
                        </CellTemplate>
                    </TemplateColumn>
                </Columns>
            </MudDataGrid>
        </MudItem>
    </MudGrid>
</MudContainer>

<!-- Bulk Tag Management Dialog -->
<MudDialog @bind-IsVisible="ShowTagDialog">
    <TitleContent>
        <MudText Typo="Typo.h6">
            Manage Tags for @SelectedVideos.Count Videos
        </MudText>
    </TitleContent>
    <DialogContent>
        <MudText Typo="Typo.body2" Class="mb-3">
            Select tags to add or remove from selected videos
        </MudText>
        
        <MudChipSet @bind-SelectedChips="SelectedTags" 
            MultiSelection="true"
            Filter="true">
            @foreach (var tag in AvailableTags)
            {
                <MudChip Text="@tag" Color="Color.Primary" />
            }
        </MudChipSet>
        
        <MudTextField @bind-Value="NewTag" 
            Label="Add New Tag"
            Placeholder="Enter new tag and press Enter"
            OnKeyDown="@(async (e) => { if (e.Key == "Enter") await AddNewTag(); })"
            Class="mt-3" />
            
        <MudRadioGroup @bind-SelectedOption="TagOperation" Class="mt-3">
            <MudRadio Option="@("add")" Color="Color.Primary">
                Add selected tags
            </MudRadio>
            <MudRadio Option="@("remove")" Color="Color.Secondary">
                Remove selected tags
            </MudRadio>
        </MudRadioGroup>
    </DialogContent>
    <DialogActions>
        <MudButton OnClick="() => ShowTagDialog = false">Cancel</MudButton>
        <MudButton OnClick="ApplyTags" Color="Color.Primary">Apply</MudButton>
    </DialogActions>
</MudDialog>

<!-- File Reorganization Dialog -->
<MudDialog @bind-IsVisible="ShowReorganizeDialog" Options="DialogOptions">
    <TitleContent>
        <MudText Typo="Typo.h6">Reorganize Files</MudText>
    </TitleContent>
    <DialogContent>
        @if (ReorganizePreview == null)
        {
            <MudProgressCircular Indeterminate="true" />
            <MudText>Calculating changes...</MudText>
        }
        else
        {
            <MudText Typo="Typo.body2" Class="mb-3">
                @ReorganizePreview.Changes.Count files will be moved
            </MudText>
            
            <MudSimpleTable Dense="true" Style="max-height: 400px; overflow-y: auto;">
                <thead>
                    <tr>
                        <th>Current Path</th>
                        <th>New Path</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach (var change in ReorganizePreview.Changes.Take(20))
                    {
                        <tr>
                            <td>@GetRelativePath(change.OldPath)</td>
                            <td>@GetRelativePath(change.NewPath)</td>
                        </tr>
                    }
                    @if (ReorganizePreview.Changes.Count > 20)
                    {
                        <tr>
                            <td colspan="2">
                                <MudText Typo="Typo.caption">
                                    ... and @(ReorganizePreview.Changes.Count - 20) more
                                </MudText>
                            </td>
                        </tr>
                    }
                </tbody>
            </MudSimpleTable>
        }
    </DialogContent>
    <DialogActions>
        <MudButton OnClick="() => ShowReorganizeDialog = false">Cancel</MudButton>
        <MudButton OnClick="ExecuteReorganization" 
            Color="Color.Primary"
            Disabled="ReorganizePreview == null">
            Reorganize Files
        </MudButton>
    </DialogActions>
</MudDialog>

@code {
    private string SearchQuery = "";
    private List<Video> FilteredVideos = new();
    private HashSet<Video> SelectedVideos = new();
    private bool SelectAll;
    private bool ShowTagDialog;
    private bool ShowReorganizeDialog;
    private List<string> AvailableTags = new();
    private MudChip[] SelectedTags = Array.Empty<MudChip>();
    private string NewTag = "";
    private string TagOperation = "add";
    private ReorganizeResult ReorganizePreview;
    private bool HasSelection => SelectedVideos.Any();
    
    private DialogOptions DialogOptions = new() 
    { 
        MaxWidth = MaxWidth.Medium,
        FullWidth = true 
    };
    
    protected override async Task OnInitializedAsync()
    {
        await LoadVideos();
        AvailableTags = await TagService.GetAllTagsAsync();
    }
    
    private async Task LoadVideos()
    {
        FilteredVideos = (await VideoService.GetAllVideosAsync()).ToList();
    }
    
    private async Task OnSearchChanged(string value)
    {
        SearchQuery = value;
        if (string.IsNullOrWhiteSpace(SearchQuery))
        {
            await LoadVideos();
        }
        else
        {
            FilteredVideos = (await VideoService.SearchVideosAsync(SearchQuery)).ToList();
        }
    }
    
    private void OnSelectAllChanged(bool value)
    {
        if (value)
        {
            SelectedVideos = new HashSet<Video>(FilteredVideos);
        }
        else
        {
            SelectedVideos.Clear();
        }
    }
    
    private async Task ShowBulkTagDialog()
    {
        ShowTagDialog = true;
    }
    
    private async Task ApplyTags()
    {
        var tags = SelectedTags.Select(c => c.Text).ToList();
        var videoIds = SelectedVideos.Select(v => v.Id).ToList();
        
        if (TagOperation == "add")
        {
            await TagService.AddTagsToVideosAsync(videoIds, tags);
        }
        else
        {
            await TagService.RemoveTagsFromVideosAsync(videoIds, tags);
        }
        
        ShowTagDialog = false;
        await LoadVideos();
        Snackbar.Add($"Tags updated for {videoIds.Count} videos", Severity.Success);
    }
    
    private async Task AddNewTag()
    {
        if (!string.IsNullOrWhiteSpace(NewTag) && !AvailableTags.Contains(NewTag))
        {
            AvailableTags.Add(NewTag);
            NewTag = "";
        }
    }
    
    private async Task ShowReorganizeDialog()
    {
        ShowReorganizeDialog = true;
        ReorganizePreview = await FileReorgService.ReorganizeCollectionAsync(preview: true);
    }
    
    private async Task ExecuteReorganization()
    {
        var result = await FileReorgService.ReorganizeCollectionAsync(preview: false);
        ShowReorganizeDialog = false;
        Snackbar.Add($"Reorganized {result.ProcessedCount} files", Severity.Success);
        await LoadVideos();
    }
    
    private async Task RegenerateNfos()
    {
        foreach (var video in SelectedVideos)
        {
            await NfoService.GenerateAndSaveNfoAsync(video);
        }
        Snackbar.Add($"Regenerated NFOs for {SelectedVideos.Count} videos", Severity.Success);
    }
    
    private string GetRelativePath(string fullPath)
    {
        var basePath = Config.MediaPath;
        return fullPath.StartsWith(basePath) 
            ? fullPath.Substring(basePath.Length).TrimStart('/', '\\')
            : fullPath;
    }
}
```
                            File.Move(video.ThumbnailPath, newThumbPath);
                            video.ThumbnailPath = newThumbPath;
                        }
                        
                        // Update database
                        video.FilePath = newPath;
                        await _videoService.UpdateVideoAsync(video);
                        
                        result.ProcessedCount++;
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to reorganize video {VideoId}", video.Id);
                result.Errors.Add($"Video {video.Title}: {ex.Message}");
            }
        }
        
        return result;
    }
}
```

#### 3.4 Tag Management Service

```csharp
// Services/TagManagementService.cs
public class TagManagementService
{
    private readonly FuzzbinDbContext _context;
    
    public async Task<List<string>> GetAllTagsAsync()
    {
        var videos = await _context.Videos.ToListAsync();
        return videos
            .SelectMany(v => v.Tags ?? new List<string>())
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(t => t)
            .ToList();
    }
    
    public async Task AddTagsToVideosAsync(List<Guid> videoIds, List<string> tags)
    {
        var videos = await _context.Videos
            .Where(v => videoIds.Contains(v.Id))
            .ToListAsync();
            
        foreach (var video in videos)
        {
            video.Tags ??= new List<string>();
            foreach (var tag in tags)
            {
                if (!video.Tags.Contains(tag, StringComparer.OrdinalIgnoreCase))
                {
                    video.Tags.Add(tag);
                }
            }
        }
        
        await _context.SaveChangesAsync();
    }
    
    public async Task RemoveTagsFromVideosAsync(List<Guid> videoIds, List<string> tags)
    {
        var videos = await _context.Videos
            .Where(v => videoIds.Contains(v.Id))
            .ToListAsync();
            
        foreach (var video in videos)
        {
            if (video.Tags != null)
            {
                video.Tags.RemoveAll(t =>
                    tags.Contains(t, StringComparer.OrdinalIgnoreCase));
            }
        }
        
        await _context.SaveChangesAsync();
    }
}
```

#### 3.5 Video Service with Search

```csharp
// Services/VideoService.cs
public class VideoService
{
    private readonly FuzzbinDbContext _context;
    private readonly IConfigurationService _configService;
    
    public async Task<IEnumerable<Video>> GetVideosAsync(Guid userId)
    {
        return await _context.Videos
            .Where(v => v.UserId == userId)
            .OrderByDescending(v => v.CreatedAt)
            .ToListAsync();
    }
    
    public async Task<IEnumerable<Video>> SearchVideosAsync(string query)
    {
        if (string.IsNullOrWhiteSpace(query))
            return await GetAllVideosAsync();
            
        var searchLower = query.ToLower();
        
        return await _context.Videos
            .Where(v =>
                EF.Functions.Like(v.Artist.ToLower(), $"%{searchLower}%") ||
                EF.Functions.Like(v.Title.ToLower(), $"%{searchLower}%"))
            .OrderBy(v => v.Artist)
            .ThenBy(v => v.Title)
            .ToListAsync();
    }
    
    public async Task<Video> CreateVideoAsync(Video video)
    {
        video.Id = Guid.NewGuid();
        video.CreatedAt = DateTime.UtcNow;
        video.Status = DownloadStatus.NotDownloaded;
        
        _context.Videos.Add(video);
        await _context.SaveChangesAsync();
        
        return video;
    }
    
    public async Task UpdateVideoAsync(Video video)
    {
        video.UpdatedAt = DateTime.UtcNow;
        _context.Videos.Update(video);
        await _context.SaveChangesAsync();
    }
    
    public async Task<IEnumerable<Video>> GetAllVideosAsync()
    {
        return await _context.Videos
            .OrderBy(v => v.Artist)
            .ThenBy(v => v.Title)
            .ToListAsync();
    }
}
```

#### 3.6 Download Service

```csharp
// Services/DownloadService.cs
public class DownloadService
{
    private readonly ILogger<DownloadService> _logger;
    private readonly IConfigurationService _configService;
    
    public async Task<bool> DownloadVideoAsync(
        QueueItem item, 
        IProgress<double> progress)
    {
        var config = await _configService.GetConfigurationAsync();
        
        var ytdlProcess = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = "yt-dlp",
                Arguments = $"--output \"{config.MediaPath}/{item.VideoId}.mp4\" " +
                           $"--format \"{config.QualityPreference}\" " +
                           $"\"{item.SourceUrl}\"",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false
            }
        };
        
        // Parse progress from yt-dlp output
        ytdlProcess.OutputDataReceived += (sender, e) =>
        {
            if (e.Data?.Contains("[download]") == true)
            {
                // Parse percentage and report progress
                var match = Regex.Match(e.Data, @"(\d+\.\d+)%");
                if (match.Success && double.TryParse(
                    match.Groups[1].Value, out var percent))
                {
                    progress?.Report(percent);
                }
            }
        };
        
        ytdlProcess.Start();
        ytdlProcess.BeginOutputReadLine();
        await ytdlProcess.WaitForExitAsync();
        
        return ytdlProcess.ExitCode == 0;
    }
}
```

### Phase 4: Real-time Updates (Week 2)

#### 4.1 SignalR Hub

```csharp
// Hubs/DownloadHub.cs
public class DownloadHub : Hub
{
    public async Task SendProgress(Guid queueId, double percent)
    {
        await Clients.User(Context.UserIdentifier)
            .SendAsync("DownloadProgress", queueId, percent);
    }
    
    public async Task JoinUserGroup()
    {
        await Groups.AddToGroupAsync(
            Context.ConnectionId, 
            Context.UserIdentifier);
    }
}
```

#### 4.2 Background Download Worker

```csharp
// Services/BackgroundServices/DownloadWorker.cs
public class DownloadWorker : BackgroundService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly Channel<QueueItem> _queue;
    
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        await foreach (var item in _queue.Reader.ReadAllAsync(stoppingToken))
        {
            using var scope = _serviceProvider.CreateScope();
            var downloadService = scope.ServiceProvider
                .GetRequiredService<DownloadService>();
            var hubContext = scope.ServiceProvider
                .GetRequiredService<IHubContext<DownloadHub>>();
            
            var progress = new Progress<double>(async percent =>
            {
                await hubContext.Clients
                    .User(item.UserId.ToString())
                    .SendAsync("DownloadProgress", item.Id, percent);
            });
            
            await downloadService.DownloadVideoAsync(item, progress);
        }
    }
}
```

### Phase 5: Settings Management (Week 3)

#### 5.1 Settings Page

```razor
@* Components/Pages/Settings.razor *@
@page "/settings"
@attribute [Authorize(Roles = "Admin")]
@inject IConfigurationService ConfigService

<MudContainer>
    <MudTabs>
        <MudTabPanel Text="API Keys">
            <MudCard>
                <MudCardContent>
                    <MudTextField Label="IMVDb API Key"
                                @bind-Value="Config.ImvdbApiKey"
                                InputType="InputType.Password" />
                </MudCardContent>
            </MudCard>
        </MudTabPanel>
        
        <MudTabPanel Text="Storage">
            <MudCard>
                <MudCardContent>
                    <MudTextField Label="Media Path"
                                @bind-Value="Config.MediaPath" />
                    <MudNumericField Label="Max Storage (GB)"
                                   Value="@(Config.MaxStorageBytes / 1_073_741_824)"
                                   ValueChanged="@((long gb) => 
                                       Config.MaxStorageBytes = gb * 1_073_741_824)" />
                </MudCardContent>
            </MudCard>
        </MudTabPanel>
    </MudTabs>
    
    <MudButton Color="Color.Primary" 
             Variant="Variant.Filled"
             OnClick="SaveConfiguration"
             Class="mt-4">
        Save Changes
    </MudButton>
</MudContainer>

@code {
    private SystemConfiguration Config = new();
    
    protected override async Task OnInitializedAsync()
    {
        Config = await ConfigService.GetConfigurationAsync();
    }
    
    private async Task SaveConfiguration()
    {
        await ConfigService.UpdateConfigurationAsync(Config);
        Snackbar.Add("Configuration saved", Severity.Success);
    }
}
```

## Docker Deployment

### Dockerfile

```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS build
WORKDIR /src
COPY ["Fuzzbin.csproj", "."]
RUN dotnet restore
COPY . .
RUN dotnet publish -c Release -o /app/publish \
    --runtime linux-musl-x64 \
    /p:PublishTrimmed=true

FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine AS runtime
WORKDIR /app

# Install yt-dlp
RUN apk add --no-cache python3 py3-pip ffmpeg \
    && pip3 install --no-cache-dir --break-system-packages yt-dlp

# Create directories
RUN mkdir -p /data /media && chmod 755 /data /media

COPY --from=build /app/publish .

EXPOSE 8080
VOLUME ["/data", "/media"]

ENTRYPOINT ["dotnet", "Fuzzbin.dll"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  fuzzbin:
    image: fuzzbin:latest
    container_name: fuzzbin
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
      - ./media:/media
    # No environment variables needed!
```

## Testing Strategy

### Unit Tests

```csharp
// Fuzzbin.Tests/Services/ConfigurationServiceTests.cs
public class ConfigurationServiceTests
{
    [Fact]
    public async Task GetConfiguration_ReturnsCachedValue()
    {
        // Arrange
        var context = GetInMemoryContext();
        var cache = new MemoryCache(new MemoryCacheOptions());
        var service = new ConfigurationService(context, cache);
        
        // Act
        var config1 = await service.GetConfigurationAsync();
        var config2 = await service.GetConfigurationAsync();
        
        // Assert
        Assert.Same(config1, config2);
    }
}
```

### Integration Tests

```csharp
// Fuzzbin.Tests/Integration/SetupTests.cs
public class SetupTests : IClassFixture<WebApplicationFactory<Program>>
{
    [Fact]
    public async Task FirstRun_RedirectsToSetup()
    {
        // Arrange
        var client = _factory.CreateClient();
        
        // Act
        var response = await client.GetAsync("/");
        
        // Assert
        Assert.Equal(HttpStatusCode.Redirect, response.StatusCode);
        Assert.Equal("/setup", response.Headers.Location.ToString());
    }
}
```

## Performance Optimization

### 1. Memory Management
- Use `ArrayPool<byte>` for large buffers
- Implement `IAsyncDisposable` for resources
- Configure GC for server workload

### 2. Database Optimization
- Index frequently queried fields
- Use projection for read operations
- Implement cursor-based pagination

### 3. Caching Strategy
- Cache configuration for 5 minutes
- Cache IMVDb responses for 24 hours
- Use ETags for static resources

## Monitoring

### Health Checks

```csharp
builder.Services.AddHealthChecks()
    .AddDbContextCheck<FuzzbinDbContext>()
    .AddCheck("storage", () =>
    {
        var freeSpace = GetFreeSpace("/media");
        return freeSpace > 1_073_741_824 
            ? HealthCheckResult.Healthy()
            : HealthCheckResult.Degraded("Low disk space");
    });
```

### Metrics Endpoint

```csharp
app.MapGet("/metrics", async (VideoService videoService) =>
{
    return new
    {
        Videos = await videoService.GetCountAsync(),
        QueueSize = await queueService.GetQueueSizeAsync(),
        StorageUsed = await storageService.GetUsedSpaceAsync()
    };
}).RequireAuthorization();
```

## Deployment Checklist

- [ ] Build Docker image
- [ ] Create data and media volumes
- [ ] Start container
- [ ] Complete setup wizard
- [ ] Configure API keys in Settings
- [ ] Test video download
- [ ] Verify real-time updates
- [ ] Setup backup schedule
- [ ] Configure reverse proxy (optional)
- [ ] Enable HTTPS (production)

## Common Issues & Solutions

### Issue: Container won't start
```bash
# Check logs
docker logs fuzzbin

# Verify volumes
docker volume inspect fuzzbin_data
```

### Issue: Downloads fail
- Check API keys in Settings
- Verify yt-dlp is installed
- Check storage permissions

### Issue: Real-time updates not working
- Ensure WebSocket support in reverse proxy
- Check SignalR connection in browser console

## Week 5 External Integration Notes

- **IMVDb HTTP client**: A typed Refit client (`IImvdbApi`) now handles all outbound calls with Polly retry/circuit-breaker policies and a fixed-window rate limiter derived from `ImvdbOptions`. Provide the API key via Settings or environment overrides to enable lookups.
- **MetadataService refresh**: The service consumes the IMVDb client with an `IMemoryCache` layer and shared `ImvdbMapper`, enriching videos with directors, genres, and artwork where available while caching responses for 24 hours.
- **ExternalSearchService**: Newly registered as `IExternalSearchService`, it merges IMVDb metadata and yt-dlp results into unified items so operators can discover missing videos and see download links alongside metadata quality signals.
- **Blazor updates**: `/search` now includes an "External Sources" panel with controls for IMVDb/yt-dlp toggles, max results, and quick copy of current filters. Settings highlights the IMVDb dependency with a contextual alert.
- **Regression coverage**: Unit tests cover `ImvdbApiKeyProvider` caching/priority rules and the external aggregation workflow to guard against regressions as integrations evolve.

## Next Steps

1. **Extend Features**:
   - Add playlist support
   - Implement batch downloads
   - Add video transcoding

2. **Improve UI**:
   - Add dark mode
   - Create mobile-responsive design
   - Add drag-and-drop upload

3. **Scale Performance**:
   - Implement distributed caching
   - Add CDN for media delivery
   - Support horizontal scaling

## Resources

- [ASP.NET Core Documentation](https://docs.microsoft.com/aspnet/core)
- [Blazor Documentation](https://docs.microsoft.com/aspnet/core/blazor)
- [Entity Framework Core](https://docs.microsoft.com/ef/core)
- [SignalR Documentation](https://docs.microsoft.com/aspnet/core/signalr)
- [MudBlazor Components](https://mudblazor.com)

## Summary

This implementation provides:
- ✅ Single C# codebase
- ✅ Single Docker container
- ✅ Database-driven configuration
- ✅ No environment variables needed
- ✅ First-run setup wizard
- ✅ Real-time progress updates
- ✅ Encrypted sensitive data
- ✅ 80% less resource usage than Python/Node.js
- ✅ 1-minute deployment

### Week 8: Library Import & Source Verification

#### Library Import Service (`Fuzzbin.Services/LibraryImportService.cs`)

```csharp
public async Task<LibraryImportSession> StartImportAsync(LibraryImportRequest request, CancellationToken cancellationToken = default)
{
    var rootPath = request.RootPath ?? await _libraryPathManager.GetLibraryRootAsync(cancellationToken);
    var importItems = new List<LibraryImportItem>();

    foreach (var file in Directory.EnumerateFiles(rootPath, "*.*", SearchOption.AllDirectories))
    {
        if (!allowedExtensions.Contains(Path.GetExtension(file).ToLowerInvariant()))
        {
            continue;
        }

        var item = await BuildImportItemAsync(session, file, Path.GetRelativePath(rootPath, file), request,
            existingVideoIndex, existingVideos, sessionHashes, sessionPaths, cancellationToken);
        importItems.Add(item);
    }

    await _itemRepository.AddRangeAsync(importItems);
    session.Status = LibraryImportStatus.ReadyForReview;
    session.Items = importItems;
    await _sessionRepository.UpdateAsync(session);
    await _unitOfWork.SaveChangesAsync();
    return session;
}
```

- Scans the configured library root, extracts metadata via `IMetadataService`, hashes files with SHA-256, and performs fuzzy matching (FuzzySharp `WeightedRatio`) against existing videos.
- Persists `LibraryImportSession`/`LibraryImportItem` with duplicate classification, match candidates, and manual override slots.
- Commit path applies metadata to new or existing videos and records created IDs for safe rollback.

#### Import Wizard UI (`Fuzzbin.Web/Components/Pages/Import.razor`)

- Three-panel Blazor workflow: kickoff form, recent session selector, and a review grid with inline filtering/actions.
- `MudTable` rows expose manual override select, duplicate chips, and one-click approve/reject/flag controls.
- Buttons wire into the new service endpoints (`CommitAsync`, `RollbackAsync`, `RefreshSessionAsync`) and summary chips show review progress.

#### Source Verification Service (`Fuzzbin.Services/SourceVerificationService.cs`)

```csharp
public async Task<VideoSourceVerification> VerifyVideoAsync(Video video, SourceVerificationRequest request, CancellationToken cancellationToken = default)
{
    var sourceUrl = ResolveSourceUrl(video, request);
    if (string.IsNullOrWhiteSpace(sourceUrl))
    {
        return await PersistResultAsync(video, request, null, null, VideoSourceVerificationStatus.SourceMissing, 0, cancellationToken);
    }

    var metadata = await _ytDlpService.GetVideoMetadataAsync(sourceUrl, cancellationToken);
    var comparison = BuildComparison(video, metadata);
    var confidence = ComputeConfidence(video, metadata, request, comparison);
    var status = confidence >= request.ConfidenceThreshold
        ? VideoSourceVerificationStatus.Verified
        : VideoSourceVerificationStatus.Mismatch;

    return await PersistResultAsync(video, request, comparison, sourceUrl, status, confidence, cancellationToken);
}
```

- Wraps yt-dlp metadata retrieval, calculates duration/frame-rate/resolution deltas, and stores `VideoSourceVerification` snapshots with serialized comparison data.
- Exposes manual override for mismatches (notes + explicit status) and surfaces verification state on the `VideoDetails` page.

#### Tests (`Fuzzbin.Tests/Services`)

- `LibraryImportServiceTests` validates duplicate detection and metadata extraction against temp files.
- `SourceVerificationServiceTests` verifies yt-dlp integration using a stub service and asserts manual override behaviour.
- All new tests run under `dotnet test` without external dependencies.
