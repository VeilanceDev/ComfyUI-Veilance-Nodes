import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

/**
 * Prompt Selector Extension
 * Adds refresh functionality and searchable dropdowns to the PromptSelector node.
 */
app.registerExtension({
    name: "Veilance.PromptSelector",

    async setup() {
        // Extension setup - nothing needed on initial load
    },

    /**
     * Add refresh option to node right-click menu
     */
    getNodeMenuItems(node) {
        const items = [];

        if (node.comfyClass?.startsWith("PromptSelector")) {
            items.push({
                content: "🔄 Refresh Prompt Lists",
                callback: async () => {
                    await refreshPromptLists(node);
                }
            });
        }

        return items;
    },

    /**
     * Add refresh button and enhance combo widgets when node is created
     */
    async nodeCreated(node) {
        if (node.comfyClass?.startsWith("PromptSelector")) {
            // Add a button widget to the node
            const refreshWidget = node.addWidget(
                "button",
                "🔄 Refresh Lists",
                null,
                async () => {
                    await refreshPromptLists(node);
                },
                {}
            );

            // Store reference to widget
            node.refreshWidget = refreshWidget;

            // Enhance combo widgets with search functionality
            enhanceComboWidgets(node);
        }
    }
});

/**
 * Enhance combo widgets with search/filter functionality
 */
function enhanceComboWidgets(node) {
    if (!node.widgets) return;

    for (const widget of node.widgets) {
        if (widget.type !== "combo") continue;
        if (widget._searchEnhanced) continue; // Already enhanced

        // Store original callback
        const originalCallback = widget.callback;
        const originalOptions = widget.options;

        // Create a custom draw function to show search hint
        const originalDraw = widget.draw;

        // Override the combo's mouse handler to add search
        widget._searchEnhanced = true;
        widget._searchMode = false;
        widget._searchQuery = "";
        widget._filteredValues = null;

        // Store original values getter
        const getValues = () => {
            if (widget.options?.values) {
                return typeof widget.options.values === "function"
                    ? widget.options.values()
                    : widget.options.values;
            }
            return [];
        };

        // Override combo click to show search dialog
        const originalMouseDown = widget.mouse;
        widget.mouse = function (event, pos, node) {
            if (event.type === "mousedown") {
                showSearchableCombo(widget, getValues(), node);
                return true;
            }
            return originalMouseDown?.call(this, event, pos, node);
        };
    }
}

/**
 * Show a searchable combo dialog
 */
function showSearchableCombo(widget, values, node) {
    // Create overlay
    const overlay = document.createElement("div");
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        z-index: 10000;
        display: flex;
        justify-content: center;
        align-items: center;
    `;

    // Create dialog
    const dialog = document.createElement("div");
    dialog.style.cssText = `
        background: #2a2a2a;
        border: 1px solid #555;
        border-radius: 8px;
        padding: 16px;
        min-width: 300px;
        max-width: 500px;
        max-height: 80vh;
        display: flex;
        flex-direction: column;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    `;

    // Create search input
    const searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.placeholder = "Type to filter...";
    searchInput.style.cssText = `
        width: 100%;
        padding: 10px 12px;
        margin-bottom: 12px;
        border: 1px solid #555;
        border-radius: 4px;
        background: #1a1a1a;
        color: #fff;
        font-size: 14px;
        outline: none;
        box-sizing: border-box;
    `;

    // Create options list
    const optionsList = document.createElement("div");
    optionsList.style.cssText = `
        flex: 1;
        overflow-y: auto;
        max-height: 400px;
    `;

    // Render options
    function renderOptions(filter = "") {
        optionsList.innerHTML = "";
        const filterLower = filter.toLowerCase();

        const filteredValues = values.filter(v =>
            v.toLowerCase().includes(filterLower)
        );

        for (const value of filteredValues) {
            const option = document.createElement("div");
            option.textContent = value;
            option.style.cssText = `
                padding: 8px 12px;
                cursor: pointer;
                border-radius: 4px;
                margin-bottom: 2px;
                transition: background 0.15s;
                ${widget.value === value ? "background: #4a4a4a;" : ""}
            `;

            option.addEventListener("mouseenter", () => {
                option.style.background = "#3a3a3a";
            });

            option.addEventListener("mouseleave", () => {
                option.style.background = widget.value === value ? "#4a4a4a" : "";
            });

            option.addEventListener("click", () => {
                widget.value = value;
                widget.callback?.(value);
                node.setDirtyCanvas(true, true);
                document.body.removeChild(overlay);
            });

            optionsList.appendChild(option);
        }

        if (filteredValues.length === 0) {
            const noResults = document.createElement("div");
            noResults.textContent = "No matches found";
            noResults.style.cssText = `
                padding: 12px;
                color: #888;
                text-align: center;
                font-style: italic;
            `;
            optionsList.appendChild(noResults);
        }
    }

    // Initial render
    renderOptions();

    // Filter on input
    searchInput.addEventListener("input", (e) => {
        renderOptions(e.target.value);
    });

    // Handle escape key
    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            document.body.removeChild(overlay);
        } else if (e.key === "Enter") {
            const firstOption = optionsList.querySelector("div");
            if (firstOption) {
                firstOption.click();
            }
        }
    });

    // Close on overlay click
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) {
            document.body.removeChild(overlay);
        }
    });

    // Assemble dialog
    dialog.appendChild(searchInput);
    dialog.appendChild(optionsList);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // Focus search input
    searchInput.focus();
}

/**
 * Call the refresh API endpoint and update the node widgets
 */
async function refreshPromptLists(node) {
    showNotification("🔄 Refreshing prompt lists...", "info");

    try {
        // Call the refresh endpoint to reload files on the backend
        const response = await api.fetchApi("/prompt_selector/refresh", {
            method: "POST"
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();

        if (result.status !== "ok") {
            throw new Error(result.message || "Unknown error");
        }

        // Fetch fresh node definitions from the server for this node type only
        const objectInfoResponse = await api.fetchApi(`/object_info/${node.comfyClass}`);
        if (!objectInfoResponse.ok) {
            throw new Error("Failed to fetch node info");
        }
        const nodeInfo = await objectInfoResponse.json();

        // Get the node definition
        const nodeDef = nodeInfo[node.comfyClass];
        if (!nodeDef?.input) {
            throw new Error("Invalid node definition received");
        }

        // Merge required and optional inputs
        const allInputs = { ...nodeDef.input.required, ...nodeDef.input.optional };

        // Debug: log what we're working with
        console.log("[PromptSelector] Node widgets:", node.widgets?.map(w => ({ name: w.name, type: w.type })));
        console.log("[PromptSelector] Server inputs:", Object.keys(allInputs));

        let updatedCount = 0;

        // Update each combo widget with new options
        for (const widget of node.widgets || []) {
            if (widget.type !== "combo") continue;

            // Find matching input from server
            const inputDef = allInputs[widget.name];
            if (!inputDef) {
                console.log(`[PromptSelector] No match for widget: ${widget.name}`);
                continue;
            }

            const newOptions = inputDef[0];
            if (!Array.isArray(newOptions)) continue;

            // Update widget options
            widget.options.values = newOptions;
            updatedCount++;

            // Reset value if no longer valid
            if (!newOptions.includes(widget.value)) {
                widget.value = newOptions[0] || "❌ Disabled";
            }
        }

        // Force canvas redraw
        node.setDirtyCanvas(true, true);
        app.graph.setDirtyCanvas(true, true);

        // Success notification
        showNotification(
            `✅ Refreshed! ${result.prompts} prompts in ${result.categories} categories (${updatedCount} widgets updated)`,
            "success"
        );

    } catch (error) {
        console.error("[PromptSelector] Refresh failed:", error);
        showNotification(`❌ Refresh failed: ${error.message}`, "error");
    }
}


/**
 * Show a toast notification to the user
 */
function showNotification(message, type = "info") {
    // Log to console always
    console.log(`[PromptSelector] ${type}: ${message}`);

    // Try ComfyUI's extensionManager toast (newer API)
    if (app.extensionManager?.toast) {
        app.extensionManager.toast.add({
            severity: type === "error" ? "error" : type === "success" ? "success" : "info",
            summary: "Prompt Selector",
            detail: message,
            life: 3000
        });
        return;
    }

    // Try app.ui.toast (older API)
    if (app.ui?.toast) {
        app.ui.toast({
            content: message,
            type: type,
            timeout: 3000
        });
        return;
    }

    // Try window toast if available
    if (window.toast) {
        window.toast(message, { type, timeout: 3000 });
        return;
    }
}
