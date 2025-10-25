using System;
using System.Net;
using System.Net.Http;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace Fuzzbin.Tests.Integration;

public class ManageRoutesTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public ManageRoutesTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    [Theory]
    [InlineData("/manage/genres")]
    [InlineData("/manage/tags")]
    public async Task ManageRoutes_ShouldReturn200OrRedirect(string url)
    {
        // Act
        var response = await _client.GetAsync(url);

        // Assert - Either 200 OK or 302 Redirect (to login if auth is required)
        Assert.True(
            response.StatusCode == HttpStatusCode.OK ||
            response.StatusCode == HttpStatusCode.Redirect ||
            response.StatusCode == HttpStatusCode.Found,
            $"Expected 200 or redirect, but got {response.StatusCode} for {url}");
    }

    [Theory]
    [InlineData("/api/genres")]
    [InlineData("/api/tags")]
    public async Task ManageApiEndpoints_ShouldBeAccessible(string url)
    {
        // Act
        var response = await _client.GetAsync(url);

        // Assert - Should not be 404
        Assert.NotEqual(HttpStatusCode.NotFound, response.StatusCode);
    }
}