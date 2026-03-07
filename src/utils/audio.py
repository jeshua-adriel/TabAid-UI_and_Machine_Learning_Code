import subprocess


class SystemMixer:
    """
    Auto-detects and controls the system ALSA mixer.
    """

    PREFERRED_CONTROLS = [
        "Master",
        "PCM",
        "Speaker",
        "Headphone"
    ]

    def __init__(self):
        self.control = self._detect_control()

    def _run(self, command: list[str]) -> str:
        try:
            return subprocess.check_output(command, stderr=subprocess.DEVNULL).decode()
        except Exception:
            return ""

    def _detect_control(self) -> str | None:
        output = self._run(["amixer", "scontrols"])
        if not output:
            return None

        available = [
            line.split("'")[1]
            for line in output.splitlines()
            if "Simple mixer control" in line
        ]

        for preferred in self.PREFERRED_CONTROLS:
            if preferred in available:
                return preferred

        return available[0] if available else None

    def is_available(self) -> bool:
        return self.control is not None

    def set_volume(self, percent: int):
        if not self.control:
            return
        percent = max(0, min(100, percent))
        self._run(["amixer", "set", self.control, f"{percent}%"])

    def mute(self):
        if not self.control:
            return
        self._run(["amixer", "set", self.control, "mute"])

    def unmute(self):
        if not self.control:
            return
        self._run(["amixer", "set", self.control, "unmute"])

    def get_volume(self) -> int:
        if not self.control:
            return 50

        output = self._run(["amixer", "get", self.control])
        for token in output.split():
            if token.endswith("%]"):
                return int(token.strip("[]%"))
        return 50
