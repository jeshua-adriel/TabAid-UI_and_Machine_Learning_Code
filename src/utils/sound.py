# src/utils/sound.py
from __future__ import annotations

import os
from typing import Dict, Optional

from kivy.core.audio import SoundLoader


class SoundManager:
    """
    Handles in-app audio playback:
    - one looping background music
    - multiple sound effects / voice clips
    """

    def __init__(self):
        self.bgm = None
        self.sounds: Dict[str, object] = {}

        self.bgm_enabled = True
        self.sfx_enabled = True

        self.bgm_volume = 0.25
        self.sfx_volume = 0.80

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _safe_load(self, path: str):
        if not path or not os.path.exists(path):
            print(f"WARNING: Audio file not found: {path}")
            return None

        snd = SoundLoader.load(path)
        if snd is None:
            print(f"WARNING: Could not load audio: {path}")
        return snd

    # --------------------------------------------------
    # Background music
    # --------------------------------------------------
    def load_bgm(self, path: str, volume: Optional[float] = None):
        self.stop_bgm()

        snd = self._safe_load(path)
        if snd is None:
            self.bgm = None
            return

        snd.loop = True
        snd.volume = self.bgm_volume if volume is None else float(volume)
        self.bgm = snd

    def play_bgm(self):
        if not self.bgm_enabled or self.bgm is None:
            return

        try:
            self.bgm.stop()
        except Exception:
            pass

        self.bgm.volume = self.bgm_volume
        self.bgm.play()

    def stop_bgm(self):
        if self.bgm is not None:
            try:
                self.bgm.stop()
            except Exception:
                pass

    def set_bgm_volume(self, volume: float):
        self.bgm_volume = max(0.0, min(1.0, float(volume)))
        if self.bgm is not None:
            self.bgm.volume = self.bgm_volume

    def enable_bgm(self, enabled: bool):
        self.bgm_enabled = bool(enabled)
        if not self.bgm_enabled:
            self.stop_bgm()

    # --------------------------------------------------
    # Sound effects / voice
    # --------------------------------------------------
    def load_sound(self, key: str, path: str):
        snd = self._safe_load(path)
        if snd is None:
            return
        snd.volume = self.sfx_volume
        self.sounds[key] = snd

    def play(self, key: str):
        if not self.sfx_enabled:
            return

        snd = self.sounds.get(key)
        if snd is None:
            print(f"WARNING: Sound key not loaded: {key}")
            return

        try:
            snd.stop()
        except Exception:
            pass

        snd.volume = self.sfx_volume
        snd.play()

    def stop(self, key: str):
        snd = self.sounds.get(key)
        if snd is not None:
            try:
                snd.stop()
            except Exception:
                pass

    def set_sfx_volume(self, volume: float):
        self.sfx_volume = max(0.0, min(1.0, float(volume)))
        for snd in self.sounds.values():
            try:
                snd.volume = self.sfx_volume
            except Exception:
                pass

    def enable_sfx(self, enabled: bool):
        self.sfx_enabled = bool(enabled)