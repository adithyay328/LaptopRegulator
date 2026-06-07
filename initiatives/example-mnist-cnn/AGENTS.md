# AGENTS.md — MNIST CNN Initiative

## What This Initiative Is

A reference example of a self-contained machine learning initiative — it exists to
demonstrate the initiative structure and issue workflow, not any particular tech
choice. The goal is a small, reproducible CNN that classifies MNIST digits.

## Design Principles

- **Reproducibility first.** Pin the random seed, commit the training config, log all hyperparameters.
- **Simplicity.** CNN only — no ResNet, no transformers. The goal is correctness, not state-of-the-art.
- **Portability.** Export to ONNX so the model can run anywhere.

## Tech Stack

| Concern | Technology |
|---|---|
| Language | Python |
| Framework | PyTorch |
| Model export | ONNX |
| Dataset | `torchvision.datasets.MNIST` |
| Evaluation | `torchmetrics` accuracy |

## Conventions

- Python code lives in `src/`.
- Training config is a single `config.yaml` in `src/`.
- Model weights are saved to `checkpoints/` (ignored in `.gitignore`).
- Never commit large binary files to git.
- All source code must pass `ruff` linting.

## Before Making Changes

- Read this `AGENTS.md` in full before editing the initiative.
- Follow the issue system conventions for any work items.
- The training script must remain runnable end-to-end in one command: `python src/train.py`.
