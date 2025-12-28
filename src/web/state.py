import threading
import time
import cv2
import numpy as np

class SharedState:
    """
    Singleton class to share state between the main processing loop 
    and the Flask web server.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SharedState, cls).__new__(cls)
                    cls._instance.frame = None
                    cls._instance.frame_lock = threading.Lock()
                    cls._instance.database = None
                    cls._instance.config = None
                    cls._instance.config_lock = threading.Lock()
                    cls._instance.config_path = None
                    cls._instance.system_stats = {
                        "fps": 0,
                        "cpu_usage": 0,
                        "memory_usage": 0,
                        "start_time": 0,
                        "last_frame_ts": None,
                    }
        return cls._instance
    
    def set_frame(self, frame):
        """Update the current video frame."""
        with self.frame_lock:
            if frame is not None:
                # Encode frame to JPEG for streaming to save bandwidth/processing later
                # For now, just store the raw frame or a copy
                self.frame = frame.copy()
                # Track when the last frame arrived for health/status endpoints.
                self.system_stats["last_frame_ts"] = time.time()
    
    def get_frame(self):
        """Get the current video frame."""
        with self.frame_lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def set_database(self, db):
        self.database = db
        
    def set_config(self, config, config_path):
        with self.config_lock:
            self.config = config
            self.config_path = config_path

    def get_config_copy(self):
        with self.config_lock:
            if self.config is None:
                return None
            # shallow copy of dict tree is fine for read-mostly usage
            return dict(self.config)

    def update_config(self, new_config):
        with self.config_lock:
            self.config = new_config

    def update_system_stats(self, stats):
        self.system_stats.update(stats)

    def get_system_stats_copy(self):
        """Return a shallow copy of current system stats."""
        return dict(self.system_stats)

# Global instance
state = SharedState()

