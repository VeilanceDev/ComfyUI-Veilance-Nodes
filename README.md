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
- `Model Loader Trio`
- `Model Loader Checkpoint + VAE`
- `Pipe Builder`
- `Pipe Router`
- `KSampler (Pipe Full)`
- `Sampler Presets`
- `Seed Strategy`
- `LoRA Stack`
- `NanoGPT Text Generator` (`Veilance/Utils/Prompts`)
- `Save Image (CivitAI Metadata)` (`Veilance/Image`)
- `Film Grain` (`Veilance/Image`)
- `Sharpen` (`Veilance/Image/Sharpen`)
- `Unsharp Mask` (`Veilance/Image/Sharpen`)
- `Edge Sharpen` (`Veilance/Image/Sharpen`)
- `String Combiner` (`Veilance/Utils/Prompts`)
- `Text Search & Replace` (`Veilance/Utils/Prompts`)
- `Vignette` (`Veilance/Image`)
- `Basic Color Adjust` (`Veilance/Image`)
- `Crop to Ratio` (`Veilance/Image`)
- `Any Switch` (`Veilance/Utils`)
- `Any Switch (Inverse)` (`Veilance/Utils`)
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
- `js/text_utils.js`

## NanoGPT Alias Profiles

`NanoGPT Text Generator` supports two config modes:

- `manual`: use node widget values directly (legacy behavior)
- `alias`: load API URL, model, and key source/API key from a saved alias

Alias data model:

- Non-secret alias settings (`custom_api_url`, `model`, key-source metadata) are stored in `nano_gpt/aliases.json`
- API keys are stored in OS keychain via Python `keyring` (not in workflow JSON)
- `key_source` can be `keyring`, `env` (from env var name), or `none`
- Generation controls (temperature, max tokens, top-p, penalties, response format) remain on the node widgets

Open the alias manager from:

- ComfyUI Settings (`Veilance.NanoGPT`)
- NanoGPT node button/context menu (`Manage Aliases`)

## Notes

- `watchdog` is optional but enables auto-refresh for prompt file changes.
- `pyyaml` is optional but required for YAML prompt files.
- `keyring` is optional but required for encrypted API key storage in NanoGPT aliases.

For detailed architecture and development notes, see [`project.md`](project.md).
