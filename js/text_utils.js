import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Veilance.TextUtils",
    async nodeCreated(node) {
        if (node.comfyClass === "VeilanceStringCombiner") {
            // Restore inputs from workflow
            const origConfigure = node.configure;
            node.configure = function(info) {
                if (info.inputs) {
                    for (let inp of info.inputs) {
                        if (inp.name.startsWith("string_") && node.findInputSlot(inp.name) === -1) {
                            node.addInput(inp.name, "STRING");
                        }
                    }
                }
                origConfigure?.apply(this, arguments);
            };

            node.addWidget("button", "➕ Add String", "add_string", () => {
                let i = 1;
                while (node.findInputSlot(`string_${i}`) !== -1) {
                    i++;
                }
                node.addInput(`string_${i}`, "STRING");
                node.size = node.computeSize();
                app.graph.setDirtyCanvas(true, true);
            });

            node.addWidget("button", "➖ Remove String", "remove_string", () => {
                let inputs = node.inputs || [];
                let stringInputs = inputs.filter(inp => inp.name.startsWith("string_"));
                // Keep at least two strings
                if (stringInputs.length > 2) {
                    let last = stringInputs[stringInputs.length - 1];
                    let slot = node.findInputSlot(last.name);
                    if (slot !== -1) {
                        node.removeInput(slot);
                        node.size = node.computeSize();
                        app.graph.setDirtyCanvas(true, true);
                    }
                }
            });
        }
        
        if (node.comfyClass === "VeilanceTextSearchAndReplace") {
            const origConfigure = node.configure;
            node.configure = function(info) {
                // The widget layout is [search_1, replace_1] (length=2) based on default ones.
                // Any extra pairs are added based on total length.
                // In VeilanceTextSearchAndReplace we have 'text' input and 'search_1', 'replace_1' widgets.
                // Wait, text is forceInput. So only search_1 and replace_1 are widgets!
                if (info.widgets_values) {
                    let pairs = info.widgets_values.length / 2;
                    for (let i = 2; i <= pairs; i++) {
                       if (!node.widgets || !node.widgets.find(w => w.name === `search_${i}`)) {
                           node.addWidget("text", `search_${i}`, "");
                           node.addWidget("text", `replace_${i}`, "");
                       }
                    }
                }
                origConfigure?.apply(this, arguments);
            };

            node.addWidget("button", "➕ Add Find/Replace", "add_replace", () => {
                let i = 1;
                while (node.widgets && node.widgets.find(w => w.name === `search_${i}`)) {
                    i++;
                }
                node.addWidget("text", `search_${i}`, "");
                node.addWidget("text", `replace_${i}`, "");
                node.size = node.computeSize();
                app.graph.setDirtyCanvas(true, true);
            });

            node.addWidget("button", "➖ Remove Find/Replace", "remove_replace", () => {
                let i = 1;
                while (node.widgets && node.widgets.find(w => w.name === `search_${i}`)) {
                    i++;
                }
                i--;
                if (i > 1) {
                    let searchIdx = node.widgets.findIndex(w => w.name === `search_${i}`);
                    if (searchIdx !== -1) node.widgets.splice(searchIdx, 1);
                    
                    let replaceIdx = node.widgets.findIndex(w => w.name === `replace_${i}`);
                    if (replaceIdx !== -1) node.widgets.splice(replaceIdx, 1);
                    
                    if (node.widgets_values && node.widgets_values.length > 2) {
                        node.widgets_values.length = node.widgets_values.length - 2;
                    }
                    
                    node.size = node.computeSize();
                    app.graph.setDirtyCanvas(true, true);
                }
            });
        }
    }
});
