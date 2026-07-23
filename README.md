# ComfyUI Prompt Tools

A small ComfyUI node pack for prompt text, CL Tagger output, and LoRA trigger words.

## Nodes

| Node | Category | Purpose |
| --- | --- | --- |
| Random Text Picker | `text/random` | Selects text from files by random seed, sequence, or index. |
| Anima Prompt Formatter | `text/anima` | Normalizes Anima tags, underscores, separators, and parentheses. |
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

## CL Tagger Filter

Connect Mira `CL Tagger v2` text output to `CL Tagger Action Filter`.
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
