namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Represents a configuration setting stored in the database
    /// </summary>
    public class Configuration : BaseEntity
    {
        /// <summary>
        /// Configuration key
        /// </summary>
        public string Key { get; set; } = string.Empty;

        /// <summary>
        /// Configuration value (stored as JSON for complex types)
        /// </summary>
        public string Value { get; set; } = string.Empty;

        /// <summary>
        /// Configuration category (e.g., "System", "IMVDb", "MusicBrainz", "Paths")
        /// </summary>
        public string Category { get; set; } = string.Empty;

        /// <summary>
        /// Configuration description
        /// </summary>
        public string? Description { get; set; }

        /// <summary>
        /// Indicates if this value is encrypted
        /// </summary>
        public bool IsEncrypted { get; set; } = false;

        /// <summary>
        /// Indicates if this is a system configuration that shouldn't be modified by users
        /// </summary>
        public bool IsSystem { get; set; } = false;
    }
}