using System;
using System.Linq;
using Fuzzbin.Data.Context;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Xunit;

namespace Fuzzbin.Tests.Integration;

[CollectionDefinition("Integration")]
public class IntegrationTestCollection : ICollectionFixture<IntegrationTestFactory>
{
}

public class IntegrationTestFactory : WebApplicationFactory<Program>
{
    private const string TestDatabaseName = "FuzzbinIntegrationTests";
    private static bool _databaseInitialized = false;
    private static readonly object _lock = new object();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        // Set environment first to prevent migrations
        builder.UseEnvironment("Testing");
        
        builder.ConfigureServices(services =>
        {
            // Remove all DbContext-related service descriptors
            // This includes pooled contexts, regular contexts, and options
            var descriptorsToRemove = services
                .Where(d => d.ServiceType.IsGenericType &&
                           (d.ServiceType.GetGenericTypeDefinition() == typeof(DbContextOptions<>) ||
                            d.ServiceType.Name.Contains("DbContext") ||
                            d.ServiceType.Name.Contains("IDbContextPool")))
                .ToList();
            
            // Also remove by exact type
            descriptorsToRemove.AddRange(services.Where(
                d => d.ServiceType == typeof(DbContextOptions) ||
                     d.ServiceType == typeof(ApplicationDbContext) ||
                     d.ImplementationType == typeof(ApplicationDbContext)).ToList());

            foreach (var descriptor in descriptorsToRemove.Distinct())
            {
                services.Remove(descriptor);
            }

            // Add ApplicationDbContext using a SHARED in-memory database for all tests
            services.AddDbContext<ApplicationDbContext>(options =>
            {
                options.UseInMemoryDatabase(TestDatabaseName);
                options.EnableSensitiveDataLogging();
            });
        });
    }
    
    protected override IHost CreateHost(IHostBuilder builder)
    {
        var host = base.CreateHost(builder);
        
        // Seed database once for all tests
        lock (_lock)
        {
            if (!_databaseInitialized)
            {
                using var scope = host.Services.CreateScope();
                var db = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
                
                // Ensure database is created
                db.Database.EnsureCreated();
                
                // Mark setup as complete to bypass setup middleware
                if (!db.Configurations.Any(c => c.Key == "SetupComplete" && c.Category == "System"))
                {
                    db.Configurations.Add(new Fuzzbin.Core.Entities.Configuration
                    {
                        Id = Guid.NewGuid(),
                        Category = "System",
                        Key = "SetupComplete",
                        Value = "true",
                        CreatedAt = DateTime.UtcNow,
                        UpdatedAt = DateTime.UtcNow
                    });
                    db.SaveChanges();
                }
                
                _databaseInitialized = true;
            }
        }
        
        return host;
    }
}