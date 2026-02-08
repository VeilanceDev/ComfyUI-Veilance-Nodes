import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const DISABLED_OPTION = "❌ Disabled";

function getNodeClassName(node) {
    return node?.comfyClass || node?.type || "";
}

function isPromptSelectorNode(node) {
    return getNodeClassName(node).startsWith("PromptSelector");
}

app.registerExtension({
    name: "Veilance.PromptSelector",

    async setup() {
        // No setup required.
    },

    getNodeMenuItems(node) {
        if (!isPromptSelectorNode(node)) {
            return [];
        }
        return [
            {
                content: "🔄 Refresh Prompt Lists",
                callback: async () => {
                    await refreshPromptLists(node);
                },
            },
        ];
    },

    async nodeCreated(node) {
        if (!isPromptSelectorNode(node)) {
            return;
        }

        const refreshWidget = node.addWidget(
            "button",
            "🔄 Refresh Lists",
            null,
            async () => {
                await refreshPromptLists(node);
            },
            {}
        );
        node.refreshWidget = refreshWidget;

        enhanceComboWidgets(node);
    },
});

function enhanceComboWidgets(node) {
    if (!node.widgets) return;

    for (const widget of node.widgets) {
        if (widget.type !== "combo") continue;
        const getValues = () => {
            const values = widget.options?.values;
            if (typeof values === "function") return values();
            return Array.isArray(values) ? values : [];
        };

        attachCanvasComboHandler(widget, node, getValues);
        attachDomComboHandler(widget, node, getValues);
    }
}

function attachCanvasComboHandler(widget, node, getValues) {
    if (widget._searchCanvasEnhanced) return;
    widget._searchCanvasEnhanced = true;

    const originalMouseDown = widget.mouse;
    widget.mouse = function(event, pos, currentNode) {
        const eventType = event?.type;
        const isPrimaryPress =
            (eventType === "mousedown" || eventType === "pointerdown") &&
            (event?.button === undefined || event.button === 0);

        if (isPrimaryPress) {
            showSearchableCombo(widget, getValues(), currentNode || node);
            return true;
        }
        return originalMouseDown?.call(this, event, pos, currentNode);
    };
}

function attachDomComboHandler(widget, node, getValues) {
    const bind = () => {
        const inputEl = widget.inputEl;
        if (!(inputEl instanceof HTMLElement)) {
            return false;
        }

        const existingBinding = widget._searchDomBinding;
        if (existingBinding?.element === inputEl) {
            return true;
        }

        if (existingBinding?.element) {
            existingBinding.element.removeEventListener("pointerdown", existingBinding.pressHandler, true);
            existingBinding.element.removeEventListener("mousedown", existingBinding.pressHandler, true);
            existingBinding.element.removeEventListener("keydown", existingBinding.keyHandler, true);
        }

        const maybeOpenDialog = () => {
            const now = Date.now();
            const lastOpen = widget._searchLastOpenTs || 0;
            if (now - lastOpen < 110) return;
            widget._searchLastOpenTs = now;
            showSearchableCombo(widget, getValues(), node);
        };

        const pressHandler = (event) => {
            if (typeof event.button === "number" && event.button !== 0) return;
            event.preventDefault();
            event.stopPropagation();
            maybeOpenDialog();
        };

        const keyHandler = (event) => {
            if (event.key !== "Enter" && event.key !== " " && event.key !== "ArrowDown") {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            maybeOpenDialog();
        };

        inputEl.addEventListener("pointerdown", pressHandler, true);
        inputEl.addEventListener("mousedown", pressHandler, true);
        inputEl.addEventListener("keydown", keyHandler, true);

        widget._searchDomBinding = {
            element: inputEl,
            pressHandler,
            keyHandler,
        };
        return true;
    };

    if (bind()) {
        widget._searchDomBindScheduled = false;
        return;
    }
    if (widget._searchDomBindScheduled) return;
    widget._searchDomBindScheduled = true;

    let attempts = 0;
    const maxAttempts = 30;
    const tryBind = () => {
        if (bind()) {
            widget._searchDomBindScheduled = false;
            return;
        }
        attempts += 1;
        if (attempts < maxAttempts) {
            setTimeout(tryBind, 200);
            return;
        }
        widget._searchDomBindScheduled = false;
    };
    tryBind();
}

function buildTheme() {
    const rootStyle = getComputedStyle(document.documentElement);
    const isDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ?? true;

    const pick = (varName, fallback) => {
        const value = rootStyle.getPropertyValue(varName).trim();
        return value || fallback;
    };

    return {
        overlay: isDark ? "rgba(0, 0, 0, 0.45)" : "rgba(0, 0, 0, 0.28)",
        dialogBg: pick("--comfy-menu-bg", isDark ? "#262626" : "#f4f4f4"),
        panelBg: pick("--comfy-input-bg", isDark ? "#1d1d1d" : "#ffffff"),
        border: pick("--border-color", isDark ? "#555" : "#c7c7c7"),
        text: pick("--fg-color", isDark ? "#f1f1f1" : "#1a1a1a"),
        muted: pick("--descrip-text", isDark ? "#a0a0a0" : "#6a6a6a"),
        hover: isDark ? "#3a3a3a" : "#e7e7e7",
        selected: isDark ? "#4b4b4b" : "#dcdcdc",
        positiveHeader: isDark ? "#7fd58f" : "#2a7a39",
        negativeHeader: isDark ? "#f08a8a" : "#9b2626",
    };
}

function showSearchableCombo(widget, values, node) {
    const theme = buildTheme();

    const overlay = document.createElement("div");
    overlay.style.cssText = `
        position: fixed;
        inset: 0;
        background: ${theme.overlay};
        z-index: 10000;
        display: flex;
        justify-content: center;
        align-items: center;
    `;

    const dialog = document.createElement("div");
    dialog.style.cssText = `
        background: ${theme.dialogBg};
        border: 1px solid ${theme.border};
        border-radius: 10px;
        padding: 14px;
        min-width: 320px;
        width: min(520px, 90vw);
        max-height: 82vh;
        display: flex;
        flex-direction: column;
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.32);
        position: relative;
    `;

    const searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.placeholder = "Type to filter...";
    searchInput.style.cssText = `
        width: 100%;
        padding: 10px 12px;
        margin-bottom: 10px;
        border: 1px solid ${theme.border};
        border-radius: 6px;
        background: ${theme.panelBg};
        color: ${theme.text};
        font-size: 14px;
        outline: none;
        box-sizing: border-box;
    `;

    const optionsList = document.createElement("div");
    optionsList.style.cssText = `
        flex: 1;
        overflow-y: auto;
        max-height: 440px;
    `;

    let filteredValues = [];
    let optionElements = [];
    let highlightIndex = -1;

    const closeDialog = () => {
        if (overlay.parentElement) {
            overlay.parentElement.removeChild(overlay);
        }
    };

    const setHighlight = (index, shouldScroll = true) => {
        if (!optionElements.length) {
            highlightIndex = -1;
            return;
        }

        const clamped = Math.max(0, Math.min(index, optionElements.length - 1));
        highlightIndex = clamped;

        optionElements.forEach((element, elementIndex) => {
            const value = element.dataset.value || "";
            const isSelectedValue = widget.value === value;
            if (elementIndex === clamped) {
                element.style.background = theme.hover;
            } else {
                element.style.background = isSelectedValue ? theme.selected : "transparent";
            }
        });

        if (shouldScroll) {
            optionElements[clamped].scrollIntoView({ block: "nearest" });
        }
    };

    const commitSelection = (value) => {
        widget.value = value;
        widget.callback?.(value);
        node?.setDirtyCanvas?.(true, true);
        closeDialog();
    };

    const renderOptions = (filter = "") => {
        optionsList.innerHTML = "";
        optionElements = [];

        const filterLower = filter.toLowerCase();
        filteredValues = values.filter((value) => value.toLowerCase().includes(filterLower));

        if (!filteredValues.length) {
            const noResults = document.createElement("div");
            noResults.textContent = "No matches found";
            noResults.style.cssText = `
                padding: 12px;
                color: ${theme.muted};
                text-align: center;
                font-style: italic;
            `;
            optionsList.appendChild(noResults);
            highlightIndex = -1;
            return;
        }

        for (const value of filteredValues) {
            const option = document.createElement("div");
            option.dataset.value = value;
            option.textContent = value;
            option.style.cssText = `
                padding: 8px 10px;
                cursor: pointer;
                border-radius: 5px;
                margin-bottom: 2px;
                transition: background 0.12s ease;
                color: ${theme.text};
                background: ${widget.value === value ? theme.selected : "transparent"};
            `;

            option.addEventListener("mouseenter", () => {
                const hoverIndex = optionElements.indexOf(option);
                if (hoverIndex >= 0) setHighlight(hoverIndex, false);
            });

            option.addEventListener("click", () => commitSelection(value));

            optionsList.appendChild(option);
            optionElements.push(option);
        }

        const selectedIndex = filteredValues.indexOf(widget.value);
        setHighlight(selectedIndex >= 0 ? selectedIndex : 0, false);
    };

    searchInput.addEventListener("input", (event) => {
        renderOptions(event.target.value);
    });

    searchInput.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            event.preventDefault();
            closeDialog();
            return;
        }

        if (event.key === "ArrowDown") {
            event.preventDefault();
            setHighlight(highlightIndex + 1);
            return;
        }

        if (event.key === "ArrowUp") {
            event.preventDefault();
            setHighlight(highlightIndex - 1);
            return;
        }

        if (event.key === "Enter") {
            event.preventDefault();
            if (highlightIndex >= 0 && filteredValues[highlightIndex]) {
                commitSelection(filteredValues[highlightIndex]);
                return;
            }
            if (filteredValues[0]) {
                commitSelection(filteredValues[0]);
            }
        }
    });

    overlay.addEventListener("click", (event) => {
        if (event.target === overlay) {
            closeDialog();
        }
    });

    dialog.appendChild(searchInput);
    dialog.appendChild(optionsList);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    renderOptions();
    searchInput.focus();
}

function getDesiredComboDefinitions(nodeDef) {
    const optionalInputs = nodeDef?.input?.optional || {};
    return Object.entries(optionalInputs)
        .filter(([, inputDef]) => Array.isArray(inputDef?.[0]))
        .map(([name, inputDef]) => {
            const options = Array.isArray(inputDef[0]) ? inputDef[0] : [];
            const config = typeof inputDef[1] === "object" ? inputDef[1] : {};
            return {
                name,
                options,
                defaultValue: config.default ?? options[0] ?? DISABLED_OPTION,
            };
        });
}

function reconcileComboWidgets(node, desiredCombos) {
    if (!node.widgets) {
        node.widgets = [];
    }

    const desiredNames = new Set(desiredCombos.map((combo) => combo.name));
    let removedCount = 0;
    let addedCount = 0;
    let updatedCount = 0;

    for (let i = node.widgets.length - 1; i >= 0; i--) {
        const widget = node.widgets[i];
        if (widget.type !== "combo") continue;
        if (desiredNames.has(widget.name)) continue;
        node.widgets.splice(i, 1);
        removedCount++;
    }

    const comboWidgetByName = new Map(
        (node.widgets || [])
            .filter((widget) => widget.type === "combo")
            .map((widget) => [widget.name, widget])
    );

    for (const combo of desiredCombos) {
        if (comboWidgetByName.has(combo.name)) continue;
        const newWidget = node.addWidget(
            "combo",
            combo.name,
            combo.defaultValue,
            (value) => value,
            { values: combo.options }
        );
        comboWidgetByName.set(combo.name, newWidget);
        addedCount++;
    }

    for (const combo of desiredCombos) {
        const widget = comboWidgetByName.get(combo.name);
        if (!widget) continue;

        widget.options = widget.options || {};
        widget.options.values = combo.options;

        if (!combo.options.includes(widget.value)) {
            widget.value = combo.defaultValue;
        }
        updatedCount++;
    }

    pinRefreshWidgetToBottom(node);

    return { removedCount, addedCount, updatedCount };
}

function pinRefreshWidgetToBottom(node) {
    if (!Array.isArray(node.widgets) || node.widgets.length === 0) {
        return;
    }

    const refreshWidget =
        node.refreshWidget ||
        node.widgets.find(
            (widget) => widget?.type === "button" && widget?.name === "🔄 Refresh Lists"
        );

    if (!refreshWidget) {
        return;
    }

    const currentIndex = node.widgets.indexOf(refreshWidget);
    if (currentIndex < 0 || currentIndex === node.widgets.length - 1) {
        return;
    }

    node.widgets.splice(currentIndex, 1);
    node.widgets.push(refreshWidget);
}

async function updateGlobalNodeDefinitionsIfNeeded(result) {
    const classChanges = [
        ...(result.classes_added || []),
        ...(result.classes_removed || []),
    ];
    if (!classChanges.length) {
        return false;
    }

    try {
        const response = await api.fetchApi("/object_info");
        if (!response.ok) {
            return false;
        }
        const allNodeDefs = await response.json();

        if (typeof app.registerNodesFromDefs === "function") {
            app.registerNodesFromDefs(allNodeDefs);
            return true;
        }
    } catch (error) {
        console.warn("[PromptSelector] Failed to update global node defs:", error);
    }

    return false;
}

async function refreshPromptLists(node) {
    showNotification("🔄 Refreshing prompt lists...", "info");

    try {
        const nodeClass = getNodeClassName(node);
        const response = await api.fetchApi("/prompt_selector/refresh", {
            method: "POST",
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();
        if (result.status !== "ok") {
            throw new Error(result.message || "Unknown error");
        }

        const registryUpdated = await updateGlobalNodeDefinitionsIfNeeded(result);

        let desiredCombos = [];
        const nodeInfoResponse = await api.fetchApi(`/object_info/${nodeClass}`);
        if (nodeInfoResponse.ok) {
            const nodeInfo = await nodeInfoResponse.json();
            desiredCombos = getDesiredComboDefinitions(nodeInfo[nodeClass]);
        } else {
            const classWasRemoved = (result.classes_removed || []).includes(nodeClass);
            if (!classWasRemoved) {
                throw new Error("Failed to fetch refreshed node definition");
            }
        }

        const syncResult = reconcileComboWidgets(node, desiredCombos);
        enhanceComboWidgets(node);

        node.setDirtyCanvas(true, true);
        app.graph.setDirtyCanvas(true, true);

        const classesAdded = (result.classes_added || []).length;
        const classesRemoved = (result.classes_removed || []).length;
        if ((classesAdded || classesRemoved) && !registryUpdated) {
            showNotification(
                "ℹ Prompt Selector categories changed. Reload ComfyUI if new node types are not visible yet.",
                "info"
            );
        }
        showNotification(
            `✅ Refreshed ${result.prompts} prompts (${syncResult.updatedCount} updated, ${syncResult.addedCount} added, ${syncResult.removedCount} removed, node classes +${classesAdded}/-${classesRemoved})`,
            "success"
        );
    } catch (error) {
        console.error("[PromptSelector] Refresh failed:", error);
        showNotification(`❌ Refresh failed: ${error.message}`, "error");
    }
}

function showNotification(message, type = "info") {
    console.log(`[PromptSelector] ${type}: ${message}`);

    if (app.extensionManager?.toast) {
        app.extensionManager.toast.add({
            severity: type === "error" ? "error" : type === "success" ? "success" : "info",
            summary: "Prompt Selector",
            detail: message,
            life: 3500,
        });
        return;
    }

    if (app.ui?.toast) {
        app.ui.toast({
            content: message,
            type: type,
            timeout: 3500,
        });
        return;
    }

    if (window.toast) {
        window.toast(message, { type, timeout: 3500 });
    }
}
