import torch
import torch.nn.functional as F

from autoforge.Helper.ImageHelper import srgb_to_lab
from autoforge.Helper.OptimizerHelper import composite_image_cont


def loss_fn(
    params: dict,
    target: torch.Tensor,
    tau_height: float,
    tau_global: float,
    h: float,
    max_layers: int,
    material_colors: torch.Tensor,
    material_TDs: torch.Tensor,
    background: torch.Tensor,
    add_penalty_loss: float = 0.0,
    focus_map: torch.Tensor = None,
    alpha: torch.Tensor = None,
) -> torch.Tensor:
    """
    Full forward pass for continuous assignment:
    composite, then compute unified loss.
    focus_map acts as a priority mask (values in [0,1]) where 1.0 means full weight and 0 means low weight.
    alpha (optional) is a per-pixel alpha mask [H,W] or [H,W,1] in 0-255 range;
        pixels with alpha < 128 are masked out of the loss.
    """
    comp = composite_image_cont(
        params["pixel_height_logits"],
        params["global_logits"],
        tau_height,
        tau_global,
        h,
        max_layers,
        material_colors,
        material_TDs,
        background,
    )
    return compute_loss(
        comp=comp,
        target=target,
        pixel_height_logits=params.get("pixel_height_logits", None),
        tau_height=tau_height,
        add_penalty_loss=add_penalty_loss,
        focus_map=focus_map,
        alpha=alpha,
    )


def compute_loss(
    comp: torch.Tensor,
    target: torch.Tensor,
    pixel_height_logits: torch.Tensor = None,
    tau_height: float = 1.0,
    add_penalty_loss: float = 0.0,
    focus_map: torch.Tensor = None,
    alpha: torch.Tensor = None,
) -> torch.Tensor:
    """
    Compute loss between composite and target.

    If focus_map (priority mask) is provided (shape [H,W] normalized 0..1), we apply per-pixel weights:
        weight = 0.1 + 0.9 * focus_map
    (So outside mask -> 0.1, fully prioritized -> 1.0, gradients respected.)

    If alpha is provided (shape [H,W] or [H,W,1], values 0-255), transparent pixels
    (alpha < 128) are masked out entirely (weight = 0). When both focus_map and alpha
    are provided, the masks are combined multiplicatively.

    The final loss is the weighted mean of per-pixel Lab-space MSE.
    We normalize by the mean weight to keep the magnitude comparable with the unweighted loss.
    """
    comp_lab = srgb_to_lab(comp)
    target_lab = srgb_to_lab(target)

    if focus_map is None and alpha is None:
        mse_loss = F.mse_loss(comp_lab, target_lab)
        total_loss = mse_loss
    else:
        per_pixel_mse = (comp_lab - target_lab).pow(2).mean(dim=2)  # [H,W]
        weights = torch.ones_like(per_pixel_mse)

        if focus_map is not None:
            if focus_map.dim() == 3 and focus_map.shape[-1] == 1:
                focus_map_proc = focus_map.squeeze(-1)
            else:
                focus_map_proc = focus_map
            focus_map_proc = torch.clamp(focus_map_proc, 0.0, 1.0)
            weights = weights * (0.1 + 0.9 * focus_map_proc)

        if alpha is not None:
            if alpha.dim() == 3 and alpha.shape[-1] == 1:
                alpha_proc = alpha.squeeze(-1)
            else:
                alpha_proc = alpha
            # Resize alpha to match per_pixel_mse spatial dims (safety net
            # for any resolution mismatch in the pipeline)
            if alpha_proc.shape != per_pixel_mse.shape:
                alpha_proc = F.interpolate(
                    alpha_proc.unsqueeze(0).unsqueeze(0),
                    size=per_pixel_mse.shape[-2:],
                    mode="nearest",
                ).squeeze(0).squeeze(0)
            alpha_mask = (alpha_proc >= 128).float()
            weights = weights * alpha_mask

        weighted_loss = per_pixel_mse * weights
        total_loss = weighted_loss.mean() / weights.mean().clamp(min=1e-8)

    # Height-map smoothness penalty (Laplacian / total variation)
    if add_penalty_loss > 0 and pixel_height_logits is not None and pixel_height_logits.dim() == 2:
        dy = (pixel_height_logits[:, 1:] - pixel_height_logits[:, :-1]).pow(2).mean()
        dx = (pixel_height_logits[1:, :] - pixel_height_logits[:-1, :]).pow(2).mean()
        total_loss = total_loss + (dx + dy) * add_penalty_loss

    return total_loss
