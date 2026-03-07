# src/main.py
import os
from kivy.config import Config

# --------------------------------------------------
# IMPORTANT:
# Do NOT import anything that imports Kivy modules
# before all Config.set(...) calls below.
# --------------------------------------------------

# Pi-like sizing on windows
if os.name == "nt":
    # Make dp()/sp() behave closer to Raspberry Pi
    os.environ["KIVY_METRICS_DENSITY"] = "0.5"
    os.environ["KIVY_DPI"] = "96"

# Touch stability (good on Pi touchscreen)
Config.set("input", "mouse", "mouse,disable_multitouch")
Config.set("input", "mtdev", "")

# Use system keyboard (no Kivy virtual keyboard)
Config.set("kivy", "keyboard_mode", "system")

# Now safe to import platform config (must NOT import kivy inside!)
from utils.platform_config import get_config

CFG = get_config()

# -----------------------------
# Window / graphics (cross-platform)
# -----------------------------
if CFG.IS_RASPI:
    Config.set("graphics", "fullscreen", "1" if CFG.FULLSCREEN_ON_PI else "0")
    Config.set("graphics", "borderless", "1" if CFG.BORDERLESS_ON_PI else "0")
else:
    Config.set("graphics", "fullscreen", "0")
    Config.set("graphics", "borderless", "0")

    if CFG.FORCE_WINDOW_SIZE_ON_WINDOWS:
        Config.set("graphics", "width", str(CFG.TARGET_W))
        Config.set("graphics", "height", str(CFG.TARGET_H))
        Config.set("graphics", "resizable", "0")

# --------------------------------------------------
# Now it's safe to import Kivy modules
# --------------------------------------------------
from kivy.app import App
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, FadeTransition

from utils.audio import SystemMixer
from utils.database import init_db
from utils.sound import SoundManager

from screens.start import StartScreen
from screens.login import LoginScreen
from screens.menu import MenuScreen
from screens.settings import SettingsScreen
from screens.game1 import Game1Screen
from screens.game2 import Game2Screen
from screens.game3 import Game3Screen

from ml.grader import SiameseGrader


class TabAidApp(App):
    title = "Tab-Aid"

    current_user_id = None
    current_user_name = None

    def build(self):
        # Apply runtime Window flags too (Config already set; this is a safety net)
        if CFG.IS_RASPI:
            Window.borderless = bool(CFG.BORDERLESS_ON_PI)
            Window.fullscreen = bool(CFG.FULLSCREEN_ON_PI)
        else:
            Window.fullscreen = False
            Window.borderless = False

            if CFG.FORCE_WINDOW_SIZE_ON_WINDOWS:
                try:
                    Window.size = (int(CFG.TARGET_W), int(CFG.TARGET_H))
                except Exception:
                    pass

        # Initialize DB
        init_db()

        # Load KV
        kv_path = str(CFG.PATHS.SRC_DIR / "main.kv")
        Builder.load_file(kv_path)

        # --------------------------------------------------
        # System mixer (device/system volume)
        # --------------------------------------------------
        self.mixer = SystemMixer()
        if not self.mixer.is_available():
            print("WARNING: No ALSA mixer detected (this is normal on Windows)")

        # --------------------------------------------------
        # In-app sounds
        # --------------------------------------------------
        self.sound = SoundManager()

        audio_dir = CFG.PATHS.ASSETS_DIR / "audio"
        self.bgm_dir = audio_dir / "bgm"
        sfx_dir = audio_dir / "sfx"
        voice_dir = audio_dir / "voice"

        # remember current bgm so we do NOT restart unnecessarily
        self.current_bgm_key = None

        # --- Sound Effects ---
        self.sound.load_sound("click", str(sfx_dir / "click.ogg"))
        self.sound.load_sound("success", str(sfx_dir / "success.ogg"))
        self.sound.load_sound("error", str(sfx_dir / "error.ogg"))

        # --- Placeholder voice clips (optional now) ---
        self.sound.load_sound("welcome", str(voice_dir / "welcome.ogg"))
        self.sound.load_sound("game1_instruction", str(voice_dir / "game1_instruction.ogg"))
        self.sound.load_sound("game2_instruction", str(voice_dir / "game2_instruction.ogg"))
        self.sound.load_sound("game2_connect_instruction", str(voice_dir / "game2_connect_instruction.ogg"))
        self.sound.load_sound("game3_instruction", str(voice_dir / "game3_instruction.ogg"))
        self.sound.load_sound("game3_tree_instruction", str(voice_dir / "game3_tree_instruction.ogg"))
        self.sound.load_sound("great_job", str(voice_dir / "great_job_1.ogg"))
        self.sound.load_sound("try_again", str(voice_dir / "oops_try_again_1.ogg"))
        self.sound.load_sound("game_complete", str(voice_dir / "game_complete_1.ogg"))

        # --------------------------------------------------
        # ML grader (load once)
        # --------------------------------------------------
        model_path = str(CFG.PATHS.ML_DIR / "outputs" / "checkpoints" / "siamese.pth")
        self.game2_grader = SiameseGrader(model_path=model_path)
        self.game3_grader = self.game2_grader

        # --------------------------------------------------
        # Screens
        # --------------------------------------------------
        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(StartScreen(name="start"))
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(MenuScreen(name="menu"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(Game1Screen(name="game1"))
        sm.add_widget(Game2Screen(name="game2"))
        sm.add_widget(Game3Screen(name="game3"))

        # Watch screen changes for BGM switching
        sm.bind(current=self._on_screen_changed)

        # Initial screen
        sm.current = "start"

        # initial bgm
        self._switch_bgm_for_screen("start")

        return sm

    # --------------------------------------------------
    # BGM switching
    # --------------------------------------------------
    def _on_screen_changed(self, instance, screen_name):
        self._switch_bgm_for_screen(screen_name)

    def _switch_bgm_for_screen(self, screen_name: str):
        """
        Continuous looping music behavior:
        - start/login/menu/settings -> menu_bgm.ogg
        - game1/game2/game3 -> game_bgm.ogg

        IMPORTANT:
        If already in the same bgm group, do nothing.
        So Game1 -> Game2 -> Game3 keeps playing continuously.
        """
        if screen_name in ("game1", "game2", "game3"):
            target_key = "game"
            target_file = self.bgm_dir / "game_bgm.ogg"
        else:
            target_key = "menu"
            target_file = self.bgm_dir / "menu_bgm.ogg"

        # do NOT restart if same music group
        if self.current_bgm_key == target_key:
            return

        self.current_bgm_key = target_key
        self.sound.load_bgm(str(target_file), volume=self.sound.bgm_volume)
        self.sound.play_bgm()

    # --------------------------------------------------
    # Convenience helpers for screens
    # --------------------------------------------------
    def play_click(self):
        if hasattr(self, "sound"):
            self.sound.play("click")

    def play_success(self):
        if hasattr(self, "sound"):
            self.sound.play("success")

    def play_error(self):
        if hasattr(self, "sound"):
            self.sound.play("error")

    def play_voice(self, key: str):
        if hasattr(self, "sound"):
            self.sound.play(key)

    def set_music_volume_percent(self, percent: int):
        percent = max(0, min(100, int(percent)))
        volume = percent / 100.0

        if hasattr(self, "sound"):
            self.sound.set_bgm_volume(volume)
            self.sound.set_sfx_volume(volume)

        if hasattr(self, "mixer") and self.mixer.is_available():
            self.mixer.set_volume(percent)

    def mute_all(self):
        if hasattr(self, "sound"):
            self.sound.enable_bgm(False)
            self.sound.enable_sfx(False)
        if hasattr(self, "mixer") and self.mixer.is_available():
            self.mixer.mute()

    def unmute_all(self):
        if hasattr(self, "sound"):
            self.sound.enable_bgm(True)
            self.sound.enable_sfx(True)
            self.sound.play_bgm()
        if hasattr(self, "mixer") and self.mixer.is_available():
            self.mixer.unmute()


if __name__ == "__main__":
    TabAidApp().run()