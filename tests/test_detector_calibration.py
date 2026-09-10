"""
The detector's count accuracy — what was measured, and that it still applies.

The calibration measurement (scripts/calibrate_yolo.py) found that the served
detector finds 91% of vehicles by count, and that a fitted correction factor
made held-out counts slightly worse. So none is applied, and the Lab tells a
visitor the measured figures instead of "recall is 0.36, so counts undercount".

These tests hold that together. A measurement describes one detector at one
set of settings; change the weights, the confidence or the image size and it
describes a different one. The failure worth catching is a quiet one — the
settings move and the Lab keeps quoting figures that no longer apply.
"""

from __future__ import annotations

import json
import pathlib
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
MEASUREMENT = ROOT / "results" / "yolo" / "calibration.json"
WEIGHTS = ROOT / "results" / "yolo" / "dats_v8n" / "weights" / "best.pt"

pytestmark = pytest.mark.skipif(
    not (MEASUREMENT.exists() and WEIGHTS.exists()),
    reason="detector weights or calibration measurement not present",
)


@pytest.fixture(scope="module")
def measurement() -> dict:
    return json.loads(MEASUREMENT.read_text())


@pytest.fixture(scope="module")
def analyser():
    from app.services.vision_service import _load

    return _load()


def test_the_measurement_describes_the_detector_being_served(measurement, analyser):
    """
    Weights, confidence and image size must match what was measured.

    If this fails, the settings changed after the measurement was taken. Re-run
    scripts/calibrate_yolo.py — do not edit the JSON to match.
    """
    measured = measurement["detector"]
    served = {"weights": analyser.weights_path.name,
              "conf": analyser.conf, "imgsz": analyser.imgsz}
    for key, value in served.items():
        assert measured[key] == value, (
            f"measured at {key}={measured[key]!r}, served at {value!r} — "
            "re-run scripts/calibrate_yolo.py"
        )


def test_the_served_correction_is_the_one_the_measurement_supports(measurement, analyser):
    """
    No factor is applied because none helped on held-out images.

    The tempting correction is 1 / recall = 2.78. Measured, it overcounted by
    about two and a half times. A retrained detector may genuinely benefit
    from a factor — in which case this fails, and the fix is to apply the one
    the new measurement recommends, not to delete this test.
    """
    err = measurement["heldOutError"]
    best = measurement["bestOnHeldOut"]

    assert best == min(err, key=lambda name: err[name]["pcu_mae"])
    if best == "raw":
        assert analyser.calibration == 1.0, (
            "a correction is being applied that the measurement did not support"
        )

    # The finding the whole design rests on, kept visible.
    assert err["divide_by_recall"]["vehicles_mae"] > err["raw"]["vehicles_mae"]


def test_every_vehicle_class_was_measured(measurement):
    """A class absent from the measurement would be served with no evidence at all."""
    from vision.detector import VEHICLE_PCU

    assert set(measurement["perClass"]) == set(VEHICLE_PCU)
    assert measurement["appliesTo"] == "occupancy", (
        "only stills were measured — flow must not be claimed as calibrated"
    )


def test_the_lab_is_told_the_measured_figures(measurement):
    """The visitor-facing note must quote the measurement, including its gaps."""
    from app.services.vision_service import VisionService

    info = VisionService().detector_info()
    acc = info["countAccuracy"]

    assert acc["measured"] and not acc["stale"]
    assert acc["images"] == measurement["images"]
    assert "0.36" not in info["note"], "the misleading recall figure is back"

    blind = sorted(n for n, c in measurement["perClass"].items()
                   if c["groundTruth"] and not c["detected"])
    for name in blind:
        assert name in info["note"], f"{name} is never detected and the note hides it"

    # Occupancy only — the note must not let flow pass as calibrated.
    assert "flow" in info["note"]


def test_a_measurement_for_other_settings_is_reported_as_stale():
    """
    Figures measured at one confidence must not be quoted at another.

    Simulated with a detector whose confidence differs from the measured one,
    since actually re-serving at another threshold would change every test in
    the suite.
    """
    from app.services.vision_service import _count_accuracy

    other = SimpleNamespace(weights_path=pathlib.Path("best.pt"), conf=0.5, imgsz=416)
    acc = _count_accuracy(other)

    assert acc["stale"] is True
    assert "91%" not in acc["summary"], "stale figures were quoted anyway"
