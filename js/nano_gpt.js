import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "NanoGPTTextGenerator";
const SETTINGS_ID_OPEN = "Veilance.NanoGPT.OpenAliasManager";
const SETTINGS_ID_INFO = "Veilance.NanoGPT.AliasInfo";

const KEY_SOURCES = ["keyring", "env", "none"];

function getNodeClassName(node) {
    return node?.comfyClass || node?.type || "";
}

function isNanoGPTNode(node) {
    return getNodeClassName(node) === NODE_CLASS;
}

function showNotification(message, type = "info") {
    if (app.extensionManager?.toast) {
        app.extensionManager.toast.add({
            severity: type === "error" ? "error" : type === "success" ? "success" : "info",
            summary: "NanoGPT",
            detail: message,
            life: 3500,
        });
        return;
    }
    if (app.ui?.toast) {
        app.ui.toast({
            content: message,
            type,
            timeout: 3500,
        });
        return;
    }
    console.log(`[NanoGPT] ${type}: ${message}`);
}

async function fetchAliases() {
    const response = await api.fetchApi("/veilance/nano_gpt/aliases");
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    if (payload.status !== "ok") {
        throw new Error(payload.message || "Failed to load aliases");
    }
    return payload;
}

async function upsertAlias(payload) {
    const response = await api.fetchApi("/veilance/nano_gpt/aliases/upsert", {
        method: "POST",
        body: JSON.stringify(payload),
        headers: { "Content-Type": "application/json" },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.status !== "ok") {
        throw new Error(data.message || `HTTP ${response.status}`);
    }
    return data;
}

async function deleteAlias(name) {
    const response = await api.fetchApi("/veilance/nano_gpt/aliases/delete", {
        method: "POST",
        body: JSON.stringify({ name }),
        headers: { "Content-Type": "application/json" },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.status !== "ok") {
        throw new Error(data.message || `HTTP ${response.status}`);
    }
    return data;
}

function buildTheme() {
    const rootStyle = getComputedStyle(document.documentElement);
    const isDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ?? true;
    const pick = (varName, fallback) => {
        const value = rootStyle.getPropertyValue(varName).trim();
        return value || fallback;
    };
    return {
        overlay: isDark ? "rgba(0,0,0,0.5)" : "rgba(0,0,0,0.28)",
        panelBg: pick("--comfy-menu-bg", isDark ? "#252525" : "#f4f4f4"),
        sectionBg: pick("--comfy-input-bg", isDark ? "#1a1a1a" : "#ffffff"),
        border: pick("--border-color", isDark ? "#505050" : "#c8c8c8"),
        text: pick("--fg-color", isDark ? "#efefef" : "#151515"),
        muted: pick("--descrip-text", isDark ? "#aaaaaa" : "#666666"),
        accent: isDark ? "#7fc3ff" : "#245f99",
        danger: isDark ? "#ff8f8f" : "#a72323",
    };
}

function createInputField(labelText, inputEl, theme) {
    const wrapper = document.createElement("div");
    wrapper.style.cssText = "display:flex;flex-direction:column;gap:6px;";
    const label = document.createElement("label");
    label.textContent = labelText;
    label.style.cssText = `font-size:12px;color:${theme.muted};`;
    wrapper.append(label, inputEl);
    return wrapper;
}

function inputStyle(theme) {
    return [
        "width:100%",
        "box-sizing:border-box",
        "padding:8px 10px",
        `border:1px solid ${theme.border}`,
        "border-radius:6px",
        `background:${theme.sectionBg}`,
        `color:${theme.text}`,
        "font-size:13px",
    ].join(";");
}

function openAliasManager() {
    const existing = document.getElementById("veilance-nanogpt-alias-manager");
    if (existing) {
        existing.remove();
    }

    const theme = buildTheme();
    const overlay = document.createElement("div");
    overlay.id = "veilance-nanogpt-alias-manager";
    overlay.style.cssText = `
        position:fixed;
        inset:0;
        z-index:10000;
        background:${theme.overlay};
        display:flex;
        justify-content:center;
        align-items:center;
        padding:20px;
    `;

    const panel = document.createElement("div");
    panel.style.cssText = `
        width:min(860px,95vw);
        max-height:92vh;
        overflow:auto;
        border:1px solid ${theme.border};
        border-radius:12px;
        background:${theme.panelBg};
        color:${theme.text};
        box-shadow:0 16px 40px rgba(0,0,0,0.35);
        padding:16px;
    `;

    const title = document.createElement("h3");
    title.textContent = "NanoGPT Alias Manager";
    title.style.cssText = "margin:0 0 12px 0;font-size:18px;";

    const subtitle = document.createElement("div");
    subtitle.textContent =
        "Aliases store API URL/model and API key source metadata; keyring keys stay in the OS keychain.";
    subtitle.style.cssText = `margin:0 0 14px 0;font-size:12px;color:${theme.muted};`;

    const status = document.createElement("div");
    status.style.cssText = `min-height:18px;margin-bottom:12px;font-size:12px;color:${theme.muted};`;

    const grid = document.createElement("div");
    grid.style.cssText = "display:grid;grid-template-columns:220px 1fr;gap:14px;";

    const left = document.createElement("div");
    left.style.cssText = `
        border:1px solid ${theme.border};
        border-radius:10px;
        padding:10px;
        background:${theme.sectionBg};
        display:flex;
        flex-direction:column;
        gap:8px;
        min-height:300px;
    `;
    const right = document.createElement("div");
    right.style.cssText = `
        border:1px solid ${theme.border};
        border-radius:10px;
        padding:10px;
        background:${theme.sectionBg};
        display:grid;
        grid-template-columns:1fr 1fr;
        gap:10px;
    `;

    const aliasSelect = document.createElement("select");
    aliasSelect.style.cssText = inputStyle(theme);
    aliasSelect.size = 12;

    const keyringStatus = document.createElement("div");
    keyringStatus.style.cssText = `font-size:12px;color:${theme.muted};`;

    const aliasNameInput = document.createElement("input");
    aliasNameInput.type = "text";
    aliasNameInput.placeholder = "Alias name";
    aliasNameInput.style.cssText = inputStyle(theme);

    const customUrlInput = document.createElement("input");
    customUrlInput.type = "text";
    customUrlInput.placeholder = "https://example.com/v1";
    customUrlInput.style.cssText = inputStyle(theme);

    const modelInput = document.createElement("input");
    modelInput.type = "text";
    modelInput.placeholder = "openai/gpt-5.2";
    modelInput.style.cssText = inputStyle(theme);

    const keySourceInput = document.createElement("select");
    keySourceInput.style.cssText = inputStyle(theme);
    KEY_SOURCES.forEach((source) => {
        const opt = document.createElement("option");
        opt.value = source;
        opt.textContent = source;
        keySourceInput.appendChild(opt);
    });

    const apiKeyEnvInput = document.createElement("input");
    apiKeyEnvInput.type = "text";
    apiKeyEnvInput.placeholder = "OPENAI_API_KEY";
    apiKeyEnvInput.style.cssText = inputStyle(theme);

    const apiKeyInput = document.createElement("input");
    apiKeyInput.type = "password";
    apiKeyInput.placeholder = "Leave blank to keep current key";
    apiKeyInput.autocomplete = "new-password";
    apiKeyInput.style.cssText = inputStyle(theme);

    const clearStoredKeyLabel = document.createElement("label");
    clearStoredKeyLabel.style.cssText = "display:flex;align-items:center;gap:8px;font-size:12px;";
    const clearStoredKeyInput = document.createElement("input");
    clearStoredKeyInput.type = "checkbox";
    clearStoredKeyLabel.append(clearStoredKeyInput, document.createTextNode("Clear stored keyring key"));

    const fieldAliasName = createInputField("Alias", aliasNameInput, theme);
    const fieldCustomUrl = createInputField("API URL", customUrlInput, theme);
    const fieldModel = createInputField("Model", modelInput, theme);
    const fieldKeySource = createInputField("Key Source", keySourceInput, theme);
    const fieldApiEnv = createInputField("API Key Env", apiKeyEnvInput, theme);
    const fieldApiKey = createInputField("API Key", apiKeyInput, theme);

    right.append(
        fieldAliasName,
        fieldCustomUrl,
        fieldModel,
        fieldKeySource,
        fieldApiEnv,
        fieldApiKey,
        clearStoredKeyLabel
    );

    const actions = document.createElement("div");
    actions.style.cssText = "display:flex;justify-content:space-between;align-items:center;margin-top:12px;";

    const leftActions = document.createElement("div");
    leftActions.style.cssText = "display:flex;gap:8px;";
    const rightActions = document.createElement("div");
    rightActions.style.cssText = "display:flex;gap:8px;";

    const refreshBtn = document.createElement("button");
    refreshBtn.textContent = "Refresh";
    const saveBtn = document.createElement("button");
    saveBtn.textContent = "Save Alias";
    const deleteBtn = document.createElement("button");
    deleteBtn.textContent = "Delete Alias";
    deleteBtn.style.cssText = `border-color:${theme.danger};color:${theme.danger};`;
    const closeBtn = document.createElement("button");
    closeBtn.textContent = "Close";

    [refreshBtn, saveBtn, deleteBtn, closeBtn].forEach((btn) => {
        btn.style.cssText = `
            padding:8px 12px;
            border:1px solid ${theme.border};
            border-radius:7px;
            background:${theme.sectionBg};
            color:${theme.text};
            cursor:pointer;
        `;
    });

    const aliasMap = new Map();
    let keyringAvailable = false;

    function setStatus(message, type = "info") {
        status.textContent = message;
        status.style.color = type === "error" ? theme.danger : type === "success" ? theme.accent : theme.muted;
    }

    function updateKeyFieldVisibility() {
        const source = keySourceInput.value;
        const showEnv = source === "env";
        const showKey = source === "keyring";
        fieldApiEnv.style.display = showEnv ? "" : "none";
        fieldApiKey.style.display = showKey ? "" : "none";
        clearStoredKeyLabel.style.display = showKey ? "" : "none";
    }

    function applyAliasToForm(alias) {
        if (!alias) return;
        aliasNameInput.value = alias.name || "";
        customUrlInput.value = alias.custom_api_url || "";
        modelInput.value = alias.model || "openai/gpt-5.2";
        keySourceInput.value = alias.key_source || "keyring";
        apiKeyEnvInput.value = alias.api_key_env || "";
        apiKeyInput.value = "";
        clearStoredKeyInput.checked = false;
        updateKeyFieldVisibility();
    }

    function renderAliasList(aliases) {
        aliasMap.clear();
        aliasSelect.innerHTML = "";
        for (const alias of aliases) {
            aliasMap.set(alias.name, alias);
            const opt = document.createElement("option");
            const keyLabel = alias.has_api_key ? "key:yes" : "key:no";
            opt.value = alias.name;
            opt.textContent = `${alias.name} (${alias.model || "no-model"}, ${keyLabel})`;
            aliasSelect.appendChild(opt);
        }
        if (!aliases.length) {
            const opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "(no aliases)";
            aliasSelect.appendChild(opt);
            return;
        }
        aliasSelect.selectedIndex = 0;
        applyAliasToForm(aliases[0]);
    }

    async function loadAliases() {
        setStatus("Loading aliases...");
        try {
            const payload = await fetchAliases();
            keyringAvailable = !!payload.keyring_available;
            keyringStatus.textContent = keyringAvailable
                ? "Keyring backend available."
                : "Keyring unavailable. Install Python package 'keyring' for encrypted key storage.";
            renderAliasList(payload.aliases || []);
            setStatus(`Loaded ${payload.aliases?.length || 0} alias(es).`, "success");
        } catch (error) {
            setStatus(`Failed to load aliases: ${error.message}`, "error");
        }
    }

    aliasSelect.addEventListener("change", () => {
        const alias = aliasMap.get(aliasSelect.value);
        if (alias) {
            applyAliasToForm(alias);
        }
    });

    keySourceInput.addEventListener("change", updateKeyFieldVisibility);

    refreshBtn.addEventListener("click", async () => {
        await loadAliases();
    });

    saveBtn.addEventListener("click", async () => {
        const name = aliasNameInput.value.trim();
        if (!name) {
            setStatus("Alias name is required.", "error");
            return;
        }

        const payload = {
            name,
            custom_api_url: customUrlInput.value.trim(),
            model: modelInput.value.trim(),
            key_source: keySourceInput.value,
            api_key_env: apiKeyEnvInput.value.trim(),
            clear_api_key: clearStoredKeyInput.checked,
        };

        if (payload.key_source === "keyring" && apiKeyInput.value.trim()) {
            payload.api_key = apiKeyInput.value;
        }

        if (payload.key_source === "keyring" && !keyringAvailable) {
            setStatus("Keyring is unavailable. Install keyring or use env/none key source.", "error");
            return;
        }

        setStatus("Saving alias...");
        try {
            await upsertAlias(payload);
            apiKeyInput.value = "";
            clearStoredKeyInput.checked = false;
            await loadAliases();
            aliasSelect.value = name;
            const alias = aliasMap.get(name);
            if (alias) {
                applyAliasToForm(alias);
            }
            setStatus(`Saved alias '${name}'.`, "success");
            showNotification(`Saved NanoGPT alias '${name}'.`, "success");
        } catch (error) {
            setStatus(`Save failed: ${error.message}`, "error");
            showNotification(`Alias save failed: ${error.message}`, "error");
        }
    });

    deleteBtn.addEventListener("click", async () => {
        const name = aliasNameInput.value.trim();
        if (!name) {
            setStatus("Alias name is required to delete.", "error");
            return;
        }
        const confirmed = window.confirm(`Delete alias '${name}' and its stored key?`);
        if (!confirmed) return;

        setStatus("Deleting alias...");
        try {
            await deleteAlias(name);
            await loadAliases();
            if (aliasSelect.value) {
                const alias = aliasMap.get(aliasSelect.value);
                if (alias) {
                    applyAliasToForm(alias);
                }
            } else {
                aliasNameInput.value = "";
                apiKeyInput.value = "";
            }
            setStatus(`Deleted alias '${name}'.`, "success");
            showNotification(`Deleted NanoGPT alias '${name}'.`, "success");
        } catch (error) {
            setStatus(`Delete failed: ${error.message}`, "error");
            showNotification(`Alias delete failed: ${error.message}`, "error");
        }
    });

    function closeDialog() {
        overlay.remove();
    }

    closeBtn.addEventListener("click", closeDialog);
    overlay.addEventListener("click", (event) => {
        if (event.target === overlay) closeDialog();
    });
    document.addEventListener(
        "keydown",
        (event) => {
            if (event.key === "Escape") closeDialog();
        },
        { once: true }
    );

    left.append(aliasSelect, keyringStatus);

    leftActions.append(refreshBtn);
    rightActions.append(deleteBtn, saveBtn, closeBtn);
    actions.append(leftActions, rightActions);

    grid.append(left, right);
    panel.append(title, subtitle, status, grid, actions);
    overlay.append(panel);
    document.body.append(overlay);

    updateKeyFieldVisibility();
    loadAliases();
}

function registerSettingsButton() {
    const settings = app.ui?.settings;
    if (!settings?.addSetting) {
        return;
    }

    settings.addSetting({
        id: SETTINGS_ID_INFO,
        name: "Veilance.NanoGPT Alias Profiles",
        type: () => {
            const row = document.createElement("tr");
            const title = document.createElement("td");
            title.textContent = "NanoGPT Alias Profiles";
            const valueCell = document.createElement("td");
            valueCell.style.cssText = "display:flex;align-items:center;gap:10px;";

            const text = document.createElement("span");
            text.textContent = "Store API URL/model in aliases and keep API keys in the OS keyring.";
            text.style.cssText = "font-size:12px;opacity:0.85;";
            const button = document.createElement("button");
            button.textContent = "Manage Aliases";
            button.style.cssText = "padding:6px 10px;cursor:pointer;";
            button.addEventListener("click", () => openAliasManager());
            valueCell.append(text, button);
            row.append(title, valueCell);
            return row;
        },
    });

    settings.addSetting({
        id: SETTINGS_ID_OPEN,
        name: "Veilance.NanoGPT Open Alias Manager",
        defaultValue: false,
        type: "boolean",
        tooltip: "Opens NanoGPT alias manager dialog.",
        onChange: async (value) => {
            if (!value) return;
            openAliasManager();
            try {
                if (app.extensionManager?.setting?.set) {
                    app.extensionManager.setting.set(SETTINGS_ID_OPEN, false);
                } else if (app.ui?.settings?.setSettingValue) {
                    app.ui.settings.setSettingValue(SETTINGS_ID_OPEN, false);
                }
            } catch (error) {
                console.warn("[NanoGPT] Failed to reset open-manager setting:", error);
            }
        },
    });
}

function attachNodeButton(node) {
    if (!isNanoGPTNode(node)) return;
    if (node.widgets?.some((widget) => widget?.name === "🔐 Manage Aliases")) return;

    node.addWidget(
        "button",
        "🔐 Manage Aliases",
        null,
        () => {
            openAliasManager();
        },
        {}
    );
}

app.registerExtension({
    name: "Veilance.NanoGPT",

    async setup() {
        registerSettingsButton();
    },

    getNodeMenuItems(node) {
        if (!isNanoGPTNode(node)) return [];
        return [
            {
                content: "🔐 Manage NanoGPT Aliases",
                callback: () => openAliasManager(),
            },
        ];
    },

    async nodeCreated(node) {
        attachNodeButton(node);
    },
});
