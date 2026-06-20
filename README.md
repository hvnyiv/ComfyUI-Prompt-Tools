# ComfyUI Random Text Picker

A small ComfyUI custom node that reads `.txt` files from a folder and outputs one file's text.

## Install

Clone this repository directly into ComfyUI's `custom_nodes` directory:

```powershell
cd ComfyUI\custom_nodes
git clone https://github.com/hvnyiv/comfyui-custom-nude.git
```

Or copy this repository folder into:

```text
ComfyUI/custom_nodes/comfyui-custom-nude
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