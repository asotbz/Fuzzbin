using System;

namespace Fuzzbin.Core.Entities
{
    public class CollectionVideo : BaseEntity
    {
        public Guid CollectionId { get; set; }
        public Collection Collection { get; set; } = null!;
        
        public Guid VideoId { get; set; }
        public Video Video { get; set; } = null!;
        
        public int Position { get; set; } // Order within collection
        public DateTime AddedToCollectionDate { get; set; } = DateTime.UtcNow;
        public string? Notes { get; set; } // User notes for this video in this collection
    }
}