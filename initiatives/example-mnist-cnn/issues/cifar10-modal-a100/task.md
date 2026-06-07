---
id: 019e7c1d-617b-73f0-a85b-e703d21f93ed
status: done
priority: high
assignee: adithya.yerramsetty@gmail.com
created: 2026-05-30T15:00:00.000Z
---

# CIFAR-10 CNN on Modal A100 — 78.71% accuracy

Train a convolutional neural network on CIFAR-10 using Modal with an A100 GPU. 

## Results

- **Final test accuracy:** 78.71%
- **Training time:** 91.05s
- **Epochs:** 10
- **Batch size:** 128
- **GPU:** A100

## Scope

- Use a standard CNN architecture (ResNet-18 or equivalent depth) suitable for CIFAR-10 (32×32 RGB images, 10 classes).
- Train for exactly 10 epochs.
- Batch size 128.
- A100 GPU via Modal.
- Standard data augmentation (random crop, horizontal flip, normalization).
- Report final top-1 test accuracy.

## Acceptance Criteria

- [x] Training script runs end-to-end on Modal A100.
- [x] 10 epochs complete without error.
- [x] Final test accuracy reported in a comment on this issue.
- [x] Results are reproducible with a pinned random seed.

## Context

- CIFAR-10 dataset from `torchvision.datasets.CIFAR10`.
- Framework: PyTorch.
- See `initiatives/example-mnist-cnn/AGENTS.md` for general ML conventions (reproducibility, no large binaries in git).
