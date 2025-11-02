using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace Fuzzbin.Data.Context;

/// <summary>
/// Design-time factory for creating ApplicationDbContext instances for EF Core migrations
/// </summary>
public class DesignTimeDbContextFactory : IDesignTimeDbContextFactory<ApplicationDbContext>
{
    public ApplicationDbContext CreateDbContext(string[] args)
    {
        var optionsBuilder = new DbContextOptionsBuilder<ApplicationDbContext>();
        
        // Use SQLite with a temporary database path for migrations
        optionsBuilder.UseSqlite("Data Source=fuzzbin_design.db");
        
        return new ApplicationDbContext(optionsBuilder.Options);
    }
}