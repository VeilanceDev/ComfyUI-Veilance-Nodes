# AGENTS.md

Technical guidance for LLM agents reviewing or modifying this repository.

## Scope

This project is a ComfyUI custom-node package. The root [`__init__.py`](__init__.py) aggregates node mappings from submodules and exposes `WEB_DIRECTORY = "./js"`.

## Repository Map

- `__init__.py`: global node registration.
- `project.md`: long-form architecture and node behavior reference.
- `requirements.txt`: optional Python dependencies (`pyyaml`, `watchdog`).
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
- `prompt_selector` dynamically generates classes at runtime from `data/prompts/`.
- `prompt_selector` also registers `POST /prompt_selector/refresh` via `PromptServer`.

## External/API Node Notes

- `nano_gpt/nano_gpt.py` calls OpenAI-compatible `/chat/completions` endpoints.
- It supports multiple providers, optional image input, retries, and in-memory caching.
- Review API error handling carefully: HTTP errors are surfaced as string outputs, not raised exceptions.

## Review Priorities

When reviewing code, prioritize:

1. Behavioral regressions in existing node outputs/types.
2. Workflow compatibility (class names, return order, category changes).
3. Runtime safety under missing optional deps (`pyyaml`, `watchdog`, PIL/numpy/torch paths).
4. Dynamic node refresh logic in `prompt_selector` (thread safety and registry sync).
5. Network-call robustness for `nano_gpt` (timeouts, retries, auth handling).

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
