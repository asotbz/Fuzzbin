window.dragDropInterop = {
    initializeSortable: function (element, dotNetRef) {
        if (!element) return;
        
        // Initialize Sortable.js for drag and drop
        const sortable = new Sortable(element, {
            animation: 150,
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            dragClass: 'sortable-drag',
            handle: '.drag-handle',
            
            onEnd: function (evt) {
                // Notify Blazor component about the reordering
                dotNetRef.invokeMethodAsync('OnItemReordered', evt.oldIndex, evt.newIndex);
            }
        });
        
        // Store reference for cleanup
        element._sortableInstance = sortable;
        
        return sortable;
    },
    
    destroySortable: function (element) {
        if (element && element._sortableInstance) {
            element._sortableInstance.destroy();
            delete element._sortableInstance;
        }
    },
    
    // Simple drag and drop for file uploads
    initializeDropZone: function (element, dotNetRef) {
        if (!element) return;
        
        const preventDefault = (e) => {
            e.preventDefault();
            e.stopPropagation();
        };
        
        const handleDragEnter = (e) => {
            preventDefault(e);
            element.classList.add('drag-over');
        };
        
        const handleDragLeave = (e) => {
            preventDefault(e);
            if (e.target === element) {
                element.classList.remove('drag-over');
            }
        };
        
        const handleDrop = async (e) => {
            preventDefault(e);
            element.classList.remove('drag-over');
            
            const files = Array.from(e.dataTransfer.files);
            const fileData = [];
            
            for (const file of files) {
                fileData.push({
                    name: file.name,
                    size: file.size,
                    type: file.type,
                    lastModified: file.lastModified
                });
            }
            
            // Notify Blazor component about dropped files
            await dotNetRef.invokeMethodAsync('OnFilesDropped', fileData);
        };
        
        element.addEventListener('dragenter', handleDragEnter);
        element.addEventListener('dragover', preventDefault);
        element.addEventListener('dragleave', handleDragLeave);
        element.addEventListener('drop', handleDrop);
        
        // Store handlers for cleanup
        element._dropHandlers = {
            dragenter: handleDragEnter,
            dragover: preventDefault,
            dragleave: handleDragLeave,
            drop: handleDrop
        };
    },
    
    destroyDropZone: function (element) {
        if (element && element._dropHandlers) {
            element.removeEventListener('dragenter', element._dropHandlers.dragenter);
            element.removeEventListener('dragover', element._dropHandlers.dragover);
            element.removeEventListener('dragleave', element._dropHandlers.dragleave);
            element.removeEventListener('drop', element._dropHandlers.drop);
            delete element._dropHandlers;
        }
    }
};