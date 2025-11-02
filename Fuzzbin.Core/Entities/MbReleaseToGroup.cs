using System;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Join table linking releases to release groups
/// </summary>
public class MbReleaseToGroup
{
    public Guid ReleaseId { get; set; }
    public Guid ReleaseGroupId { get; set; }
    
    // Navigation properties
    public virtual MbRelease Release { get; set; } = null!;
    public virtual MbReleaseGroup ReleaseGroup { get; set; } = null!;
}