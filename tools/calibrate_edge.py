#!/usr/bin/env python3
"""
Interactive edge calibration tool:
- Live preview from the configured camera
- Toggle RGB/BGR swap to fix "wrong colors"
- Click two points to set the counting line
- Save results into config/config.yaml as minimal overrides

Usage:
  python3 tools/calibrate_edge.py --config config/config.yaml

Controls:
  - Left click: set P1 then P2 (counting line)
  - r: reset points
  - s: toggle camera.swap_rb
  - w: write config/config.yaml (overrides)
  - q / ESC: quit
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, Optional, Tuple

import cv2
import yaml

# Add project directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.camera.camera import create_camera, inject_rtsp_credentials  # noqa: E402


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_layered_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration with layering consistent with src/main.py:
    - config/default.yaml
    - config/config.yaml
    - explicit --config path (if different from config/config.yaml)
    """
    cfg_dir = os.path.dirname(config_path) or "config"
    base_path = os.path.join(cfg_dir, "default.yaml")
    local_overrides_path = os.path.join(cfg_dir, "config.yaml")

    base_cfg: Dict[str, Any] = {}
    if os.path.exists(base_path):
        with open(base_path, "r", encoding="utf-8") as f:
            base_cfg = yaml.safe_load(f) or {}

    local_cfg: Dict[str, Any] = {}
    if os.path.exists(local_overrides_path):
        with open(local_overrides_path, "r", encoding="utf-8") as f:
            local_cfg = yaml.safe_load(f) or {}

    merged = _deep_merge(base_cfg, local_cfg)

    if os.path.exists(config_path) and os.path.abspath(config_path) != os.path.abspath(local_overrides_path):
        with open(config_path, "r", encoding="utf-8") as f:
            explicit_cfg = yaml.safe_load(f) or {}
        merged = _deep_merge(merged, explicit_cfg)

    return merged


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def write_overrides_yaml(target_path: str, updates: Dict[str, Any]) -> None:
    """
    Merge updates into existing overrides file (config/config.yaml) and write back.
    We intentionally keep it minimal (overrides only).
    """
    existing: Dict[str, Any] = {}
    if os.path.exists(target_path):
        with open(target_path, "r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}

    merged = _deep_merge(existing, updates)
    _ensure_parent_dir(target_path)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write("# Auto-generated overrides by tools/calibrate_edge.py\n")
        f.write("# Keep only values that differ from config/default.yaml.\n")
        yaml.safe_dump(merged, f, sort_keys=False)


def _ratios_from_pixels(p: Tuple[int, int], w: int, h: int) -> Tuple[float, float]:
    x, y = p
    xr = 0.0 if w <= 0 else max(0.0, min(1.0, x / float(w)))
    yr = 0.0 if h <= 0 else max(0.0, min(1.0, y / float(h)))
    return (round(xr, 6), round(yr, 6))


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive camera + counting-line calibration")
    parser.add_argument("--config", type=str, default="config/config.yaml", help="Config path (layered)")
    parser.add_argument("--output", type=str, default="config/config.yaml", help="Overrides file to write")
    args = parser.parse_args()

    cfg = load_layered_config(args.config)
    cam_cfg = cfg.get("camera", {}) or {}
    det_cfg = cfg.get("detection", {}) or {}

    # Ensure RTSP creds can be injected for preview
    try:
        inject_rtsp_credentials(cam_cfg)
    except Exception:
        pass

    # Current values
    swap_rb = bool(cam_cfg.get("swap_rb", False))

    p1: Optional[Tuple[int, int]] = None
    p2: Optional[Tuple[int, int]] = None

    # If a counting line already exists in config, we can visualize it after first frame is known.
    existing_line = det_cfg.get("counting_line")

    win = "Traffic Monitor - Calibrate (q=quit, w=write, s=swap_rb, r=reset)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    click_state = {"p1": None, "p2": None}

    def on_mouse(event, x, y, flags, param):
        nonlocal p1, p2
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if p1 is None:
            p1 = (int(x), int(y))
        else:
            p2 = (int(x), int(y))

    cv2.setMouseCallback(win, on_mouse)

    camera = create_camera(cam_cfg)
    try:
        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                key = cv2.waitKey(50) & 0xFF
                if key in (27, ord("q")):
                    break
                continue

            # Apply preview swap (does NOT change runtime unless you write the config)
            preview = frame
            if swap_rb:
                preview = preview[..., ::-1].copy()

            h, w = preview.shape[:2]

            # Draw existing config line (if present and no new points set)
            if p1 is None and p2 is None and isinstance(existing_line, list) and len(existing_line) == 2:
                try:
                    (x1r, y1r), (x2r, y2r) = existing_line
                    ex1 = (int(float(x1r) * w), int(float(y1r) * h))
                    ex2 = (int(float(x2r) * w), int(float(y2r) * h))
                    cv2.line(preview, ex1, ex2, (0, 255, 255), 2)
                    cv2.putText(preview, "Existing counting_line", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                except Exception:
                    pass

            # Draw selected points/line
            if p1 is not None:
                cv2.circle(preview, p1, 6, (0, 255, 0), -1)
                cv2.putText(preview, f"P1 {p1}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            if p2 is not None:
                cv2.circle(preview, p2, 6, (0, 255, 0), -1)
                cv2.line(preview, p1, p2, (0, 255, 0), 2)
                cv2.putText(preview, f"P2 {p2}", (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.putText(
                preview,
                f"swap_rb={'ON' if swap_rb else 'OFF'}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )
            cv2.putText(
                preview,
                "Click 2 points for counting line | s=toggle colors | w=write config",
                (10, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

            cv2.imshow(win, preview)
            key = cv2.waitKey(1) & 0xFF

            if key in (27, ord("q")):
                break
            if key == ord("s"):
                swap_rb = not swap_rb
            if key == ord("r"):
                p1, p2 = None, None
            if key == ord("w"):
                updates: Dict[str, Any] = {"camera": {"swap_rb": bool(swap_rb)}}
                if p1 is not None and p2 is not None:
                    p1r = _ratios_from_pixels(p1, w, h)
                    p2r = _ratios_from_pixels(p2, w, h)
                    updates["detection"] = {"counting_line": [list(p1r), list(p2r)]}

                write_overrides_yaml(args.output, updates)
                print(f"Wrote overrides to {args.output}")
                if "detection" in updates:
                    existing_line = updates["detection"]["counting_line"]

    finally:
        camera.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


