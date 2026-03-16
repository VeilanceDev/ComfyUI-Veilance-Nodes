import { app } from "../../scripts/app.js";

const IMAGE_LOADER_CLASS = "VeilanceLoadImageUploadOrUrl";
const ROTATION_WIDGET_NAME = "rotation_steps";
const ROTATE_CCW_ICON = "↺";
const ROTATE_CW_ICON = "↻";

function getNodeClassName(node) {
    return node?.comfyClass || node?.type || "";
}

function isImageLoaderNode(node) {
    return getNodeClassName(node) === IMAGE_LOADER_CLASS;
}

function getRotationWidget(node) {
    if (!Array.isArray(node?.widgets)) return null;
    return node.widgets.find((widget) => widget?.name === ROTATION_WIDGET_NAME) || null;
}

function hideWidget(widget) {
    if (!widget || widget._veilanceHidden) return;
    widget._veilanceHidden = true;
    widget._veilanceOriginalType = widget.type;
    widget._veilanceOriginalComputeSize = widget.computeSize?.bind(widget);
    widget.type = "hidden";
    widget.computeSize = () => [0, -4];
}

function normalizeRotationSteps(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
        return 0;
    }
    return ((Math.round(numeric) % 4) + 4) % 4;
}

function persistWidgetValue(node, widget, value) {
    widget.value = value;
    widget.callback?.(value);

    if (Array.isArray(node.widgets_values)) {
        const widgetIndex = node.widgets.indexOf(widget);
        if (widgetIndex >= 0 && widgetIndex < node.widgets_values.length) {
            node.widgets_values[widgetIndex] = value;
        }
    }
}

function getImageDimensions(source) {
    if (!source) return null;

    if (typeof source.naturalWidth === "number" && typeof source.naturalHeight === "number") {
        if (source.naturalWidth > 0 && source.naturalHeight > 0) {
            return [source.naturalWidth, source.naturalHeight];
        }
    }

    if (typeof source.videoWidth === "number" && typeof source.videoHeight === "number") {
        if (source.videoWidth > 0 && source.videoHeight > 0) {
            return [source.videoWidth, source.videoHeight];
        }
    }

    if (typeof source.width === "number" && typeof source.height === "number") {
        if (source.width > 0 && source.height > 0) {
            return [source.width, source.height];
        }
    }

    return null;
}

function resolvePreviewSource(node, source) {
    if (typeof source !== "string") {
        return source;
    }

    node._veilancePreviewImageCache ||= new Map();
    if (node._veilancePreviewImageCache.has(source)) {
        return node._veilancePreviewImageCache.get(source);
    }

    const image = new Image();
    image.onload = () => {
        refreshPreviewRotation(node);
    };
    image.src = source;
    node._veilancePreviewImageCache.set(source, image);
    return image;
}

function buildRotatedPreview(node, source, steps) {
    const normalizedSteps = normalizeRotationSteps(steps);
    const resolvedSource = resolvePreviewSource(node, source);
    if (normalizedSteps === 0) {
        return resolvedSource;
    }

    const dimensions = getImageDimensions(resolvedSource);
    if (!dimensions) {
        return resolvedSource;
    }

    const [width, height] = dimensions;
    const canvas = document.createElement("canvas");
    const swapsAxes = normalizedSteps % 2 === 1;
    canvas.width = swapsAxes ? height : width;
    canvas.height = swapsAxes ? width : height;

    const context = canvas.getContext("2d");
    if (!context) {
        return resolvedSource;
    }

    context.translate(canvas.width / 2, canvas.height / 2);
    context.rotate(normalizedSteps * (Math.PI / 2));
    context.drawImage(resolvedSource, -width / 2, -height / 2, width, height);
    return canvas;
}

function markCanvasDirty(node) {
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
}

function refreshPreviewRotation(node) {
    if (!isImageLoaderNode(node)) return;

    const currentImages = Array.isArray(node.imgs) ? node.imgs : null;
    if (currentImages && currentImages !== node._veilanceRotatedPreviewImages) {
        node._veilanceSourcePreviewImages = currentImages.slice();
    }

    const sourceImages = node._veilanceSourcePreviewImages;
    if (!Array.isArray(sourceImages) || !sourceImages.length) {
        return;
    }

    const rotationWidget = getRotationWidget(node);
    const steps = normalizeRotationSteps(rotationWidget?.value);
    const rotatedImages = sourceImages.map((source) => buildRotatedPreview(node, source, steps));
    node._veilanceRotatedPreviewImages = rotatedImages;
    node.imgs = rotatedImages;
    markCanvasDirty(node);
}

function installPreviewHook(node) {
    if (node._veilancePreviewHookInstalled) return;
    node._veilancePreviewHookInstalled = true;

    const originalOnDrawBackground = node.onDrawBackground;
    node.onDrawBackground = function(...args) {
        const currentImages = Array.isArray(this.imgs) ? this.imgs : null;
        if (currentImages && currentImages !== this._veilanceRotatedPreviewImages) {
            this._veilanceSourcePreviewImages = currentImages.slice();
            refreshPreviewRotation(this);
        }
        return originalOnDrawBackground?.apply(this, args);
    };
}

function rotateNode(node, delta) {
    const rotationWidget = getRotationWidget(node);
    if (!rotationWidget) return;

    const nextValue = normalizeRotationSteps(Number(rotationWidget.value || 0) + delta);
    persistWidgetValue(node, rotationWidget, nextValue);
    refreshPreviewRotation(node);
}

function attachRotationButtons(node) {
    if (!isImageLoaderNode(node)) return;
    if (node.widgets?.some((widget) => widget?._veilanceRotationButton)) return;

    const rotateLeft = node.addWidget("button", ROTATE_CCW_ICON, null, () => {
        rotateNode(node, -1);
    });
    rotateLeft._veilanceRotationButton = true;

    const rotateRight = node.addWidget("button", ROTATE_CW_ICON, null, () => {
        rotateNode(node, 1);
    });
    rotateRight._veilanceRotationButton = true;
}

app.registerExtension({
    name: "Veilance.ImageLoader",

    async nodeCreated(node) {
        if (!isImageLoaderNode(node)) {
            return;
        }

        hideWidget(getRotationWidget(node));
        attachRotationButtons(node);
        installPreviewHook(node);
        refreshPreviewRotation(node);
    },
});
