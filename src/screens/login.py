# src/screens/login.py
from kivy.uix.screenmanager import Screen
from kivy.uix.togglebutton import ToggleButton
from kivy.properties import NumericProperty, StringProperty
from kivy.app import App

from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp

from utils.database import get_users, add_user, delete_user, get_user_details


class LoginScreen(Screen):
    selected_user_id = NumericProperty(0)
    selected_user_name = StringProperty("None")
    selected_user_age = StringProperty("--")
    selected_user_gender = StringProperty("--")
    selected_game1 = StringProperty("--")
    selected_game2 = StringProperty("--")
    selected_game3 = StringProperty("--")

    # prevents popup immediately reopening due to touch "fall-through"
    _dialog_lock = False

    def on_pre_enter(self):
        self.load_users()
        self.clear_selected_info()

    def clear_selected_info(self):
        self.selected_user_id = 0
        self.selected_user_name = "None"
        self.selected_user_age = "--"
        self.selected_user_gender = "--"
        self.selected_game1 = "--"
        self.selected_game2 = "--"
        self.selected_game3 = "--"

    def load_users(self):
        container = self.ids.user_list
        container.clear_widgets()

        for uid, name in get_users():
            btn = ToggleButton(
                text=name,
                group="users",
                size_hint_y=None,
                height=dp(70),
                font_size="20sp"
            )
            btn.bind(on_press=lambda b, u=uid, n=name: self.select_user(u, n))
            container.add_widget(btn)

    def select_user(self, user_id, name):
        self.selected_user_id = int(user_id)
        self.selected_user_name = str(name)

        info = get_user_details(user_id)
        if not info:
            self.selected_user_age = "--"
            self.selected_user_gender = "--"
            self.selected_game1 = "--"
            self.selected_game2 = "--"
            self.selected_game3 = "--"
            return

        age = info.get("age", 0)
        gender = info.get("gender", "")

        self.selected_user_age = str(age) if age > 0 else "--"
        self.selected_user_gender = gender if gender else "--"

        game1_score = int(info.get("game1_score", 0))
        game1_total = int(info.get("game1_total", 5))
        game2_avg = int(info.get("game2_avg", 0))
        game3_avg = int(info.get("game3_avg", 0))

        self.selected_game1 = f"{game1_score} / {game1_total}"
        self.selected_game2 = f"{game2_avg}%"
        self.selected_game3 = f"{game3_avg}%"

    # ---------- helpers ----------
    def _lock_dialog(self):
        self._dialog_lock = True

    def _unlock_dialog_later(self, *_):
        Clock.schedule_once(lambda dt: setattr(self, "_dialog_lock", False), 0.25)

    # ───── POPUP ACTIONS ─────

    def show_add_user_popup(self):
        if self._dialog_lock:
            return
        self._lock_dialog()

        layout = BoxLayout(
            orientation="vertical",
            padding=20,
            spacing=15
        )

        label = Label(
            text="Enter new user details",
            font_size=22,
            size_hint_y=None,
            height=40
        )

        name_input = TextInput(
            hint_text="Name",
            multiline=False,
            font_size=24,
            padding=[15, 15],
            write_tab=False,
            size_hint_y=None,
            height=60
        )

        age_input = TextInput(
            hint_text="Age",
            multiline=False,
            input_filter="int",
            font_size=24,
            padding=[15, 15],
            write_tab=False,
            size_hint_y=None,
            height=60
        )

        gender_row = BoxLayout(size_hint_y=None, height=60, spacing=12)
        btn_male = ToggleButton(text="Male", group="gender")
        btn_female = ToggleButton(text="Female", group="gender")
        gender_row.add_widget(btn_male)
        gender_row.add_widget(btn_female)

        btn_row = BoxLayout(size_hint_y=None, height=60, spacing=20)
        btn_cancel = Button(text="Cancel")
        btn_ok = Button(text="OK")

        btn_row.add_widget(btn_cancel)
        btn_row.add_widget(btn_ok)

        layout.add_widget(label)
        layout.add_widget(name_input)
        layout.add_widget(age_input)
        layout.add_widget(gender_row)
        layout.add_widget(btn_row)

        popup = Popup(
            title="Add User",
            content=layout,
            size_hint=(0.72, 0.55),
            auto_dismiss=False
        )

        popup.bind(on_dismiss=self._unlock_dialog_later)

        def close_popup(*_):
            btn_ok.disabled = True
            btn_cancel.disabled = True
            try:
                Window.release_all_touches()
            except Exception:
                pass
            Clock.schedule_once(lambda dt: popup.dismiss(), 0)

        def do_ok(*_):
            name = name_input.text.strip()
            age_text = age_input.text.strip()

            gender = ""
            if btn_male.state == "down":
                gender = "Male"
            elif btn_female.state == "down":
                gender = "Female"

            if not name:
                return

            age = int(age_text) if age_text.isdigit() else 0

            add_user(name, age, gender)
            self.load_users()
            self.clear_selected_info()
            close_popup()

        btn_ok.bind(on_press=do_ok)
        btn_cancel.bind(on_press=close_popup)

        popup.open()
        Clock.schedule_once(lambda dt: setattr(name_input, "focus", True), 0.3)

    def show_delete_popup(self):
        if self._dialog_lock:
            return
        if not self.selected_user_id:
            return

        self._lock_dialog()

        layout = BoxLayout(orientation="vertical", padding=20, spacing=20)

        label = Label(
            text=f"Delete '{self.selected_user_name}'?",
            font_size=22
        )

        btn_row = BoxLayout(size_hint_y=None, height=60, spacing=20)
        btn_no = Button(text="No")
        btn_yes = Button(text="Yes")

        btn_row.add_widget(btn_no)
        btn_row.add_widget(btn_yes)

        layout.add_widget(label)
        layout.add_widget(btn_row)

        popup = Popup(
            title="Confirm Delete",
            content=layout,
            size_hint=(0.6, 0.3),
            auto_dismiss=False
        )

        popup.bind(on_dismiss=self._unlock_dialog_later)

        def close_popup(*_):
            btn_yes.disabled = True
            btn_no.disabled = True
            try:
                Window.release_all_touches()
            except Exception:
                pass
            Clock.schedule_once(lambda dt: popup.dismiss(), 0)

        def do_delete(*_):
            delete_user(self.selected_user_id)
            self.load_users()
            self.clear_selected_info()
            close_popup()

        btn_yes.bind(on_press=do_delete)
        btn_no.bind(on_press=close_popup)

        popup.open()

    # ───── NAVIGATION ─────

    def proceed(self):
        if not self.selected_user_id:
            return

        app = App.get_running_app()
        app.current_user_id = self.selected_user_id
        app.current_user_name = self.selected_user_name
        self.manager.current = "menu"

    def go_back(self):
        self.manager.current = "start"