import glob
import os
import random


class RandomTextPicker:
    """Pick a txt file from a folder and output its contents."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder_path": ("STRING", {"default": "", "multiline": False}),
                "mode": (["random", "sequential", "index"], {"default": "random"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "index": ("INT", {"default": 0, "min": 0, "max": 999999}),
                "recursive": ("BOOLEAN", {"default": False}),
                "file_pattern": ("STRING", {"default": "*.txt", "multiline": False}),
                "encoding": (["utf-8", "utf-8-sig", "gbk", "latin-1"], {"default": "utf-8"}),
                "strip_whitespace": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("text", "file_path", "selected_index")
    FUNCTION = "pick_text"
    CATEGORY = "text/random"

    @classmethod
    def IS_CHANGED(cls, folder_path, mode, seed, index, recursive, file_pattern, encoding, strip_whitespace):
        files = cls._list_txt_files(folder_path, recursive, file_pattern)
        signature = [(path, os.path.getmtime(path), os.path.getsize(path)) for path in files]
        return (mode, seed, index, recursive, file_pattern, encoding, strip_whitespace, tuple(signature))

    def pick_text(self, folder_path, mode, seed, index, recursive, file_pattern, encoding, strip_whitespace):
        files = self._list_txt_files(folder_path, recursive, file_pattern)
        if not files:
            raise FileNotFoundError(f"No files matching '{file_pattern}' found in: {folder_path}")

        selected_index = self._select_index(len(files), mode, seed, index)
        selected_path = files[selected_index]

        with open(selected_path, "r", encoding=encoding) as file:
            text = file.read()

        if strip_whitespace:
            text = text.strip()

        return (text, selected_path, selected_index)

    @staticmethod
    def _list_txt_files(folder_path, recursive, file_pattern):
        folder_path = os.path.abspath(os.path.expanduser(folder_path.strip()))
        if not os.path.isdir(folder_path):
            raise NotADirectoryError(f"Folder does not exist: {folder_path}")

        pattern = os.path.join(folder_path, "**", file_pattern) if recursive else os.path.join(folder_path, file_pattern)
        return sorted(path for path in glob.glob(pattern, recursive=recursive) if os.path.isfile(path))

    @staticmethod
    def _select_index(file_count, mode, seed, index):
        if mode == "random":
            return random.Random(seed).randrange(file_count)
        if mode == "sequential":
            return index % file_count
        if mode == "index":
            if index < 0 or index >= file_count:
                raise IndexError(f"Index {index} is out of range for {file_count} files")
            return index
        raise ValueError(f"Unknown mode: {mode}")


NODE_CLASS_MAPPINGS = {
    "RandomTextPicker": RandomTextPicker,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomTextPicker": "Random Text Picker",
}
