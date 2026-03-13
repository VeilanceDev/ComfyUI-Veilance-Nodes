# AGENTS.md

Technical guidance for LLM agents reviewing or modifying this repository. Make sure to keep this file up to date with codebase modifications.

## Scope

This project is a ComfyUI custom-node package. The root [`__init__.py`](__init__.py) aggregates node mappings from submodules via guarded per-package imports and exposes `WEB_DIRECTORY = "./js"`.

## Repository Map

- `__init__.py`: global node registration.
- `comfy_reflection.py`: shared ComfyUI node/loader reflection helpers used by compatibility wrapper nodes.
- `project.md`: long-form architecture and node behavior reference.
- `requirements.txt`: optional Python dependencies (`pyyaml`, `watchdog`, `keyring`).
- Node packages:
  - `resolution_selector/`
  - `prompt_selector/`
  - `prompt_cleaner/`
  - `model_loader_trio/`
  - `model_loader_checkpoint_vae/`
  - `pipe_builder/`
  - `pipe_router/`
  - `pipe_ksampler/`
  - `sampler_presets/`
  - `seed_strategy/`
  - `lora_stack/`
  - `nano_gpt/`
  - `image_loader/`
  - `save_image_civitai/`
  - `image_sharpen/`
  - `film_grain/`
  - `image_artifacts/`
  - `text_utils/`
  - `image_adjustments/`
  - `workflow_utils/`
  - `workflow_utils/source_filename_nodes.py`: graph-aware MODEL/CLIP/VAE filename extraction from prompt metadata.
- Frontend extensions: `js/`
- Prompt data: `data/prompts/`

## Node Contract

Each node package should follow:

1. `package/__init__.py` exports `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`.
2. `package/package.py` defines node classes with:
   - `INPUT_TYPES`
   - `RETURN_TYPES`
   - `RETURN_NAMES`
   - `FUNCTION`
   - `CATEGORY`
3. Root `__init__.py` imports and merges that package mappings.

Preserve existing node class keys when possible; changing keys breaks saved workflows.
Resolution selector currently exports both `ResolutionSelector` and `VeilanceResolutionSelector` (alias) keys for workflow compatibility and collision avoidance.

## Important Internal Conventions

- `PIPE` tuple ordering is used across multiple nodes. Core slots:
  - `0 model`
  - `1 clip`
  - `2 vae`
  - `3 positive`
  - `4 negative`
  - `5 latent`
  - `6 seed`
- Some nodes preserve extra `PIPE` tail values; do not truncate unless intentional.
- Compatibility wrapper nodes (`model_loader_trio`, `model_loader_checkpoint_vae`, `pipe_ksampler`, `lora_stack`, `sampler_presets`) share reflection utilities from `comfy_reflection.py`; update the shared helper first when changing fallback class resolution or required-input handling.
- `model_loader_trio` keeps legacy class keys (`ModelLoaderTrio`, `ModelLoaderTrioWithParams`) for workflow compatibility, but the display names are `Load Model + Clip + VAE` and `Load Model + Clip + VAE (Adv.)`.
- `model_loader_checkpoint_vae` exports both `ModelLoaderCheckpointVAE` and `ModelLoaderCheckpointVAEWithParams`; the advanced variant adds prompt conditioning and empty latent outputs while preserving the standard `PIPE` slot order.
- `prompt_selector` dynamically generates classes at runtime from `data/prompts/`.
- Prompt selector class names now append a stable hash suffix only when multiple categories normalize to the same legacy class key, avoiding registry collisions while preserving legacy names when unique.
- Dynamic prompt selector nodes are grouped under the ComfyUI category path `Veilance/Prompts/Dynamic Lists`.
- `prompt_selector` also registers `POST /prompt_selector/refresh` via `PromptServer`.
- `nano_gpt` exposes two nodes: `LLM Text Generator (Manual)` for direct provider/API-key/model entry and `LLM Text Generator (Alias)` for alias-based connection/auth/model settings.
- `LLM Text Generator (Alias)` exposes `alias_name` as a dropdown populated from the saved alias list; `js/nano_gpt.js` refreshes that widget after alias-manager changes.
- Alias metadata stores `api_provider`, `custom_api_url`, `model`, and key-source metadata in `nano_gpt/aliases.json`, while API keys are resolved from OS keyring (`keyring`) or env vars.
- `nano_gpt` image input requires Pillow and numpy at runtime; missing deps now return a clear node error instead of failing later during image conversion.
- `nano_gpt` response caching is an in-memory LRU+TTL cache keyed by request payload plus auth scope (`manual` vs `alias`, alias name when used, API-key fingerprint), so cached responses do not leak across different credentials.
- `image_loader` provides `Load Image (Upload or URL)`, which mirrors ComfyUI-style local upload selection via `image_upload` and can alternatively fetch an HTTP/HTTPS image URL, returning standard `IMAGE` and `MASK` outputs.
- `nano_gpt` registers alias management routes:
  - `GET /veilance/nano_gpt/aliases`
  - `POST /veilance/nano_gpt/aliases/upsert`
  - `POST /veilance/nano_gpt/aliases/delete`
- `save_image_civitai` is an output node that writes CivitAI-compatible metadata for PNG/JPG/WEBP and optionally embeds Comfy workflow metadata.
- `save_image_civitai` prefers ComfyUI `folder_paths` output directory, with a local `./output` fallback when `folder_paths` is unavailable.
- `image_sharpen` provides torch-first image post-processing nodes with an optional Pillow/numpy fallback for blur operations.
- `film_grain` provides deterministic torch-based film grain with stock presets, clumped band-limited grain synthesis, adaptive luminance/detail masking, stock-specific RGB chroma imbalance, and mild resolution-aware grain scaling.
- `film_grain` exposes optional `clumpiness_scale` and `resolution_response_scale` inputs as stock-relative multipliers; the default `1.0` preserves each stock preset's internal tuning.
- `image_artifacts` provides a Pillow-backed `Jpegify` node that simulates JPEG re-encode artifacts in memory, preserves non-RGB extra channels, and raises a clear runtime error when Pillow/numpy are unavailable.
- `workflow_utils` is organized into focused modules (`switch_nodes.py`, `image_nodes.py`, `helpers.py`, `registry.py`), while `workflow_utils/workflow_utils.py` remains the compatibility export surface for existing imports.
- `workflow_utils` also includes `global_nodes.py` for `Global Sampler + Scheduler` and `Global Seed`; `js/global_controls.js` propagates those widget values to matching sampler/scheduler/seed widgets across the loaded graph.
- `workflow_utils` also includes `variable_nodes.py` for `Set Variable` and `Get Variable`; `Get Variable` resolves a matching `Set Variable` by exact `name` from prompt metadata at execution time, expands through `VeilanceAnySwitch` to preserve arbitrary upstream datatypes, and raises a clear runtime error when names are missing or duplicated.
- `workflow_utils` also includes `source_filename_nodes.py` for `Source Filename`; it traces supported loader and wrapper nodes through prompt metadata to recover the selected base filename for MODEL/CLIP/VAE sources and returns `<unknown filename>` when unsupported.
- Root package registration loads node packages through a guarded import helper so one broken package does not prevent unrelated nodes from appearing in ComfyUI.
- Root startup logs include a per-run package load summary (`loaded`, `skipped`, `nodes`) and list any skipped package names.
- `resolution_selector` now outputs `width`, `height`, `megapixels`, and `aspect_ratio_actual`; the old `pixel_delta` output has been removed.

## External/API Node Notes

- `nano_gpt/nano_gpt.py` calls OpenAI-compatible `/chat/completions` endpoints.
- It supports multiple providers, optional image input, retries, in-memory caching, and split manual/alias node surfaces so each node only exposes the settings it actually uses.
- Review API error handling carefully: HTTP errors are surfaced as string outputs, not raised exceptions.
- `nano_gpt/alias_store.py` handles alias persistence and keyring interactions. Avoid storing API secrets in workflow widgets or plaintext JSON.

## Review Priorities

When reviewing code, prioritize:

1. Behavioral regressions in existing node outputs/types.
2. Workflow compatibility (class names, return order, category changes).
3. Runtime safety under missing optional deps (`pyyaml`, `watchdog`, PIL/numpy/torch paths).
4. Dynamic node refresh logic in `prompt_selector` (thread safety and registry sync).
5. Network-call robustness for `nano_gpt` (timeouts, retries, auth handling).
6. Alias/key handling safety in `nano_gpt` (`keyring` availability, env fallback behavior, no secret leakage to workflow payloads).
7. Metadata compatibility and format-specific save behavior in `save_image_civitai` (PNG text chunks vs JPG/WEBP EXIF).
8. Image-processing safety in `image_sharpen`, `film_grain`, and `image_artifacts` (batch shape preservation, clamping, deterministic behavior where applicable, preserved extra channels, and graceful runtime handling).
9. Variable-node resolution in `workflow_utils` (exact-name matching, duplicate detection, arbitrary-type passthrough, and safe behavior when prompt metadata is missing).
10. Source-filename tracing in `workflow_utils` (loader key mapping, pipe component routing, baked-VAE fallback, and graceful `<unknown filename>` behavior on unsupported graphs).

## Local Validation

There is no dedicated test suite in this repo. Minimum checks after edits:

```bash
python -m compileall .
```

Recommended spot checks:

```bash
rg "NODE_CLASS_MAPPINGS" -n
rg "NODE_DISPLAY_NAME_MAPPINGS" -n
```

If you add a node package, confirm it is imported and merged in root `__init__.py`.
