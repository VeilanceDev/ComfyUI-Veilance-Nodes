# AGENTS.md

Technical guidance for LLM agents reviewing or modifying this repository. Make sure to keep this file up to date with codebase modifications.

## Scope

This project is a ComfyUI custom-node package. The root [`__init__.py`](__init__.py) aggregates node mappings from submodules via guarded per-package imports and exposes `WEB_DIRECTORY = "./js"`.

## Repository Map

- `__init__.py`: global node registration.
- `node_packages/`: custom-node package implementations imported by the root registration file.
- `utils/comfy_reflection.py`: shared ComfyUI node/loader reflection helpers used by compatibility wrapper nodes, including KSampler/VAE/preview and advanced prompt-conditioning helpers.
- `utils/pipe_utils.py`: shared `PIPE` slot constants plus tuple/list item and tail helpers.
- `utils/http_utils.py`: shared bounded HTTP response-reading helpers for network-backed nodes.
- `project.md`: long-form architecture and node behavior reference.
- `requirements.txt`: optional Python dependencies (`pyyaml`, `watchdog`, `keyring`).
- Node packages under `node_packages/`:
  - `node_packages/resolution_selector/`
  - `node_packages/prompt_selector/`
  - `node_packages/prompt_cleaner/`
  - `node_packages/model_loader_trio/`
  - `node_packages/model_loader_checkpoint_vae/`
  - `node_packages/pipe_builder/`
  - `node_packages/pipe_router/`
  - `node_packages/pipe_ksampler/`
  - `node_packages/hires_fix/`
  - `node_packages/sampler_presets/`
  - `node_packages/seed_strategy/`
  - `node_packages/lora_stack/`
  - `node_packages/nano_gpt/`
  - `node_packages/image_loader/`
  - `node_packages/image_upscaler/`
  - `node_packages/save_image_civitai/`
  - `node_packages/text_utils/`
  - `node_packages/math_expression/`
  - `node_packages/workflow_utils/`
  - `node_packages/workflow_utils/source_filename_nodes.py`: graph-aware MODEL/CLIP/VAE filename extraction from prompt metadata.
- Frontend extensions: `js/`
- `js/image_loader.js`: image-loader frontend controls, including icon-only rotation buttons that update the node preview.
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
- Compatibility wrapper nodes (`model_loader_trio`, `model_loader_checkpoint_vae`, `pipe_ksampler`, `hires_fix`, `lora_stack`, `sampler_presets`) share reflection utilities from `utils/comfy_reflection.py`; update the shared helper first when changing fallback class resolution, required-input handling, KSampler/VAE execution, advanced prompt conditioning, or ComfyUI normalized-output compatibility.
- Nodes that read or preserve `PIPE` slots should use `utils/pipe_utils.py` constants/helpers instead of duplicating numeric indexes.
- `hires_fix` exports `PipeHiResFix` / `HiRes Fix`, a refine-stage wrapper node that preserves `PIPE` slot order, defaults to `upscale_by = 1.5` and `denoise = 0.3`, supports latent upscale-by fallback, and can optionally use ComfyUI's built-in `Load Upscale Model` + `Upscale Image (using Model)` path before the denoise pass.
- `hires_fix` populates `upscale_model` from ComfyUI's registered upscale-model lists, preferring the `upscale_models` registry used for ESRGAN/upscale models with a legacy `esrgan` fallback.
- `hires_fix` now respects the requested `upscale_by` even when an ESRGAN/upscale model has a different native scale by resizing the model-upscaled image back to the node's target dimensions before VAE re-encode.
- `model_loader_trio` keeps legacy class keys (`ModelLoaderTrio`, `ModelLoaderTrioWithParams`) for workflow compatibility, but the display names are `Load Model + Clip + VAE` and `Load Model + Clip + VAE (Adv.)`; the advanced variant also exposes `clip_skip` and optional `a1111_prompt_style`, applying ComfyUI `CLIP Set Last Layer` before prompt encoding and using `ComfyUI_smZNodes` `CLIP Text Encode++` when A1111 mode is enabled. Before invoking that path it patches ComfyUI SDXL encoder classes with a legacy `encode` alias when newer builds only expose `execute`, preventing the current `smZNodes` SDXL API mismatch from crashing.
- `model_loader_checkpoint_vae` exports both `ModelLoaderCheckpointVAE` and `ModelLoaderCheckpointVAEWithParams`; the advanced variant adds prompt conditioning and empty latent outputs while preserving the standard `PIPE` slot order, and now mirrors the trio advanced loader's `clip_skip` plus optional `a1111_prompt_style` behavior, including the same SDXL `smZNodes` compatibility shim.
- `prompt_selector` dynamically generates classes at runtime from `data/prompts/`.
- `prompt_selector` implementation is split by concern: `parsers.py` handles YAML/CSV/JSON parsing and data types, `cache.py` handles category discovery/indexing/cache lookup, `watcher.py` handles optional watchdog integration, and `file_utils.py` remains the compatibility export surface.
- Prompt selector class names now append a stable hash suffix only when multiple categories normalize to the same legacy class key, avoiding registry collisions while preserving legacy names when unique.
- Dynamic prompt selector nodes are grouped under the ComfyUI category path `Veilance/Prompts/Dynamic Lists`.
- `prompt_selector` also registers `POST /prompt_selector/refresh` via `PromptServer`.
- `nano_gpt` exposes two nodes: `LLM Text Generator (Manual)` for direct provider/API-key/model entry and `LLM Text Generator (Alias)` for alias-based connection/auth/model settings.
- `LLM Text Generator (Alias)` exposes `alias_name` as a dropdown populated from the saved alias list; `js/nano_gpt.js` refreshes that widget after alias-manager changes.
- Alias metadata stores `api_provider`, `custom_api_url`, `model`, and key-source metadata in ignored `node_packages/nano_gpt/aliases.local.json`, with read-only fallback migration from legacy `node_packages/nano_gpt/aliases.json`; API keys are resolved from OS keyring (`keyring`) or env vars.
- `nano_gpt` image input requires Pillow and numpy at runtime; missing deps now return a clear node error instead of failing later during image conversion.
- `nano_gpt` response caching is an in-memory LRU+TTL cache keyed by request payload plus auth scope (`manual` vs `alias`, alias name when used, API-key fingerprint), so cached responses do not leak across different credentials.
- `image_loader` provides `Load Image (Upload or URL)`, which mirrors ComfyUI-style local upload selection via `image_upload`, can alternatively fetch one or more HTTP/HTTPS image URLs from the multiline `image_url` field (one URL per line), bounds remote response reads via `utils/http_utils.py`, and applies quarter-turn rotation through icon-only frontend buttons backed by a hidden `rotation_steps` input so execution output and preview stay aligned.
- `image_upscaler` provides `Image Upscaler`, an IMAGE-to-IMAGE wrapper around ComfyUI's `Load Upscale Model` + `Upscale Image (using Model)` path. It exposes only `upscale_model`, `upscale_by`, and preview controls; there is no KSampler, denoise, latent, or PIPE behavior. Like `hires_fix`, it corrects the final image to the requested `upscale_by` target size when the selected ESRGAN/upscale model has a different native scale.
- `nano_gpt` registers alias management routes:
  - `GET /veilance/nano_gpt/aliases`
  - `POST /veilance/nano_gpt/aliases/upsert`
  - `POST /veilance/nano_gpt/aliases/delete`
- `save_image_civitai` is an output node that writes CivitAI-compatible metadata for PNG/JPG/WEBP and optionally embeds Comfy workflow metadata.
- `save_image_civitai` prefers ComfyUI `folder_paths` output directory, with a local `./output` fallback when `folder_paths` is unavailable.
- `math_expression` provides `Math Expression`, a safe AST-based evaluator node with `x/y/z/w` variables (plus `a/b/c/d` aliases), optional linked numeric overrides, and `FLOAT` + `INT` outputs for arithmetic expressions without using Python `eval`.
- `workflow_utils` is organized into focused modules (`switch_nodes.py`, `image_nodes.py`, `helpers.py`, `registry.py`), while `node_packages/workflow_utils/workflow_utils.py` remains the compatibility export surface for existing imports.
- `workflow_utils` also includes `global_nodes.py` for `Global Sampler + Scheduler` and `Global Seed`; `js/global_controls.js` propagates those widget values to matching sampler/scheduler/seed widgets across the loaded graph.
- `workflow_utils` also includes `variable_nodes.py` for `Set Variable` and `Get Variable`; `Get Variable` resolves a matching `Set Variable` by exact `name` from prompt metadata at execution time, expands through `VeilanceAnySwitch` to preserve arbitrary upstream datatypes, and raises a clear runtime error when names are missing or duplicated.
- `workflow_utils` also includes `source_filename_nodes.py` for `Source Filename`; it traces supported loader and wrapper nodes through prompt metadata to recover the selected base filename for MODEL/CLIP/VAE sources and returns `<unknown filename>` when unsupported.
- Root package registration loads node packages through a guarded import helper so one broken package does not prevent unrelated nodes from appearing in ComfyUI.
- Root startup logs include a per-run package load summary (`loaded`, `skipped`, `nodes`) and list any skipped package names.
- `resolution_selector` now outputs `width`, `height`, `megapixels`, and `aspect_ratio_actual`; the old `pixel_delta` output has been removed.

## External/API Node Notes

- `node_packages/nano_gpt/nano_gpt.py` calls OpenAI-compatible `/chat/completions` endpoints.
- It supports multiple providers, optional image input, retries, in-memory caching, and split manual/alias node surfaces so each node only exposes the settings it actually uses.
- Review API error handling carefully: HTTP errors are surfaced as string outputs, not raised exceptions.
- `node_packages/nano_gpt/alias_store.py` handles alias persistence and keyring interactions. Avoid storing API secrets in workflow widgets or plaintext JSON.

## Review Priorities

When reviewing code, prioritize:

1. Behavioral regressions in existing node outputs/types.
2. Workflow compatibility (class names, return order, category changes).
3. Runtime safety under missing optional deps (`pyyaml`, `watchdog`, PIL/numpy/torch paths).
4. Dynamic node refresh logic in `prompt_selector` (thread safety and registry sync).
5. Network-call robustness for `nano_gpt` (timeouts, retries, auth handling).
6. Alias/key handling safety in `nano_gpt` (`keyring` availability, env fallback behavior, no secret leakage to workflow payloads).
7. Metadata compatibility and format-specific save behavior in `save_image_civitai` (PNG text chunks vs JPG/WEBP EXIF).
8. Variable-node resolution in `workflow_utils` (exact-name matching, duplicate detection, arbitrary-type passthrough, and safe behavior when prompt metadata is missing).
9. Source-filename tracing in `workflow_utils` (loader key mapping, pipe component routing, baked-VAE fallback, and graceful `<unknown filename>` behavior on unsupported graphs).
10. HiRes Fix compatibility and fallback behavior (`hires_fix` should stay usable when ComfyUI upscale-model extras are unavailable in latent-only mode, while image-model mode should fail with a targeted runtime error).
11. Advanced loader prompt compatibility (`clip_skip` should be applied before conditioning; enabling `a1111_prompt_style` should fail with a clear runtime error when `ComfyUI_smZNodes` is unavailable and otherwise route through `CLIP Text Encode++`).

## Local Validation

Minimum checks after edits:

```bash
python -m unittest discover -s tests
python -m compileall -q -x "(\\.venv|\\.git)" .
```

Recommended spot checks:

```bash
rg "NODE_CLASS_MAPPINGS" -n
rg "NODE_DISPLAY_NAME_MAPPINGS" -n
```

If you add a node package, confirm it is imported and merged in root `__init__.py`.
