using MudBlazor;
using Microsoft.Extensions.Logging;
using Microsoft.JSInterop;

namespace Fuzzbin.Web.Services;

public sealed class ThemeService
{
    private const string StorageKey = "fz:theme:preference";
    private readonly IJSRuntime _jsRuntime;
    private readonly ILogger<ThemeService> _logger;
    private bool _initialized;

    public event Action? ThemeChanged;

    public ThemeService(IJSRuntime jsRuntime, ILogger<ThemeService> logger)
    {
        _jsRuntime = jsRuntime;
        _logger = logger;
    }

    private readonly MudTheme _theme = new()
    {
        PaletteLight = new PaletteLight
        {
            Primary = "#4C6EF5",
            Secondary = "#868E96",
            Background = "#F8F9FA",
            Surface = "#FFFFFF",
            AppbarBackground = "#FFFFFF",
            AppbarText = "#212529",
            DrawerBackground = "#F1F3F5",
            DrawerText = "#212529",
            Success = "#2F9E44",
            Warning = "#F59F00",
            Error = "#E03131"
        },
        PaletteDark = new PaletteDark
        {
            Primary = "#748FFC",
            Secondary = "#ADB5BD",
            Background = "#1A1B1E",
            Surface = "#222326",
            AppbarBackground = "#222326",
            AppbarText = "#F8F9FA",
            DrawerBackground = "#1F2023",
            DrawerText = "#F1F3F5",
            Success = "#51CF66",
            Warning = "#FCC419",
            Error = "#FF6B6B"
        }
    };

    public bool IsDarkMode { get; private set; }

    public MudTheme Theme => _theme;

    public async Task EnsureInitializedAsync()
    {
        if (_initialized)
        {
            return;
        }

        var storedPreference = await GetStoredPreferenceAsync();
        var systemPreference = await GetSystemPreferenceAsync();

        IsDarkMode = storedPreference ?? systemPreference;
        _initialized = true;
        _logger.LogInformation("ThemeService initialized. Stored={StoredPreference}, System={SystemPreference}, ActiveMode={Mode}",
            storedPreference, systemPreference, IsDarkMode ? "Dark" : "Light");
        ThemeChanged?.Invoke();
    }

    public async Task ToggleAsync()
    {
        await SetModeAsync(!IsDarkMode);
    }

    public async Task SetModeAsync(bool darkMode)
    {
        if (IsDarkMode == darkMode)
        {
            _logger.LogTrace("ThemeService received SetModeAsync with no change (Mode={Mode})", darkMode ? "Dark" : "Light");
            return;
        }

        IsDarkMode = darkMode;
        await PersistPreferenceAsync(darkMode);
        _logger.LogInformation("Theme mode changed to {Mode}", darkMode ? "Dark" : "Light");
        ThemeChanged?.Invoke();
    }

    private async Task PersistPreferenceAsync(bool darkMode)
    {
        try
        {
            await _jsRuntime.InvokeVoidAsync("localStorage.setItem", StorageKey, darkMode ? "dark" : "light");
            _logger.LogTrace("Persisted theme preference to local storage (Mode={Mode})", darkMode ? "Dark" : "Light");
        }
        catch
        {
            // Ignore storage failures (private browsing, etc.)
            _logger.LogWarning("Unable to persist theme preference to local storage. Continuing without persistence.");
        }
    }

    private async Task<bool?> GetStoredPreferenceAsync()
    {
        try
        {
            var value = await _jsRuntime.InvokeAsync<string?>("localStorage.getItem", StorageKey);
            var preference = value?.Trim().ToLowerInvariant() switch
            {
                "dark" => true,
                "light" => false,
                _ => (bool?)null
            };
            _logger.LogTrace("Loaded stored theme preference: {Preference}", preference);
            return preference;
        }
        catch
        {
            _logger.LogDebug("Failed to read stored theme preference; defaulting to system preference.");
            return null;
        }
    }

    private async Task<bool> GetSystemPreferenceAsync()
    {
        try
        {
            var prefersDark = await _jsRuntime.InvokeAsync<bool>("themeInterop.prefersDarkMode");
            _logger.LogTrace("System prefers dark mode: {PrefersDark}", prefersDark);
            return prefersDark;
        }
        catch
        {
            _logger.LogDebug("Unable to determine system color scheme preference; defaulting to light mode.");
            return false;
        }
    }
}
