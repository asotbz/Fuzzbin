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
            Primary = "#7D3C98",
            PrimaryLighten = "#9B59B6",
            PrimaryDarken = "#5B2C6F",
            PrimaryContrastText = "#FDFEFE",
            Secondary = "#2E4053",
            SecondaryLighten = "#526476",
            SecondaryDarken = "#1B2836",
            SecondaryContrastText = "#FDFEFE",
            Tertiary = "#D5DBDB",
            TertiaryLighten = "#EEF1F1",
            TertiaryDarken = "#AEB6B6",
            TertiaryContrastText = "#212F3D",
            Info = "#5DADE2",
            InfoLighten = "#AEDFF7",
            InfoDarken = "#3498DB",
            InfoContrastText = "#0B2636",
            Success = "#58D68D",
            SuccessLighten = "#A9F2C9",
            SuccessDarken = "#27AE60",
            SuccessContrastText = "#0D2516",
            Warning = "#F4D03F",
            WarningLighten = "#FAE69E",
            WarningDarken = "#B7950B",
            WarningContrastText = "#3D2E04",
            Error = "#E74C3C",
            ErrorLighten = "#F5A398",
            ErrorDarken = "#C0392B",
            ErrorContrastText = "#FDFEFE",
            Background = "#FDFEFE",
            BackgroundGray = "#EBEEF0",
            Surface = "#F8F9F9",
            AppbarBackground = "#FDFEFE",
            AppbarText = "#212F3D",
            DrawerBackground = "#EBEEF0",
            DrawerText = "#212F3D",
            TextPrimary = "#212F3D",
            TextSecondary = "#5A6A78",
            TextDisabled = "#A0A7AD",
            LinesDefault = "#D5DBDB",
            LinesInputs = "#CACFD2"
        },
        PaletteDark = new PaletteDark
        {
            Primary = "#7D3C98",
            PrimaryLighten = "#9B59B6",
            PrimaryDarken = "#5B2C6F",
            PrimaryContrastText = "#FDFEFE",
            Secondary = "#2E4053",
            SecondaryLighten = "#526476",
            SecondaryDarken = "#1B2836",
            SecondaryContrastText = "#FDFEFE",
            Tertiary = "#556070",
            TertiaryLighten = "#707C8E",
            TertiaryDarken = "#3B4654",
            TertiaryContrastText = "#F8F9F9",
            Info = "#6EB9E8",
            InfoLighten = "#95CCF1",
            InfoDarken = "#3F92C4",
            InfoContrastText = "#081420",
            Success = "#6FDFA3",
            SuccessLighten = "#9BEFC3",
            SuccessDarken = "#3DAF78",
            SuccessContrastText = "#071E12",
            Warning = "#F6DB7B",
            WarningLighten = "#F9E69F",
            WarningDarken = "#C9B154",
            WarningContrastText = "#2C2205",
            Error = "#FF8474",
            ErrorLighten = "#FFADA3",
            ErrorDarken = "#E15C4C",
            ErrorContrastText = "#160503",
            Background = "#101218",
            BackgroundGray = "#1B1F26",
            Surface = "#161B23",
            AppbarBackground = "#161B23",
            AppbarText = "#F8F9F9",
            DrawerBackground = "#12161E",
            DrawerText = "#E5E9F0",
            TextPrimary = "#E5E9F0",
            TextSecondary = "#B3B9C4",
            TextDisabled = "#7F8792",
            LinesDefault = "#2C3440",
            LinesInputs = "#343E4C"
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
