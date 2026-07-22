import glob
import gzip
import json
import os
import random
import re
import threading

import comfy.sd
import comfy.utils
import folder_paths
from aiohttp import web
from server import PromptServer


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

ACTION_TAG_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "action_tag_semantic_cache.json.gz"
)
_ACTION_TAG_CACHE = None

LORA_TRIGGER_PRESET_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "lora_trigger_presets.json"
)
_LORA_TRIGGER_PRESET_LOCK = threading.Lock()


def _load_lora_trigger_presets():
    with _LORA_TRIGGER_PRESET_LOCK:
        if not os.path.isfile(LORA_TRIGGER_PRESET_FILE):
            return {}
        with open(LORA_TRIGGER_PRESET_FILE, "r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            raise ValueError("LoRA trigger preset file must contain a JSON object")
        return {
            str(name): str(trigger_words)
            for name, trigger_words in payload.items()
            if isinstance(name, str) and isinstance(trigger_words, str)
        }


def _save_lora_trigger_preset(lora_name, trigger_words):
    lora_name = str(lora_name).strip()
    trigger_words = str(trigger_words).strip()
    if not lora_name or lora_name == "None":
        raise ValueError("Select a LoRA before saving its trigger preset")
    if len(lora_name) > 1024 or len(trigger_words) > 16384:
        raise ValueError("LoRA name or trigger preset is too long")

    with _LORA_TRIGGER_PRESET_LOCK:
        if os.path.isfile(LORA_TRIGGER_PRESET_FILE):
            with open(LORA_TRIGGER_PRESET_FILE, "r", encoding="utf-8") as file:
                payload = json.load(file)
            if not isinstance(payload, dict):
                payload = {}
        else:
            payload = {}

        if trigger_words:
            payload[lora_name] = trigger_words
        else:
            payload.pop(lora_name, None)

        temporary_path = LORA_TRIGGER_PRESET_FILE + ".tmp"
        with open(temporary_path, "w", encoding="utf-8", newline="\n") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
            file.write("\n")
        os.replace(temporary_path, LORA_TRIGGER_PRESET_FILE)


@PromptServer.instance.routes.get("/custom-nude/lora-trigger-preset")
async def get_lora_trigger_preset(request):
    lora_name = request.query.get("lora_name", "")
    try:
        presets = _load_lora_trigger_presets()
        return web.json_response({
            "lora_name": lora_name,
            "trigger_words": presets.get(lora_name, ""),
        })
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return web.json_response({"error": str(error)}, status=500)


@PromptServer.instance.routes.post("/custom-nude/lora-trigger-preset")
async def set_lora_trigger_preset(request):
    try:
        payload = await request.json()
        _save_lora_trigger_preset(
            payload.get("lora_name", ""), payload.get("trigger_words", "")
        )
        return web.json_response({"ok": True})
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return web.json_response({"error": str(error)}, status=400)


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


def _load_action_tag_cache():
    global _ACTION_TAG_CACHE
    if _ACTION_TAG_CACHE is None:
        if not os.path.isfile(ACTION_TAG_CACHE_FILE):
            raise FileNotFoundError(
                f"Action tag semantic cache is missing: {ACTION_TAG_CACHE_FILE}"
            )
        with gzip.open(ACTION_TAG_CACHE_FILE, "rt", encoding="utf-8") as file:
            payload = json.load(file)
        if payload.get("schema_version") not in {1, 2} or not isinstance(payload.get("tags"), dict):
            raise ValueError(f"Unsupported action tag semantic cache: {ACTION_TAG_CACHE_FILE}")
        character_tags = payload.get("character_tags", [])
        if not isinstance(character_tags, list):
            raise ValueError(f"Invalid character tag cache: {ACTION_TAG_CACHE_FILE}")
        payload["_character_tag_set"] = frozenset(character_tags)
        _ACTION_TAG_CACHE = payload
    return _ACTION_TAG_CACHE


def _canonicalize_action_tag(tag):
    tag = tag.strip().replace(r"\(", "(").replace(r"\)", ")")
    tag = tag.replace("_", " ").lower()
    return " ".join(tag.split())


def _split_tagger_output_line(line):
    return [tag.strip() for tag in line.split(",") if tag.strip()]


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


class CLTaggerActionFilter:
    """Filter CL Tagger v2 text output using the first semantic classification cache."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "tags": ("STRING", {"default": "", "multiline": True}),
                "preset": (["balanced", "strict", "all_candidates"], {"default": "balanced"}),
                "include_gaze": ("BOOLEAN", {"default": True}),
                "separator": ("STRING", {"default": ", ", "multiline": False}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT", "INT", "STRING", "INT")
    RETURN_NAMES = (
        "filtered_tags",
        "removed_tags",
        "kept_count",
        "removed_count",
        "character_tags",
        "character_count",
    )
    FUNCTION = "filter_tags"
    CATEGORY = "text/tagger"

    def filter_tags(self, tags, preset, include_gaze, separator):
        cache = _load_action_tag_cache()
        try:
            thresholds = cache["presets"][preset]
        except KeyError as error:
            raise ValueError(f"Unknown action filter preset: {preset}") from error

        minimum_score = float(thresholds["score"])
        minimum_margin = float(thresholds["margin"])
        filtered_lines = []
        removed_lines = []
        character_lines = []
        kept_count = 0
        removed_count = 0
        character_count = 0

        input_lines = tags.splitlines() or [tags]
        for line in input_lines:
            kept = []
            removed = []
            characters = []
            for original_tag in _split_tagger_output_line(line):
                canonical_tag = _canonicalize_action_tag(original_tag)
                if canonical_tag in cache["_character_tag_set"]:
                    characters.append(original_tag.replace("_", " "))
                    character_count += 1
                classification = cache["tags"].get(canonical_tag)
                should_keep = classification is not None
                if should_keep and classification["category"] == "gaze_eye_state" and not include_gaze:
                    should_keep = False
                if should_keep and classification["category"] not in {"action_pose", "gaze_eye_state"}:
                    should_keep = False
                if should_keep and float(classification["score"]) < minimum_score:
                    should_keep = False
                if should_keep and float(classification["margin"]) < minimum_margin:
                    should_keep = False

                if should_keep:
                    kept.append(original_tag)
                    kept_count += 1
                else:
                    removed.append(original_tag)
                    removed_count += 1

            filtered_lines.append(separator.join(kept))
            removed_lines.append(separator.join(removed))
            character_lines.append(separator.join(characters))

        return (
            "\n".join(filtered_lines),
            "\n".join(removed_lines),
            kept_count,
            removed_count,
            "\n".join(character_lines),
            character_count,
        )


class LoRALoaderWithTriggerPreset:
    """Load a LoRA and output user-defined trigger words saved in the workflow."""

    def __init__(self):
        self.loaded_lora = None

    @classmethod
    def INPUT_TYPES(cls):
        lora_names = folder_paths.get_filename_list("loras")
        if not lora_names:
            lora_names = ["None"]

        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "lora_name": (lora_names,),
                "strength_model": (
                    "FLOAT",
                    {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01},
                ),
                "strength_clip": (
                    "FLOAT",
                    {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01},
                ),
                "preset_trigger_words": (
                    "STRING",
                    {"default": "", "multiline": True, "dynamicPrompts": False},
                ),
            }
        }

    RETURN_TYPES = ("MODEL", "CLIP", "STRING")
    RETURN_NAMES = ("model", "clip", "trigger_words")
    FUNCTION = "load_lora_with_trigger_preset"
    CATEGORY = "loaders/lora"
    DESCRIPTION = (
        "Loads one LoRA and outputs its user-defined trigger words. The trigger "
        "preset is stored with the ComfyUI workflow."
    )

    def load_lora_with_trigger_preset(
        self,
        model,
        clip,
        lora_name,
        strength_model,
        strength_clip,
        preset_trigger_words,
    ):
        trigger_words = preset_trigger_words.strip()

        if lora_name == "None" or (strength_model == 0 and strength_clip == 0):
            return (model, clip, trigger_words)

        lora_path = folder_paths.get_full_path("loras", lora_name)
        if lora_path is None:
            raise FileNotFoundError(f"LoRA not found: {lora_name}")

        lora = None
        if self.loaded_lora is not None:
            if self.loaded_lora[0] == lora_path:
                lora = self.loaded_lora[1]
            else:
                self.loaded_lora = None

        if lora is None:
            lora = comfy.utils.load_torch_file(lora_path, safe_load=True)
            self.loaded_lora = (lora_path, lora)

        model_lora, clip_lora = comfy.sd.load_lora_for_models(
            model, clip, lora, strength_model, strength_clip
        )
        return (model_lora, clip_lora, trigger_words)


NODE_CLASS_MAPPINGS = {
    "RandomTextPicker": RandomTextPicker,
    "AnimaPromptFormatter": AnimaPromptFormatter,
    "CLTaggerActionFilter": CLTaggerActionFilter,
    "LoRALoaderWithTriggerPreset": LoRALoaderWithTriggerPreset,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomTextPicker": "Random Text Picker",
    "AnimaPromptFormatter": "Anima Prompt Formatter",
    "CLTaggerActionFilter": "CL Tagger Action Filter",
    "LoRALoaderWithTriggerPreset": "LoRA Trigger Loader",
}
