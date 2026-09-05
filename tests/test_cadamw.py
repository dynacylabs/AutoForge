"""Tests for autoforge.Helper.CAdamW.

CAdamW is AdamW plus the "cautious" update mask: a coordinate is only
stepped when the running first moment and the current gradient agree in
sign. These tests pin that behaviour down, not just "params moved".
"""

import math

import pytest
import torch

from autoforge.Helper.CAdamW import CAdamW


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"lr": -1e-3},
        {"betas": (-0.1, 0.999)},
        {"betas": (0.9, 1.5)},
        {"eps": -1e-6},
    ],
)
def test_invalid_hyperparameters_raise(kwargs):
    p = torch.nn.Parameter(torch.zeros(1))
    with pytest.raises(ValueError):
        CAdamW([p], **kwargs)


# --------------------------------------------------------------------------
# basic optimisation
# --------------------------------------------------------------------------


def test_step_moves_params_and_stays_finite():
    torch.manual_seed(0)
    model = torch.nn.Linear(4, 2)
    opt = CAdamW(model.parameters(), lr=1e-2, weight_decay=0.1)
    x, y = torch.randn(3, 4), torch.randn(3, 2)
    before = [p.clone() for p in model.parameters()]
    for _ in range(3):
        opt.zero_grad()
        torch.nn.functional.mse_loss(model(x), y).backward()
        opt.step()
    for b, p in zip(before, model.parameters()):
        assert not torch.equal(b, p)
        assert torch.isfinite(p).all()


def test_minimises_a_simple_quadratic():
    p = torch.nn.Parameter(torch.tensor([5.0, -3.0]))
    opt = CAdamW([p], lr=1e-1)
    for _ in range(500):
        opt.zero_grad()
        (p.pow(2).sum()).backward()
        opt.step()
    assert torch.allclose(p.detach(), torch.zeros(2), atol=1e-2)


# --------------------------------------------------------------------------
# the cautious mask
# --------------------------------------------------------------------------


def test_coordinate_is_frozen_when_gradient_disagrees_with_momentum():
    p = torch.nn.Parameter(torch.zeros(2))
    opt = CAdamW([p], lr=1e-1, weight_decay=0.0, correct_bias=False)

    # Build up a strongly positive first moment on both coordinates.
    for _ in range(5):
        opt.zero_grad()
        p.grad = torch.tensor([1.0, 1.0])
        opt.step()
    after_buildup = p.detach().clone()
    assert (after_buildup < 0).all()  # positive grad -> params driven negative

    # Now coordinate 1's gradient flips sign; its momentum is still positive,
    # so the cautious mask must zero that coordinate's update this step.
    opt.zero_grad()
    p.grad = torch.tensor([1.0, -1.0])
    opt.step()
    assert p.detach()[0] < after_buildup[0]           # coord 0 keeps moving
    assert p.detach()[1] == pytest.approx(after_buildup[1].item())  # coord 1 frozen


def test_first_step_updates_every_nonzero_gradient_coordinate():
    # On step 1 exp_avg == (1-beta1)*grad, so exp_avg*grad >= 0 everywhere.
    p = torch.nn.Parameter(torch.zeros(3))
    opt = CAdamW([p], lr=1e-1, correct_bias=False)
    opt.zero_grad()
    p.grad = torch.tensor([1.0, -1.0, 2.0])
    opt.step()
    assert (p.detach() != 0).all()
    assert p.detach()[0] < 0 and p.detach()[1] > 0 and p.detach()[2] < 0


# --------------------------------------------------------------------------
# bias correction / state
# --------------------------------------------------------------------------


def test_bias_correction_scales_the_first_step_size():
    beta1, beta2 = 0.9, 0.999
    g = 1.0
    steps = {}
    for correct in (False, True):
        p = torch.nn.Parameter(torch.zeros(1))
        opt = CAdamW([p], lr=1e-1, betas=(beta1, beta2), eps=0.0,
                     correct_bias=correct)
        opt.zero_grad()
        p.grad = torch.tensor([g])
        opt.step()
        steps[correct] = -float(p.detach())
    # correct_bias multiplies step_size by sqrt(1-b2)/(1-b1) on step 1
    ratio = steps[True] / steps[False]
    assert ratio == pytest.approx(math.sqrt(1 - beta2) / (1 - beta1), rel=1e-4)


def test_state_dict_round_trip_preserves_moment_buffers_and_step():
    p1 = torch.nn.Parameter(torch.tensor([2.0, -1.0]))
    o1 = CAdamW([p1], lr=1e-2)
    for _ in range(4):
        o1.zero_grad()
        (p1.pow(2).sum()).backward()
        o1.step()

    p2 = torch.nn.Parameter(p1.detach().clone().requires_grad_(True))
    o2 = CAdamW([p2], lr=1e-2)
    o2.load_state_dict(o1.state_dict())

    s1, s2 = o1.state[p1], o2.state[p2]
    assert s1["step"] == s2["step"] == 4
    assert torch.allclose(s1["exp_avg"], s2["exp_avg"])
    assert torch.allclose(s1["exp_avg_sq"], s2["exp_avg_sq"])

    # a further step from the restored state stays finite and keeps descending
    for opt, p in ((o1, p1), (o2, p2)):
        opt.zero_grad()
        (p.pow(2).sum()).backward()
        opt.step()
    assert torch.allclose(p1.detach(), p2.detach(), atol=1e-2)
    assert p2.detach().abs().sum() < 3.0
