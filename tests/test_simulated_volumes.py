"""
The simulator's quoted daily volumes must be the measured ones.

traffic/simulator.py used to quote 12-hour volumes that were stale and that
nothing in the repository could reproduce. They are now produced by
scripts/measure_simulated_volumes.py into results/traffic/simulated_volumes.json.

The failure worth catching is drift: the script is re-run after the simulator
changes, the JSON moves, and the docstring and DATA.md go on quoting the old
figures — or someone edits a number by hand. These tests do not re-run the
measurement (it loads the full graph); they check that what is written down
matches what was last measured.
"""

from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
MEASUREMENT = ROOT / "results" / "traffic" / "simulated_volumes.json"

pytestmark = pytest.mark.skipif(not MEASUREMENT.exists(),
                                reason="volume measurement not present")


@pytest.fixture(scope="module")
def measured() -> dict:
    return json.loads(MEASUREMENT.read_text())


def test_the_simulator_quotes_the_measured_volumes(measured):
    import traffic.simulator as sim

    doc = sim.__doc__
    assert "STALE" not in doc, "the stale-figures warning is back"
    for cls in ("motorway", "trunk", "primary", "secondary"):
        row = measured["perRoadPcu12h"][cls]
        for key in ("median", "p5", "p95"):
            assert f"{row[key]:,}" in doc, (
                f"{cls} {key} {row[key]:,} is not what the docstring quotes — "
                "re-run the script and update the table together"
            )
        share = f"{row['shareOfCapacityOver12h']:.0%}"
        assert share in doc, f"{cls} capacity share {share} missing from the docstring"


def test_junction_comparison_is_quoted_as_measured(measured):
    """The HMDA comparison appears in two places; both must match the file."""
    import traffic.simulator as sim

    data_md = (ROOT / "DATA.md").read_text(encoding="utf-8")
    for arms in ("3-arm", "4-arm"):
        j = measured["perJunctionInflowPcu12h"][arms]
        median = f"{j['median']:,}"
        inside = f"{j['shareInsideHmdaRange']:.0%}"
        above = f"{j['shareAboveHmdaMax']:.0%}"
        for where, text in (("simulator docstring", sim.__doc__), ("DATA.md", data_md)):
            assert median in text, f"{arms} median {median} missing from {where}"
            assert inside in text, f"{arms} share inside {inside} missing from {where}"
            assert above in text, f"{arms} share above {above} missing from {where}"


def test_nothing_claims_the_simulator_is_calibrated_to_hmda():
    """It is compared with HMDA, not fitted to it. The claim must not return."""
    data_md = (ROOT / "DATA.md").read_text(encoding="utf-8")
    offending = "synthetic peak-hour volumes\nare calibrated to HMDA"
    # Quoted in DATA.md only as the sentence NOT to use.
    assert data_md.count("calibrated to HMDA CTS observed PCU ranges") <= 1
    assert offending not in data_md
