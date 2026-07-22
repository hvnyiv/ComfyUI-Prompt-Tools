import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_NAME = "LoRALoaderWithTriggerPreset";
const API_PATH = "/custom-nude/lora-trigger-preset";

async function readPreset(loraName) {
    const response = await api.fetchApi(
        `${API_PATH}?lora_name=${encodeURIComponent(loraName || "")}`
    );
    if (!response.ok) {
        throw new Error(`Could not load trigger preset (${response.status})`);
    }
    return await response.json();
}

async function writePreset(loraName, triggerWords) {
    const response = await api.fetchApi(API_PATH, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            lora_name: loraName || "",
            trigger_words: triggerWords || "",
        }),
    });
    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.error || `Could not save trigger preset (${response.status})`);
    }
    return result;
}

app.registerExtension({
    name: "custom-nude.LoRATriggerPreset",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) {
            return;
        }

        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalOnNodeCreated?.apply(this, arguments);
            const loraWidget = this.widgets?.find((widget) => widget.name === "lora_name");
            const triggerWidget = this.widgets?.find(
                (widget) => widget.name === "preset_trigger_words"
            );

            if (!loraWidget || !triggerWidget) {
                return result;
            }

            let requestSerial = 0;
            const loadSelectedPreset = async () => {
                const selectedName = loraWidget.value || "";
                const serial = ++requestSerial;
                try {
                    const preset = await readPreset(selectedName);
                    if (serial !== requestSerial || loraWidget.value !== selectedName) {
                        return;
                    }
                    triggerWidget.value = preset.trigger_words || "";
                    triggerWidget.callback?.(triggerWidget.value);
                    this.setDirtyCanvas(true, true);
                } catch (error) {
                    console.error("[custom-nude] Failed to load LoRA trigger preset", error);
                }
            };

            const originalLoraCallback = loraWidget.callback;
            loraWidget.callback = function (value) {
                const callbackResult = originalLoraCallback?.apply(this, arguments);
                void loadSelectedPreset();
                return callbackResult;
            };

            this.addWidget("button", "Save Trigger Preset", null, async () => {
                try {
                    await writePreset(loraWidget.value, triggerWidget.value);
                    this.graph?.setDirtyCanvas(true, true);
                } catch (error) {
                    console.error("[custom-nude] Failed to save LoRA trigger preset", error);
                    window.alert(`Failed to save LoRA trigger preset: ${error.message}`);
                }
            });

            setTimeout(() => void loadSelectedPreset(), 0);
            return result;
        };
    },
});
