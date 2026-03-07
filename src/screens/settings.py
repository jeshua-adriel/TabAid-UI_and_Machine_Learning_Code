# src/screens/settings.py
from kivy.uix.screenmanager import Screen
from kivy.properties import NumericProperty
from kivy.app import App


class SettingsScreen(Screen):
    volume = NumericProperty(50)

    def on_pre_enter(self):
        app = App.get_running_app()
        mixer = getattr(app, "mixer", None)

        if mixer and mixer.is_available():
            self.volume = mixer.get_volume()
        else:
            # fallback for Windows / no ALSA
            self.volume = 50

    def go_back(self):
        app = App.get_running_app()
        if hasattr(app, "play_click"):
            app.play_click()
        self.manager.current = "menu"

    def on_volume_change(self, value):
        app = App.get_running_app()
        value = int(value)
        self.volume = value

        # update in-app sound volume
        if hasattr(app, "sound"):
            app.sound.set_bgm_volume(value / 100.0)
            app.sound.set_sfx_volume(value / 100.0)

            if value == 0:
                app.sound.enable_bgm(False)
                app.sound.enable_sfx(False)
            else:
                app.sound.enable_bgm(True)
                app.sound.enable_sfx(True)

                # resume bgm if needed
                if app.sound.bgm is not None:
                    try:
                        app.sound.play_bgm()
                    except Exception:
                        pass

        # update Raspberry Pi system volume
        mixer = getattr(app, "mixer", None)
        if mixer and mixer.is_available():
            if value == 0:
                mixer.mute()
            else:
                mixer.unmute()
                mixer.set_volume(value)