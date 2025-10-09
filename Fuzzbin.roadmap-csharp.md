# Fuzzbin C# Implementation Roadmap

## Executive Summary

This roadmap outlines the development plan for Fuzzbin built with C# and .NET 8 as a unified single-container solution. The project is structured in 4 phases over approximately 12 weeks, prioritizing core functionality and self-hosted deployment simplicity.

## Key Advantages of C# Refactor

### Technical Benefits
- **Unified Stack**: Single language and framework across entire application
- **Performance**: Native AOT compilation, better memory management
- **Deployment**: Single container, single executable option
- **Maintenance**: Simplified debugging, consistent tooling
- **Type Safety**: Strong typing throughout the stack

### Operational Benefits
- **Resource Efficiency**: Optimized memory usage with .NET 8
- **Fast Startup**: < 5 seconds with compiled application
- **Simplified Hosting**: Single process, no orchestration needed
- **Better Integration**: Native Windows service support
- **Reduced Dependencies**: No Redis, single integrated application

## Project Timeline Overview

```
Phase 1: Foundation (Weeks 1-3)      ██████
Phase 2: Core Features (Weeks 4-6)   ██████
Phase 3: Advanced (Weeks 7-9)        ██████
Phase 4: Testing & Deploy (Weeks 10-12) ██████
```

## Team Requirements (Reduced)

### Core Team
- **Senior .NET Developer** (1): Full-stack C#, Blazor, ASP.NET Core
- **Mid-level .NET Developer** (0.5): Supporting development
- **DevOps Engineer** (0.25): Docker, deployment automation
- **QA Engineer** (0.25): Testing, quality assurance

### Total: 2 FTE (optimized team structure)

---

## Phase 1: Foundation & Core Infrastructure (Weeks 1-3)

### Week 1: Project Setup & Architecture

#### Setup Tasks
```bash
# Create solution structure
dotnet new sln -n Fuzzbin
dotnet new blazorserver -n Fuzzbin.Web
dotnet new classlib -n Fuzzbin.Core
dotnet new classlib -n Fuzzbin.Data
dotnet new xunit -n Fuzzbin.Tests

# Add projects to solution
dotnet sln add Fuzzbin.Web/Fuzzbin.Web.csproj
dotnet sln add Fuzzbin.Core/Fuzzbin.Core.csproj
dotnet sln add Fuzzbin.Data/Fuzzbin.Data.csproj
dotnet sln add Fuzzbin.Tests/Fuzzbin.Tests.csproj

# Add NuGet packages
dotnet add Fuzzbin.Web package MudBlazor
dotnet add Fuzzbin.Data package Microsoft.EntityFrameworkCore.Sqlite
dotnet add Fuzzbin.Web package Serilog.AspNetCore
```

#### Core Components
- [ ] Solution structure with clean architecture
- [ ] Configure Blazor Server with MudBlazor UI
- [ ] Set up SQLite with Entity Framework Core
- [ ] Implement Serilog logging with file rotation
- [ ] Configure dependency injection
- [ ] Create base entity classes and interfaces
- [ ] Set up configuration management
- [ ] Implement health check endpoints
- [ ] Create Dockerfile with multi-stage build

**Deliverables:**
- Working Blazor application
- SQLite database integration
- Docker container building
- Basic project structure

### Week 2: Authentication & User Management

#### Identity Implementation
- [ ] Implement simplified ASP.NET Core Identity
- [ ] Create custom user store with SQLite/EF Core
- [ ] Build login/logout Blazor components
- [ ] Implement cookie authentication
- [ ] Add remember me functionality
- [ ] Create user profile management
- [ ] Implement password reset flow
- [ ] Add user settings storage
- [ ] Create authorization policies

#### UI Components
```razor
@* LoginComponent.razor *@
<MudCard>
    <MudCardContent>
        <MudTextField @bind-Value="Email" Label="Email" />
        <MudTextField @bind-Value="Password" Label="Password" 
                     InputType="InputType.Password" />
        <MudCheckBox @bind-Checked="RememberMe" Label="Remember Me" />
    </MudCardContent>
    <MudCardActions>
        <MudButton OnClick="HandleLogin" Color="Color.Primary">
            Login
        </MudButton>
    </MudCardActions>
</MudCard>
```

**Deliverables:**
- Complete authentication system
- User management UI
- Secure session handling
- Profile management

### Week 3: Data Layer & Video Management

#### Data Models & Repository Pattern
- [ ] Create Video entity with all properties
- [ ] Implement QueueItem entity
- [ ] Create generic repository interface
- [ ] Implement EF Core repository with SQLite
- [ ] Add unit of work pattern
- [ ] Create data access layer tests
- [ ] Implement query specifications
- [ ] Add database migrations/seeding
- [ ] Create backup/restore functionality

##### Repository Query Specifications (Finalized)
- **Specification infrastructure**
  - Add `ISpecification<T>` contract exposing `Criteria`, `Includes`, `OrderClauses`, `Skip/Take`, and `AsNoTracking` flags.
  - Include a reusable `SpecificationEvaluator` that applies specifications against `IQueryable<T>` and supports chained `ThenBy` operations.
  - Extend `IRepository<T>` with `Task<IReadOnlyList<T>> ListAsync(ISpecification<T> spec)`, `Task<T?> FirstOrDefaultAsync(ISpecification<T> spec)`, and `Task<int> CountAsync(ISpecification<T> spec)` to keep IQueryable usage inside the data layer.
- **VideoQuery DTO**
  - Fields: `string? Search`, `List<Guid> GenreIds`, `List<Guid> TagIds`, `List<Guid> CollectionIds`, `int? YearFrom`, `int? YearTo`, `int? DurationFrom`, `int? DurationTo`, `int? MinRating`, `bool? HasFile`, `bool? MissingMetadata`, `bool IncludeInactive`, `VideoSortOption SortBy`, `SortDirection SortDirection`, `int Page`, `int PageSize` (default 50, max 200).
  - Normalise search input (trim, case-insensitive) and pre-build term tokens for matching on title, artist, album, featured artists, and tag names.
- **Video specification catalog**
  - `VideoByIdSpecification(Guid id, bool includeRelations = true)`: eager loads genres, tags, featured artists, and collections; optional `AsTracking` toggle for updates.
  - `VideoBulkByIdsSpecification(IEnumerable<Guid> ids, bool asNoTracking = true)`: maintains input order via `CASE` ordering when needed for playlist assembly.
  - `VideoQuerySpecification(VideoQuery query)`: central paginated catalog query with dynamic filters, optional eager loading toggles, configurable sort map (`Title`, `Artist`, `CreatedAt`, `LastPlayedAt`, `PlayCount`, `Rating`, `Year`, `Duration`, `Random`), and `ThenBy(v => v.Title)` as deterministic fallback.
  - `VideoDuplicatesSpecification(string artist, string title)`: canonicalises strings, compares against both primary artist and featured artists, and groups by `Artist + Title` to surface duplicates (used before inserts and for maintenance jobs).
  - `VideoRecentImportsSpecification(int take = 40)`: filters by `CreatedAt >= UtcNow - 30d`, orders by `CreatedAt` descending, and exposes `Take` override for dashboard widgets.
  - `VideoMostPlayedSpecification(int take = 40, DateTime? since = null)`: optional `since` applies `LastPlayedAt >= since`; sorts by `PlayCount` then `LastPlayedAt`.
  - `VideoNeedingMetadataSpecification()`: flags videos missing `ImvdbId`, `ThumbnailPath`, or `Description`, and those linked to failed metadata fetch attempts (tracked via `ActivityLog`).
  - `VideoOrphansSpecification()`: identifies inactive entries (`!IsActive` or `FilePath == null`) and those whose physical file check fails (deferred to background validator via `PostProcessingAction`).
- **Download queue specifications**
  - `DownloadQueueByStatusSpecification(DownloadStatus status, bool includeVideo = false)`: sorts ascending by `Priority`, then `CreatedAt`, optional include of associated `Video` stub.
  - `DownloadQueueActiveSpecification()`: combines `Queued` and `Downloading`, enforces `AsTracking` for worker updates, and projects limited fields for minimal locking.
  - `DownloadQueueRetrySpecification(TimeSpan retryWindow, int maxRetries)`: returns failed items whose `RetryCount < maxRetries` and `UpdatedAt <= UtcNow - retryWindow`.
  - `DownloadQueueHistorySpecification(DateTime? olderThan = null)`: retrieves completed/cancelled items for archival cleanup with pagination defaults (`PageSize = 100`).
- **Supporting collections**
  - `CollectionWithVideosSpecification(Guid collectionId)` and `CollectionsForVideoSpecification(Guid videoId)` ensure consistent eager loading of `CollectionVideos` join entities with projection to DTOs.
  - `TagLookupSpecification(IEnumerable<Guid> tagIds)` and `GenreLookupSpecification(IEnumerable<Guid> genreIds)` centralise eager loading for association management and validation flows.
- **Testing expectations**
  - Unit tests cover each specification's predicate, ordering, and pagination behaviour using the in-memory provider and verifying generated SQL via `QueryString` when feasible.
  - Integration tests validate that `VideoQuerySpecification` supports combined filters (e.g., search + genre + year range) and enforces the 200 item cap.
  - Include guard tests confirming `SpecificationEvaluator` refuses null specs and honours `AsNoTracking` toggles.

#### Service Layer
```csharp
public interface IVideoService
{
    Task<Video> CreateVideoAsync(VideoCreateDto dto);
    Task<Video> GetVideoAsync(Guid id);
    Task<PagedResult<Video>> GetVideosAsync(VideoQuery query);
    Task UpdateVideoAsync(Guid id, VideoUpdateDto dto);
    Task DeleteVideoAsync(Guid id);
    Task<bool> CheckDuplicateAsync(string artist, string title);
}
```

**Deliverables:**
- Complete data layer
- Video CRUD operations
- Repository pattern implementation
- Service layer with business logic

---

## Phase 2: Core Features (Weeks 4-6)

### Week 4: Blazor UI Implementation

#### Component Development
- [ ] Create video grid component with virtualization
- [ ] Build video card with hover effects
- [ ] Implement video details page
- [ ] Create search bar with autocomplete
- [ ] Build filter sidebar
- [ ] Add pagination component
- [ ] Implement view switcher (grid/list)
- [ ] Create video editor dialog
- [ ] Add bulk selection functionality

#### Real-time Features
```csharp
// SignalR setup for real-time updates
@code {
    private HubConnection? hubConnection;
    
    protected override async Task OnInitializedAsync()
    {
        hubConnection = new HubConnectionBuilder()
            .WithUrl(Navigation.ToAbsoluteUri("/hubs/updates"))
            .WithAutomaticReconnect()
            .Build();
            
        hubConnection.On<Video>("VideoUpdated", async (video) =>
        {
            await UpdateVideoInList(video);
            await InvokeAsync(StateHasChanged);
        });
        
        await hubConnection.StartAsync();
    }
}
```

**Deliverables:**
- Complete video library UI
- Real-time updates via SignalR
- Responsive design
- Search and filter functionality

### Week 5: External API Integration

#### IMVDb Integration & yt-dlp Search
- [x] Create IMVDb API client with Refit
- [x] Implement yt-dlp search integration
- [x] Add Polly for resilience policies
- [x] Create metadata mapping services
- [x] Implement caching with IMemoryCache
- [x] Build search aggregation service
- [x] Add rate limiting
- [x] Create API response models
- [x] Implement error handling

#### API Client Implementation
```csharp
// IMVDb API client using Refit
[Headers("Authorization: Bearer")]
public interface IImvdbApi
{
    [Get("/search")]
    Task<ImvdbSearchResponse> SearchAsync(
        [Query] string q, 
        [Query] int page = 1);
        
    [Get("/video/{id}")]
    Task<ImvdbVideo> GetVideoAsync(string id);
}

// Service with caching
public class MetadataService
{
    private readonly IMemoryCache _cache;
    private readonly IImvdbApi _imvdbApi;
    
    public async Task<ImvdbVideo> GetVideoAsync(string id)
    {
        return await _cache.GetOrCreateAsync(
            $"imvdb:{id}",
            async entry =>
            {
                entry.SlidingExpiration = TimeSpan.FromHours(24);
                return await _imvdbApi.GetVideoAsync(id);
            });
    }
}
```

**Deliverables:**
- IMVDb integration
- yt-dlp search integration
- Metadata enrichment
- Search functionality

### Week 6: Download System

#### Background Service Implementation
- [ ] Create download queue with Channels
- [ ] Implement YoutubeDL-Sharp integration
- [ ] Build progress tracking system
- [ ] Add retry mechanism
- [ ] Create download service
- [ ] Implement bandwidth throttling
- [ ] Add concurrent download limits
- [ ] Create file management service
- [ ] Implement cleanup tasks

#### Queue Management
```csharp
public class DownloadQueueService : BackgroundService
{
    private readonly Channel<QueueItem> _queue;
    private readonly SemaphoreSlim _semaphore;
    
    public DownloadQueueService()
    {
        _queue = Channel.CreateUnbounded<QueueItem>();
        _semaphore = new SemaphoreSlim(3); // Max 3 concurrent
    }
    
    protected override async Task ExecuteAsync(
        CancellationToken cancellationToken)
    {
        await foreach (var item in _queue.Reader
            .ReadAllAsync(cancellationToken))
        {
            await _semaphore.WaitAsync(cancellationToken);
            
            _ = Task.Run(async () =>
            {
                try
                {
                    await ProcessDownloadAsync(item, cancellationToken);
                }
                finally
                {
                    _semaphore.Release();
                }
            }, cancellationToken);
        }
    }
}
```

**Deliverables:**
- Download queue system
- yt-dlp integration
- Progress tracking
- Queue management UI

---

## Phase 3: Advanced Features & NFO Generation (Weeks 7-9)

### Week 7: NFO Generation & File Organization

#### NFO Generator Service
- [ ] Create NFO XML templates
- [ ] Implement Kodi-compatible NFO generation
- [ ] Build file organization service
- [ ] Add filename sanitization
- [ ] Create directory structure manager
- [ ] Implement artist NFO generation
- [ ] Add thumbnail/artwork handling
- [ ] Create metadata export service
- [ ] Build import/export functionality

#### NFO Generation
```csharp
public class NfoGenerator
{
    public XDocument GenerateVideoNfo(Video video)
    {
        return new XDocument(
            new XDeclaration("1.0", "UTF-8", "yes"),
            new XElement("musicvideo",
                new XElement("title", video.Title),
                new XElement("artist", video.Artist),
                new XElement("album", video.Album),
                new XElement("year", video.Year),
                new XElement("genre", video.Genre),
                new XElement("director", video.Director),
                new XElement("studio", video.Studio),
                new XElement("runtime", 
                    video.Duration?.TotalSeconds),
                new XElement("plot", video.Description),
                video.Tags?.Select(t => 
                    new XElement("tag", t)) ?? Enumerable.Empty<XElement>()
            ));
    }
}
```

**Deliverables:**
- Complete NFO generation
- File organization system
- Metadata export/import
- Kodi compatibility

### Week 8: Library Import & Source Verification

#### Library Scanner
- [ ] Create directory scanning service
- [ ] Implement video file detection
- [ ] Build metadata extraction with MediaInfo
- [ ] Create filename parsing patterns
- [ ] Implement fuzzy matching algorithm
- [ ] Add duplicate detection
- [ ] Create import wizard UI
- [ ] Build match review interface
- [ ] Implement rollback functionality

#### Source Verification
- [ ] Create source verification service
- [ ] Implement video source verification via yt-dlp
- [ ] Build source comparison algorithm
- [ ] Add confidence scoring
- [ ] Create mismatch detection
- [ ] Implement alternative source finder
- [ ] Build verification UI components
- [ ] Add manual override functionality

**Deliverables:**
- Library import system
- Source verification
- Duplicate management
- Import wizard

### Week 9: Performance Optimization

#### Optimization Tasks
- [ ] Implement response compression
- [ ] Add output caching for static data
- [ ] Optimize database queries with indexes
- [ ] Implement lazy loading for large lists
- [ ] Add image optimization pipeline
- [ ] Create thumbnail generation service
- [ ] Implement chunked file uploads
- [ ] Add connection pooling
- [ ] Optimize Blazor component rendering

#### Performance Monitoring
```csharp
// Custom metrics collection
public class MetricsService
{
    private readonly ILogger<MetricsService> _logger;
    private readonly PerformanceCounter _cpuCounter;
    private readonly PerformanceCounter _memCounter;
    
    public SystemMetrics GetMetrics()
    {
        return new SystemMetrics
        {
            CpuUsage = _cpuCounter.NextValue(),
            MemoryUsageMB = _memCounter.NextValue() / 1024 / 1024,
            ActiveDownloads = _downloadService.ActiveCount,
            QueueSize = _queueService.Count,
            TotalVideos = _videoService.Count,
            UptimeHours = (DateTime.UtcNow - _startTime).TotalHours
        };
    }
}
```

**Deliverables:**
- Performance optimizations
- Resource usage optimization
- Caching implementation

---

## Phase 4: Testing & Deployment (Weeks 10-12)

### Week 10: UI Polish & Mobile Optimization

#### UI Enhancements
- [ ] Add loading skeletons
- [ ] Implement smooth animations
- [ ] Create error boundaries
- [ ] Add tooltips and help text
- [ ] Implement keyboard shortcuts
- [ ] Create onboarding flow
- [ ] Add dark/light theme toggle

**Deliverables:**
- Polished UI

### Week 11: Testing & Quality Assurance

#### Comprehensive Testing
- [ ] Unit tests for all services (80% coverage)
- [ ] Integration tests for API endpoints
- [ ] UI component tests with bUnit
- [ ] End-to-end tests with Playwright
- [ ] Performance testing with NBomber
- [ ] Security testing with OWASP ZAP
- [ ] Load testing for concurrent users
- [ ] Backup/restore testing
- [ ] Docker container testing

#### Test Implementation
```csharp
// Example service test
[Fact]
public async Task CreateVideo_Should_Return_Video_With_Id()
{
    // Arrange
    var service = new VideoService(_mockRepo.Object);
    var dto = new VideoCreateDto 
    { 
        Artist = "Test Artist", 
        Title = "Test Title" 
    };
    
    // Act
    var result = await service.CreateVideoAsync(dto);
    
    // Assert
    Assert.NotNull(result);
    Assert.NotEqual(Guid.Empty, result.Id);
    Assert.Equal(dto.Artist, result.Artist);
}
```

**Deliverables:**
- Complete test coverage
- Performance benchmarks
- Security audit results
- Test documentation

### Week 12: Deployment & Documentation

#### Deployment Preparation
- [ ] Create production Dockerfile
- [ ] Build GitHub Actions CI/CD pipeline
- [ ] Set up automated releases
- [ ] Create backup scripts
- [ ] Implement update mechanism
- [ ] Create installation script
- [ ] Build Docker Compose examples

#### Documentation
- [ ] Write installation guide
- [ ] Create user manual
- [ ] Document API endpoints
- [ ] Create troubleshooting guide
- [ ] Write developer documentation
- [ ] Build FAQ section
- [ ] Document configuration options
- [ ] Create deployment best practices

#### Single Container Deployment
```yaml
# docker-compose.yml
version: '3.8'

services:
  fuzzbin:
    image: ghcr.io/yourusername/fuzzbin:latest
    container_name: fuzzbin
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
      - ./media:/media
      - ./config:/config
    environment:
      - ASPNETCORE_ENVIRONMENT=Production
      - ApiKeys__ImvdbApiKey=${IMVDB_API_KEY}
    healthcheck:
      test: ["CMD", "wget", "--spider", "http://localhost:8080/health"]
      interval: 30s
      timeout: 3s
      retries: 3
```

**Deliverables:**
- Production Docker image
- CI/CD pipeline
- Complete documentation
- Deployment scripts

---

## Performance Targets

### Resource Usage Goals

| Metric | Target | Notes |
|--------|--------|-------|
| Memory (Idle) | < 150MB | Efficient baseline memory usage |
| Memory (Load) | < 400MB | Under heavy load conditions |
| CPU (Idle) | 1-2% | Minimal background processing |
| Startup Time | < 5s | Fast application startup |
| Docker Image | < 200MB | Compact deployment package |
| Dependencies | < 30 packages | Minimal external dependencies |

### Performance Metrics Goals

| Operation | Target | Notes |
|-----------|--------|-------|
| API Response | < 100ms | Fast API responses |
| Page Load | < 1s | Quick page rendering |
| Search Query | < 200ms | Responsive search |
| File Upload (100MB) | < 5s | Efficient file handling |
| Concurrent Users | 100+ | Good scalability |

---

## Risk Mitigation

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Blazor learning curve | Medium | Provide training, use templates |
| SQLite scalability | Low | Design for migration to PostgreSQL if needed |
| Single container failure | High | Implement proper backup/restore |
| Memory leaks | Medium | Use proper disposal patterns |
| SignalR scaling | Low | Implement backplane if needed |

---

## Budget Comparison

### Development Investment (3 months)

**C# Implementation:**
- Senior .NET Developer: $35,000
- Mid .NET Developer (0.5): $12,500
- DevOps (0.25): $7,500
- **Total Investment**: $55,000

This represents a lean, efficient development approach with:
- Single technology stack reducing complexity
- Smaller team due to unified development
- Reduced DevOps overhead with single container architecture

### Operational Costs (Monthly)

**C# Implementation:**
- Hosting (1 container): $20
- **Total**: $20/month

Benefits of single container approach:
- Minimal hosting requirements
- No external dependencies (Redis, etc.)
- Simplified monitoring and maintenance
- Reduced operational overhead

---

## Success Criteria

### Phase 1 Success (Week 3)
- ✓ Single container builds and runs
- ✓ Authentication working
- ✓ Basic CRUD operations
- ✓ Memory usage < 200MB

### Phase 2 Success (Week 6)
- ✓ API integrations functional
- ✓ Download system operational
- ✓ Real-time updates working
- ✓ UI feature complete

### Phase 3 Success (Week 9)
- ✓ NFO generation working
- ✓ Library import functional
- ✓ Performance targets met
- ✓ Source verification operational

### Phase 4 Success (Week 12)
- ✓ All tests passing
- ✓ Documentation complete
- ✓ Docker image < 200MB
- ✓ Production deployment successful

---

## Conclusion

The Fuzzbin C# implementation delivers:

1. **Simplicity**: Single language, single container architecture
2. **Performance**: Optimized resource usage and fast response times
3. **Cost-Effectiveness**: Lean development team and minimal operational costs
4. **Maintainability**: Unified tooling and debugging experience
5. **Deployment**: Self-contained single container with database-driven configuration

This roadmap provides a clear path to deliver a modern, efficient, and easily deployable music video management system with enterprise-grade features while maintaining simplicity for self-hosted deployments.
