# ComfyUI Random Text Picker

A small ComfyUI custom node that reads `.txt` files from a folder and outputs one file's text.

## Install

Clone this repository directly into ComfyUI's `custom_nodes` directory:

```powershell
cd ComfyUI\custom_nodes
git clone https://github.com/hvnyiv/ComfyUI-Random-Text-Picker.git
```

Or copy this repository folder into:

```text
ComfyUI/custom_nodes/ComfyUI-Random-Text-Picker
```

Then restart ComfyUI.

## Node

`Random Text Picker` is under:

```text
text/random
```

## Inputs

- `folder_path`: Folder containing txt files.
- `mode`: `random`, `sequential`, or `index`.
- `seed`: Used by `random` mode for repeatable selection.
- `index`: Used by `sequential` and `index` modes.
- `recursive`: Search subfolders too.
- `file_pattern`: Defaults to `*.txt`; can be changed to patterns like `*.prompt.txt`.
- `encoding`: Text file encoding.
- `strip_whitespace`: Trim leading and trailing whitespace.

## Outputs

- `text`: Selected txt content.
- `file_path`: Selected txt file path.
- `selected_index`: Index of the selected file in sorted file order.

## CL Tagger Action Filter

`CL Tagger Action Filter` is under:

```text
text/tagger
```

Connect the `tags` output of Mira `CL Tagger v2` to this node's `tags` input.
The node keeps tags classified as character actions or poses and optionally gaze/eye-state tags.

### Inputs

- `tags`: Comma-separated CL Tagger v2 output. Multi-image newline output is preserved.
- `preset`:
  - `strict`: Higher-confidence first-pass action tags.
  - `balanced`: Default first-pass score and margin thresholds.
  - `all_candidates`: Every tag whose top semantic class was action/pose or gaze/eye state.
- `include_gaze`: Keep gaze direction and eye-state candidates.
- `separator`: Separator used in the two text outputs.

### Outputs

- `filtered_tags`: Tags retained as actions/poses and optional gaze tags.
- `removed_tags`: All input tags not retained.
- `kept_count`: Total retained tag count.
- `removed_count`: Total removed tag count.
- `character_tags`: Character tags matched against all 49,516 Character entries in CL Tagger v2.00.
- `character_count`: Total matched character tag count.

Underscores in `character_tags` are converted to spaces.

`character_tags` is an additional view of the input. Character tags remain present in
`removed_tags` because that output means "not retained as an action"; this preserves the
existing output behavior and connections.

The bundled cache is an experimental first-pass semantic classification of the 47,654
General tags in CL Tagger v2.00. It is intended for workflow testing and contains both
false positives and false negatives; `removed_tags` should be inspected while evaluating it.
