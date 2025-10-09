using System;
using System.IO;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Identity;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Data.Context;

namespace Fuzzbin.PasswordReset;

class Program
{
    static async Task<int> Main(string[] args)
    {
        Console.WriteLine("Fuzzbin Password Reset Utility");
        Console.WriteLine("===================================\n");

        // Parse command-line arguments
        if (args.Length < 2)
        {
            ShowUsage();
            return 1;
        }

        string? username = null;
        string? password = null;
        string? dbPath = null;

        for (int i = 0; i < args.Length; i++)
        {
            switch (args[i].ToLowerInvariant())
            {
                case "--username" or "-u":
                    if (i + 1 < args.Length)
                        username = args[++i];
                    break;
                case "--password" or "-p":
                    if (i + 1 < args.Length)
                        password = args[++i];
                    break;
                case "--database" or "-d":
                    if (i + 1 < args.Length)
                        dbPath = args[++i];
                    break;
                case "--help" or "-h":
                    ShowUsage();
                    return 0;
            }
        }

        if (string.IsNullOrWhiteSpace(username) || string.IsNullOrWhiteSpace(password))
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine("Error: Username and password are required.\n");
            Console.ResetColor();
            ShowUsage();
            return 1;
        }

        // Determine database path
        if (string.IsNullOrWhiteSpace(dbPath))
        {
            // Default to sibling data directory
            var baseDir = AppDomain.CurrentDomain.BaseDirectory;
            var parentDir = Directory.GetParent(baseDir)?.Parent?.Parent?.Parent?.Parent?.FullName;
            if (parentDir != null)
            {
                dbPath = Path.Combine(parentDir, "Fuzzbin.Web", "data", "fuzzbin.db");
            }

            if (string.IsNullOrWhiteSpace(dbPath) || !File.Exists(dbPath))
            {
                dbPath = Path.Combine("data", "fuzzbin.db");
            }
        }

        if (!File.Exists(dbPath))
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine($"Error: Database not found at: {dbPath}");
            Console.WriteLine("Please specify the database path using --database option.\n");
            Console.ResetColor();
            return 1;
        }

        Console.WriteLine($"Database: {dbPath}");
        Console.WriteLine($"Username: {username}\n");

        try
        {
            var result = await ResetPasswordAsync(dbPath, username, password);
            return result ? 0 : 1;
        }
        catch (Exception ex)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine($"Error: {ex.Message}");
            Console.ResetColor();
            return 1;
        }
    }

    static async Task<bool> ResetPasswordAsync(string dbPath, string username, string password)
    {
        // Build connection string
        var connectionStringBuilder = new SqliteConnectionStringBuilder
        {
            DataSource = dbPath,
            Mode = SqliteOpenMode.ReadWrite
        };

        // Setup services
        var services = new ServiceCollection();

        // Add logging
        services.AddLogging(builder =>
        {
            builder.AddConsole();
            builder.SetMinimumLevel(LogLevel.Warning);
        });

        // Add DbContext
        services.AddDbContext<ApplicationDbContext>(options =>
        {
            options.UseSqlite(connectionStringBuilder.ToString());
        });

        // Add Identity
        services.AddIdentityCore<ApplicationUser>(options =>
        {
            options.Password.RequireDigit = false;
            options.Password.RequireNonAlphanumeric = false;
            options.Password.RequireUppercase = false;
            options.Password.RequiredLength = 8;
        })
        .AddRoles<IdentityRole<Guid>>()
        .AddEntityFrameworkStores<ApplicationDbContext>()
        .AddDefaultTokenProviders();

        var serviceProvider = services.BuildServiceProvider();

        using var scope = serviceProvider.CreateScope();
        var userManager = scope.ServiceProvider.GetRequiredService<UserManager<ApplicationUser>>();
        var logger = scope.ServiceProvider.GetRequiredService<ILogger<Program>>();

        // Find user
        Console.Write("Looking up user... ");
        var user = await userManager.FindByNameAsync(username);
        
        if (user == null)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine("NOT FOUND");
            Console.WriteLine($"\nUser '{username}' does not exist in the database.");
            Console.ResetColor();
            return false;
        }

        Console.ForegroundColor = ConsoleColor.Green;
        Console.WriteLine("FOUND");
        Console.ResetColor();
        Console.WriteLine($"Display Name: {user.DisplayName ?? "(not set)"}");
        Console.WriteLine($"User ID: {user.Id}");
        Console.WriteLine($"Account Status: {(user.IsActive ? "Active" : "Inactive")}\n");

        // Validate password requirements
        if (password.Length < 8)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine("Error: Password must be at least 8 characters long.");
            Console.ResetColor();
            return false;
        }

        // Reset password
        Console.Write("Resetting password... ");
        
        try
        {
            // Generate password reset token
            var resetToken = await userManager.GeneratePasswordResetTokenAsync(user);
            
            // Reset the password
            var result = await userManager.ResetPasswordAsync(user, resetToken, password);

            if (result.Succeeded)
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("SUCCESS");
                Console.ResetColor();
                Console.WriteLine($"\nPassword has been reset for user '{username}'.");
                Console.WriteLine("The user can now sign in with the new password.\n");
                
                logger.LogInformation("Password reset successful for user {Username} ({UserId})", username, user.Id);
                return true;
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("FAILED");
                Console.ResetColor();
                Console.WriteLine("\nPassword reset failed:");
                
                foreach (var error in result.Errors)
                {
                    Console.WriteLine($"  - {error.Description}");
                }
                
                Console.WriteLine();
                return false;
            }
        }
        catch (Exception ex)
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine("FAILED");
            Console.ResetColor();
            Console.WriteLine($"\nError: {ex.Message}\n");
            logger.LogError(ex, "Password reset failed for user {Username}", username);
            return false;
        }
    }

    static void ShowUsage()
    {
        Console.WriteLine("Usage:");
        Console.WriteLine("  Fuzzbin.PasswordReset --username <username> --password <password> [--database <path>]");
        Console.WriteLine();
        Console.WriteLine("Options:");
        Console.WriteLine("  -u, --username <username>    Username of the account to reset");
        Console.WriteLine("  -p, --password <password>    New password (minimum 8 characters)");
        Console.WriteLine("  -d, --database <path>        Path to fuzzbin.db (optional)");
        Console.WriteLine("  -h, --help                   Show this help message");
        Console.WriteLine();
        Console.WriteLine("Examples:");
        Console.WriteLine("  Fuzzbin.PasswordReset --username admin --password NewPassword123");
        Console.WriteLine("  Fuzzbin.PasswordReset -u admin -p MySecurePass2024 -d /path/to/fuzzbin.db");
        Console.WriteLine();
    }
}
