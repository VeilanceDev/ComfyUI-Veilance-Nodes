"""
Image loading nodes for ComfyUI.
"""

from __future__ import annotations

import hashlib
import io
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

import torch

try:
    import folder_paths  # type: ignore
except ImportError:
    folder_paths = None

try:
    import numpy as np
    from PIL import Image, ImageFile, ImageOps, ImageSequence

    ImageFile.LOAD_TRUNCATED_IMAGES = True
except ImportError:
    np = None
    Image = None
    ImageFile = None
    ImageOps = None
    ImageSequence = None


SUPPORTED_IMAGE_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
EXCLUDED_ANIMATION_FORMATS = {"MPO"}
URL_TIMEOUT_SECONDS = 30


def _require_image_dependencies() -> None:
    if np is None or Image is None or ImageOps is None or ImageSequence is None:
        raise RuntimeError(
            "Load Image (Upload or URL) requires Pillow and numpy to decode images."
        )


def _parse_image_urls(image_url: str) -> list[str]:
    return [
        line.strip()
        for line in str(image_url or "").splitlines()
        if line.strip()
    ]


def _list_uploadable_images() -> list[str]:
    if folder_paths is None or not hasattr(folder_paths, "get_input_directory"):
        return [""]

    input_dir = folder_paths.get_input_directory()
    if not os.path.isdir(input_dir):
        return [""]

    files = [
        filename
        for filename in os.listdir(input_dir)
        if os.path.isfile(os.path.join(input_dir, filename))
    ]

    filter_files = getattr(folder_paths, "filter_files_content_types", None)
    if callable(filter_files):
        try:
            files = list(filter_files(files, ["image"]))
        except Exception:
            files = [
                filename
                for filename in files
                if os.path.splitext(filename)[1].lower() in SUPPORTED_IMAGE_EXTENSIONS
            ]
    else:
        files = [
            filename
            for filename in files
            if os.path.splitext(filename)[1].lower() in SUPPORTED_IMAGE_EXTENSIONS
        ]

    files = sorted(files)
    return files or [""]


def _resolve_uploaded_image_path(image: str) -> str:
    image_name = str(image or "").strip()
    if not image_name:
        raise FileNotFoundError("No uploaded image was selected.")

    candidates: list[str] = []

    if folder_paths is not None and hasattr(folder_paths, "get_annotated_filepath"):
        try:
            candidates.append(folder_paths.get_annotated_filepath(image_name))
        except Exception:
            pass

    candidates.append(image_name)

    if folder_paths is not None and hasattr(folder_paths, "get_input_directory"):
        candidates.append(os.path.join(folder_paths.get_input_directory(), image_name))

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(f"Uploaded image '{image_name}' was not found.")


def _hash_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file_handle:
        while True:
            chunk = file_handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _content_type_looks_non_image(content_type: str) -> bool:
    normalized = str(content_type or "").split(";", 1)[0].strip().lower()
    if not normalized:
        return False
    if normalized.startswith("image/"):
        return False
    return normalized.startswith(("text/", "application/json", "application/xml"))


def _load_image_bytes_from_url(image_url: str) -> bytes:
    request = urllib.request.Request(
        image_url,
        headers={
            "User-Agent": "ComfyUI-Veilance-Nodes/1.0",
            "Accept": "image/*,*/*;q=0.8",
        },
    )

    with urllib.request.urlopen(request, timeout=URL_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get("Content-Type", "")
        if _content_type_looks_non_image(content_type):
            raise RuntimeError(
                f"Image URL returned non-image content type '{content_type}'."
            )
        data = response.read()

    if not data:
        raise RuntimeError("Image URL returned an empty response.")

    return data


def _load_frames_as_tensors(img: Image.Image) -> tuple[torch.Tensor, torch.Tensor]:
    _require_image_dependencies()

    output_images = []
    output_masks = []
    expected_size = None
    image_format = str(getattr(img, "format", "") or "").upper()

    for frame in ImageSequence.Iterator(img):
        frame = ImageOps.exif_transpose(frame)
        if frame.mode == "I":
            frame = frame.point(lambda value: value * (1 / 255))

        rgb_frame = frame.convert("RGB")
        if expected_size is None:
            expected_size = rgb_frame.size

        if image_format not in EXCLUDED_ANIMATION_FORMATS and rgb_frame.size != expected_size:
            continue

        rgb_array = np.asarray(rgb_frame, dtype=np.float32) / 255.0
        image_tensor = torch.from_numpy(rgb_array)[None,]

        if "A" in frame.getbands():
            alpha = np.asarray(frame.getchannel("A"), dtype=np.float32) / 255.0
            mask_tensor = 1.0 - torch.from_numpy(alpha)
        else:
            mask_tensor = torch.zeros(
                (rgb_frame.size[1], rgb_frame.size[0]),
                dtype=torch.float32,
            )

        output_images.append(image_tensor)
        output_masks.append(mask_tensor.unsqueeze(0))

    if not output_images:
        raise RuntimeError("Image did not contain any decodable frames.")

    if len(output_images) == 1 or image_format in EXCLUDED_ANIMATION_FORMATS:
        return output_images[0], output_masks[0]

    return torch.cat(output_images, dim=0), torch.cat(output_masks, dim=0)


def _load_uploaded_image(image: str) -> tuple[torch.Tensor, torch.Tensor]:
    image_path = _resolve_uploaded_image_path(image)
    with Image.open(image_path) as img:
        return _load_frames_as_tensors(img)


def _load_remote_image(image_url: str) -> tuple[torch.Tensor, torch.Tensor]:
    try:
        data = _load_image_bytes_from_url(image_url)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Image URL request failed with HTTP {exc.code}: {exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"Image URL request failed: {reason}") from exc

    with Image.open(io.BytesIO(data)) as img:
        return _load_frames_as_tensors(img)


def _combine_image_batches(
    loaded_batches: list[tuple[str, torch.Tensor, torch.Tensor]]
) -> tuple[torch.Tensor, torch.Tensor]:
    if not loaded_batches:
        raise RuntimeError("No image URLs were provided.")

    if len(loaded_batches) == 1:
        _, image_tensor, mask_tensor = loaded_batches[0]
        return image_tensor, mask_tensor

    expected_image_shape = tuple(loaded_batches[0][1].shape[1:])
    expected_mask_shape = tuple(loaded_batches[0][2].shape[1:])

    image_tensors: list[torch.Tensor] = []
    mask_tensors: list[torch.Tensor] = []

    for url, image_tensor, mask_tensor in loaded_batches:
        image_shape = tuple(image_tensor.shape[1:])
        mask_shape = tuple(mask_tensor.shape[1:])
        if image_shape != expected_image_shape:
            raise RuntimeError(
                "All URL images must share the same image dimensions and channels to "
                f"be batched. Expected {expected_image_shape}, got {image_shape} for "
                f"'{url}'."
            )
        if mask_shape != expected_mask_shape:
            raise RuntimeError(
                "All URL images must share the same mask dimensions to be batched. "
                f"Expected {expected_mask_shape}, got {mask_shape} for '{url}'."
            )

        image_tensors.append(image_tensor)
        mask_tensors.append(mask_tensor)

    return torch.cat(image_tensors, dim=0), torch.cat(mask_tensors, dim=0)


def _load_remote_images(image_url: str) -> tuple[torch.Tensor, torch.Tensor]:
    urls = _parse_image_urls(image_url)
    if not urls:
        raise RuntimeError(
            "image_url must contain at least one http:// or https:// image URL."
        )

    loaded_batches = []
    for url in urls:
        loaded_image, loaded_mask = _load_remote_image(url)
        loaded_batches.append((url, loaded_image, loaded_mask))

    return _combine_image_batches(loaded_batches)


def _rotate_image_and_mask(
    image_tensor: torch.Tensor,
    mask_tensor: torch.Tensor,
    rotation_steps: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    steps = int(rotation_steps) % 4
    if steps == 0:
        return image_tensor, mask_tensor

    # IMAGE tensors are BHWC, MASK tensors are BHW.
    rotated_image = torch.rot90(image_tensor, k=-steps, dims=(1, 2))
    rotated_mask = torch.rot90(mask_tensor, k=-steps, dims=(1, 2))
    return rotated_image, rotated_mask


class VeilanceLoadImageUploadOrUrl:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source": (["upload", "url"], {"default": "upload"}),
                "image": (_list_uploadable_images(), {"image_upload": True}),
                "image_url": ("STRING", {"default": "https://", "multiline": True}),
                "rotation_steps": ("INT", {"default": 0, "min": 0, "max": 3, "step": 1}),
            }
        }

    CATEGORY = "Veilance/Image"
    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "load_image"
    SEARCH_ALIASES = [
        "load image",
        "upload image",
        "image url",
        "web image",
        "download image",
    ]

    @classmethod
    def VALIDATE_INPUTS(cls, source, image, image_url, rotation_steps):
        try:
            rotation = int(rotation_steps)
        except (TypeError, ValueError):
            return "rotation_steps must be an integer between 0 and 3."
        if rotation < 0 or rotation > 3:
            return "rotation_steps must be an integer between 0 and 3."

        if source == "url":
            urls = _parse_image_urls(image_url)
            if not urls:
                return "image_url must contain at least one http:// or https:// image URL."
            for url in urls:
                parsed = urlparse(url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    return (
                        "Each image_url line must be an http:// or https:// image URL. "
                        f"Invalid line: '{url}'."
                    )
            return True

        try:
            _resolve_uploaded_image_path(image)
        except FileNotFoundError as exc:
            return str(exc)
        return True

    @classmethod
    def IS_CHANGED(cls, source, image, image_url, rotation_steps):
        rotation = int(rotation_steps) % 4
        if source == "url":
            return float("nan")

        try:
            image_path = _resolve_uploaded_image_path(image)
            return f"upload:{_hash_file(image_path)}:rotation:{rotation}"
        except Exception:
            return float("nan")

    def load_image(self, source, image, image_url, rotation_steps):
        _require_image_dependencies()

        if source == "url":
            loaded_image, loaded_mask = _load_remote_images(image_url)
        else:
            loaded_image, loaded_mask = _load_uploaded_image(image)

        return _rotate_image_and_mask(loaded_image, loaded_mask, rotation_steps)


NODE_CLASS_MAPPINGS = {
    "VeilanceLoadImageUploadOrUrl": VeilanceLoadImageUploadOrUrl,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VeilanceLoadImageUploadOrUrl": "Load Image (Upload or URL)",
}
