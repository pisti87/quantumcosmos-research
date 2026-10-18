#!/usr/bin/env python3
"""
QuantumCosmos Research Framework
Python 3.10+; dependency: numpy

A deliberately conservative research prototype:
- separates observations from hypotheses and simulations;
- performs basic FFT-based radio-signal analysis;
- stores photon events and quantum-state data;
- provides a simple idealized BB84 protocol simulation;
- estimates the Drake equation's product;
- defines an adapter boundary for future quantum hardware.

This is NOT a dark-matter detector, an alien-signal detector, or a validated
physical model. Demo data are synthetic and are labeled as such.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np



# ------------------------------ Evidence and provenance -----------------------

class EvidenceKind(str, Enum):
    OBSERVATION = "observation"
    SIMULATION = "simulation"
    HYPOTHESIS = "hypothesis"


class ConfidenceLabel(str, Enum):
    ESTABLISHED_METHOD = "established_method"
    MEASURED = "measured"
    MODEL_DEPENDENT = "model_dependent"
    SPECULATIVE = "speculative"


@dataclass
class Provenance:
    kind: EvidenceKind
    source: str
    method: str
    collected_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: str = ""
 

@dataclass
class Measurement:
    value: float
    unit: str
    uncertainty: Optional[float] = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("Measurement value must be finite.")
        if self.uncertainty is not None:
            if not math.isfinite(self.uncertainty) or self.uncertainty < 0:
                raise ValueError("Uncertainty must be finite and non-negative.")


# ------------------------------ Radio astronomy ------------------------------

@dataclass
class RadioSignal:
    sample_rate_hz: float
    samples: list[float]
    provenance: Provenance
    center_frequency_hz: Optional[float] = None
    observation_id: str = "unnamed"   
    
    def __post_init__(self) -> None:
        if not math.isfinite(self.sample_rate_hz) or self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive and finite.")
        if len(self.samples) < 8:
            raise ValueError("At least 8 samples are required.")
        if not all(math.isfinite(float(x)) for x in self.samples):
            raise ValueError("Signal samples must be finite.")
        if self.center_frequency_hz is not None and self.center_frequency_hz < 0:
            raise ValueError("center_frequency_hz cannot be negative.")


@dataclass
class SpectralPeak:
    frequency_hz: float
    relative_amplitude: float


@dataclass
class RadioAnalysis:
    observation_id: str
    sample_count: int
    duration_s: float
    rms_amplitude: float
    dominant_peaks: list[SpectralPeak]
    provenance_kind: str
    caveats: list[str] = field(default_factory=list)



class RadioAnalyzer:
    """Basic real-valued FFT analysis; not a calibrated observatory pipeline."""

    @staticmethod
    def analyze(signal: RadioSignal, peak_count: int = 5) -> RadioAnalysis:
        if peak_count < 1:
            raise ValueError("peak_count must be >= 1")

        x = np.asarray(signal.samples, dtype=float)
        x = x - np.mean(x)
        rms = float(np.sqrt(np.mean(x * x)))
        windowed = x * np.hanning(len(x))
        spectrum = np.abs(np.fft.rfft(windowed))
        frequencies = np.fft.rfftfreq(
            len(x), d=1.0 / signal.sample_rate_hz
        )

        if len(spectrum):
            spectrum[0] = 0.0  # exclude residual DC component

        usable = np.arange(1, len(spectrum))

        if usable.size:
            order = usable[
                np.argsort(spectrum[usable])[::-1][:peak_count]
            ]
            maximum = (
                float(np.max(spectrum[order])) if order.size else 0.0
            )
            peaks = [
                SpectralPeak(
                    frequency_hz=float(frequencies[i]),
                    relative_amplitude=(
                        float(spectrum[i] / maximum)
                        if maximum > 0
                        else 0.0
                    ),
                )
                for i in order
            ]
        else:
            peaks = []

        caveats = [
            "FFT peaks are candidate spectral features, not evidence of an artificial source.",
            "Calibration, interference rejection, telescope metadata, and independent confirmation are not implemented.",
        ]

        if signal.provenance.kind != EvidenceKind.OBSERVATION:
            caveats.append(
                "This input is not labeled as a real observation."
            )

        return RadioAnalysis(
            observation_id=signal.observation_id,
            sample_count=len(x),
            duration_s=len(x) / signal.sample_rate_hz,
            rms_amplitude=rms,
            dominant_peaks=peaks,
            provenance_kind=signal.provenance.kind.value,
            caveats=caveats,
        )


# ------------------------------ Photon events --------------------------------

@dataclass
class PhotonEvent:
    arrival_time_s: float
    wavelength_m: Optional[float]
    detector_id: str
    polarization: Optional[str]
    provenance: Provenance
    detection_probability: Optional[float] = None

    def __post_init__(self) -> None:
        if self.arrival_time_s < 0 or not math.isfinite(self.arrival_time_s):
            raise ValueError("arrival_time_s must be finite and non-negative.")
        if self.wavelength_m is not None and (
            not math.isfinite(self.wavelength_m) or self.wavelength_m <= 0
        ):
            raise ValueError("wavelength_m must be positive and finite.")
        if self.detection_probability is not None and not (
            0 <= self.detection_probability <= 1
        ):
            raise ValueError("detection_probability must be between 0 and 1.")


# ------------------------------ Quantum data ---------------------------------

@dataclass
class QuantumState:
    """Pure state vector in computational basis; amplitudes are complex."""

    amplitudes: list[complex]
    qubit_count: int
    label: str = "unspecified"

    def __post_init__(self) -> None:
        if self.qubit_count < 1:
            raise ValueError("qubit_count must be >= 1.")
        if len(self.amplitudes) != 2 ** self.qubit_count:
            raise ValueError("State-vector length must equal 2**qubit_count.")
        vector = np.asarray(self.amplitudes, dtype=complex)
        if not np.all(np.isfinite(vector.real)) or not np.all(np.isfinite(vector.imag)):
            raise ValueError("Amplitudes must be finite.")
        norm = float(np.vdot(vector, vector).real)
        if not math.isclose(norm, 1.0, rel_tol=1e-8, abs_tol=1e-8):
            raise ValueError(f"State must be normalized; squared norm is {norm}.")


@dataclass
class QuantumChannel:
    distance_m: float
    transmission_efficiency: float
    error_rate: float
    protocol: str = "BB84"
    provenance: Provenance = field(
        default_factory=lambda: Provenance(
            kind=EvidenceKind.SIMULATION,
            source="unspecified",
            method="idealized channel model",
        )
    )

    def __post_init__(self) -> None:
        if not math.isfinite(self.distance_m) or self.distance_m < 0:
            raise ValueError("distance_m must be finite and non-negative.")
        if not 0 <= self.transmission_efficiency <= 1:
            raise ValueError("transmission_efficiency must be between 0 and 1.")
        if not 0 <= self.error_rate <= 1:
            raise ValueError("error_rate must be between 0 and 1.")


@dataclass
class BB84Result:
    transmitted_bits: int
    sifted_bits: int
    estimated_qber: Optional[float]
    detected_fraction: float
    note: str


def simulate_bb84(
    bit_count: int = 1000,
    channel: Optional[QuantumChannel] = None,
    seed: int = 7,
) -> BB84Result:
    """
    Idealized BB84 key-distribution toy model.
    
    It models random bit/basis choices, probabilistic photon detection, and
    independent bit flips. It does not simulate optical hardware, photon
    number splitting, detector side channels, authentication, or a full
    security proof. Do not use for real cryptographic key generation.
    """
    if bit_count < 1:
        raise ValueError("bit_count must be >= 1.")
    channel = channel or QuantumChannel(
        distance_m=0.0,
        transmission_efficiency=1.0,
        error_rate=0.0,
    )
    rng = np.random.default_rng(seed)

    alice_bits = rng.integers(0, 2, size=bit_count)
    alice_bases = rng.integers(0, 2, size=bit_count)
    bob_bases = rng.integers(0, 2, size=bit_count)
    detected = rng.random(bit_count) < channel.transmission_efficiency
    matching = alice_bases == bob_bases
    keep = detected & matching
    kept_indices = np.flatnonzero(keep)

    bob_bits = alice_bits[kept_indices].copy()
    flips = rng.random(len(kept_indices)) < channel.error_rate
    bob_bits[flips] ^= 1
    alice_kept = alice_bits[kept_indices]
    qber = (
        float(np.mean(alice_kept != bob_bits))
              if len(kept_indices) else None
    )
    return BB84Result(
        transmitted_bits=bit_count,
        sifted_bits=int(len(kept_indices)),
        estimated_qber=qber,
        detected_fraction=float(np.mean(detected)),
        note=(
            "Educational simulation only; not a secure implementation or a "
            "claim of physical quantum communication."
        ),
    )


class QuantumHardwareAdapter(ABC):
    """Future integration point for vendor-specific quantum/photon hardware."""

    @abstractmethod
    def device_info(self) -> dict[str, Any]:
        """Return device metadata and calibration status."""
        raise NotImplementedError

    @abstractmethod
    def acquire(self, request: dict[str, Any]) -> dict[str, Any]:
        """Acquire data using a documented hardware API."""
        raise NotImplementedError  
 

# ------------------------------ Dark matter ----------------------------------

@dataclass
class DarkMatterModel:
    name: str
    description: str
    assumptions: list[str]
    confidence: ConfidenceLabel = ConfidenceLabel.SPECULATIVE
    evidence_refs: list[str] = field(default_factory=list)
    predicted_observables: list[str] = field(default_factory=list)

    def as_hypothesis_record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "assumptions": self.assumptions,
            "confidence": self.confidence.value,
            "evidence_refs": self.evidence_refs,
            "predicted_observables": self.predicted_observables,
            "warning": (
                "A model record is not a detection. Compare predictions with "
                "calibrated observations and competing explanations."
            ),
        }


# ------------------------------ Drake equation -------------------------------

@dataclass
class DrakeParameters:
    # R_star: stars formed per year; L: years; other terms are dimensionless.
    star_formation_rate_per_year: float
    fraction_with_planets: float
    habitable_planets_per_system: float
    life_probability: float
    intelligence_probability: float
    detectable_technology_probability: float
    detectable_lifetime_years: float

    def __post_init__(self) -> None:
        nonnegative = (
            self.star_formation_rate_per_year,
            self.habitable_planets_per_system,
            self.detectable_lifetime_years,
        )
        if any(not math.isfinite(x) or x < 0 for x in nonnegative):
            raise ValueError("Rates, counts, and lifetimes must be finite and non-negative.")
        probabilities = (
            self.fraction_with_planets,
            self.life_probability,
            self.intelligence_probability,
            self.detectable_technology_probability,
        )
        if any(not math.isfinite(x) or not 0 <= x <= 1 for x in probabilities):
            raise ValueError("Probability factors must be between 0 and 1.")

    def estimate(self) -> float:
        return (
            self.star_formation_rate_per_year
            * self.fraction_with_planets
            * self.habitable_planets_per_system
            * self.life_probability
            * self.intelligence_probability
            * self.detectable_technology_probability
            * self.detectable_lifetime_years
        )


# ------------------------------ Reports and demo -----------------------------

def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, complex):
        return {"real": obj.real, "imag": obj.imag}
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def run_demo() -> dict[str, Any]:
    rng = np.random.default_rng(42)
    sample_rate = 1024.0
    duration_s = 2.0
    t = np.arange(int(sample_rate * duration_s)) / sample_rate
    samples = (
        0.8 * np.sin(2 * np.pi * 123.0 * t)
        + 0.25 * np.sin(2 * np.pi * 287.0 * t)
        + rng.normal(0, 0.15, size=len(t))
    )
    synthetic_signal = RadioSignal(
        sample_rate_hz=sample_rate,
        samples=samples.tolist(),
        observation_id="demo-synthetic-001",
        provenance=Provenance(
            kind=EvidenceKind.SIMULATION,    
             source="built-in demo generator",
            method="synthetic tones plus Gaussian noise",
            notes="Not collected from a telescope or radio receiver.",
        ),
    )
    radio_result = RadioAnalyzer.analyze(synthetic_signal)

    quantum_channel = QuantumChannel(
        distance_m=1000.0,
        transmission_efficiency=0.70,
        error_rate=0.02,
        protocol="BB84 toy model",
        provenance=Provenance(
            kind=EvidenceKind.SIMULATION,
            source="built-in demo",
            method="idealized random-channel simulation",
        ),
    )
    qkd_result = simulate_bb84(1000, quantum_channel, seed=11)

    # Arbitrary example values demonstrate the formula only; they are not
    # presented as agreed scientific estimates.
    drake = DrakeParameters(
        star_formation_rate_per_year=1.5,
        fraction_with_planets=0.8,
        habitable_planets_per_system=0.2,
        life_probability=0.1,
        intelligence_probability=0.01,
        detectable_technology_probability=0.2,
        detectable_lifetime_years=10000,
    )
    dark_matter = DarkMatterModel(       
          name="generic-gravitational-hypothesis",
        description=(
            "A placeholder model record for comparing a proposed dark-matter "
            "scenario with gravitational and astrophysical observations."
        ),
        assumptions=[
            "The model must specify quantitative predictions.",
            "Ordinary astrophysical sources and instrumental effects must be considered.",
        ],
        confidence=ConfidenceLabel.SPECULATIVE,
        predicted_observables=[
            "gravitational effects",
            "model-specific structure or lensing predictions",
        ],
    )

    return {
        "framework": "Cosmic Signal & Quantum Communication Research Framework",
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "evidence_policy": {
            "observation": "measured data with provenance and instrument metadata",
            "simulation": "generated data, never relabeled as observation",
            "hypothesis": "testable model, not a confirmed discovery",
        },
        "radio_analysis": to_jsonable(radio_result),
        "quantum_communication_simulation": to_jsonable(qkd_result),
        "drake_equation_demo": {
            "estimated_detectable_civilizations": drake.estimate(),
            "parameters": to_jsonable(drake),
            "warning": "Illustrative arbitrary inputs, not a scientific consensus estimate.",
        },      
         "dark_matter_hypothesis_record": dark_matter.as_hypothesis_record(),
        "limitations": [
            "No dark-matter detection algorithm is implemented.",
            "Radio FFT peaks are not automatically classified as artificial signals.",
            "The quantum protocol is a toy simulation, not secure QKD software.",
            "No real telescope, detector, or quantum device is connected.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the JSON demo report.",
    )
    args = parser.parse_args()

    report = run_demo()
    rendered = json.dumps(to_jsonable(report), indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Demo report written to: {args.output}")
    else:
        print(rendered)
    return 0       
   

if __name__ == "__main__":
    raise SystemExit(main())

     
