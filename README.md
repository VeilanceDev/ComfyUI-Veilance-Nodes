# ComfyUI Veilance Nodes

Custom nodes for ComfyUI focused on workflow utilities, prompt tooling, pipe composition, and LLM prompt generation.

## Install

1. Copy or clone this repository into `ComfyUI/custom_nodes/`.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Restart ComfyUI.

## Included Nodes

- `Resolution Selector` (`Veilance/Utils`)
- `Prompt Selector` (dynamic category nodes from `data/prompts/`)
- `Prompt Cleaner` (`Veilance/Utils/Prompts`)
- `Load Model + Clip + VAE`
- `Load Model + Clip + VAE (Adv.)`
- `Load Checkpoint + VAE`
- `Load Checkpoint + VAE (Adv.)`
- `Pipe Builder`
- `Pipe Router`
- `KSampler (Pipe Full)`
- `Sampler Presets`
- `Seed Strategy`
- `LoRA Stack`
- `LLM Text Generator (Manual)` (`Veilance/Utils/Prompts`)
- `LLM Text Generator (Alias)` (`Veilance/Utils/Prompts`)
- `Save Image (CivitAI Metadata)` (`Veilance/Image`)
- `Film Grain` (`Veilance/Image`)
- `Jpegify` (`Veilance/Image`)
- `Sharpen` (`Veilance/Image/Sharpen`)
- `Unsharp Mask` (`Veilance/Image/Sharpen`)
- `Edge Sharpen` (`Veilance/Image/Sharpen`)
- `String Combiner` (`Veilance/Utils/Prompts`)
- `Text Search & Replace` (`Veilance/Utils/Prompts`)
- `Vignette` (`Veilance/Image`)
- `Basic Color Adjust` (`Veilance/Image`)
- `Crop to Ratio` (`Veilance/Image`)
- `Global Sampler + Scheduler` (`Veilance/Utils`)
- `Global Seed` (`Veilance/Utils`)
- `Any Switch` (`Veilance/Utils`)
- `Any Switch (Inverse)` (`Veilance/Utils`)
- `Set Variable` (`Veilance/Utils`)
- `Get Variable` (`Veilance/Utils`)
- `Image Size & Empty Latent` (`Veilance/Utils`)

## Prompt Selector Data

Prompt files are loaded from `data/prompts/` and can be:

- `.yaml` / `.yml`
- `.csv`
- `.json`

Each category folder becomes its own node. Each file in that category becomes a dropdown widget.

## JavaScript Extensions

Frontend extensions are loaded from `js/` via `WEB_DIRECTORY = "./js"` in the package root.

Current extensions:

- `js/prompt_selector.js`
- `js/lora_stack.js`
- `js/nano_gpt.js`
- `js/global_controls.js`
- `js/text_utils.js`

## Workflow Utils Structure

`workflow_utils/` is split by concern so small utility nodes can evolve without accumulating unrelated logic in one file:

- `global_nodes.py`: `Global Sampler + Scheduler` and `Global Seed`
- `switch_nodes.py`: `Any Switch` nodes
- `variable_nodes.py`: `Set Variable` and `Get Variable`
- `image_nodes.py`: `Image Size & Empty Latent`
- `helpers.py`: shared input-schema and latent helpers
- `registry.py`: exported node/display-name mappings
- `workflow_utils.py`: compatibility re-export surface for existing imports

`Global Sampler + Scheduler` and `Global Seed` also ship with a frontend helper in `js/global_controls.js` that propagates their widget values to matching sampler/scheduler/seed widgets elsewhere in the loaded graph.
`Set Variable` and `Get Variable` resolve exact variable names at execution time and forward arbitrary upstream outputs through an internal passthrough expansion, so they can be used with models, conditioning, images, strings, latents, and similar node outputs without long wires.

## LLM Alias Profiles

The LLM text generator is split into two nodes:

- `LLM Text Generator (Manual)`: uses node widget values directly for provider/API/auth/model settings
- `LLM Text Generator (Alias)`: loads provider/API URL, model, and key source/API key from a saved alias, with `alias_name` offered as a dropdown of saved aliases

Alias data model:

- Non-secret alias settings (`api_provider`, `custom_api_url`, `model`, key-source metadata) are stored in `nano_gpt/aliases.json`
- API keys are stored in OS keychain via Python `keyring` (not in workflow JSON)
- `key_source` can be `keyring`, `env` (from env var name), or `none`
- Generation controls (temperature, max tokens, top-p, penalties, response format) remain on the node widgets for both nodes

Open the alias manager from:

- ComfyUI Settings (`Veilance.LLM`)
- `LLM Text Generator (Alias)` node button/context menu (`Manage Aliases`)

## Notes

- `watchdog` is optional but enables auto-refresh for prompt file changes.
- `pyyaml` is optional but required for YAML prompt files.
- `keyring` is optional but required for encrypted API key storage in LLM aliases.
- `Film Grain` uses deterministic seeded grain with tone-aware masking, clumped spatial structure, and stock-specific chroma variation rather than plain per-pixel noise.
- `Film Grain` also exposes optional `clumpiness_scale` and `resolution_response_scale` controls for per-node tuning while keeping stock defaults at `1.0`.
- `Jpegify` simulates JPEG re-encoding artifacts in memory with adjustable intensity, pass count, and chroma subsampling.

For detailed architecture and development notes, see [`project.md`](project.md).
