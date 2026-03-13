import { app } from "../../scripts/app.js";

const GLOBAL_SAMPLER_CLASS = "VeilanceGlobalSamplerScheduler";
const GLOBAL_SEED_CLASS = "VeilanceGlobalSeed";
const GLOBAL_CLASSES = new Set([GLOBAL_SAMPLER_CLASS, GLOBAL_SEED_CLASS]);

function getGraphNodes() {
    return Array.isArray(app.graph?._nodes) ? app.graph._nodes : [];
}

function getNodeClassName(node) {
    return node?.comfyClass || node?.type || "";
}

function getWidget(node, name) {
    if (!Array.isArray(node?.widgets)) {
        return null;
    }
    return node.widgets.find((widget) => widget?.name === name) || null;
}

function getWidgetOptions(widget) {
    const values = widget?.options?.values;
    if (typeof values === "function") {
        try {
            return values();
        } catch (error) {
            console.warn("[Veilance.GlobalControls] Failed to resolve widget options:", error);
            return [];
        }
    }
    return Array.isArray(values) ? values : [];
}

function setWidgetValue(node, widget, value) {
    if (!widget) {
        return false;
    }

    const comboOptions = getWidgetOptions(widget);
    if (comboOptions.length && !comboOptions.includes(value)) {
        return false;
    }

    if (widget.value === value) {
        return false;
    }

    widget.value = value;

    try {
        widget.callback?.(value);
    } catch (error) {
        console.warn(
            `[Veilance.GlobalControls] Widget callback failed for ${widget.name}:`,
            error
        );
    }

    if (typeof node?.onWidgetChanged === "function") {
        try {
            node.onWidgetChanged(widget.name, value, undefined, widget);
        } catch (error) {
            console.warn(
                `[Veilance.GlobalControls] onWidgetChanged failed for ${widget.name}:`,
                error
            );
        }
    }

    node?.setDirtyCanvas?.(true, true);
    return true;
}

function syncSamplerScheduler(sourceNode) {
    const samplerWidget = getWidget(sourceNode, "sampler_name");
    const schedulerWidget = getWidget(sourceNode, "scheduler");
    if (!samplerWidget || !schedulerWidget) {
        return false;
    }

    let changed = false;
    for (const node of getGraphNodes()) {
        if (node === sourceNode || GLOBAL_CLASSES.has(getNodeClassName(node))) {
            continue;
        }
        changed = setWidgetValue(node, getWidget(node, "sampler_name"), samplerWidget.value) || changed;
        changed = setWidgetValue(node, getWidget(node, "scheduler"), schedulerWidget.value) || changed;
    }
    return changed;
}

function syncSeed(sourceNode) {
    const seedWidget = getWidget(sourceNode, "seed");
    if (!seedWidget) {
        return false;
    }

    const seedValue = Number(seedWidget.value);
    let changed = false;
    for (const node of getGraphNodes()) {
        if (node === sourceNode || GLOBAL_CLASSES.has(getNodeClassName(node))) {
            continue;
        }
        changed = setWidgetValue(node, getWidget(node, "seed"), seedValue) || changed;
        changed = setWidgetValue(node, getWidget(node, "noise_seed"), seedValue) || changed;
    }
    return changed;
}

function syncFromNode(node) {
    const className = getNodeClassName(node);
    let changed = false;

    if (className === GLOBAL_SAMPLER_CLASS) {
        changed = syncSamplerScheduler(node);
    } else if (className === GLOBAL_SEED_CLASS) {
        changed = syncSeed(node);
    }

    if (changed) {
        app.graph?.setDirtyCanvas?.(true, true);
    }
}

function syncAllGlobals() {
    for (const node of getGraphNodes()) {
        if (GLOBAL_CLASSES.has(getNodeClassName(node))) {
            syncFromNode(node);
        }
    }
}

function wrapWidgetCallback(node, widget) {
    if (!widget || widget._veilanceGlobalWrapped) {
        return;
    }

    const originalCallback = widget.callback;
    widget.callback = function(value, ...rest) {
        const result = originalCallback?.call(this, value, ...rest);
        syncFromNode(node);
        return result;
    };
    widget._veilanceGlobalWrapped = true;
}

function initializeGlobalNode(node) {
    if (!GLOBAL_CLASSES.has(getNodeClassName(node))) {
        return;
    }

    if (node._veilanceGlobalInitialized) {
        return;
    }
    node._veilanceGlobalInitialized = true;

    wrapWidgetCallback(node, getWidget(node, "sampler_name"));
    wrapWidgetCallback(node, getWidget(node, "scheduler"));
    wrapWidgetCallback(node, getWidget(node, "seed"));

    const originalConfigure = node.configure;
    node.configure = function(info) {
        const result = originalConfigure?.call(this, info);
        setTimeout(() => {
            wrapWidgetCallback(node, getWidget(node, "sampler_name"));
            wrapWidgetCallback(node, getWidget(node, "scheduler"));
            wrapWidgetCallback(node, getWidget(node, "seed"));
            syncFromNode(node);
        }, 0);
        return result;
    };

    setTimeout(() => syncFromNode(node), 0);
}

app.registerExtension({
    name: "Veilance.GlobalControls",

    async nodeCreated(node) {
        initializeGlobalNode(node);
        setTimeout(() => syncAllGlobals(), 0);
    },
});
