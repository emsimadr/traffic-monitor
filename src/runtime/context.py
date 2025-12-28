from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class RuntimeContext:
    """Holds runtime state and service references; avoids global singletons."""

    config: dict
    db: Any
    cloud_sync: Any
    camera: Any
    detector: Any
    tracker: Any
    counter: Any
    web_state: Any
    video_writer: Any = None
    output_path: Optional[str] = None
    fourcc: Optional[int] = None

    # Observability
    system_stats: dict = field(default_factory=dict)

    # Frame cache for web preview
    latest_frame: Optional[np.ndarray] = None

    def update_frame(self, frame: np.ndarray, fps: float):
        self.latest_frame = frame
        self.system_stats["fps"] = fps
        from time import time
        self.system_stats["last_frame_ts"] = time()
        if hasattr(self.web_state, "set_frame"):
            self.web_state.set_frame(frame)
        if hasattr(self.web_state, "update_system_stats"):
            self.web_state.update_system_stats({"fps": fps, "last_frame_ts": self.system_stats["last_frame_ts"]})

    def get_system_stats_copy(self):
        return dict(self.system_stats)


