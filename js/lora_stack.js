import { app } from "../../scripts/app.js";

const LORA_STACK_CLASS = "LoraStack5";
const SLOT_COUNT_WIDGET = "active_lora_slots";
const SLOT_COUNT = 5;

function findWidget(node, name) {
    if (!Array.isArray(node?.widgets)) return null;
    return node.widgets.find((widget) => widget?.name === name) || null;
}

function collectSlotWidgets(node) {
    const result = new Map();
    const visited = new Set();

    const addToSlot = (slotIndex, widget) => {
        if (!Number.isFinite(slotIndex)) return;
        if (!result.has(slotIndex)) {
            result.set(slotIndex, []);
        }
        const slotList = result.get(slotIndex);
        if (!slotList.includes(widget)) {
            slotList.push(widget);
        }
    };

    const visit = (widget, inheritedSlotIndex = null) => {
        if (!widget || visited.has(widget)) return;
        visited.add(widget);

        const name = typeof widget.name === "string" ? widget.name : "";
        const match = /^lora_(?:name|strength)_(\d+)$/.exec(name);
        let slotIndex = inheritedSlotIndex;
        if (match) {
            slotIndex = Number.parseInt(match[1], 10);
        }

        if (slotIndex !== null) {
            addToSlot(slotIndex, widget);
        }

        if (Array.isArray(widget.linkedWidgets)) {
            widget.linkedWidgets.forEach((linkedWidget) => visit(linkedWidget, slotIndex));
        }
    };

    if (Array.isArray(node?.widgets)) {
        node.widgets.forEach((widget) => visit(widget, null));
    }

    return result;
}

function normalizeSlotCount(value) {
    const parsed = Number.parseInt(String(value), 10);
    if (!Number.isFinite(parsed)) return 1;
    return Math.max(1, Math.min(SLOT_COUNT, parsed));
}

function hideWidget(widget) {
    if (!widget || widget.__veilanceHiddenState) return;

    widget.__veilanceHiddenState = {
        type: widget.type,
        computeSize: widget.computeSize,
        hidden: widget.hidden,
        inputDisplay: widget.inputEl?.style?.display,
        elementDisplay: widget.element?.style?.display,
    };
    widget.hidden = true;
    if (widget.inputEl?.style) {
        widget.inputEl.style.display = "none";
    }
    if (widget.element?.style) {
        widget.element.style.display = "none";
    }
    widget.type = "converted-widget";
    widget.computeSize = () => [0, -4];
}

function showWidget(widget) {
    if (!widget || !widget.__veilanceHiddenState) return;

    const state = widget.__veilanceHiddenState;
    widget.type = state.type;
    if (typeof state.computeSize === "function") {
        widget.computeSize = state.computeSize;
    } else {
        delete widget.computeSize;
    }
    if (state.hidden === undefined) {
        delete widget.hidden;
    } else {
        widget.hidden = state.hidden;
    }
    if (widget.inputEl?.style) {
        widget.inputEl.style.display = state.inputDisplay ?? "";
    }
    if (widget.element?.style) {
        widget.element.style.display = state.elementDisplay ?? "";
    }
    delete widget.__veilanceHiddenState;
}

function applySlotVisibility(node) {
    const slotWidget = findWidget(node, SLOT_COUNT_WIDGET);
    const visibleSlots = normalizeSlotCount(slotWidget?.value ?? 1);
    const slotWidgets = collectSlotWidgets(node);

    if (slotWidget && slotWidget.value !== visibleSlots) {
        slotWidget.value = visibleSlots;
    }

    for (let index = 1; index <= SLOT_COUNT; index++) {
        const shouldShow = index <= visibleSlots;
        const widgets = slotWidgets.get(index) || [];

        if (shouldShow) {
            widgets.forEach((widget) => showWidget(widget));
        } else {
            widgets.forEach((widget) => hideWidget(widget));
        }
    }

    if (typeof node.computeSize === "function" && typeof node.setSize === "function") {
        node.setSize(node.computeSize());
    }
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function bindSlotWidget(node) {
    const widget = findWidget(node, SLOT_COUNT_WIDGET);
    if (!widget || widget.__veilanceSlotHooked) return;

    widget.__veilanceSlotHooked = true;
    const originalCallback = widget.callback;
    widget.callback = function(value, ...rest) {
        if (typeof originalCallback === "function") {
            originalCallback.call(this, value, ...rest);
        }
        applySlotVisibility(node);
    };
}

function initializeLoraStackNode(node) {
    bindSlotWidget(node);
    applySlotVisibility(node);
    setTimeout(() => applySlotVisibility(node), 0);
    setTimeout(() => applySlotVisibility(node), 100);
}

app.registerExtension({
    name: "Veilance.LoraStack",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData?.name !== LORA_STACK_CLASS) {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function(...args) {
            const result = onNodeCreated?.apply(this, args);
            initializeLoraStackNode(this);
            return result;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function(...args) {
            const result = onConfigure?.apply(this, args);
            initializeLoraStackNode(this);
            return result;
        };
    },
});
