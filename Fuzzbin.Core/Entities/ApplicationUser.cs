using System;
using System.Collections.Generic;
using Microsoft.AspNetCore.Identity;

namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Application user entity extending ASP.NET Core Identity with domain specific fields.
    /// </summary>
    public class ApplicationUser : IdentityUser<Guid>
    {
        public string? DisplayName { get; set; }

        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

        public DateTime? LastLoginAt { get; set; }

        public bool IsActive { get; set; } = true;

        public long StorageQuotaBytes { get; set; } = 52_428_800_000; // 50GB default

        public long StorageUsedBytes { get; set; }

        public ICollection<UserPreference> Preferences { get; set; } = new List<UserPreference>();
    }
}
