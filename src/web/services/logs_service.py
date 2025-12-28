from __future__ import annotations

from typing import List, Optional


class LogsService:
    @staticmethod
    def tail(path: Optional[str], lines: int = 200) -> List[str]:
        if not path:
            return ["(log_path not configured)"]
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = f.readlines()
            return data[-max(1, lines) :]
        except FileNotFoundError:
            return [f"(log file not found: {path})"]
        except Exception as e:
            return [f"(failed to read log file: {e})"]


