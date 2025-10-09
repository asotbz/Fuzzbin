window.themeInterop = window.themeInterop || {};

window.themeInterop.prefersDarkMode = () => {
    if (window.matchMedia) {
        return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
};
