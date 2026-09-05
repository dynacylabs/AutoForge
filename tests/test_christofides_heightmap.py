"""Tests for the Christofides height-map initializer.

Consolidated from the former test_christofides_height_map.py,
test_christofides_heightmap.py and test_heightmap_init.py, which all
exercised autoforge.Helper.Heightmaps.ChristofidesHeightMap with heavily
overlapping cases.
"""

import numpy as np
import pytest

pytest.importorskip("sklearn")
pytest.importorskip("skimage")

from skimage.color import rgb2lab

from autoforge.Helper.Heightmaps.ChristofidesHeightMap import (
    _compute_distinctiveness,
    build_distance_matrix,
    christofides_tsp,
    compute_ordering_metric,
    create_mapping,
    find_eulerian_tour,
    find_odd_vertexes,
    interpolate_arrays,
    matrix_to_graph,
    minimum_spanning_tree,
    minimum_weight_matching,
    prune_ordering,
    sample_pixels_for_silhouette,
    segmentation_quality,
    tsp_order_christofides_path,
    two_stage_weighted_kmeans,
)


# --------------------------------------------------------------------------
# Clustering
# --------------------------------------------------------------------------


def test_two_stage_weighted_kmeans_random_image():
    rng = np.random.default_rng(0)
    img = rng.integers(0, 256, size=(16, 16, 3), dtype=np.uint8).astype(np.float32) / 255.0
    lab = rgb2lab(img)
    labs, labels = two_stage_weighted_kmeans(
        lab.reshape(-1, 3), 16, 16, overcluster_k=20, final_k=4, random_state=0
    )
    assert labs.shape == (4, 3)
    assert labels.shape == (16, 16)
    assert set(np.unique(labels)).issubset(set(range(4)))


def test_two_stage_weighted_kmeans_two_color_separation():
    H, W = 20, 20
    lab = np.zeros((H * W, 3), dtype=np.float32)
    lab[: (H * W) // 2] = np.array([50, 0, 0])
    lab[(H * W) // 2 :] = np.array([80, 20, -10])
    centroids, labels = two_stage_weighted_kmeans(
        lab, H, W, overcluster_k=10, final_k=2, random_state=42
    )
    assert centroids.shape == (2, 3)
    assert set(np.unique(labels)) <= {0, 1}
    # The two halves must land in different clusters.
    assert labels[0, 0] != labels[-1, -1]


def test_sample_pixels_and_segmentation_quality():
    labels = np.tile(np.array([[0, 1], [1, 0]], dtype=int), (5, 5))
    idx, subset = sample_pixels_for_silhouette(labels, sample_size=10, random_state=0)
    assert len(idx) == len(subset)

    X = np.random.rand(labels.size, 3).astype(float)
    score = segmentation_quality(X, labels, sample_size=50, random_state=0)
    assert isinstance(score, float)
    assert -1.0 <= score <= 1.0


# --------------------------------------------------------------------------
# Distance matrix / distinctiveness
# --------------------------------------------------------------------------


def test_compute_distinctiveness_shape():
    centroids = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    d = _compute_distinctiveness(centroids)
    assert d.shape == (3,)
    assert np.all(np.isfinite(d))


def test_build_distance_matrix_is_euclidean():
    centroids = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    nodes = [0, 1, 2]
    D = build_distance_matrix(centroids, nodes)
    assert D.shape == (3, 3)
    assert np.isclose(D[0, 1], 1.0)
    assert np.isclose(D[1, 2], np.sqrt(2))
    assert np.allclose(np.diag(D), 0.0)
    assert np.allclose(D, D.T)


# --------------------------------------------------------------------------
# Christofides TSP pieces
# --------------------------------------------------------------------------


def test_christofides_cycle_visits_every_node_and_closes():
    labs = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=float)
    nodes = [0, 1, 2, 3]
    D = build_distance_matrix(labs, nodes)
    G = matrix_to_graph(D, nodes)
    cycle = christofides_tsp(G)
    assert cycle[0] == cycle[-1]
    assert set(cycle[:-1]) == set(nodes)


def test_christofides_component_pipeline_runs():
    labs = np.array([[0, 0], [1, 0], [0, 1], [1, 1]], dtype=float)
    nodes = [0, 1, 2, 3]
    D = build_distance_matrix(labs, nodes)
    G = matrix_to_graph(D, nodes)
    MST = minimum_spanning_tree(G)
    odd = find_odd_vertexes(MST)
    minimum_weight_matching(MST, G, odd)
    tour = find_eulerian_tour(MST, G)
    assert len(tour) >= 4
    path = christofides_tsp(G)
    assert len(path) >= 4


# --------------------------------------------------------------------------
# Ordering metric + path ordering
# --------------------------------------------------------------------------


def test_ordering_metric_prefers_straight_path():
    labs = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float)
    straight = compute_ordering_metric([0, 1, 2], labs)
    zigzag = compute_ordering_metric([0, 2, 1], labs)
    assert straight < zigzag
    assert straight == pytest.approx(2.0)


def test_tsp_order_christofides_path_pins_bg_and_fg():
    labs = np.array([[0, 0, 0], [2, 0, 0], [1, 0, 0]], dtype=float)
    nodes = [0, 1, 2]
    ordering = tsp_order_christofides_path(nodes, labs, bg=0, fg=1)
    assert ordering[0] == 0 and ordering[-1] == 1
    assert set(ordering) == set(nodes)


def test_prune_ordering_keeps_min_length_and_endpoints():
    labs = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]], dtype=float)
    pruned = prune_ordering(
        [0, 1, 2, 3], labs, bg=0, fg=3, min_length=3, improvement_factor=0.1
    )
    assert len(pruned) >= 3
    assert pruned[0] == 0 and pruned[-1] == 3


# --------------------------------------------------------------------------
# Mapping + interpolation
# --------------------------------------------------------------------------


def test_create_mapping_spans_zero_to_one():
    labs = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float)
    mapping = create_mapping([0, 1, 2], labs, [0, 1, 2])
    assert set(mapping.keys()) == {0, 1, 2}
    assert mapping[0] == 0.0 and mapping[2] == 1.0
    assert 0.0 < mapping[1] < 1.0


def test_interpolate_arrays_shape_and_endpoints():
    pairs = [
        (0.0, np.array([1.0, 0.0, 0.0], dtype=np.float32)),
        (0.5, np.array([0.5, 0.5, 0.1], dtype=np.float32)),
        (1.0, np.array([0.0, 1.0, 0.0], dtype=np.float32)),
    ]
    out = interpolate_arrays(pairs, num_points=5)
    assert out.shape == (5, 3)
    assert np.allclose(out[0], pairs[0][1])
    assert np.allclose(out[-1], pairs[-1][1])
