---
id: 019e8001-1234-7000-8000-000000000000
status: pending
priority: high
assignee: alice.smith@example.com
created: 2026-05-30T14:00:00.000Z
---

# Train Baseline MNIST CNN

Build and train a baseline CNN that hits the initiative's accuracy target (>99% on MNIST test set).

## Scope

1. **Model definition**
   - 2 convolutional blocks (Conv2d → ReLU → MaxPool).
   - 2 fully-connected layers.
   - Output: 10-class softmax.

2. **Training pipeline**
   - Data loading with `torchvision.datasets.MNIST`.
   - Standard data augmentation (random rotations, affine transforms).
   - Cross-entropy loss + Adam optimizer.
   - Reproducible with `random.seed` and `torch.manual_seed`.

3. **Evaluation**
   - Compute test accuracy after each epoch.
   - Log results to a simple CSV or stdout.

## Acceptance Criteria

- [ ] Training script runs end-to-end in one command (`python src/train.py`).
- [ ] Final test accuracy > 99%.
- [ ] Wall-clock training time < 10 minutes on a modern CPU.
- [ ] Model exported to ONNX (`checkpoints/model.onnx`).

## Context

- See `AGENTS.md` in `initiatives/example-mnist-cnn/` for the full spec.
- All code must pass `ruff` linting.
- Checkpoints are gitignored — do **not** commit weights to git.
