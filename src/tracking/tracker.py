"""
Tracking adapter.

For now this re-exports the existing VehicleTracker implementation while the
project migrates to the new structure.
"""

from __future__ import annotations

from detection.tracker import VehicleTracker, TrackedVehicle

__all__ = ["VehicleTracker", "TrackedVehicle"]


