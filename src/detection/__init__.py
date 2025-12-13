"""
Traffic Monitoring System - Detection Module

This module handles vehicle detection in video frames.
"""

from .vehicle import VehicleDetector
from .tracker import VehicleTracker

__all__ = ['VehicleDetector', 'VehicleTracker']
