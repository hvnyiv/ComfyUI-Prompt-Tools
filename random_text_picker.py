import glob
import os
import random
import re


COMPOUND_TAG_NOUNS = {
    "background",
    "bow",
    "breasts",
    "dress",
    "ears",
    "eyes",
    "hair",
    "horns",
    "mouth",
    "quality",
    "ribbon",
    "shirt",
    "skin",
    "skirt",
    "sleeves",
    "socks",
    "tail",
    "thighhighs",
}

COMMON_ANIME_PHRASES = {
    ("cowboy", "shot"),
    ("full", "body"),
    ("from", "behind"),
    ("looking", "at", "viewer"),
    ("upper", "body"),
}


def normalize_anime_prompt(text, separator=", ", escape_parentheses=True, underscore_mode="space"):
    tags = _merge_common_anime_tags(
        _normalize_underscore(tag, underscore_mode) for tag in _split_prompt_tags(text)
    )

    normalized_tags = []
    for tag in tags:
        if escape_parentheses:
            tag = re.sub(r"(?<!\\)([()])", r"\\\1", tag)
        normalized_tags.append(tag)

    return separator.join(normalized_tags)


def _normalize_underscore(text, underscore_mode):
    if underscore_mode == "remove":
        return text.replace("_", "")
    if underscore_mode == "space":
        return text.replace("_", " ")
    raise ValueError(f"Unknown underscore_mode: {underscore_mode}")


def _split_prompt_tags(text):
    tags = []
    current = []
    paren_depth = 0

    for char in text.strip():
        if char == "(":
            paren_depth += 1
            current.append(char)
        elif char == ")":
            current.append(char)
            paren_depth = max(0, paren_depth - 1)
        elif paren_depth == 0 and (char == "," or char.isspace()):
            _append_tag(tags, current)
        else:
            current.append(char)

    _append_tag(tags, current)
    return tags


def _append_tag(tags, current):
    tag = "".join(current).strip()
    if tag:
        tags.append(tag)
    current.clear()


def _merge_common_anime_tags(tags):
    tags = list(tags)
    merged = []
    index = 0

    while index < len(tags):
        phrase = _find_common_phrase(tags, index)
        if phrase:
            merged.append(" ".join(phrase))
            index += len(phrase)
            continue

        if _should_merge_compound_tag(tags, index):
            merged.append(f"{tags[index]} {tags[index + 1]}")
            index += 2
            continue

        merged.append(tags[index])
        index += 1

    return merged


def _find_common_phrase(tags, index):
    for phrase in sorted(COMMON_ANIME_PHRASES, key=len, reverse=True):
        end = index + len(phrase)
        if tuple(tag.lower() for tag in tags[index:end]) == phrase:
            return tags[index:end]
    return None


def _should_merge_compound_tag(tags, index):
    if index + 1 >= len(tags):
        return False

    current_tag = tags[index]
    next_tag = tags[index + 1]
    if " " in current_tag or " " in next_tag:
        return False

    return next_tag.lower() in COMPOUND_TAG_NOUNS


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


class AnimaPromptFormatter:
    """Normalize a prompt for anima-style tag prompts."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "separator": ("STRING", {"default": ", ", "multiline": False}),
                "escape_parentheses": ("BOOLEAN", {"default": True}),
                "underscore_mode": (["space", "remove"], {"default": "space"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "format_prompt"
    CATEGORY = "text/anima"

    def format_prompt(self, prompt, separator, escape_parentheses, underscore_mode):
        normalized_prompt = normalize_anime_prompt(prompt, separator, escape_parentheses, underscore_mode)
        return (normalized_prompt,)


NODE_CLASS_MAPPINGS = {
    "RandomTextPicker": RandomTextPicker,
    "AnimaPromptFormatter": AnimaPromptFormatter,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomTextPicker": "Random Text Picker",
    "AnimaPromptFormatter": "Anima Prompt Formatter",
}
