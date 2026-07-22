# ComfyUI Custom Nude

A compact ComfyUI custom-node pack for text selection, anime prompt formatting,
CL Tagger v2 filtering, and LoRA trigger-word presets.

## Nodes

### Random Text Picker

Category: `text/random`

Reads matching text files from a folder and returns one file's contents, path,
and sorted index. Supports random, sequential, and direct-index selection,
recursive search, custom file patterns, and common text encodings.

### Anime Prompt Formatter

Category: `text/anime`

Normalizes anime tag prompts, merges common multi-word tags, handles underscores,
escapes parentheses when requested, and joins tags with a configurable separator.

### CL Tagger Action Filter

Category: `text/tagger`

Connect the `tags` output from Mira `CL Tagger v2` to this node. It outputs:

- filtered action/pose tags
- removed tags
- kept and removed counts
- exact CL Tagger v2.00 character tags and their count

`balanced` is the recommended default. `strict` keeps fewer high-confidence
action tags, while `all_candidates` is intended for testing. The bundled
semantic action cache is experimental and can contain false positives or false
negatives. Character matching is exact against the v2.00 Character vocabulary.

### LoRA Trigger Loader

Category: `loaders/lora`

Loads one LoRA and outputs `model`, `clip`, and its preset `trigger_words`.
Select a LoRA, enter its trigger words, and press **Save Trigger Preset**. When
that LoRA is selected again, the saved words are restored automatically.

Presets are stored locally in `lora_trigger_presets.json`. This file is ignored
by Git so personal trigger presets are not published. Enter an empty preset and
save it to delete that LoRA's stored preset.

## Installation

Clone the repository directly into ComfyUI's `custom_nodes` folder:

```powershell
cd ComfyUI\custom_nodes
git clone https://github.com/hvnyiv/comfyui-custom-nude.git
```

Restart ComfyUI after installation or updating. No additional Python packages
are required beyond ComfyUI's own runtime.

## Update

```powershell
cd ComfyUI\custom_nodes\comfyui-custom-nude
git pull
```

Then restart ComfyUI and refresh the browser with `Ctrl+F5` if an old node UI
is still cached.

## Included Files

- `random_text_picker.py` — backend node implementations and preset API
- `action_tag_semantic_cache.json.gz` — compressed CL Tagger lookup data
- `web/lora_trigger_presets.js` — automatic LoRA preset loading and save button
- `__init__.py` — ComfyUI node and web-extension registration
