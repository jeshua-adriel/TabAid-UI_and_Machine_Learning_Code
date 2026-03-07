# src/screens/start.py
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.app import App
from kivy.core.window import Window


class StartScreen(Screen):
    def go_to_login(self):
        self.manager.current = "login"

    def show_exit_popup(self):
        layout = BoxLayout(orientation="vertical", padding=20, spacing=18)

        label = Label(
            text="Are you sure you want to exit?",
            font_size='28sp',
            halign='center',
            valign='middle'
        )
        label.bind(size=lambda *_: setattr(label, "text_size", label.size))

        btn_row = BoxLayout(size_hint_y=None, height=60, spacing=20)
        btn_no = Button(text="No")
        btn_yes = Button(text="Yes")

        btn_row.add_widget(btn_no)
        btn_row.add_widget(btn_yes)

        layout.add_widget(label)
        layout.add_widget(btn_row)

        popup = Popup(
            title="Exit",
            content=layout,
            size_hint=(0.65, 0.35),
            auto_dismiss=False
        )

        def close_popup(*_):
            try:
                Window.release_all_touches()
            except Exception:
                pass
            popup.dismiss()

        def exit_app(*_):
            popup.dismiss()
            Clock.schedule_once(lambda dt: App.get_running_app().stop(), 0.1)

        btn_no.bind(on_press=close_popup)
        btn_yes.bind(on_press=exit_app)

        popup.open()
