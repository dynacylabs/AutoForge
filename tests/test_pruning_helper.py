"""Tests for the pure/self-contained helpers in autoforge.Helper.PruningHelper.

Consolidated with the pruning half of the former test_perception_and_pruning.py.
The higher-level prune_* routines that need a full FilamentOptimizer are
exercised in test_optimizer_training.py.
"""

import torch

from autoforge.Helper.PruningHelper import (
    disc_to_logits,
    find_color_bands,
    merge_bands,
    merge_color,
    remove_outlier_pixels,
    smooth_coplanar_faces,
)


# --------------------------------------------------------------------------
# disc_to_logits
# --------------------------------------------------------------------------


def test_disc_to_logits_is_argmax_recoverable():
    dg = torch.tensor([0, 1, 2, 1])
    logits = disc_to_logits(dg, num_materials=3)
    assert logits.shape == (4, 3)
    assert torch.equal(logits.argmax(dim=1), dg)
    for i, c in enumerate(dg):
        assert logits[i, c] > 1e3
        assert (logits[i, torch.arange(3) != c] < 0).all()


# --------------------------------------------------------------------------
# merge_color
# --------------------------------------------------------------------------


def test_merge_color_reassigns_only_the_source_index():
    dg = torch.tensor([0, 1, 2, 1])
    merged = merge_color(dg, c_from=1, c_to=0)
    assert torch.equal(merged, torch.tensor([0, 0, 2, 0]))
    # original untouched
    assert torch.equal(dg, torch.tensor([0, 1, 2, 1]))


# --------------------------------------------------------------------------
# find_color_bands / merge_bands
# --------------------------------------------------------------------------


def test_find_color_bands_returns_contiguous_runs():
    dg = torch.tensor([0, 0, 1, 1, 1, 2, 2])
    assert find_color_bands(dg) == [(0, 1, 0), (2, 4, 1), (5, 6, 2)]


def test_find_color_bands_counts_recurring_material_separately():
    dg = torch.tensor([0, 0, 1, 1, 2, 2, 1])
    assert len(find_color_bands(dg)) == 4


def test_merge_bands_forward_and_backward():
    dg = torch.tensor([0, 0, 1, 1, 1, 2, 2])
    bands = find_color_bands(dg)
    fwd = merge_bands(dg, bands[0], bands[1], direction="forward")
    assert torch.equal(fwd, torch.tensor([0, 0, 0, 0, 0, 2, 2]))
    bwd = merge_bands(dg, bands[0], bands[1], direction="backward")
    assert torch.equal(bwd, torch.tensor([1, 1, 1, 1, 1, 2, 2]))


# --------------------------------------------------------------------------
# remove_outlier_pixels
# --------------------------------------------------------------------------


def test_remove_outlier_pixels_pulls_spike_toward_neighbours():
    h = torch.zeros(5, 5)
    h[2, 2] = 10.0
    cleaned = remove_outlier_pixels(h, threshold=1.0)
    assert cleaned.shape == h.shape
    assert cleaned[2, 2] != 10.0
    assert abs(float(cleaned[2, 2])) < 10.0


def test_remove_outlier_pixels_leaves_smooth_field_alone():
    h = torch.full((5, 5), 3.0)
    cleaned = remove_outlier_pixels(h, threshold=1.0)
    assert torch.allclose(cleaned, h)


# --------------------------------------------------------------------------
# smooth_coplanar_faces
# --------------------------------------------------------------------------


def test_smooth_coplanar_faces_reduces_a_small_bump():
    base = torch.ones(8, 8)
    base[4, 4] = 1.5
    smoothed = smooth_coplanar_faces(base, angle_threshold=10.0)
    assert smoothed.shape == base.shape
    assert smoothed[4, 4] < base[4, 4]
