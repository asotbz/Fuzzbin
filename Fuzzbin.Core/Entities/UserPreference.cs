using System;

namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Stores user-specific settings in a simple key/value form for quick access.
    /// </summary>
    public class UserPreference : BaseEntity
    {
        public Guid UserId { get; set; }

        public string Key { get; set; } = string.Empty;

        public string Value { get; set; } = string.Empty;

        public ApplicationUser? User { get; set; }
    }
}
