# Fuzzbin Product Brief

## Executive Summary

**Fuzzbin** is a modern, self-hosted music video management system built with C# and ASP.NET Core 8.0. It provides a comprehensive solution for downloading, organizing, and managing music video collections with rich metadata integration from IMVDb (Internet Music Video Database) and MusicBrainz.

**Technology Stack:** ASP.NET Core 8.0, Blazor Server, SQLite, Entity Framework Core  
**Deployment:** Single Docker container, ~200MB image size  
**License:** Open Source

---

## Product Vision

Create a modern, self-contained web application that automates the acquisition and organization of music videos with rich metadata, deployed as a single Docker container for maximum simplicity and portability.

### Core Philosophy

- **Single Language**: C# throughout the entire stack
- **Single Container**: All components in one Docker image
- **Self-Hosted First**: Optimized for personal/small team deployment
- **Resource Efficient**: Minimal memory (~150MB idle) and CPU footprint
- **Zero External Dependencies**: Embedded SQLite database, no external services required

---

## Key Features

### 🎵 Music Video Management

- **Comprehensive Video Library**: Store and organize unlimited music videos with rich metadata
- **Advanced Search & Filtering**: Real-time search across artist, title, album, genres, and tags
- **Collection Management**: Organize videos into custom collections and playlists
- **Bulk Operations**: Multi-select actions for tags, collections, and metadata updates
- **Smart Duplicate Detection**: SHA-256 file hashing and fuzzy matching prevent duplicates

### 📥 Intelligent Download System

- **Automated Downloads**: Integration with yt-dlp for video downloads from YouTube and other platforms
- **Queue Management**: Concurrent download management with priority queuing
- **Progress Tracking**: Real-time download progress via SignalR WebSockets
- **Retry Logic**: Automatic retry with exponential backoff for failed downloads
- **Quality Selection**: Configurable quality preferences (2160p/1080p/720p/480p)

### 🎨 Rich Metadata Integration

- **IMVDb Integration**: Primary source for music video metadata including:
  - Video release year and directors
  - Official video sources and links
  - Thumbnail artwork
  - Production company information

- **MusicBrainz Integration**: Audio metadata enrichment:
  - Featured artists detection and tracking
  - Album associations
  - Genre classification (specific and broad)
  - Record label information (direct and parent labels)

- **Metadata Caching**: 24-hour cache reduces API calls and improves performance
- **Resilient API Calls**: Polly retry policies and circuit breakers ensure reliability

### 📄 Kodi-Compatible NFO Generation

- **Automated NFO Files**: Generate Kodi-compatible `.nfo` metadata files
- **Configurable Format**: 
  - Featured artist handling (title/artist field inclusion)
  - Genre specificity (specific vs. broad)
  - Label display (direct vs. parent company)
  - Custom separators for featured artists

- **Pattern-Based Organization**: Flexible file naming patterns:
  ```
  {artist}/{year}/{artist} - {title}
  {genre}/{artist_full} - {title}
  {year}/{month} - {artist} - {title}
  ```

- **Safe filenames**: optional ability to remove all special characters and diacritics, replace spaces with underscores, and normalize to single underscore

### 📚 Library Import & Organization

- **Collection Scanner**: Import existing video collections from filesystem
- **NFO Parsing**: Read existing `.nfo` files to preserve metadata
- **Filename Detection**: Intelligent parsing of common naming patterns
- **Fuzzy Matching**: Automatic matching with IMVDb/MusicBrainz entries
- **Bulk Reorganization**: Preview and apply file structure changes across entire library

### ✅ Source Verification

- **Video Authenticity**: Verify video sources using yt-dlp metadata comparison
- **Quality Metrics**: Compare duration, frame rate, and resolution
- **Confidence Scoring**: Algorithmic confidence ratings for matches
- **Manual Override**: Flag and annotate mismatches with notes
- **Alternative Sources**: Discover and track multiple source URLs

### 🎭 Modern User Interface

- **Blazor Server UI**: Responsive, real-time interface with MudBlazor components
- **Theme Support**: Light and dark mode with customizable themes
- **Keyboard Shortcuts**: Power-user productivity features
- **Grid & List Views**: Multiple visualization options
- **Video Player**: Integrated streaming player with range request support
- **Onboarding Wizard**: First-run setup guide for new installations

### 🔐 Security & Authentication

- **ASP.NET Core Identity**: Robust user authentication system
- **Single-User Mode**: Simplified deployment for personal use
- **Role-Based Access**: Admin and user role separation
- **Data Protection API**: Encrypted sensitive data (API keys) in database
- **HTTPS Support**: TLS/SSL for secure connections
- **CSRF Protection**: Built-in antiforgery token validation

---

## Technical Architecture

### Clean Architecture Design

```
┌─────────────────────────────────────────┐
│         Fuzzbin.Web (Blazor UI)         │
│  - Components, Pages, Dialogs           │
│  - SignalR Hubs (Real-time updates)     │
│  - Authentication & Authorization       │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│      Fuzzbin.Services (Business)        │
│  - Video, Download, Metadata Services   │
│  - Background Workers                   │
│  - External API Integration             │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│    Fuzzbin.Data (Persistence)           │
│  - Repository Pattern                   │
│  - Unit of Work                         │
│  - EF Core Migrations                   │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│    Fuzzbin.Core (Domain Models)         │
│  - Entities, Interfaces                 │
│  - Domain Logic                         │
└─────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | ASP.NET Core 8.0 | Modern, high-performance web framework |
| **UI** | Blazor Server | Real-time, interactive UI with minimal JavaScript |
| **Database** | SQLite + EF Core | Embedded, zero-configuration database |
| **UI Components** | MudBlazor | Material Design component library |
| **Real-time** | SignalR | WebSocket-based live updates |
| **Logging** | Serilog | Structured logging with file rotation |
| **HTTP Client** | Refit + Polly | Type-safe API clients with resilience |
| **Video Download** | yt-dlp | Robust video extraction |
| **Caching** | IMemoryCache | In-memory caching for performance |

### Data Models

#### Video Entity
- Comprehensive metadata (title, artist, album, year, duration)
- Technical details (codec, resolution, bitrate, format)
- External IDs (IMVDb, MusicBrainz, YouTube)
- Relationships (genres, tags, featured artists, collections)
- Playback tracking (play count, last played, rating)
- File information (path, hash, size)

#### Collections
- Custom video groupings
- Many-to-many relationships
- Order preservation
- Metadata (description, cover art)

#### Download Queue
- Priority-based processing
- Status tracking (queued, downloading, completed, failed)
- Retry management
- Progress reporting

---

## Performance Characteristics

### Resource Usage

| Metric | Target | Actual |
|--------|--------|--------|
| **Memory (Idle)** | < 150MB | ~120-140MB |
| **Memory (Load)** | < 400MB | ~250-350MB |
| **CPU (Idle)** | 1-2% | ~1% |
| **Docker Image** | < 200MB | ~180MB |
| **Startup Time** | < 5s | ~3-4s |

### Scalability

- **Video Library**: Thousands of videos without degradation
- **Search Performance**: < 200ms for full-text search
- **API Response**: < 100ms average response time
- **Page Load**: < 1s initial load time

---

## Key Technical Decisions

### 1. **Single Container Architecture**

**Decision**: Deploy entire application as one Docker container  
**Rationale**: 
- Simplified deployment and maintenance
- No orchestration complexity
- Portable across environments
- Reduced operational overhead

**Trade-offs**: Limited horizontal scaling (acceptable for self-hosted use case)

### 2. **Blazor Server over Blazor WebAssembly**

**Decision**: Use Blazor Server for UI  
**Rationale**:
- Real-time updates via SignalR already required
- Smaller initial payload
- Full .NET runtime access on server
- Simpler state management

**Trade-offs**: Requires persistent connection (acceptable with SignalR infrastructure)

### 3. **SQLite over PostgreSQL/SQL Server**

**Decision**: Embedded SQLite database  
**Rationale**:
- Zero configuration required
- Single file portability
- Perfect for self-hosted scenarios
- Sufficient performance for target scale

**Migration Path**: Architecture supports future migration to PostgreSQL if needed

### 4. **Repository Pattern + Unit of Work**

**Decision**: Implement repository abstraction layer  
**Rationale**:
- Testability (mock repositories)
- Specification pattern support
- Consistent data access patterns
- Future flexibility

### 5. **Background Services with Channels**

**Decision**: Use `System.Threading.Channels` for queue processing  
**Rationale**:
- High-performance async queuing
- Built-in backpressure support
- Clean cancellation semantics
- No external dependencies (vs. Hangfire/Quartz)

### 6. **SignalR for Real-time Updates**

**Decision**: Integrate SignalR throughout application  
**Rationale**:
- Native ASP.NET Core integration
- Automatic reconnection
- Multiple transport fallbacks
- Excellent Blazor support

### 7. **Polly Resilience Patterns**

**Decision**: Wrap external API calls with Polly policies  
**Rationale**:
- Automatic retry with exponential backoff
- Circuit breaker prevents cascading failures
- Timeout policies prevent hung requests
- Production-ready error handling

### 8. **Refit for API Clients**

**Decision**: Use Refit for type-safe HTTP clients  
**Rationale**:
- Compile-time safety
- Clean, declarative API definitions
- Excellent with Polly integration
- Reduced boilerplate code

---

## Deployment Model

### Docker Deployment

```yaml
version: '3.8'

services:
  fuzzbin:
    image: fuzzbin:latest
    container_name: fuzzbin
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data      # SQLite database
      - ./logs:/app/logs      # Application logs
      - ./media:/app/media    # Video storage
    environment:
      - ASPNETCORE_ENVIRONMENT=Production
    restart: unless-stopped
```

### System Requirements

**Minimum**:
- 1 CPU core
- 512MB RAM
- 10GB storage (+ video storage)

**Recommended**:
- 2 CPU cores
- 1GB RAM
- 100GB+ storage

**Supported Platforms**:
- Docker (Linux, Windows, macOS)
- Linux (systemd service)
- Windows (Windows Service)

---

## User Workflows

### New User Onboarding

1. **First Launch**: Setup wizard guides initial configuration
2. **Admin Creation**: Create first admin account
3. **API Configuration**: Optional IMVDb API key entry
4. **Library Setup**: Configure media storage path
5. **Import Existing**: Scan and import existing video collection

### Video Discovery & Download

1. **Search External**: Query IMVDb for music videos
2. **Preview Metadata**: Review artist, title, year, directors
3. **Queue Download**: Add to download queue with priority
4. **Monitor Progress**: Real-time progress tracking
5. **Auto-Organization**: Files organized per naming patterns
6. **NFO Generation**: Kodi metadata automatically created

### Collection Management

1. **Browse Library**: Search/filter video collection
2. **Bulk Select**: Multi-select videos for batch operations
3. **Add Tags**: Categorize with custom tags
4. **Create Collections**: Group related videos
5. **Update Metadata**: Batch metadata refresh from APIs
6. **Reorganize Files**: Preview and apply file structure changes

---

## Integration Capabilities

### External Services

- **IMVDb API**: Primary metadata source (requires API key)
- **MusicBrainz API**: Secondary metadata enrichment (public, rate-limited)
- **yt-dlp**: Video download engine (bundled)

### File Formats

**Supported Video Formats**:
- MP4, MKV, WebM, AVI, MOV

**Metadata Formats**:
- NFO (Kodi-compatible XML)
- JSON (metadata export/import)

### Export Capabilities

- **Bulk NFO Export**: Generate NFO files for entire library
- **Metadata Backup**: JSON export of all metadata
- **Database Backup**: SQLite database snapshots

---

## Security Considerations

### Data Protection

- **Encrypted Secrets**: API keys encrypted at rest using Data Protection API
- **Secure Cookies**: HttpOnly, Secure, SameSite cookies
- **CSRF Protection**: Antiforgery tokens on all state-changing operations
- **SQL Injection**: Parameterized queries via Entity Framework

### Authentication

- **Password Hashing**: BCrypt-based password storage
- **Lockout Policy**: 5 failed attempts = 5-minute lockout
- **Session Management**: Secure cookie-based sessions

### Network Security

- **HTTPS Support**: TLS 1.2+ for production deployments
- **CORS Policy**: Configurable cross-origin policies
- **Request Validation**: Input validation and sanitization
- **Rate Limiting**: API rate limiting for external services

---

## Testing & Quality Assurance

### Test Coverage

- **Unit Tests**: Service layer and business logic (target: 80% coverage)
- **Integration Tests**: Repository and database operations
- **Component Tests**: Blazor component testing with bUnit
- **End-to-End Tests**: Critical user workflows

### Continuous Integration

- Automated builds on code changes
- Test execution in CI pipeline
- Docker image building and tagging
- Code quality analysis

---

## Success Metrics

### Technical Success
- ✅ Single container deployment
- ✅ Memory usage < 400MB under load
- ✅ Startup time < 5 seconds
- ✅ Docker image < 200MB
- ✅ Test coverage > 80%

### User Success
- ✅ Setup time < 5 minutes
- ✅ No external dependencies required
- ✅ Intuitive UI/UX
- ✅ Reliable download system
- ✅ Accurate metadata matching

### Operational Success
- ✅ Zero-downtime updates
- ✅ Automated backups
- ✅ Simple configuration
- ✅ Easy troubleshooting
- ✅ Comprehensive logging

---

## Conclusion

Fuzzbin represents a modern approach to music video management, leveraging the .NET ecosystem to deliver:

1. **Simplicity**: Single container, single language, minimal configuration
2. **Performance**: Optimized resource usage and fast response times
3. **Reliability**: Resilient API integration and robust error handling
4. **Extensibility**: Clean architecture supports future enhancements
5. **User Experience**: Intuitive Blazor UI with real-time updates

The combination of C# throughout the stack, modern ASP.NET Core features, and thoughtful architectural decisions results in a maintainable, efficient, and user-friendly music video management system ideal for self-hosted deployments.

---

**Project Status**: Active Development  
**Repository**: [GitHub](https://github.com/asotbz/fuzzbin)  
**Documentation**: [Wiki](https://github.com/asotbz/fuzzbin/wiki)  
