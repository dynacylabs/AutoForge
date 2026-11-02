"""Tests for autoforge.Helper.ImageHelper."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("cv2")

from autoforge.Helper.ImageHelper import (
    imread,
    imwrite,
    increase_saturation,
    resize_image,
    resize_image_exact,
    srgb_to_lab,
)

GRAY_WEIGHTS = torch.tensor([0.2989, 0.5870, 0.1140])


# --------------------------------------------------------------------------
# srgb_to_lab
# --------------------------------------------------------------------------


def test_srgb_to_lab_shape_preserved():
    img = torch.randint(0, 255, (10, 12, 3), dtype=torch.uint8).to(torch.float32)
    lab = srgb_to_lab(img)
    assert lab.shape == img.shape


def test_srgb_to_lab_known_anchor_colours():
    black = torch.zeros(1, 1, 3)
    white = torch.full((1, 1, 3), 255.0)
    lab_black = srgb_to_lab(black)[0, 0]
    lab_white = srgb_to_lab(white)[0, 0]
    # L in [0, 100]; black -> ~0, white -> ~100, both near-neutral a/b
    assert lab_black[0].abs() < 1.0
    assert abs(lab_white[0].item() - 100.0) < 1.0
    assert lab_black[1:].abs().max() < 2.0
    assert lab_white[1:].abs().max() < 2.0


def test_srgb_to_lab_l_channel_is_monotonic_in_brightness():
    dark = srgb_to_lab(torch.full((1, 1, 3), 40.0))[0, 0, 0]
    mid = srgb_to_lab(torch.full((1, 1, 3), 128.0))[0, 0, 0]
    bright = srgb_to_lab(torch.full((1, 1, 3), 220.0))[0, 0, 0]
    assert dark < mid < bright


def test_srgb_to_lab_is_differentiable():
    img = (torch.rand(4, 4, 3) * 255.0).requires_grad_(True)
    srgb_to_lab(img).pow(2).mean().backward()
    assert img.grad is not None and torch.isfinite(img.grad).all()


# --------------------------------------------------------------------------
# resize helpers
# --------------------------------------------------------------------------


def test_resize_image_exact_gives_requested_dimensions():
    arr = (np.random.rand(20, 30, 3) * 255).astype(np.uint8)
    out = resize_image_exact(arr, 10, 15)
    assert out.shape == (15, 10, 3)  # cv2 dsize is (w, h)


def test_resize_image_preserves_aspect_ratio_and_caps_long_side():
    arr = (np.random.rand(40, 80, 3) * 255).astype(np.uint8)  # H=40, W=80
    out = resize_image(arr, max_size=20)
    assert max(out.shape[:2]) == 20
    # 80:40 == 2:1 aspect kept -> 20 x 10
    assert out.shape[1] == 20 and out.shape[0] == 10


def test_resize_image_portrait_caps_height():
    arr = (np.random.rand(90, 30, 3) * 255).astype(np.uint8)
    out = resize_image(arr, max_size=30)
    assert out.shape[0] == 30
    assert out.shape[1] == 10


# --------------------------------------------------------------------------
# increase_saturation
# --------------------------------------------------------------------------


def test_increase_saturation_moves_pixels_away_from_gray_channel_last():
    img = torch.rand(16, 16, 3)
    out = increase_saturation(img, 0.5)
    assert out.shape == img.shape
    gray = (img * GRAY_WEIGHTS).sum(-1, keepdim=True)
    assert (out - gray).abs().mean() > (img - gray).abs().mean()


def test_increase_saturation_channel_first_shape():
    img = torch.rand(3, 8, 8)
    out = increase_saturation(img, 0.2)
    assert out.shape == img.shape


def test_increase_saturation_zero_percentage_is_identity():
    img = torch.rand(8, 8, 3)
    assert torch.allclose(increase_saturation(img, 0.0), img, atol=1e-5)


# --------------------------------------------------------------------------
# imread / imwrite round trip
# --------------------------------------------------------------------------


def test_imwrite_then_imread_round_trip(tmp_path):
    img = (np.random.rand(12, 9, 3) * 255).astype(np.uint8)
    path = str(tmp_path / "scratch.png")
    imwrite(path, img)
    back = imread(path)
    assert back.shape == img.shape
    assert np.array_equal(back, img)  # PNG is lossless
