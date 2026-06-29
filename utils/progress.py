"""ProgressReporter — thread-safe bridge from the pipeline to a progress UI.

The pipeline calls start_step()/update_step()/done_step(); a consumer (the dashboard
WebSocket handler) polls snapshot() to render live progress.
"""
import threading


class ProgressReporter:
    def __init__(self):
        self.steps: list[dict] = []
        self.current_step: str | None = None
        self.current_detail: str | None = None
        self.finished = False
        self.error: str | None = None
        self.result: dict | None = None
        self._lock = threading.Lock()

    def start_step(self, name: str, detail: str = ""):
        with self._lock:
            self.current_step = name
            self.current_detail = detail

    def update_step(self, detail: str):
        with self._lock:
            self.current_detail = detail

    def done_step(self, name: str | None = None):
        with self._lock:
            done_name = name or self.current_step
            if done_name:
                self.steps.append({"name": done_name, "status": "done"})
            self.current_step = None
            self.current_detail = None

    def fail_step(self, name: str | None = None, error: str = ""):
        with self._lock:
            fail_name = name or self.current_step
            if fail_name:
                self.steps.append({"name": fail_name, "status": "fail", "error": error})
            self.current_step = None
            self.current_detail = None

    def finish(self, result: dict | None = None):
        with self._lock:
            self.finished = True
            self.result = result

    def set_error(self, msg: str):
        with self._lock:
            self.error = msg
            self.finished = True

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "steps_done": list(self.steps),
                "current_step": self.current_step,
                "current_detail": self.current_detail,
                "finished": self.finished,
                "error": self.error,
                "result": self.result,
            }
