"""Generate colored PLY mesh from height map + color image for WebUI 3D preview."""

from typing import Optional, Tuple

import numpy as np
import trimesh
from trimesh import Trimesh


def generate_colored_preview_mesh(
    height_map: np.ndarray,
    color_image: np.ndarray,
    background_height: float,
    maximum_x_y_size: float,
    alpha_mask: Optional[np.ndarray] = None,
    background_color: Tuple[int, int, int] = (0, 0, 0),
) -> Trimesh:
    """Build a colored mesh from a height map + per-pixel RGB color image.

    Top and bottom surfaces (and the side walls at the silhouette boundary)
    all share one vertex per grid point instead of giving every triangle its
    own unique vertices. This lets a renderer interpolate color smoothly
    between adjacent pixels (avoiding a blocky "flat shaded" look) and keeps
    the mesh roughly 6x smaller, which matters for preview load time.

    Args:
        height_map: (H,W) float32, per-pixel heights in mm.
        color_image: (H,W,3) uint8 RGB — color for each top vertex.
        background_height: Height of the base/background slab in mm.
        maximum_x_y_size: Max X/Y dimension of the output mesh in mm.
        alpha_mask: Optional (H,W) bool/uint8 — True = valid. Pixels with
            alpha<128 are omitted.
        background_color: RGB tuple for bottom/side faces (0-255).

    Returns:
        Trimesh with vertex_colors set.
    """
    H, W = height_map.shape

    valid_mask: np.ndarray = (
        np.ones((H, W), dtype=bool)
        if alpha_mask is None
        else (alpha_mask >= 128).squeeze()
    )
    if valid_mask.ndim == 3 and valid_mask.shape[-1] >= 1:
        valid_mask = valid_mask[:, :, 0]
    valid_mask = valid_mask.astype(bool)

    quad_valid = (
        valid_mask[:-1, :-1]
        & valid_mask[:-1, 1:]
        & valid_mask[1:, 1:]
        & valid_mask[1:, :-1]
    )
    vi, vj = np.nonzero(quad_valid)
    if len(vi) == 0:
        return trimesh.Trimesh()

    # One shared vertex per grid point (row-major index = i * W + j), for
    # both the top surface and the bottom surface. Side walls at the
    # silhouette boundary reuse these same indices — a boundary point's
    # "top" and "bottom" vertices are exactly the wall's top/bottom corners.
    j, i = np.meshgrid(np.arange(W), np.arange(H))
    x = j.astype(np.float32)
    y = (H - 1 - i).astype(np.float32)
    scale = maximum_x_y_size / max(W - 1, H - 1, 1)
    x *= scale
    y *= scale

    top_z = height_map.astype(np.float32) + background_height
    bottom_z = np.zeros_like(top_z)

    top_vertices = np.stack([x, y, top_z], axis=2).reshape(-1, 3)
    bottom_vertices = np.stack([x, y, bottom_z], axis=2).reshape(-1, 3)

    top_colors = color_image.reshape(-1, 3).astype(np.uint8)
    bg = np.array(background_color, dtype=np.uint8)
    bottom_colors = np.broadcast_to(bg, top_colors.shape).astype(np.uint8)

    n_top = H * W
    all_vertices = np.concatenate([top_vertices, bottom_vertices], axis=0)
    all_colors = np.concatenate([top_colors, bottom_colors], axis=0)

    def top_idx(ii, jj):
        return ii * W + jj

    def bottom_idx(ii, jj):
        return n_top + ii * W + jj

    faces_list: list[np.ndarray] = []

    # --- Top surface (two triangles per valid quad) ---
    t00 = top_idx(vi, vj)
    t01 = top_idx(vi, vj + 1)
    t11 = top_idx(vi + 1, vj + 1)
    t10 = top_idx(vi + 1, vj)
    faces_list.append(np.stack([t11, t01, t00], axis=1))
    faces_list.append(np.stack([t10, t11, t00], axis=1))

    # --- Bottom surface (reversed winding so the normal points down) ---
    b00 = bottom_idx(vi, vj)
    b01 = bottom_idx(vi, vj + 1)
    b11 = bottom_idx(vi + 1, vj + 1)
    b10 = bottom_idx(vi + 1, vj)
    faces_list.append(np.stack([b00, b01, b11], axis=1))
    faces_list.append(np.stack([b00, b11, b10], axis=1))

    # --- Side walls: one quad per boundary edge, reusing top/bottom indices ---
    def add_walls(cond: np.ndarray, ia, ja, ib, jb, flip: bool):
        """Add a vertical quad between grid points (ia,ja)->(ib,jb) wherever
        `cond` is True. (ia,ja)-(ib,jb) is one edge of a valid quad that
        borders an invalid (or out-of-grid) neighbor."""
        si, sj = np.nonzero(cond)
        if len(si) == 0:
            return
        a_i, a_j = ia(si, sj), ja(si, sj)
        b_i, b_j = ib(si, sj), jb(si, sj)
        tA, tB = top_idx(a_i, a_j), top_idx(b_i, b_j)
        bA, bB = bottom_idx(a_i, a_j), bottom_idx(b_i, b_j)
        if flip:
            faces_list.append(np.stack([tA, bB, tB], axis=1))
            faces_list.append(np.stack([tA, bA, bB], axis=1))
        else:
            faces_list.append(np.stack([tA, tB, bB], axis=1))
            faces_list.append(np.stack([tA, bB, bA], axis=1))

    # Each direction's correct winding (outward normal) was derived by hand
    # and verified against mesh.volume/is_winding_consistent — it is NOT
    # uniform across directions, so each call states its own `flip`.

    # Left edges: quad (vi,vj) has no valid neighbor to its left. Outward = -X.
    left_cond = np.zeros_like(quad_valid, dtype=bool)
    left_cond[:, 0] = quad_valid[:, 0]
    left_cond[:, 1:] = quad_valid[:, 1:] & (~quad_valid[:, :-1])
    add_walls(left_cond, lambda i_, j_: i_, lambda i_, j_: j_, lambda i_, j_: i_ + 1, lambda i_, j_: j_, flip=True)

    # Right edges: quad (vi,vj) has no valid neighbor to its right. Outward = +X.
    right_cond = np.zeros_like(quad_valid, dtype=bool)
    right_cond[:, -1] = quad_valid[:, -1]
    right_cond[:, :-1] = quad_valid[:, :-1] & (~quad_valid[:, 1:])
    add_walls(right_cond, lambda i_, j_: i_ + 1, lambda i_, j_: j_ + 1, lambda i_, j_: i_, lambda i_, j_: j_ + 1, flip=True)

    # Top edges (row 0 side, i.e. smallest i): quad (vi,vj) has no valid neighbor above. Outward = +Y.
    top_cond = np.zeros_like(quad_valid, dtype=bool)
    top_cond[0, :] = quad_valid[0, :]
    top_cond[1:, :] = quad_valid[1:, :] & (~quad_valid[:-1, :])
    add_walls(top_cond, lambda i_, j_: i_, lambda i_, j_: j_ + 1, lambda i_, j_: i_, lambda i_, j_: j_, flip=True)

    # Bottom edges (last row side): quad (vi,vj) has no valid neighbor below. Outward = -Y.
    bottom_cond = np.zeros_like(quad_valid, dtype=bool)
    bottom_cond[-1, :] = quad_valid[-1, :]
    bottom_cond[:-1, :] = quad_valid[:-1, :] & (~quad_valid[1:, :])
    add_walls(bottom_cond, lambda i_, j_: i_ + 1, lambda i_, j_: j_ + 1, lambda i_, j_: i_ + 1, lambda i_, j_: j_, flip=False)

    faces = np.concatenate(faces_list, axis=0).astype(np.int64)

    # Vertices not referenced by any face (fully-invalid rows/columns) are
    # dropped so the exported mesh doesn't carry dead weight.
    used = np.unique(faces)
    remap = np.full(all_vertices.shape[0], -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    faces = remap[faces]

    mesh = trimesh.Trimesh(
        vertices=all_vertices[used],
        faces=faces,
        vertex_colors=all_colors[used],
        process=False,
    )
    return mesh


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    H, W = 4, 4
    hm = np.random.uniform(0.0, 1.0, (H, W)).astype(np.float32)
    ci = np.random.randint(0, 256, (H, W, 3), dtype=np.uint8)

    mesh = generate_colored_preview_mesh(
        height_map=hm,
        color_image=ci,
        background_height=0.24,
        maximum_x_y_size=50.0,
    )

    assert mesh.vertices.shape[0] > 0, "Mesh has no vertices"
    assert mesh.faces.shape[0] > 0, "Mesh has no faces"
    assert mesh.visual.vertex_colors is not None, "Mesh has no vertex colors"
    vc = mesh.visual.vertex_colors
    assert vc.shape[0] == mesh.vertices.shape[0]
    # Fully-valid HxW grid: exactly 2*H*W shared vertices (top + bottom).
    assert mesh.vertices.shape[0] == 2 * H * W, mesh.vertices.shape[0]

    print(f"Vertices: {mesh.vertices.shape[0]}")
    print(f"Faces: {mesh.faces.shape[0]}")
    print(f"Vertex colors shape: {vc.shape}")
    print(f"First 6 vertex colors:\n{vc[:6]}")
    print("Smoke test PASSED")
