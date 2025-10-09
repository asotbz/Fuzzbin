window.setupKeyboardShortcuts = (dotNetRef) => {
    let isInputFocused = false;
    
    // Track focus on input elements
    document.addEventListener('focusin', (e) => {
        const tagName = e.target.tagName.toLowerCase();
        const isEditable = e.target.contentEditable === 'true';
        isInputFocused = tagName === 'input' || tagName === 'textarea' || tagName === 'select' || isEditable;
    });
    
    document.addEventListener('focusout', () => {
        isInputFocused = false;
    });
    
    // Handle keyboard events
    const keyboardHandler = (e) => {
        // Don't handle shortcuts when typing in input fields
        if (isInputFocused && e.key !== 'Escape') {
            return;
        }
        
        // Prevent default for certain keys
        const preventDefaultKeys = [' ', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', '/'];
        if (preventDefaultKeys.includes(e.key) && !isInputFocused) {
            e.preventDefault();
        }
        
        // Handle Ctrl key combinations
        if (e.ctrlKey) {
            const ctrlKeys = ['a', 'v', 'c', 'd', 'h'];
            if (ctrlKeys.includes(e.key.toLowerCase())) {
                e.preventDefault();
            }
        }

        if (e.altKey) {
            const altKeys = ['h', 'v', 'd', 'i', 'c', 'l', 's', 't', 'o', 'q'];
            if (altKeys.includes(e.key.toLowerCase())) {
                e.preventDefault();
            }
        }

        // Send to .NET
        dotNetRef.invokeMethodAsync('HandleKeyPress', e.key, e.ctrlKey, e.shiftKey, e.altKey);
    };
    
    document.addEventListener('keydown', keyboardHandler);
    
    // Store handler reference for cleanup
    window._keyboardHandler = keyboardHandler;
};

window.removeKeyboardShortcuts = () => {
    if (window._keyboardHandler) {
        document.removeEventListener('keydown', window._keyboardHandler);
        delete window._keyboardHandler;
    }
};

// Focus search input
window.focusSearch = () => {
    const searchInput = document.querySelector('input[placeholder*="Search"]');
    if (searchInput) {
        searchInput.focus();
        searchInput.select();
    }
};
