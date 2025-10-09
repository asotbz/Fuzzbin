window.contextMenuHelpers = {
    preventDefaultContextMenu: function() {
        document.addEventListener('contextmenu', function(e) {
            // Check if the target is within a video card
            if (e.target.closest('.video-card')) {
                e.preventDefault();
                return false;
            }
        });
    },
    
    openContextMenu: function(x, y, dotNetRef) {
        // This can be used to position the context menu if needed
        if (dotNetRef) {
            dotNetRef.invokeMethodAsync('ShowContextMenuAt', x, y);
        }
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    window.contextMenuHelpers.preventDefaultContextMenu();
});