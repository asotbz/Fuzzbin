using System.Net.Http;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace Fuzzbin.Tests.Integration;

[Collection("Integration")]
public abstract class IntegrationTestBase : IClassFixture<IntegrationTestFactory>
{
    protected HttpClient Client { get; }
    protected IntegrationTestFactory Factory { get; }

    protected IntegrationTestBase(IntegrationTestFactory factory)
    {
        Factory = factory;
        Client = factory.CreateClient();
    }
}