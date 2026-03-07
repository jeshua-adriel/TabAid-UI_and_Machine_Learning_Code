# src/screens/game1.py
import random

from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.properties import StringProperty, BooleanProperty, NumericProperty
from kivy.clock import Clock
from kivy.app import App
from kivy.core.audio import SoundLoader
from kivy.graphics import Color, Line, Ellipse, Rectangle, Triangle
from kivy.animation import Animation

from utils.database import add_game1_score


class DraggableShape(Widget):
    shape_name = StringProperty("circle")   # "circle" | "square" | "triangle"
    dragging = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(lambda dt: self._redraw(), 0)

    def on_shape_name(self, *_):
        Clock.schedule_once(lambda dt: self._redraw(), 0)

    def on_pos(self, *_):
        Clock.schedule_once(lambda dt: self._redraw(), 0)

    def on_size(self, *_):
        Clock.schedule_once(lambda dt: self._redraw(), 0)

    def _redraw(self):
        if not self.canvas:
            return

        self.canvas.clear()

        with self.canvas:
            # Fill (pastel)
            Color(0.78, 0.92, 1.0, 1)

            if self.shape_name == "circle":
                Ellipse(pos=self.pos, size=self.size)
            elif self.shape_name == "square":
                Rectangle(pos=self.pos, size=self.size)
            else:  # triangle
                x, y = self.pos
                w, h = self.size
                Triangle(points=[x + w / 2, y + h, x, y, x + w, y])

            # Border
            Color(0.40, 0.65, 0.95, 0.95)
            if self.shape_name == "circle":
                Line(width=2.2, ellipse=(self.x, self.y, self.width, self.height))
            elif self.shape_name == "square":
                Line(width=2.2, rectangle=(self.x, self.y, self.width, self.height))
            else:
                Line(width=2.2, points=[
                    self.x + self.width / 2, self.y + self.height,
                    self.x, self.y,
                    self.x + self.width, self.y,
                    self.x + self.width / 2, self.y + self.height
                ])

    # ---- drag behavior ----
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.dragging = True
            touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self.center = touch.pos
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.dragging = False

            # notify screen
            p = self.parent
            while p and p.__class__.__name__ != "Game1Screen":
                p = p.parent
            if p:
                p.on_shape_dropped(self)
            return True
        return super().on_touch_up(touch)


class Game1Screen(Screen):
    total_rounds = NumericProperty(5)
    current_round = NumericProperty(1)
    score = NumericProperty(0)

    _active_shape = None
    _busy = False  # prevents double drop handling

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sound_right = SoundLoader.load("assets/sfx_right.wav")
        self.sound_wrong = SoundLoader.load("assets/sfx_wrong.wav")

    def on_pre_enter(self):
        # ensure ids are ready during transitions
        Clock.schedule_once(lambda dt: self.reset_game(), 0)

    def reset_game(self):
        self.current_round = 1
        self.score = 0
        self._busy = False
        self._clear_spawn()
        self._update_ui()
        self._spawn_next_shape()

    def _update_ui(self):
        if "round_label" in self.ids:
            self.ids.round_label.text = f"Round {self.current_round} / {self.total_rounds}"
        if "score_label" in self.ids:
            self.ids.score_label.text = f"Score: {self.score}"
        if "feedback_label" in self.ids:
            # don't wipe feedback if we just wrote something; only clear when spawning/resetting
            pass

    def _clear_spawn(self):
        if "spawn_area" not in self.ids:
            return
        area = self.ids.spawn_area
        area.clear_widgets()
        self._active_shape = None

    def _spawn_next_shape(self):
        self._clear_spawn()

        name = random.choice(["circle", "square", "triangle"])
        shape = DraggableShape(shape_name=name)
        self._active_shape = shape
        self.ids.spawn_area.add_widget(shape)

        # center shape after layout
        Clock.schedule_once(lambda dt: setattr(shape, "center", self.ids.spawn_area.center), 0)

        if "feedback_label" in self.ids:
            self.ids.feedback_label.text = ""

    def on_shape_dropped(self, shape_widget: DraggableShape):
        if self._busy:
            return

        dropped_on = self._which_zone(shape_widget)

        # ✅ Only proceed if released on ANY drop target (correct OR wrong)
        if dropped_on is None:
            if "feedback_label" in self.ids:
                self.ids.feedback_label.text = "Drag it to a name!"
            # snap back to spawn center
            try:
                Animation(center=self.ids.spawn_area.center, duration=0.12).start(shape_widget)
            except Exception:
                pass
            return

        self._busy = True
        correct = (dropped_on == shape_widget.shape_name)

        if correct:
            self.score += 1
            if "feedback_label" in self.ids:
                self.ids.feedback_label.text = "You did it right!"
            if self.sound_right:
                self.sound_right.stop()
                self.sound_right.play()
        else:
            if "feedback_label" in self.ids:
                self.ids.feedback_label.text = "Nice try, do it again!"
            if self.sound_wrong:
                self.sound_wrong.stop()
                self.sound_wrong.play()

        # update score label
        if "score_label" in self.ids:
            self.ids.score_label.text = f"Score: {self.score}"

        Clock.schedule_once(lambda dt: self._advance_round(), 0.6)

    def _which_zone(self, shape_widget):
        if not all(k in self.ids for k in ("dz_circle", "dz_square", "dz_triangle")):
            return None

        # Use shape CENTER for reliable hit-testing
        cx, cy = shape_widget.center
        wx, wy = shape_widget.to_window(cx, cy)

        zones = [
            ("circle", self.ids.dz_circle),
            ("square", self.ids.dz_square),
            ("triangle", self.ids.dz_triangle),
        ]

        for name, zone in zones:
            # Convert the point into the zone's local coordinate space
            zx, zy = zone.to_widget(wx, wy, relative=False)
            if zone.collide_point(zx, zy):
                return name

        return None

    def _advance_round(self):
        if self.current_round >= self.total_rounds:
            self._save_grade()
            self._show_end_popup()
            return

        self.current_round += 1
        self._busy = False

        if "round_label" in self.ids:
            self.ids.round_label.text = f"Round {self.current_round} / {self.total_rounds}"

        self._spawn_next_shape()

    def _save_grade(self):
        app = App.get_running_app()
        user_id = getattr(app, "current_user_id", 0)
        if not user_id:
            return
        add_game1_score(user_id, int(self.score), int(self.total_rounds))

    def _show_end_popup(self):
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button

        msg = self._encouraging_message()

        layout = BoxLayout(orientation="vertical", padding=20, spacing=16)
        layout.add_widget(Label(text=msg, font_size=22))

        btn_row = BoxLayout(size_hint_y=None, height=60, spacing=16)
        btn_try = Button(text="Try Again")
        btn_next = Button(text="Proceed to Game 2")
        btn_row.add_widget(btn_try)
        btn_row.add_widget(btn_next)
        layout.add_widget(btn_row)

        popup = Popup(
            title="Great Job!",
            content=layout,
            size_hint=(0.75, 0.45),
            auto_dismiss=False
        )

        def do_try(*_):
            popup.dismiss()
            self.reset_game()

        def do_next(*_):
            popup.dismiss()
            self.manager.current = "game2"

        btn_try.bind(on_release=do_try)
        btn_next.bind(on_release=do_next)

        popup.open()

    def _encouraging_message(self):
        if self.score == self.total_rounds:
            return "Amazing! Perfect score! 🌟"
        if self.score >= 3:
            return "Great job! Keep going! 😊"
        return "Nice effort! You’re getting better! 💪😊"

    def go_back(self):
        self.manager.current = "menu"
