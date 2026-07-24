import gc
import json
import os
import threading

import numpy as np
import torch
from PIL import Image

import folder_paths


MODEL_FOLDER_NAME = "cl_tagger_v2"
HUGGINGFACE_REPO_ID = "cella110n/cl_tagger_v2"
HUGGINGFACE_MODEL_VERSIONS = ("v2_00", "v2_01a")
REQUIRED_MODEL_FILES = (
    "model.onnx",
    "model.onnx.data",
    "model_vocabulary.json",
)
_MODEL_DOWNLOAD_LOCK = threading.Lock()


def _model_root():
    return os.path.join(folder_paths.models_dir, MODEL_FOLDER_NAME)


def _available_models():
    root = _model_root()
    installed_models = []
    if os.path.isdir(root):
        for current_root, _directories, files in os.walk(root):
            if all(required in files for required in REQUIRED_MODEL_FILES):
                relative_path = os.path.relpath(current_root, root)
                installed_models.append(relative_path.replace(os.sep, "/"))

    models = list(dict.fromkeys(installed_models + list(HUGGINGFACE_MODEL_VERSIONS)))
    return sorted(models)


def _normalize_tag(tag):
    return str(tag).replace("_", " ").strip().lower()


def _model_directory(model_name):
    model_root = os.path.abspath(_model_root())
    model_directory = os.path.abspath(
        os.path.join(model_root, *model_name.replace("\\", "/").split("/"))
    )
    if os.path.commonpath((model_root, model_directory)) != model_root:
        raise ValueError("CL Tagger v2 model path escapes the model folder")
    return model_directory


def _required_model_paths(model_name):
    model_directory = _model_directory(model_name)
    return {
        name: os.path.join(model_directory, name)
        for name in REQUIRED_MODEL_FILES
    }


def _missing_model_paths(required_paths):
    return [
        path for path in required_paths.values() if not os.path.isfile(path)
    ]


def _download_model(model_name):
    if model_name not in HUGGINGFACE_MODEL_VERSIONS:
        raise FileNotFoundError(
            f"Unknown CL Tagger v2 model '{model_name}' is incomplete and "
            "has no configured Hugging Face download source"
        )

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as error:
        raise RuntimeError(
            "Automatic CL Tagger v2 download requires huggingface_hub. "
            "Install the plugin requirements and restart ComfyUI."
        ) from error

    os.makedirs(_model_root(), exist_ok=True)
    print(
        f"[PromptTools:CLTaggerV2] Downloading {model_name} from "
        f"https://huggingface.co/{HUGGINGFACE_REPO_ID}"
    )
    try:
        for filename in REQUIRED_MODEL_FILES:
            hf_hub_download(
                repo_id=HUGGINGFACE_REPO_ID,
                filename=f"{model_name}/{filename}",
                local_dir=_model_root(),
            )
    except Exception as error:
        raise RuntimeError(
            "Could not download CL Tagger v2 from Hugging Face. Open "
            f"https://huggingface.co/{HUGGINGFACE_REPO_ID}, accept the "
            "model license, then sign in with `hf auth login` or set "
            "HF_TOKEN before retrying."
        ) from error


def _ensure_model(model_name):
    required_paths = _required_model_paths(model_name)
    if not _missing_model_paths(required_paths):
        return required_paths

    with _MODEL_DOWNLOAD_LOCK:
        if _missing_model_paths(required_paths):
            _download_model(model_name)

        missing = _missing_model_paths(required_paths)
        if missing:
            raise FileNotFoundError(
                "CL Tagger v2 download completed but required files are "
                "still missing: " + ", ".join(missing)
            )
    return required_paths


class CLTaggerV2:
    """Run cella110n CL Tagger v2 without depending on ComfyUI_Mira."""

    _vocabulary_cache = {}
    _always_excluded_tags = frozenset(
        {
            "censored",
            "mosaic censoring",
            "bar censored",
        }
    )

    def __init__(self):
        self._sessions = {}

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "model_name": (_available_models(),),
                "general": (
                    "FLOAT",
                    {
                        "default": 0.55,
                        "min": 0.05,
                        "max": 1.0,
                        "step": 0.01,
                    },
                ),
                "character": (
                    "FLOAT",
                    {
                        "default": 0.55,
                        "min": 0.05,
                        "max": 1.0,
                        "step": 0.01,
                    },
                ),
                "replace_space": ("BOOLEAN", {"default": True}),
                "categories": (
                    "STRING",
                    {
                        "default": (
                            "rating,quality,character,copyright,general,meta"
                        ),
                        "multiline": False,
                    },
                ),
                "exclude_tags": (
                    "STRING",
                    {"default": "", "multiline": False},
                ),
                "session_method": (
                    ["CPU", "CPU Release", "GPU", "GPU Release"],
                ),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("tags",)
    FUNCTION = "tag"
    CATEGORY = "text/tagger"
    DESCRIPTION = (
        "Runs CL Tagger v2 from ComfyUI/models/cl_tagger_v2. "
        "This node is provided directly by ComfyUI Prompt Tools."
    )

    @staticmethod
    def _preprocess_image(image):
        image_array = image.detach().cpu().numpy()
        image_array = np.clip(image_array * 255.0, 0, 255).astype(np.uint8)
        pil_image = Image.fromarray(image_array).convert("RGB")
        resampling = getattr(Image, "Resampling", Image)
        pil_image = pil_image.resize((384, 384), resampling.BICUBIC)

        normalized = np.asarray(pil_image, dtype=np.float32) / 255.0
        normalized = (normalized - 0.5) / 0.5
        return np.expand_dims(
            np.transpose(normalized, (2, 0, 1)), axis=0
        ).astype(np.float32, copy=False)

    @classmethod
    def _load_vocabulary(cls, vocabulary_path):
        cached = cls._vocabulary_cache.get(vocabulary_path)
        if cached is not None:
            return cached

        with open(vocabulary_path, "r", encoding="utf-8") as file:
            payload = json.load(file)

        if not isinstance(payload, dict):
            raise ValueError("CL Tagger v2 vocabulary must be a JSON object")

        idx_to_tag = payload.get("idx_to_tag")
        tag_to_category = payload.get("tag_to_category")
        if not isinstance(idx_to_tag, dict) or not isinstance(
            tag_to_category, dict
        ):
            raise ValueError(
                "CL Tagger v2 vocabulary is missing idx_to_tag or "
                "tag_to_category"
            )

        names = [None] * (max(int(index) for index in idx_to_tag) + 1)
        category_indices = {}
        for index_text, tag in idx_to_tag.items():
            index = int(index_text)
            names[index] = str(tag)
            category = tag_to_category.get(tag)
            if isinstance(category, str):
                category_indices.setdefault(category.lower(), []).append(index)

        vocabulary = {
            "names": names,
            "categories": {
                category: np.asarray(indices, dtype=np.int64)
                for category, indices in category_indices.items()
            },
        }
        cls._vocabulary_cache[vocabulary_path] = vocabulary
        print(
            f"[PromptTools:CLTaggerV2] Loaded {len(names)} tags from "
            f"{vocabulary_path}"
        )
        return vocabulary

    def _get_session(self, model_path, session_method):
        try:
            import onnxruntime as ort
        except ImportError as error:
            raise RuntimeError(
                "CL Tagger v2 requires onnxruntime. Install the plugin "
                "requirements and restart ComfyUI."
            ) from error

        wants_gpu = session_method.startswith("GPU")
        available_providers = ort.get_available_providers()
        if wants_gpu and "CUDAExecutionProvider" in available_providers:
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            provider_key = "gpu"
        else:
            providers = ["CPUExecutionProvider"]
            provider_key = "cpu"
            if wants_gpu:
                print(
                    "[PromptTools:CLTaggerV2] CUDAExecutionProvider is not "
                    "available; falling back to CPU."
                )

        cache_key = (model_path, provider_key)
        session = self._sessions.get(cache_key)
        if session is None:
            print(
                f"[PromptTools:CLTaggerV2] Loading {model_path} with "
                f"{providers[0]}"
            )
            session = ort.InferenceSession(model_path, providers=providers)
            self._sessions[cache_key] = session
        return session

    @staticmethod
    def _category_predictions(
        probabilities, vocabulary, general_threshold, character_threshold
    ):
        predictions = {}
        threshold_by_category = {
            "general": general_threshold,
            "meta": general_threshold,
            "character": character_threshold,
            "copyright": character_threshold,
        }

        for category, indices in vocabulary["categories"].items():
            valid_indices = indices[indices < len(probabilities)]
            if valid_indices.size == 0:
                predictions[category] = []
                continue

            category_probabilities = probabilities[valid_indices]
            if category in ("rating", "quality"):
                best_local_index = int(np.argmax(category_probabilities))
                selected_indices = valid_indices[[best_local_index]]
                selected_probabilities = category_probabilities[
                    [best_local_index]
                ]
            else:
                threshold = threshold_by_category.get(
                    category, general_threshold
                )
                selected_mask = category_probabilities >= threshold
                selected_indices = valid_indices[selected_mask]
                selected_probabilities = category_probabilities[selected_mask]

            ordered = sorted(
                zip(selected_indices.tolist(), selected_probabilities.tolist()),
                key=lambda item: item[1],
                reverse=True,
            )
            predictions[category] = [
                (vocabulary["names"][index], float(probability))
                for index, probability in ordered
                if vocabulary["names"][index] is not None
            ]

        return predictions

    def _format_tags(
        self, predictions, categories, replace_space, exclude_tags
    ):
        selected_categories = [
            category.strip().lower()
            for category in categories.split(",")
            if category.strip()
        ]
        output_tags = []
        for category in selected_categories:
            category_tags = predictions.get(category, [])
            if category in ("rating", "quality"):
                category_tags = category_tags[:1]

            for tag, _probability in category_tags:
                if category == "meta" and any(
                    blocked in tag.lower()
                    for blocked in ("id", "commentary", "request", "mismatch")
                ):
                    continue
                output_tags.append(
                    tag.replace("_", " ") if replace_space else tag
                )

        always_excluded = {
            _normalize_tag(tag) for tag in self._always_excluded_tags
        }
        user_excluded = [
            value.strip().lower()
            for value in exclude_tags.split(",")
            if value.strip()
        ]

        filtered = []
        for tag in output_tags:
            normalized = _normalize_tag(tag)
            if normalized in always_excluded:
                continue
            if any(excluded in tag.lower() for excluded in user_excluded):
                continue
            filtered.append(tag)
        return ", ".join(filtered)

    def _run_one(
        self,
        image,
        session,
        vocabulary,
        general,
        character,
        replace_space,
        categories,
        exclude_tags,
    ):
        input_tensor = self._preprocess_image(image)
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        logits = session.run([output_name], {input_name: input_tensor})[0][0]
        logits = np.nan_to_num(logits, nan=0.0, posinf=30.0, neginf=-30.0)
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(logits, -30, 30)))

        predictions = self._category_predictions(
            probabilities, vocabulary, general, character
        )
        return self._format_tags(
            predictions, categories, replace_space, exclude_tags
        )

    def _release_sessions(self):
        self._sessions.clear()
        gc.collect()

    def tag(
        self,
        image,
        model_name,
        general,
        character,
        replace_space,
        categories,
        exclude_tags,
        session_method,
    ):
        if not isinstance(image, torch.Tensor):
            raise ValueError("Input image must be a torch.Tensor")
        required_paths = _ensure_model(model_name)

        if image.ndim == 3:
            image = image.unsqueeze(0)
        if image.ndim != 4:
            raise ValueError(
                "Input image must have shape [batch, height, width, channels]"
            )

        release_after_run = session_method.endswith("Release")
        try:
            session = self._get_session(
                required_paths["model.onnx"], session_method
            )
            vocabulary = self._load_vocabulary(
                required_paths["model_vocabulary.json"]
            )
            results = [
                self._run_one(
                    image[index],
                    session,
                    vocabulary,
                    general,
                    character,
                    replace_space,
                    categories,
                    exclude_tags,
                )
                for index in range(image.shape[0])
            ]
            output = "\n".join(results)
            print(f"[PromptTools:CLTaggerV2] {output}")
            return (output,)
        finally:
            if release_after_run:
                self._release_sessions()


NODE_CLASS_MAPPINGS = {
    # Preserve the original Mira node ID so existing workflows reconnect.
    "cl_tagger_v2_mira": CLTaggerV2,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "cl_tagger_v2_mira": "CL Tagger v2",
}
