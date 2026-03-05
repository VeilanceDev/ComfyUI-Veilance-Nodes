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

## Notes

- `watchdog` is optional but enables auto-refresh for prompt file changes.
- `pyyaml` is optional but required for YAML prompt files.

For detailed architecture and development notes, see [`project.md`](project.md).
