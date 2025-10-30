# Configuration Directory Restructuring - Implementation Summary

## Overview

This document summarizes the implementation of the centralized configuration directory structure for Fuzzbin, with environment variable support and enhanced file naming pattern validation.

## Implementation Date

October 30, 2024

## Changes Summary

### 1. New Configuration Directory Structure

```
FUZZBIN_CONFIG_DIR (default: $HOME/Fuzzbin or /config in Docker)
├── data/
│   ├── fuzzbin.db           # SQLite database
│   ├── fuzzbin.db-wal       # SQLite WAL file
│   ├── fuzzbin.db-shm       # SQLite shared memory
│   └── keys/                # Data protection keys
├── backups/                 # Database backups
├── logs/                    # Application logs
├── Library/                 # All library content (videos, NFO, artwork) - UI configurable
└── Downloads/               # Default downloads location (UI configurable)
    └── tmp/
```

### 2. Environment Variable Support

- **`FUZZBIN_CONFIG_DIR`**: Overrides the default configuration directory
  - Non-Docker default: `$HOME/Fuzzbin`
  - Docker default: `/config`
  - Example: `FUZZBIN_CONFIG_DIR=/custom/path`

### 3. New Files Created

#### Core Infrastructure
- **`Fuzzbin.Core/Interfaces/IConfigurationPathService.cs`**: Interface for configuration path resolution
- **`Fuzzbin.Services/ConfigurationPathService.cs`**: Implementation with environment variable support

#### Pattern Validation Models
- **`Fuzzbin.Services/Models/PatternValidationResult.cs`**: Validation result with errors and warnings
- **`Fuzzbin.Services/Models/PatternExample.cs`**: Pattern example with description

### 4. Modified Files

#### Services Layer
- **`Fuzzbin.Services/LibraryPathManager.cs`**:
  - Injected `IConfigurationPathService`
  - Uses `GetDefaultLibraryPath()` when no configuration exists
  - Simplified: All library content (videos, metadata, artwork) in single directory
  - `GetVideoRootAsync()`, `GetMetadataRootAsync()`, and `GetArtworkRootAsync()` all return library root
  
- **`Fuzzbin.Services/DownloadSettingsProvider.cs`**:
  - Injected `IConfigurationPathService`
  - Uses `GetDefaultDownloadsPath()` for downloads directory

- **`Fuzzbin.Services/BackupService.cs`**:
  - Injected `IConfigurationPathService`
  - Uses `GetBackupDirectory()` instead of calculating from database path
  - Removed `EnsureBackupDirectoryExists()` method (handled by service)

- **`Fuzzbin.Services/FileOrganizationService.cs`**:
  - Added `ValidatePatternWithDetails()`: Comprehensive validation with errors/warnings
  - Added `GenerateExampleFilename()`: Generates example using sample data
  - Added `GetPatternExamples()`: Returns list of pre-defined pattern examples
  - Uses `PatternValidationResult` and `PatternExample` models

- **`Fuzzbin.Core/Interfaces/IFileOrganizationService.cs`**:
  - Added new method signatures for enhanced validation

#### Web Layer
- **`Fuzzbin.Web/Program.cs`**:
  - Registered `IConfigurationPathService` as singleton
  - Updated database path resolution to use `GetDatabasePath()`
  - Updated data protection keys path to use `GetDataDirectory()`
  - Reconfigured Serilog to use `GetLogsDirectory()`
  - Added logging for configuration paths

- **`Fuzzbin.Web/Components/Pages/Setup.razor`**:
  - Injected `IConfigurationPathService` and `IFileOrganizationService`
  - Displays configuration directory location
  - Shows default paths with helper text
  - Real-time pattern validation with error display
  - Example filename generation
  - Pattern validation warnings
  - Expandable sections for pattern examples and available variables
  - Click-to-apply pattern examples
  - Complete list of available pattern variables

#### Docker Configuration
- **`Dockerfile`**:
  - Creates `/config` directory structure
  - Sets `FUZZBIN_CONFIG_DIR=/config` environment variable
  - Single volume mount: `/config`

- **`docker-compose.yml`**:
  - Uses named volume `fuzzbin-config` mapped to `/config`
  - Sets `FUZZBIN_CONFIG_DIR=/config` environment variable
  - Simplified volume configuration

## Configuration Path Resolution Priority

1. **`FUZZBIN_CONFIG_DIR` environment variable** (if set)
2. **Docker detection** via `DOTNET_RUNNING_IN_CONTAINER=true` → `/config`
3. **Default** → `$HOME/Fuzzbin`

## Pattern Validation Features

### Validation Checks
- ✅ Pattern contains at least one variable
- ✅ `{format}` variable is present (required for file extension)
- ✅ All variables are recognized
- ✅ No invalid path characters outside of variables
- ⚠️ Warns if missing `{artist}` or `{title}`
- ⚠️ Warns if pattern has no directory structure

### Example Patterns Provided
1. `{artist}/{title}.{format}` - Simple: Artist/Title.mp4
2. `{artist}/{year} - {title}.{format}` - With year
3. `{year}/{artist}/{title}.{format}` - Year first
4. `{genre}/{artist} - {title}.{format}` - By genre
5. `{artist}/{artist} - {title} [{resolution}].{format}` - With quality indicator
6. `{artist_safe}/{year}/{title_safe}.{format}` - Filesystem-safe names
7. `{label}/{artist}/{title}.{format}` - By label

### Available Variables (47 total)
- **Artist**: `{artist}`, `{artist_safe}`, `{artist_sort}`, `{primary_artist}`
- **Title**: `{title}`, `{title_safe}`
- **Date**: `{year}`, `{year2}`, `{month}`, `{month_name}`, `{day}`, `{date}`
- **Genre**: `{genre}`, `{genres}`
- **Label**: `{label}`, `{label_safe}`
- **Technical**: `{resolution}`, `{width}`, `{height}`, `{codec}`, `{format}`, `{bitrate}`, `{fps}`
- **IMVDb**: `{imvdb_id}`, `{director}`, `{production}`, `{featured_artists}`
- **MusicBrainz**: `{mb_artist_id}`, `{mb_recording_id}`, `{album}`, `{track_number}`
- **Custom**: `{tags}`, `{collection}`, `{custom1}`, `{custom2}`, `{custom3}`

## UI/UX Improvements

### Setup Wizard Enhancements
1. **Configuration Info Alert**: Shows active configuration directory
2. **Default Path Hints**: Helper text shows default values
3. **Real-time Validation**: Pattern validated on blur
4. **Visual Feedback**: 
   - ✅ Example filename displayed for valid patterns
   - ❌ Error messages for invalid patterns
   - ⚠️ Warnings for non-critical issues
5. **Pattern Examples**: Expandable panel with click-to-apply examples
6. **Variable Reference**: Expandable table of all available variables
7. **Better Organization**: Grouped related settings logically

## Backward Compatibility

**Breaking Change**: No backward compatibility provided per requirements.
- Fresh installations will use new structure immediately
- Existing installations will need manual data migration

## Migration Notes for Existing Installations

For users upgrading from previous versions:

### Manual Migration Steps
1. Stop Fuzzbin
2. Set `FUZZBIN_CONFIG_DIR` environment variable (optional)
3. Move data:
   ```bash
   # Non-Docker
   mkdir -p $HOME/Fuzzbin/data
   mv /old/path/to/data/fuzzbin.db* $HOME/Fuzzbin/data/
   mv /old/path/to/data/keys $HOME/Fuzzbin/data/
   
   # Docker
   docker-compose down
   # Update docker-compose.yml to new format
   docker-compose up -d
   ```
4. Restart Fuzzbin
5. Update Library and Downloads paths in Settings if needed

## Testing Checklist

- [ ] Fresh installation on non-Docker
- [ ] Fresh installation with Docker
- [ ] Custom `FUZZBIN_CONFIG_DIR` environment variable
- [ ] Pattern validation displays errors
- [ ] Pattern validation displays warnings
- [ ] Example filename generation
- [ ] Pattern examples can be applied
- [ ] Variable reference is complete
- [ ] Database created in correct location
- [ ] Logs created in correct location
- [ ] Backups created in correct location
- [ ] Library defaults to correct location
- [ ] Downloads defaults to correct location

## Performance Considerations

- **Lazy Initialization**: Configuration paths resolved once and cached
- **Thread-Safe**: Service uses proper locking for initialization
- **Minimal Overhead**: Path resolution happens at startup, not per-request

## Security Considerations

- **Path Validation**: All paths validated before use
- **Directory Creation**: Automatic with proper error handling
- **Environment Variable Expansion**: Supported for flexibility
- **No Sensitive Data in Logs**: Paths logged at Info level only

## Future Enhancements

Potential future improvements:
1. **Migration Tool**: Automated migration from old structure
2. **Path Validation UI**: Check paths during setup
3. **Custom Variable Support**: Allow users to define custom pattern variables
4. **Pattern Templates**: Save and load custom patterns
5. **Real-time Preview**: Live preview of pattern results during typing

## Related Documentation

- [Deployment Guide](../Fuzzbin.deployment-csharp.md) - needs updating
- [Architecture Document](../Fuzzbin.architecture-csharp.md) - needs updating
- [Product Requirements](../Fuzzbin.prd-csharp.md) - needs updating

## Contributors

- Implementation Date: October 30, 2024
- Architect Mode: Initial planning and design
- Code Mode: Implementation

---

**Status**: ✅ Implementation Complete
**Version**: 1.0
**Last Updated**: October 30, 2024