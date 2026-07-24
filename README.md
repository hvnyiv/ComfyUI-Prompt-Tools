# ComfyUI Prompt Tools

A small ComfyUI node pack for prompt text, CL Tagger output, and LoRA trigger words.

## Nodes

| Node | Category | Purpose |
| --- | --- | --- |
| Random Text Picker | `text/random` | Selects text from files by random seed, sequence, or index. |
| Anima Prompt Formatter | `text/anima` | Normalizes Anima tags, underscores, separators, and parentheses. |
| CL Tagger v2 | `text/tagger` | Runs CL Tagger v2 directly without depending on ComfyUI Mira. |
| CL Tagger Action Filter | `text/tagger` | Extracts action tags and exact CL Tagger v2.00 character tags. |
| LoRA Trigger Loader | `loaders/lora` | Loads a LoRA and outputs its saved trigger-word preset. |

## Install

```powershell
cd ComfyUI\custom_nodes
git clone https://github.com/hvnyiv/ComfyUI-Prompt-Tools.git
```

Restart ComfyUI after installation.

## LoRA Trigger Presets

Select a LoRA, enter its trigger words, then click **Save Trigger Preset**.
Selecting that LoRA later restores the words automatically. Saving an empty
preset deletes it.

Personal presets are stored outside the custom-node folder at
`ComfyUI/user/__prompt_tools/lora_trigger_presets.json`, so updating or
reinstalling the node does not overwrite them. Existing presets from the old
custom-node location are copied there automatically the first time they are
loaded or saved.

## CL Tagger v2

Put each complete model version under
`ComfyUI/models/cl_tagger_v2/<version>`. A version directory must contain
`model.onnx`, `model.onnx.data`, and `model_vocabulary.json`.

The model selector includes the official `v2_00` and `v2_01a` releases. When
the selected model is incomplete or absent, the node downloads the required
files from `cella110n/cl_tagger_v2` on Hugging Face before inference. This is a
gated model: accept its license on Hugging Face and authenticate with
`hf auth login` or `HF_TOKEN` before the first automatic download.

The `CL Tagger v2` node is included directly in this plugin and does not modify
or depend on ComfyUI Mira. Its internal node ID remains compatible with the
previous Mira integration, so existing workflows reconnect after restart.

Connect `CL Tagger v2` text output to `CL Tagger Action Filter`.
`balanced` is the recommended preset; `strict` keeps fewer tags and
`all_candidates` is intended for testing.

The bundled action classification is experimental. Character matching is exact
against the 49,516 Character entries in CL Tagger v2.00.

## Update

```powershell
cd ComfyUI\custom_nodes\ComfyUI-Prompt-Tools
git pull
```

Restart ComfyUI, then use `Ctrl+F5` if the browser still shows an old node UI.

## Files

- `random_text_picker.py` — node implementations and preset API
- `action_tag_semantic_cache.json.gz` — compressed CL Tagger lookup data
- `web/lora_trigger_presets.js` — LoRA preset interface
- `__init__.py` — node and web-extension registration
