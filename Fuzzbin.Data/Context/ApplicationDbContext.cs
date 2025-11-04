using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Data.Context
{
    public class ApplicationDbContext : IdentityDbContext<ApplicationUser, IdentityRole<Guid>, Guid>
    {
        public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options)
            : base(options)
        {
        }

        // DbSets for entities
        public DbSet<Video> Videos { get; set; } = null!;
        public DbSet<Genre> Genres { get; set; } = null!;
        public DbSet<Tag> Tags { get; set; } = null!;
        public DbSet<FeaturedArtist> FeaturedArtists { get; set; } = null!;
        public DbSet<Configuration> Configurations { get; set; } = null!;
        public DbSet<DownloadQueueItem> DownloadQueueItems { get; set; } = null!;
        public DbSet<Collection> Collections { get; set; } = null!;
        public DbSet<CollectionVideo> CollectionVideos { get; set; } = null!;
        public DbSet<SavedSearch> SavedSearches { get; set; } = null!;
        public DbSet<ActivityLog> ActivityLogs { get; set; } = null!;
        public DbSet<UserPreference> UserPreferences { get; set; } = null!;
        public DbSet<LibraryImportSession> LibraryImportSessions { get; set; } = null!;
        public DbSet<LibraryImportItem> LibraryImportItems { get; set; } = null!;
        public DbSet<VideoSourceVerification> VideoSourceVerifications { get; set; } = null!;
        public DbSet<BackgroundJob> BackgroundJobs { get; set; } = null!;
        public DbSet<RecycleBin> RecycleBins { get; set; } = null!;
        public DbSet<MaintenanceExecution> MaintenanceExecutions { get; set; } = null!;
        public DbSet<CacheStatSnapshot> CacheStatSnapshots { get; set; } = null!;
        
        // Metadata Cache DbSets
        public DbSet<Query> Queries { get; set; } = null!;
        public DbSet<QuerySourceCache> QuerySourceCaches { get; set; } = null!;
        public DbSet<MbArtist> MbArtists { get; set; } = null!;
        public DbSet<MbRecording> MbRecordings { get; set; } = null!;
        public DbSet<MbRelease> MbReleases { get; set; } = null!;
        public DbSet<MbReleaseGroup> MbReleaseGroups { get; set; } = null!;
        public DbSet<MbTag> MbTags { get; set; } = null!;
        public DbSet<MbRecordingCandidate> MbRecordingCandidates { get; set; } = null!;
        public DbSet<ImvdbArtist> ImvdbArtists { get; set; } = null!;
        public DbSet<ImvdbVideo> ImvdbVideos { get; set; } = null!;
        public DbSet<ImvdbVideoCandidate> ImvdbVideoCandidates { get; set; } = null!;
        public DbSet<YtVideo> YtVideos { get; set; } = null!;
        public DbSet<YtVideoCandidate> YtVideoCandidates { get; set; } = null!;
        public DbSet<MvLink> MvLinks { get; set; } = null!;
        public DbSet<QueryResolution> QueryResolutions { get; set; } = null!;

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder);

            // Configure Video entity
            modelBuilder.Entity<Video>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Title).IsRequired().HasMaxLength(500);
                entity.Property(e => e.Artist).IsRequired().HasMaxLength(500);
                entity.Property(e => e.Album).HasMaxLength(500);
                entity.Property(e => e.FilePath).HasMaxLength(1000);
                entity.Property(e => e.ThumbnailPath).HasMaxLength(1000);
                entity.Property(e => e.NfoPath).HasMaxLength(1000);
                entity.Property(e => e.FileHash).HasMaxLength(128);
                entity.Property(e => e.Description).HasMaxLength(5000);
                entity.Property(e => e.YouTubeId).HasMaxLength(50);
                entity.Property(e => e.ImvdbId).HasMaxLength(100);
                entity.Property(e => e.MusicBrainzRecordingId).HasMaxLength(100);

                entity.HasIndex(e => e.Title);
                entity.HasIndex(e => e.Artist);
                entity.HasIndex(e => e.YouTubeId);
                entity.HasIndex(e => e.ImvdbId);
                entity.HasIndex(e => e.IsActive);
                entity.HasIndex(e => e.FileHash);
                entity.HasIndex(e => e.CreatedAt);
                entity.HasIndex(e => e.UpdatedAt);
                entity.HasIndex(e => e.LastPlayedAt);
                entity.HasIndex(e => e.PlayCount);
                entity.HasIndex(e => e.Rating);
                entity.HasIndex(e => e.Duration);
                entity.HasIndex(e => e.Year);
                entity.HasIndex(e => e.IsMissing);
                entity.HasIndex(e => e.MissingDetectedAt);

                // Configure many-to-many relationships
                entity.HasMany(e => e.Genres)
                    .WithMany(g => g.Videos)
                    .UsingEntity<Dictionary<string, object>>(
                        "VideoGenre",
                        j => j.HasOne<Genre>().WithMany().HasForeignKey("GenreId"),
                        j => j.HasOne<Video>().WithMany().HasForeignKey("VideoId"));

                entity.HasMany(e => e.Tags)
                    .WithMany(t => t.Videos)
                    .UsingEntity<Dictionary<string, object>>(
                        "VideoTag",
                        j => j.HasOne<Tag>().WithMany().HasForeignKey("TagId"),
                        j => j.HasOne<Video>().WithMany().HasForeignKey("VideoId"));

                entity.HasMany(e => e.FeaturedArtists)
                    .WithMany(f => f.Videos)
                    .UsingEntity<Dictionary<string, object>>(
                        "VideoFeaturedArtist",
                        j => j.HasOne<FeaturedArtist>().WithMany().HasForeignKey("FeaturedArtistId"),
                        j => j.HasOne<Video>().WithMany().HasForeignKey("VideoId"));
            });

            // Configure Genre entity
            modelBuilder.Entity<Genre>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Name).IsRequired().HasMaxLength(100);
                entity.Property(e => e.Description).HasMaxLength(500);
                entity.HasIndex(e => e.Name).IsUnique();
                entity.HasIndex(e => e.IsActive);
            });

            // Configure Tag entity
            modelBuilder.Entity<Tag>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Name).IsRequired().HasMaxLength(100);
                entity.Property(e => e.Color).HasMaxLength(7);
                entity.HasIndex(e => e.Name).IsUnique();
                entity.HasIndex(e => e.IsActive);
            });

            // Configure FeaturedArtist entity
            modelBuilder.Entity<FeaturedArtist>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Name).IsRequired().HasMaxLength(500);
                entity.Property(e => e.Biography).HasMaxLength(5000);
                entity.Property(e => e.ImagePath).HasMaxLength(1000);
                entity.Property(e => e.ImvdbArtistId).HasMaxLength(100);
                entity.Property(e => e.MusicBrainzArtistId).HasMaxLength(100);
                entity.HasIndex(e => e.Name);
                entity.HasIndex(e => e.ImvdbArtistId);
                entity.HasIndex(e => e.MusicBrainzArtistId);
                entity.HasIndex(e => e.IsActive);
            });

            // Configure Configuration entity
            modelBuilder.Entity<Configuration>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Key).IsRequired().HasMaxLength(200);
                entity.Property(e => e.Value).IsRequired();
                entity.Property(e => e.Category).IsRequired().HasMaxLength(100);
                entity.Property(e => e.Description).HasMaxLength(500);
                entity.HasIndex(e => new { e.Category, e.Key }).IsUnique();
                entity.HasIndex(e => e.IsActive);
            });

            // Configure DownloadQueueItem entity
            modelBuilder.Entity<DownloadQueueItem>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Url).IsRequired().HasMaxLength(2000);
                entity.Property(e => e.Title).HasMaxLength(500);
                entity.Property(e => e.Status).HasConversion<string>().HasMaxLength(50);
                entity.Property(e => e.ErrorMessage).HasMaxLength(1000);
                entity.HasIndex(e => e.Status);
                entity.HasIndex(e => e.Priority);
                entity.HasIndex(e => e.IsDeleted);
                
                // Configure relationship with Video
                entity.HasOne(e => e.Video)
                    .WithMany()
                    .HasForeignKey(e => e.VideoId)
                    .OnDelete(DeleteBehavior.SetNull);
            });

            // Configure Collection entity
            modelBuilder.Entity<Collection>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Name).IsRequired().HasMaxLength(500);
                entity.Property(e => e.Description).HasMaxLength(2000);
                entity.Property(e => e.ThumbnailPath).HasMaxLength(1000);
                entity.Property(e => e.Type).HasConversion<string>().HasMaxLength(50);
                entity.Property(e => e.SmartCriteria).HasMaxLength(5000);
                entity.HasIndex(e => e.Name);
                entity.HasIndex(e => e.Type);
                entity.HasIndex(e => e.IsPublic);
                entity.HasIndex(e => e.IsFavorite);
                entity.HasIndex(e => e.IsActive);
            });

            // Configure CollectionVideo entity (join table)
            modelBuilder.Entity<CollectionVideo>(entity =>
            {
                entity.HasKey(e => e.Id);
                
                entity.HasOne(cv => cv.Collection)
                    .WithMany(c => c.CollectionVideos)
                    .HasForeignKey(cv => cv.CollectionId)
                    .OnDelete(DeleteBehavior.Cascade);

                entity.HasOne(cv => cv.Video)
                    .WithMany(v => v.CollectionVideos)
                    .HasForeignKey(cv => cv.VideoId)
                    .OnDelete(DeleteBehavior.Cascade);

                entity.HasIndex(e => new { e.CollectionId, e.VideoId }).IsUnique();
                entity.HasIndex(e => new { e.CollectionId, e.Position });
                entity.Property(e => e.Notes).HasMaxLength(1000);
            });

            // Configure SavedSearch entity
            modelBuilder.Entity<SavedSearch>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Name).IsRequired().HasMaxLength(500);
                entity.Property(e => e.Description).HasMaxLength(2000);
                entity.Property(e => e.Query).IsRequired();
                entity.Property(e => e.Icon).HasMaxLength(100);
                entity.Property(e => e.Color).HasMaxLength(7);
                entity.HasIndex(e => e.Name);
                entity.HasIndex(e => e.UserId);
                entity.HasIndex(e => e.LastUsed);
                entity.HasIndex(e => e.IsActive);
            });

            // Configure ActivityLog entity
            modelBuilder.Entity<ActivityLog>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.UserId).IsRequired().HasMaxLength(450);
                entity.Property(e => e.Username).IsRequired().HasMaxLength(500);
                entity.Property(e => e.Action).IsRequired().HasMaxLength(200);
                entity.Property(e => e.Category).IsRequired().HasMaxLength(100);
                entity.Property(e => e.EntityType).IsRequired().HasMaxLength(200);
                entity.Property(e => e.EntityId).HasMaxLength(450);
                entity.Property(e => e.EntityName).HasMaxLength(500);
                entity.Property(e => e.Details).HasMaxLength(5000);
                entity.Property(e => e.OldValue).HasMaxLength(5000);
                entity.Property(e => e.NewValue).HasMaxLength(5000);
                entity.Property(e => e.IpAddress).HasMaxLength(45);
                entity.Property(e => e.UserAgent).HasMaxLength(1000);
                entity.Property(e => e.ErrorMessage).HasMaxLength(2000);
                
                entity.HasIndex(e => e.Timestamp);
                entity.HasIndex(e => e.UserId);
                entity.HasIndex(e => e.Category);
                entity.HasIndex(e => e.Action);
                entity.HasIndex(e => new { e.EntityType, e.EntityId });
                entity.HasIndex(e => e.IsSuccess);
            });

            // Configure UserPreference entity
            modelBuilder.Entity<UserPreference>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Key).IsRequired().HasMaxLength(200);
                entity.Property(e => e.Value).IsRequired();
                entity.HasIndex(e => new { e.UserId, e.Key }).IsUnique();

                entity.HasOne(e => e.User)
                    .WithMany(u => u.Preferences)
                    .HasForeignKey(e => e.UserId)
                    .OnDelete(DeleteBehavior.Cascade);
            });

            // Configure LibraryImportSession entity
            modelBuilder.Entity<LibraryImportSession>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.RootPath).IsRequired().HasMaxLength(2000);
                entity.Property(e => e.StartedByUserId).HasMaxLength(450);
                entity.Property(e => e.Status).HasConversion<string>().HasMaxLength(50);
                entity.Property(e => e.CreatedVideoIdsJson).HasColumnType("TEXT");
                entity.Property(e => e.Notes).HasMaxLength(2000);
                entity.Property(e => e.ErrorMessage).HasMaxLength(2000);

                entity.HasMany(e => e.Items)
                    .WithOne(i => i.Session)
                    .HasForeignKey(i => i.SessionId)
                    .OnDelete(DeleteBehavior.Cascade);

                entity.HasIndex(e => e.Status);
                entity.HasIndex(e => e.StartedAt);
            });

            // Configure LibraryImportItem entity
            modelBuilder.Entity<LibraryImportItem>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.FilePath).IsRequired().HasMaxLength(2000);
                entity.Property(e => e.RelativePath).HasMaxLength(2000);
                entity.Property(e => e.FileName).IsRequired().HasMaxLength(500);
                entity.Property(e => e.Extension).HasMaxLength(20);
                entity.Property(e => e.FileHash).HasMaxLength(128);
                entity.Property(e => e.Resolution).HasMaxLength(50);
                entity.Property(e => e.VideoCodec).HasMaxLength(100);
                entity.Property(e => e.AudioCodec).HasMaxLength(100);
                entity.Property(e => e.Title).HasMaxLength(500);
                entity.Property(e => e.Artist).HasMaxLength(500);
                entity.Property(e => e.Album).HasMaxLength(500);
                entity.Property(e => e.Status).HasConversion<string>().HasMaxLength(50);
                entity.Property(e => e.DuplicateStatus).HasConversion<string>().HasMaxLength(50);
                entity.Property(e => e.CandidateMatchesJson).HasColumnType("TEXT");
                entity.Property(e => e.Notes).HasMaxLength(1000);
                
                // NFO and metadata cache fields
                entity.Property(e => e.MetadataSource).HasMaxLength(50);
                entity.Property(e => e.NfoMetadataJson).HasColumnType("TEXT");
                entity.Property(e => e.CacheMetadataJson).HasColumnType("TEXT");
                entity.Property(e => e.FeaturedArtistsJson).HasColumnType("TEXT");

                entity.HasIndex(e => e.SessionId);
                entity.HasIndex(e => e.FileHash);
                entity.HasIndex(e => e.Status);
                entity.HasIndex(e => e.DuplicateStatus);
                entity.HasIndex(e => e.IsCommitted);
                entity.HasIndex(e => e.MetadataSource);
            });

            // Configure VideoSourceVerification entity
            modelBuilder.Entity<VideoSourceVerification>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.SourceUrl).HasMaxLength(2000);
                entity.Property(e => e.SourceProvider).HasMaxLength(100);
                entity.Property(e => e.Status).HasConversion<string>().HasMaxLength(50);
                entity.Property(e => e.ComparisonSnapshotJson).HasColumnType("TEXT");
                entity.Property(e => e.Notes).HasMaxLength(1000);

                entity.HasOne(e => e.Video)
                    .WithMany(v => v.SourceVerifications)
                    .HasForeignKey(e => e.VideoId)
                    .OnDelete(DeleteBehavior.Cascade);

                entity.HasIndex(e => e.VideoId);
                entity.HasIndex(e => e.Status);
            });

            // Configure BackgroundJob entity
            modelBuilder.Entity<BackgroundJob>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Type).HasConversion<string>().HasMaxLength(100);
                entity.Property(e => e.Status).HasConversion<string>().HasMaxLength(50);
                entity.Property(e => e.StatusMessage).HasMaxLength(1000);
                entity.Property(e => e.ErrorMessage).HasMaxLength(2000);
                entity.Property(e => e.ParametersJson).HasColumnType("TEXT");
                entity.Property(e => e.ResultJson).HasColumnType("TEXT");

                entity.HasIndex(e => e.Type);
                entity.HasIndex(e => e.Status);
                entity.HasIndex(e => e.CreatedAt);
                entity.HasIndex(e => e.StartedAt);
                entity.HasIndex(e => e.CompletedAt);
            });

            // Configure RecycleBin entity
            modelBuilder.Entity<RecycleBin>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.OriginalFilePath).IsRequired().HasMaxLength(2000);
                entity.Property(e => e.RecycleBinPath).IsRequired().HasMaxLength(2000);
                entity.Property(e => e.DeletionReason).HasMaxLength(1000);
                entity.Property(e => e.Notes).HasMaxLength(2000);
                
                entity.HasOne(e => e.DownloadQueueItem)
                    .WithMany()
                    .HasForeignKey(e => e.DownloadQueueItemId)
                    .OnDelete(DeleteBehavior.SetNull);
                
                entity.HasOne(e => e.Video)
                    .WithMany()
                    .HasForeignKey(e => e.VideoId)
                    .OnDelete(DeleteBehavior.SetNull);
                
                entity.HasIndex(e => e.DeletedAt);
                entity.HasIndex(e => e.ExpiresAt);
                entity.HasIndex(e => e.DownloadQueueItemId);
                entity.HasIndex(e => e.VideoId);
                entity.HasIndex(e => e.IsActive);
            });

            // Configure MaintenanceExecution entity
            modelBuilder.Entity<MaintenanceExecution>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.TaskName).IsRequired().HasMaxLength(200);
                entity.Property(e => e.Summary).IsRequired().HasMaxLength(2000);
                entity.Property(e => e.ErrorMessage).HasMaxLength(2000);
                entity.Property(e => e.MetricsJson).HasColumnType("TEXT");

                entity.HasIndex(e => e.TaskName);
                entity.HasIndex(e => e.StartedAt);
                entity.HasIndex(e => e.Success);
                entity.HasIndex(e => e.IsActive);
            });

            // Configure CacheStatSnapshot entity
            modelBuilder.Entity<CacheStatSnapshot>(entity =>
            {
                entity.HasKey(e => e.Id);

                entity.HasIndex(e => e.SnapshotAt);
                entity.HasIndex(e => e.IsActive);
            });

            // Configure metadata cache entities
            
            // Query entity with unique normalized key
            modelBuilder.Entity<Query>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.RawTitle).IsRequired().HasMaxLength(500);
                entity.Property(e => e.RawArtist).IsRequired().HasMaxLength(500);
                entity.Property(e => e.NormTitle).IsRequired().HasMaxLength(500);
                entity.Property(e => e.NormArtist).IsRequired().HasMaxLength(500);
                entity.Property(e => e.NormComboKey).IsRequired().HasMaxLength(1000);
                
                entity.HasIndex(e => e.NormComboKey).IsUnique();
                entity.HasIndex(e => e.NormTitle);
                entity.HasIndex(e => e.NormArtist);
                entity.HasIndex(e => e.IsActive);
            });
            
            // QuerySourceCache entity
            modelBuilder.Entity<QuerySourceCache>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Source).IsRequired().HasMaxLength(50);
                entity.Property(e => e.ResultEtag).HasMaxLength(200);
                entity.Property(e => e.Notes).HasMaxLength(1000);
                
                entity.HasOne(e => e.Query)
                    .WithMany(q => q.SourceCaches)
                    .HasForeignKey(e => e.QueryId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasIndex(e => e.QueryId);
                entity.HasIndex(e => e.Source);
                entity.HasIndex(e => e.LastCheckedAt);
            });
            
            // MusicBrainz entities
            modelBuilder.Entity<MbArtist>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Mbid).IsRequired().HasMaxLength(36);
                entity.Property(e => e.Name).IsRequired().HasMaxLength(500);
                entity.Property(e => e.SortName).HasMaxLength(500);
                entity.Property(e => e.Disambiguation).HasMaxLength(500);
                entity.Property(e => e.Country).HasMaxLength(2);
                
                entity.HasIndex(e => e.Mbid).IsUnique();
                entity.HasIndex(e => e.Name);
                entity.HasIndex(e => e.IsActive);
            });
            
            modelBuilder.Entity<MbRecording>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Mbid).IsRequired().HasMaxLength(36);
                entity.Property(e => e.Title).IsRequired().HasMaxLength(500);
                
                entity.HasIndex(e => e.Mbid).IsUnique();
                entity.HasIndex(e => e.Title);
                entity.HasIndex(e => e.IsActive);
            });
            
            modelBuilder.Entity<MbReleaseGroup>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Mbid).IsRequired().HasMaxLength(36);
                entity.Property(e => e.Title).IsRequired().HasMaxLength(500);
                entity.Property(e => e.PrimaryType).HasMaxLength(50);
                entity.Property(e => e.FirstReleaseDate).HasMaxLength(10);
                
                entity.HasIndex(e => e.Mbid).IsUnique();
                entity.HasIndex(e => e.IsActive);
            });
            
            modelBuilder.Entity<MbRelease>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Mbid).IsRequired().HasMaxLength(36);
                entity.Property(e => e.Title).IsRequired().HasMaxLength(500);
                entity.Property(e => e.ReleaseDate).HasMaxLength(10);
                entity.Property(e => e.Country).HasMaxLength(2);
                entity.Property(e => e.Barcode).HasMaxLength(50);
                entity.Property(e => e.RecordLabel).HasMaxLength(500);
                
                entity.HasIndex(e => e.Mbid).IsUnique();
                entity.HasIndex(e => e.IsActive);
            });
            
            // MusicBrainz join tables
            modelBuilder.Entity<MbRecordingArtist>(entity =>
            {
                entity.HasKey(ra => new { ra.RecordingId, ra.ArtistId });
                
                entity.HasOne(ra => ra.Recording)
                    .WithMany(r => r.Artists)
                    .HasForeignKey(ra => ra.RecordingId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasOne(ra => ra.Artist)
                    .WithMany(a => a.RecordingArtists)
                    .HasForeignKey(ra => ra.ArtistId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasIndex(e => e.RecordingId);
                entity.HasIndex(e => e.ArtistId);
            });
            
            modelBuilder.Entity<MbRecordingRelease>(entity =>
            {
                entity.HasKey(rr => new { rr.RecordingId, rr.ReleaseId });
                
                entity.HasOne(rr => rr.Recording)
                    .WithMany(r => r.Releases)
                    .HasForeignKey(rr => rr.RecordingId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasOne(rr => rr.Release)
                    .WithMany(rel => rel.Recordings)
                    .HasForeignKey(rr => rr.ReleaseId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasIndex(e => e.RecordingId);
                entity.HasIndex(e => e.ReleaseId);
            });
            
            modelBuilder.Entity<MbReleaseToGroup>(entity =>
            {
                entity.HasKey(rtg => new { rtg.ReleaseId, rtg.ReleaseGroupId });
                
                entity.HasOne(rtg => rtg.Release)
                    .WithMany(r => r.ReleaseGroups)
                    .HasForeignKey(rtg => rtg.ReleaseId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasOne(rtg => rtg.ReleaseGroup)
                    .WithMany(rg => rg.Releases)
                    .HasForeignKey(rtg => rtg.ReleaseGroupId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasIndex(e => e.ReleaseId);
                entity.HasIndex(e => e.ReleaseGroupId);
            });
            
            modelBuilder.Entity<MbTag>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.EntityType).IsRequired().HasMaxLength(50);
                entity.Property(e => e.Name).IsRequired().HasMaxLength(200);
                
                entity.HasIndex(e => new { e.EntityType, e.EntityId });
                entity.HasIndex(e => e.Name);
            });
            
            modelBuilder.Entity<MbRecordingCandidate>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.TitleNorm).IsRequired().HasMaxLength(500);
                entity.Property(e => e.ArtistNorm).IsRequired().HasMaxLength(500);
                
                entity.HasOne(e => e.Query)
                    .WithMany(q => q.MbRecordingCandidates)
                    .HasForeignKey(e => e.QueryId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasOne(e => e.Recording)
                    .WithMany(r => r.Candidates)
                    .HasForeignKey(e => e.RecordingId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasIndex(e => e.QueryId);
                entity.HasIndex(e => e.RecordingId);
                entity.HasIndex(e => new { e.QueryId, e.Rank });
                entity.HasIndex(e => e.IsActive);
            });
            
            // IMVDb entities
            modelBuilder.Entity<ImvdbArtist>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Name).IsRequired().HasMaxLength(500);
                
                entity.HasIndex(e => e.ImvdbId).IsUnique();
                entity.HasIndex(e => e.Name);
                entity.HasIndex(e => e.IsActive);
            });
            
            modelBuilder.Entity<ImvdbVideo>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.SongTitle).HasMaxLength(500);
                entity.Property(e => e.VideoTitle).HasMaxLength(500);
                entity.Property(e => e.ReleaseDate).HasMaxLength(10);
                entity.Property(e => e.DirectorCredit).HasMaxLength(500);
                
                entity.HasIndex(e => e.ImvdbId).IsUnique();
                entity.HasIndex(e => e.SongTitle);
                entity.HasIndex(e => e.IsActive);
            });
            
            modelBuilder.Entity<ImvdbVideoArtist>(entity =>
            {
                entity.HasKey(va => new { va.VideoId, va.ArtistId });
                entity.Property(e => e.Role).IsRequired().HasMaxLength(50);
                
                entity.HasOne(va => va.Video)
                    .WithMany(v => v.Artists)
                    .HasForeignKey(va => va.VideoId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasOne(va => va.Artist)
                    .WithMany(a => a.VideoArtists)
                    .HasForeignKey(va => va.ArtistId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasIndex(e => e.VideoId);
                entity.HasIndex(e => e.ArtistId);
            });
            
            modelBuilder.Entity<ImvdbVideoSource>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.Source).IsRequired().HasMaxLength(50);
                entity.Property(e => e.ExternalId).IsRequired().HasMaxLength(200);
                
                entity.HasOne(e => e.Video)
                    .WithMany(v => v.Sources)
                    .HasForeignKey(e => e.VideoId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasIndex(e => e.VideoId);
                entity.HasIndex(e => new { e.Source, e.ExternalId });
            });
            
            modelBuilder.Entity<ImvdbVideoCandidate>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.TitleNorm).IsRequired().HasMaxLength(500);
                entity.Property(e => e.ArtistNorm).IsRequired().HasMaxLength(500);
                
                entity.HasOne(e => e.Query)
                    .WithMany(q => q.ImvdbVideoCandidates)
                    .HasForeignKey(e => e.QueryId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasOne(e => e.Video)
                    .WithMany(v => v.Candidates)
                    .HasForeignKey(e => e.VideoId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasIndex(e => e.QueryId);
                entity.HasIndex(e => e.VideoId);
                entity.HasIndex(e => new { e.QueryId, e.Rank });
                entity.HasIndex(e => e.IsActive);
            });
            
            // YouTube entities
            modelBuilder.Entity<YtVideo>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.VideoId).IsRequired().HasMaxLength(50);
                entity.Property(e => e.Title).IsRequired().HasMaxLength(500);
                entity.Property(e => e.ChannelId).HasMaxLength(100);
                entity.Property(e => e.ChannelName).HasMaxLength(500);
                entity.Property(e => e.PublishedAt).HasMaxLength(30);
                entity.Property(e => e.ThumbnailUrl).HasMaxLength(1000);
                entity.Property(e => e.ThumbnailPath).HasMaxLength(1000);
                
                entity.HasIndex(e => e.VideoId).IsUnique();
                entity.HasIndex(e => e.ChannelId);
                entity.HasIndex(e => e.IsActive);
            });
            
            modelBuilder.Entity<YtVideoCandidate>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.VideoId).IsRequired().HasMaxLength(50);
                entity.Property(e => e.TitleNorm).IsRequired().HasMaxLength(500);
                entity.Property(e => e.ArtistNorm).IsRequired().HasMaxLength(500);
                
                entity.HasOne(e => e.Query)
                    .WithMany(q => q.YtVideoCandidates)
                    .HasForeignKey(e => e.QueryId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasOne(e => e.Video)
                    .WithMany(v => v.Candidates)
                    .HasForeignKey(e => e.VideoId)
                    .HasPrincipalKey(v => v.VideoId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasIndex(e => e.QueryId);
                entity.HasIndex(e => e.VideoId);
                entity.HasIndex(e => new { e.QueryId, e.Rank });
                entity.HasIndex(e => e.IsActive);
            });
            
            // Cross-linking entities
            modelBuilder.Entity<MvLink>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.YtVideoId).HasMaxLength(50);
                entity.Property(e => e.LinkType).IsRequired().HasMaxLength(50);
                entity.Property(e => e.Notes).HasMaxLength(1000);
                
                entity.HasOne(e => e.ImvdbVideo)
                    .WithMany()
                    .HasForeignKey(e => e.ImvdbVideoId)
                    .OnDelete(DeleteBehavior.SetNull);
                
                entity.HasOne(e => e.MbRecording)
                    .WithMany()
                    .HasForeignKey(e => e.MbRecordingId)
                    .OnDelete(DeleteBehavior.SetNull);
                
                entity.HasOne(e => e.YtVideo)
                    .WithMany()
                    .HasForeignKey(e => e.YtVideoId)
                    .HasPrincipalKey(v => v.VideoId)
                    .OnDelete(DeleteBehavior.SetNull);
                
                entity.HasIndex(e => e.ImvdbVideoId);
                entity.HasIndex(e => e.MbRecordingId);
                entity.HasIndex(e => e.YtVideoId);
                entity.HasIndex(e => e.LinkType);
                entity.HasIndex(e => e.IsActive);
            });
            
            modelBuilder.Entity<QueryResolution>(entity =>
            {
                entity.HasKey(e => e.Id);
                entity.Property(e => e.ChosenSource).IsRequired().HasMaxLength(50);
                
                entity.HasOne(e => e.Query)
                    .WithOne(q => q.Resolution)
                    .HasForeignKey<QueryResolution>(e => e.QueryId)
                    .OnDelete(DeleteBehavior.Cascade);
                
                entity.HasOne(e => e.MvLink)
                    .WithMany()
                    .HasForeignKey(e => e.MvLinkId)
                    .OnDelete(DeleteBehavior.SetNull);
                
                entity.HasIndex(e => e.QueryId).IsUnique();
                entity.HasIndex(e => e.ChosenSource);
                entity.HasIndex(e => e.IsActive);
            });

            // Seed initial configuration data with static dates
            var seedDate = new DateTime(2024, 1, 1, 0, 0, 0, DateTimeKind.Utc);
            
            modelBuilder.Entity<Configuration>().HasData(
                new Configuration
                {
                    Id = Guid.Parse("00000000-0000-0000-0000-000000000001"),
                    Key = "AppVersion",
                    Value = "1.0.0",
                    Category = "System",
                    Description = "Application version",
                    IsSystem = true,
                    CreatedAt = seedDate,
                    UpdatedAt = seedDate
                },
                new Configuration
                {
                    Id = Guid.Parse("00000000-0000-0000-0000-000000000002"),
                    Key = "MediaPath",
                    Value = "/media/videos",
                    Category = "Paths",
                    Description = "Default media storage path",
                    CreatedAt = seedDate,
                    UpdatedAt = seedDate
                },
                new Configuration
                {
                    Id = Guid.Parse("00000000-0000-0000-0000-000000000003"),
                    Key = "ThumbnailPath",
                    Value = "/media/thumbnails",
                    Category = "Paths",
                    Description = "Thumbnail storage path",
                    CreatedAt = seedDate,
                    UpdatedAt = seedDate
                },
                new Configuration
                {
                    Id = Guid.Parse("00000000-0000-0000-0000-000000000004"),
                    Key = "MaxConcurrentDownloads",
                    Value = "2",
                    Category = "Downloads",
                    Description = "Maximum number of concurrent downloads",
                    CreatedAt = seedDate,
                    UpdatedAt = seedDate
                },
                new Configuration
                {
                    Id = Guid.Parse("00000000-0000-0000-0000-000000000005"),
                    Key = "IsFirstRun",
                    Value = "true",
                    Category = "System",
                    Description = "Indicates if this is the first run",
                    IsSystem = true,
                    CreatedAt = seedDate,
                    UpdatedAt = seedDate
                }
            );
        }

        public override Task<int> SaveChangesAsync(CancellationToken cancellationToken = default)
        {
            var entries = ChangeTracker.Entries()
                .Where(e => e.Entity is BaseEntity && (e.State == EntityState.Added || e.State == EntityState.Modified));

            foreach (var entry in entries)
            {
                var entity = (BaseEntity)entry.Entity;
                entity.UpdatedAt = DateTime.UtcNow;

                if (entry.State == EntityState.Added)
                {
                    entity.CreatedAt = DateTime.UtcNow;
                }
            }

            return base.SaveChangesAsync(cancellationToken);
        }
    }
}
