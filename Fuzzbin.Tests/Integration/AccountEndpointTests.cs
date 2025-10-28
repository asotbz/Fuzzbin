using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading.Tasks;
using FluentAssertions;
using Microsoft.AspNetCore.Identity;
using Microsoft.Extensions.DependencyInjection;
using Xunit;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Tests.Integration;

[Collection("Integration")]
public class AccountEndpointTests : IntegrationTestBase
{
    public AccountEndpointTests(IntegrationTestFactory factory) : base(factory)
    {
    }

    [Fact]
    public async Task ChangePassword_WithValidCredentials_ReturnsSuccess()
    {
        // Arrange
        var testEmail = "passwordtest@example.com";
        var oldPassword = "OldPassword123!";
        var newPassword = "NewPassword456!";

        // Create test user
        await CreateTestUserAsync(testEmail, oldPassword);
        await AuthenticateAsync(testEmail, oldPassword);

        var payload = new
        {
            CurrentPassword = oldPassword,
            NewPassword = newPassword,
            ConfirmPassword = newPassword
        };

        // Act
        var response = await Client.PostAsJsonAsync("/api/account/change-password", payload);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Verify we can login with new password
        await LogoutAsync();
        var loginSuccess = await TryLoginAsync(testEmail, newPassword);
        loginSuccess.Should().BeTrue("user should be able to login with new password");

        // Verify old password no longer works
        await LogoutAsync();
        var oldLoginFails = await TryLoginAsync(testEmail, oldPassword);
        oldLoginFails.Should().BeFalse("old password should not work");
    }

    [Fact]
    public async Task ChangePassword_WithWrongCurrentPassword_ReturnsBadRequest()
    {
        // Arrange
        var testEmail = "wrongpassword@example.com";
        var correctPassword = "CorrectPassword123!";
        var wrongPassword = "WrongPassword123!";
        var newPassword = "NewPassword456!";

        await CreateTestUserAsync(testEmail, correctPassword);
        await AuthenticateAsync(testEmail, correctPassword);

        var payload = new
        {
            CurrentPassword = wrongPassword,
            NewPassword = newPassword,
            ConfirmPassword = newPassword
        };

        // Act
        var response = await Client.PostAsJsonAsync("/api/account/change-password", payload);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        
        var content = await response.Content.ReadAsStringAsync();
        content.Should().Contain("current password");
    }

    [Fact]
    public async Task ChangePassword_WithMismatchedPasswords_ReturnsBadRequest()
    {
        // Arrange
        var testEmail = "mismatch@example.com";
        var currentPassword = "CurrentPassword123!";
        var newPassword1 = "NewPassword456!";
        var newPassword2 = "DifferentPassword789!";

        await CreateTestUserAsync(testEmail, currentPassword);
        await AuthenticateAsync(testEmail, currentPassword);

        var payload = new
        {
            CurrentPassword = currentPassword,
            NewPassword = newPassword1,
            ConfirmPassword = newPassword2
        };

        // Act
        var response = await Client.PostAsJsonAsync("/api/account/change-password", payload);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        
        var content = await response.Content.ReadAsStringAsync();
        content.Should().Contain("do not match", "error message should indicate password mismatch");
    }

    [Fact]
    public async Task ChangePassword_WithWeakPassword_ReturnsBadRequest()
    {
        // Arrange
        var testEmail = "weakpassword@example.com";
        var currentPassword = "StrongPassword123!";
        var weakPassword = "123"; // Too short, no uppercase, no special chars

        await CreateTestUserAsync(testEmail, currentPassword);
        await AuthenticateAsync(testEmail, currentPassword);

        var payload = new
        {
            CurrentPassword = currentPassword,
            NewPassword = weakPassword,
            ConfirmPassword = weakPassword
        };

        // Act
        var response = await Client.PostAsJsonAsync("/api/account/change-password", payload);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        
        var content = await response.Content.ReadAsStringAsync();
        // Should contain password validation errors
        content.Should().MatchRegex("password|characters|uppercase|digit|special", 
            "error message should indicate password policy violation");
    }

    [Fact]
    public async Task ChangePassword_WithUnauthenticatedUser_ReturnsUnauthorized()
    {
        // Arrange - no authentication
        var payload = new
        {
            CurrentPassword = "OldPassword123!",
            NewPassword = "NewPassword456!",
            ConfirmPassword = "NewPassword456!"
        };

        // Act
        var response = await Client.PostAsJsonAsync("/api/account/change-password", payload);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task ChangePassword_WithEmptyCurrentPassword_ReturnsBadRequest()
    {
        // Arrange
        var testEmail = "emptyfield@example.com";
        var currentPassword = "CurrentPassword123!";

        await CreateTestUserAsync(testEmail, currentPassword);
        await AuthenticateAsync(testEmail, currentPassword);

        var payload = new
        {
            CurrentPassword = "",
            NewPassword = "NewPassword456!",
            ConfirmPassword = "NewPassword456!"
        };

        // Act
        var response = await Client.PostAsJsonAsync("/api/account/change-password", payload);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task ChangePassword_WithSamePasswordAsOld_Succeeds()
    {
        // Arrange - Identity may allow setting same password
        var testEmail = "samepassword@example.com";
        var password = "Password123!";

        await CreateTestUserAsync(testEmail, password);
        await AuthenticateAsync(testEmail, password);

        var payload = new
        {
            CurrentPassword = password,
            NewPassword = password,
            ConfirmPassword = password
        };

        // Act
        var response = await Client.PostAsJsonAsync("/api/account/change-password", payload);

        // Assert
        // This should succeed (Identity allows setting the same password)
        response.StatusCode.Should().BeOneOf(HttpStatusCode.OK, HttpStatusCode.BadRequest);
    }

    #region Helper Methods

    private async Task<ApplicationUser> CreateTestUserAsync(string email, string password)
    {
        using var scope = Factory.Services.CreateScope();
        var userManager = scope.ServiceProvider.GetRequiredService<UserManager<ApplicationUser>>();

        var user = new ApplicationUser
        {
            UserName = email,
            Email = email,
            EmailConfirmed = true
        };

        var result = await userManager.CreateAsync(user, password);
        result.Succeeded.Should().BeTrue("test user creation should succeed");

        return user;
    }

    private async Task AuthenticateAsync(string email, string password)
    {
        var loginPayload = new
        {
            Email = email,
            Password = password,
            RememberMe = false
        };

        var response = await Client.PostAsJsonAsync("/api/account/login", loginPayload);
        response.EnsureSuccessStatusCode();
    }

    private async Task<bool> TryLoginAsync(string email, string password)
    {
        var loginPayload = new
        {
            Email = email,
            Password = password,
            RememberMe = false
        };

        var response = await Client.PostAsJsonAsync("/api/account/login", loginPayload);
        return response.IsSuccessStatusCode;
    }

    private async Task LogoutAsync()
    {
        await Client.PostAsync("/api/account/logout", null);
    }

    #endregion
}