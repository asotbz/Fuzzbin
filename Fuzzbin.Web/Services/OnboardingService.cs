using Microsoft.JSInterop;

namespace Fuzzbin.Web.Services;

public sealed class OnboardingService
{
    private const string StorageKey = "fz:onboarding:completed";
    private readonly IJSRuntime _jsRuntime;

    public event Action? OnStateChanged;

    public OnboardingService(IJSRuntime jsRuntime)
    {
        _jsRuntime = jsRuntime;
    }

    public async Task<bool> ShouldShowAsync()
    {
        var completed = await IsCompletedAsync();
        return !completed;
    }

    public async Task<bool> IsCompletedAsync()
    {
        try
        {
            var value = await _jsRuntime.InvokeAsync<string?>("localStorage.getItem", StorageKey);
            return string.Equals(value, "true", StringComparison.OrdinalIgnoreCase);
        }
        catch
        {
            return false;
        }
    }

    public async Task MarkCompletedAsync()
    {
        try
        {
            await _jsRuntime.InvokeVoidAsync("localStorage.setItem", StorageKey, "true");
            OnStateChanged?.Invoke();
        }
        catch
        {
            // ignore storage restrictions
        }
    }

    public async Task ResetAsync()
    {
        try
        {
            await _jsRuntime.InvokeVoidAsync("localStorage.removeItem", StorageKey);
            OnStateChanged?.Invoke();
        }
        catch
        {
            // ignore storage restrictions
        }
    }
}
