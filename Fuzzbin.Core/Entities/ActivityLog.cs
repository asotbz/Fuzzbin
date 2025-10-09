using System;

namespace Fuzzbin.Core.Entities
{
    public class ActivityLog
    {
        public int Id { get; set; }
        public DateTime Timestamp { get; set; }
        public string UserId { get; set; } = string.Empty;
        public string Username { get; set; } = string.Empty;
        public string Action { get; set; } = string.Empty;
        public string Category { get; set; } = string.Empty;
        public string EntityType { get; set; } = string.Empty;
        public string? EntityId { get; set; }
        public string? EntityName { get; set; }
        public string? Details { get; set; }
        public string? OldValue { get; set; }
        public string? NewValue { get; set; }
        public string IpAddress { get; set; } = string.Empty;
        public string UserAgent { get; set; } = string.Empty;
        public bool IsSuccess { get; set; } = true;
        public string? ErrorMessage { get; set; }
        public TimeSpan? Duration { get; set; }
    }

    public static class ActivityCategories
    {
        public const string Authentication = "Authentication";
        public const string Video = "Video";
        public const string Collection = "Collection";
        public const string Download = "Download";
        public const string System = "System";
        public const string Import = "Import";
        public const string Export = "Export";
        public const string Playlist = "Playlist";
        public const string Search = "Search";
        public const string Settings = "Settings";
        public const string Backup = "Backup";
    }

    public static class ActivityActions
    {
        // Authentication
        public const string Login = "Login";
        public const string Logout = "Logout";
        public const string Register = "Register";
        public const string PasswordChange = "PasswordChange";
        public const string PasswordReset = "PasswordReset";
        
        // CRUD Operations
        public const string Create = "Create";
        public const string Read = "Read";
        public const string Update = "Update";
        public const string Delete = "Delete";
        public const string BulkUpdate = "BulkUpdate";
        public const string BulkDelete = "BulkDelete";
        
        // Video Operations
        public const string Play = "Play";
        public const string Queue = "Queue";
        public const string Organize = "Organize";
        public const string GenerateThumbnail = "GenerateThumbnail";
        public const string ExportNfo = "ExportNfo";
        
        // Download Operations
        public const string StartDownload = "StartDownload";
        public const string CompleteDownload = "CompleteDownload";
        public const string FailDownload = "FailDownload";
        public const string CancelDownload = "CancelDownload";
        
        // Import/Export
        public const string Import = "Import";
        public const string Export = "Export";
        
        // System
        public const string Backup = "Backup";
        public const string Restore = "Restore";
        public const string ConfigChange = "ConfigChange";
        public const string SystemStart = "SystemStart";
        public const string SystemStop = "SystemStop";
    }
}