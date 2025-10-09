using Microsoft.AspNetCore.Components;
using Microsoft.AspNetCore.Components.Web;
using Microsoft.JSInterop;

namespace Fuzzbin.Web.Services;

public class KeyboardShortcutService : IDisposable
{
    private readonly IJSRuntime _jsRuntime;
    private readonly NavigationManager _navigation;
    private DotNetObjectReference<KeyboardShortcutService>? _dotNetRef;
    
    // Event handlers for various shortcuts
    public event Action? OnTogglePlayPause;
    public event Action? OnNext;
    public event Action? OnPrevious;
    public event Action? OnVolumeUp;
    public event Action? OnVolumeDown;
    public event Action? OnToggleMute;
    public event Action? OnToggleFullscreen;
    public event Action? OnSearch;
    public event Action? OnAddVideo;
    public event Action? OnShowHelp;
    public event Action? OnEscape;
    
    private bool _isInitialized = false;
    private readonly Dictionary<string, ShortcutRegistration> _shortcuts = new();
    
    public KeyboardShortcutService(IJSRuntime jsRuntime, NavigationManager navigation)
    {
        _jsRuntime = jsRuntime;
        _navigation = navigation;
    }
    
    public async Task InitializeAsync()
    {
        if (_isInitialized) return;
        
        _dotNetRef = DotNetObjectReference.Create(this);
        await _jsRuntime.InvokeVoidAsync("setupKeyboardShortcuts", _dotNetRef);
        _isInitialized = true;
    }
    
    public void RegisterShortcut(string shortcut, string category, Action action, string? description = null)
    {
        _shortcuts[shortcut] = new ShortcutRegistration(category, description ?? BuildFriendlyDescription(shortcut), action);
    }
    
    public void UnregisterShortcut(string shortcut)
    {
        _shortcuts.Remove(shortcut);
    }
    
    [JSInvokable]
    public void HandleKeyPress(string key, bool ctrlKey, bool shiftKey, bool altKey)
    {
        // Build shortcut string
        var shortcut = BuildShortcutString(key, ctrlKey, shiftKey, altKey);
        
        // Check registered shortcuts first
        if (_shortcuts.TryGetValue(shortcut, out var registeredShortcut))
        {
            registeredShortcut.Action?.Invoke();
            return;
        }
        
        // Media controls
        if (key == " " && !ctrlKey && !shiftKey && !altKey) // Space
        {
            OnTogglePlayPause?.Invoke();
        }
        else if (key == "ArrowRight" && !ctrlKey && !shiftKey && !altKey) // Right arrow
        {
            OnNext?.Invoke();
        }
        else if (key == "ArrowLeft" && !ctrlKey && !shiftKey && !altKey) // Left arrow
        {
            OnPrevious?.Invoke();
        }
        else if (key == "ArrowUp" && !ctrlKey && !shiftKey && !altKey) // Up arrow
        {
            OnVolumeUp?.Invoke();
        }
        else if (key == "ArrowDown" && !ctrlKey && !shiftKey && !altKey) // Down arrow
        {
            OnVolumeDown?.Invoke();
        }
        else if (key == "m" && !ctrlKey && !shiftKey && !altKey) // M
        {
            OnToggleMute?.Invoke();
        }
        else if (key == "f" && !ctrlKey && !shiftKey && !altKey) // F
        {
            OnToggleFullscreen?.Invoke();
        }
        
        // Navigation shortcuts
        else if (key == "/" && !ctrlKey && !shiftKey && !altKey) // Forward slash
        {
            OnSearch?.Invoke();
        }
        else if (key == "a" && ctrlKey && !shiftKey && !altKey) // Ctrl+A
        {
            OnAddVideo?.Invoke();
        }
        else if (key == "v" && ctrlKey && !shiftKey && !altKey) // Ctrl+V
        {
            _navigation.NavigateTo("/videos");
        }
        else if (key == "c" && ctrlKey && !shiftKey && !altKey) // Ctrl+C
        {
            _navigation.NavigateTo("/collections");
        }
        else if (key == "d" && ctrlKey && !shiftKey && !altKey) // Ctrl+D
        {
            _navigation.NavigateTo("/downloads");
        }
        else if (key == "h" && ctrlKey && !shiftKey && !altKey) // Ctrl+H
        {
            _navigation.NavigateTo("/");
        }
        
        // Help and escape
        else if (key == "?" && !ctrlKey && shiftKey && !altKey) // Shift+?
        {
            OnShowHelp?.Invoke();
        }
        else if (key == "Escape" && !ctrlKey && !shiftKey && !altKey) // Escape
        {
            OnEscape?.Invoke();
        }
    }
    
    private string BuildShortcutString(string key, bool ctrlKey, bool shiftKey, bool altKey)
    {
        var parts = new List<string>();
        if (ctrlKey) parts.Add("Ctrl");
        if (altKey) parts.Add("Alt");
        if (shiftKey) parts.Add("Shift");
        parts.Add(key);
        return string.Join("+", parts);
    }
    
    public List<ShortcutInfo> GetShortcuts()
    {
        var shortcuts = new List<ShortcutInfo>
        {
            new ShortcutInfo { Category = "Media Controls", Key = "Space", Description = "Play/Pause" },
            new ShortcutInfo { Category = "Media Controls", Key = "→", Description = "Next track" },
            new ShortcutInfo { Category = "Media Controls", Key = "←", Description = "Previous track" },
            new ShortcutInfo { Category = "Media Controls", Key = "↑", Description = "Volume up" },
            new ShortcutInfo { Category = "Media Controls", Key = "↓", Description = "Volume down" },
            new ShortcutInfo { Category = "Media Controls", Key = "M", Description = "Toggle mute" },
            new ShortcutInfo { Category = "Media Controls", Key = "F", Description = "Toggle fullscreen" },
            
            new ShortcutInfo { Category = "Navigation", Key = "/", Description = "Focus search" },
            new ShortcutInfo { Category = "Navigation", Key = "Ctrl+A", Description = "Add video" },
            new ShortcutInfo { Category = "Navigation", Key = "Ctrl+V", Description = "Go to Videos" },
            new ShortcutInfo { Category = "Navigation", Key = "Ctrl+C", Description = "Go to Collections" },
            new ShortcutInfo { Category = "Navigation", Key = "Ctrl+D", Description = "Go to Downloads" },
            new ShortcutInfo { Category = "Navigation", Key = "Ctrl+H", Description = "Go to Home" },
            
            new ShortcutInfo { Category = "General", Key = "?", Description = "Show keyboard shortcuts" },
            new ShortcutInfo { Category = "General", Key = "Esc", Description = "Close dialog/Exit fullscreen" }
        };
        
        // Add registered shortcuts
        foreach (var kvp in _shortcuts)
        {
            shortcuts.Add(new ShortcutInfo
            {
                Category = kvp.Value.Category,
                Key = kvp.Key,
                Description = kvp.Value.Description
            });
        }

        return shortcuts;
    }

    private static string BuildFriendlyDescription(string shortcut)
    {
        return shortcut.Replace("+", " + ");
    }
    
    public void Dispose()
    {
        if (_dotNetRef != null)
        {
            _jsRuntime.InvokeVoidAsync("removeKeyboardShortcuts");
            _dotNetRef.Dispose();
        }
    }
    
    public class ShortcutInfo
    {
        public string Category { get; set; } = "";
        public string Key { get; set; } = "";
        public string Description { get; set; } = "";
    }

    private sealed record ShortcutRegistration(string Category, string Description, Action Action);
}
