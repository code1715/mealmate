"""Unit tests for the Haversine distance formula."""

from app.utils.haversine import haversine


def test_haversine_same_point_is_zero():
    assert haversine(50.0, 30.0, 50.0, 30.0) == 0.0


def test_haversine_one_degree_latitude_is_approx_111km():
    d = haversine(50.0, 30.0, 51.0, 30.0)
    assert 110.0 < d < 112.0


def test_haversine_symmetry():
    d1 = haversine(50.0, 30.0, 50.5, 30.5)
    d2 = haversine(50.5, 30.5, 50.0, 30.0)
    assert abs(d1 - d2) < 0.001


def test_haversine_small_distance_kyiv_couriers():
    # Burger Palace (50.462, 30.519) to Ivan Petrenko (50.464, 30.520) — ~0.25 km
    d = haversine(50.462, 30.519, 50.464, 30.520)
    assert 0.1 < d < 0.5
