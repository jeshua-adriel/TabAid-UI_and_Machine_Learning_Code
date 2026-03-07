# src/screens/game3.py
import os
import time
import threading

import cv2
import numpy as np

from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, ListProperty, StringProperty
from kivy.graphics import Color, Line
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.app import App
from kivy.animation import Animation

from utils.database import add_game3_scores


GAME3_STAGES = [
    {
        "id": 1,
        "name": "Apple",
        "guide": "g3_stage1_apple.png",
        "ref": "ref1.png",
        "colors": [("#FF010C", "Red")],
    },
    {
        "id": 2,
        "name": "Tree",
        "guide": "g3_stage2_tree.png",
        "ref": "ref2.png",
        "colors": [
            ("#B8FF00", "Leaves"),
            ("#FF9900", "Trunk"),
        ],
    },
]


def _src_dir():
    return os.path.dirname(os.path.dirname(__file__))


REFS_DIR = os.path.join(_src_dir(), "ml", "refs", "game3")


def _export_size():
    w = int(os.environ.get("TABAID_EXPORT_W", "1152"))
    h = int(os.environ.get("TABAID_EXPORT_H", "648"))
    return w, h


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# =========================================================
# IMAGE NORMALIZATION (FIXED: EXACT RESIZE)
# =========================================================
def normalize_image_to_target(src_path: str, dst_path: str):
    target_w, target_h = _export_size()

    img = cv2.imread(src_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Cannot read image: {src_path}")

    # alpha -> composite on white
    if len(img.shape) == 3 and img.shape[2] == 4:
        bgr = img[:, :, :3].astype(np.float32)
        a = img[:, :, 3:4].astype(np.float32) / 255.0
        white = np.ones_like(bgr) * 255.0
        img = (bgr * a + white * (1.0 - a)).astype(np.uint8)

    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    resized = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_AREA)
    cv2.imwrite(dst_path, resized)


# =========================================================
# COLOR PAD (stroke width normalized)
# =========================================================
def hex_to_rgba(hex_color: str):
    h = hex_color.strip().lstrip("#")
    if len(h) != 6:
        return (0, 0, 0, 1)
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r, g, b, 1)


class ColorPad(Widget):
    """
    Same fix as PaintPad:
    keep stroke thickness stable in final exported image.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._lines = []
        self._min_dist = 2.5
        self._last_pos = None
        self._rgba = (1, 0, 0, 1)

        self.export_stroke_px = 24.0  # desired thickness in exported PNG

    def _stroke_width_now(self) -> float:
        export_w, _export_h = _export_size()
        if self.width <= 1:
            return self.export_stroke_px
        w = self.export_stroke_px * (self.width / float(export_w))
        return float(max(1.0, min(96.0, w)))

    def _clamp_xy(self, x, y):
        return (
            _clamp(x, self.x, self.right),
            _clamp(y, self.y, self.top),
        )

    def set_hex_color(self, hex_color: str):
        self._rgba = hex_to_rgba(hex_color)

    def clear(self):
        self.canvas.clear()
        self._lines.clear()
        self._last_pos = None

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        x, y = self._clamp_xy(touch.x, touch.y)

        with self.canvas:
            Color(*self._rgba)
            line = Line(
                points=[x, y],
                width=self._stroke_width_now(),
                cap="round",
                joint="round"
            )

        touch.grab(self)
        self._lines.append(line)
        self._last_pos = (x, y)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_move(touch)

        if not self._lines:
            return True

        x, y = self._clamp_xy(touch.x, touch.y)

        lx, ly = self._last_pos if self._last_pos else (x, y)
        dx = x - lx
        dy = y - ly
        if (dx * dx + dy * dy) < (self._min_dist * self._min_dist):
            return True

        self._lines[-1].points += [x, y]
        self._last_pos = (x, y)
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._last_pos = None
            return True
        return super().on_touch_up(touch)


# =========================================================
# GAME 3 SCREEN
# =========================================================
class Game3Screen(Screen):
    stage_index = NumericProperty(0)
    scores = ListProperty([0, 0])
    status_text = StringProperty("Color then press ✓")
    selected_color_hex = StringProperty("#FF010C")
    _busy = False

    def on_pre_enter(self):
        Clock.schedule_once(lambda dt: self.reset_game(), 0)

    def reset_game(self):
        self.stage_index = 0
        self.scores = [0, 0]
        self._busy = False
        self._load_stage()

    def _avg_score(self) -> int:
        return int(round(sum(self.scores) / 2.0))

    def _load_stage(self):
        stage = GAME3_STAGES[self.stage_index]

        if "guide_img" in self.ids:
            self.ids.guide_img.source = os.path.join("assets/images/guides/game3", stage["guide"])
            self.ids.guide_img.reload()

        default_hex = stage["colors"][0][0]
        self.selected_color_hex = default_hex

        if "color_pad" in self.ids:
            self.ids.color_pad.set_hex_color(default_hex)
            self.ids.color_pad.clear()

        self.status_text = f"Stage {stage['id']}/2: Color the {stage['name']} then press ✓"
        self._update_header()
        self._update_color_buttons()

    def _update_header(self):
        if "stage_label" in self.ids:
            self.ids.stage_label.text = f"Stage {self.stage_index + 1} / 2"

        if "avg_label" in self.ids:
            self.ids.avg_label.text = f"Avg: {self._avg_score()}%"

        if "s1_label" in self.ids:
            self.ids.s1_label.text = f"S1: {int(self.scores[0])}%"
        if "s2_label" in self.ids:
            self.ids.s2_label.text = f"S2: {int(self.scores[1])}%"

    # ---------- color buttons ----------
    def _update_color_buttons(self):
        stage = GAME3_STAGES[self.stage_index]
        colors = stage["colors"]

        if "color_row_1" in self.ids:
            self.ids.color_row_1.opacity = 1
            self.ids.color_row_1.disabled = False

        if "color_row_2" in self.ids:
            if len(colors) >= 2:
                self.ids.color_row_2.opacity = 1
                self.ids.color_row_2.disabled = False
            else:
                self.ids.color_row_2.opacity = 0
                self.ids.color_row_2.disabled = True

        if "btn_color_1" in self.ids:
            self.ids.btn_color_1.text = colors[0][1]
        if "btn_color_2" in self.ids:
            self.ids.btn_color_2.text = colors[1][1] if len(colors) >= 2 else ""

        self._apply_color_button_state()

    def _apply_color_button_state(self):
        stage = GAME3_STAGES[self.stage_index]
        colors = stage["colors"]

        if "btn_color_1" in self.ids:
            self.ids.btn_color_1.opacity = 1.0 if self.selected_color_hex == colors[0][0] else 0.75
        if "btn_color_2" in self.ids and len(colors) >= 2:
            self.ids.btn_color_2.opacity = 1.0 if self.selected_color_hex == colors[1][0] else 0.75

    def pick_color_1(self):
        stage = GAME3_STAGES[self.stage_index]
        hexc = stage["colors"][0][0]
        self.selected_color_hex = hexc
        if "color_pad" in self.ids:
            self.ids.color_pad.set_hex_color(hexc)
        self._apply_color_button_state()

    def pick_color_2(self):
        stage = GAME3_STAGES[self.stage_index]
        if len(stage["colors"]) < 2:
            return
        hexc = stage["colors"][1][0]
        self.selected_color_hex = hexc
        if "color_pad" in self.ids:
            self.ids.color_pad.set_hex_color(hexc)
        self._apply_color_button_state()

    def go_back(self):
        self.manager.current = "menu"

    def clear_coloring(self):
        if self._busy:
            return
        if "color_pad" in self.ids:
            self.ids.color_pad.clear()
        self.status_text = "Cleared. Color again then press ✓"

    # =====================================================
    # SAVE IMAGE (fixed)
    # =====================================================
    def _save_child_image(self, stage_id: int) -> str:
        app = App.get_running_app()
        user_id = getattr(app, "current_user_id", 0) or 0

        out_dir = os.path.join(_src_dir(), "data", "game3_submissions", f"user_{user_id}")
        os.makedirs(out_dir, exist_ok=True)

        ts = int(time.time())
        tmp_path = os.path.join(out_dir, f"_tmp_stage{stage_id}_{ts}.png")
        out_path = os.path.join(out_dir, f"stage{stage_id}_{ts}.png")

        # export visible stage area (guide overlay included)
        self.ids.stage_area.export_to_png(tmp_path)

        # normalize EXACT to export target
        normalize_image_to_target(tmp_path, out_path)

        try:
            os.remove(tmp_path)
        except Exception:
            pass

        return out_path

    # =====================================================
    # GRADING
    # =====================================================
    def grade_current(self):
        if self._busy:
            return
        self._busy = True

        try:
            Window.release_all_touches()
        except Exception:
            pass

        stage = GAME3_STAGES[self.stage_index]
        self.status_text = "Checking..."

        ref_path = os.path.join(REFS_DIR, stage["ref"])
        child_path = self._save_child_image(stage["id"])

        app = App.get_running_app()
        grader = getattr(app, "game3_grader", None)

        threading.Thread(
            target=self._run_grading_thread,
            args=(grader, ref_path, child_path, self.stage_index),
            daemon=True
        ).start()

    def _run_grading_thread(self, grader, ref_path, child_path, stage_index):
        score = 0
        err = None
        try:
            if grader is None:
                raise RuntimeError("No grader available (app.game3_grader).")
            score, sim, details = grader.grade_activity("shading", ref_path, child_path)
        except Exception as e:
            err = str(e)
            score = 0

        Clock.schedule_once(lambda dt: self._on_grade_done(stage_index, score, err), 0)

    def _on_grade_done(self, stage_index: int, score: int, err):
        self.scores[stage_index] = int(score)

        if err:
            self.status_text = "Couldn't grade. Please try again."
        else:
            self.status_text = f"Saved: {int(score)}%"

        if "avg_label" in self.ids:
            try:
                w = self.ids.avg_label
                Animation.cancel_all(w)
                (Animation(opacity=0.3, duration=0.06) + Animation(opacity=1.0, duration=0.10)).start(w)
            except Exception:
                pass

        self._busy = False
        self._update_header()

    # =====================================================
    # FLOW
    # =====================================================
    def next_stage(self):
        if self._busy:
            return
        if self.stage_index < 1:
            self.stage_index += 1
            self._load_stage()
        else:
            self.finish_game()

    def finish_game(self):
        app = App.get_running_app()
        user_id = getattr(app, "current_user_id", 0)

        if user_id:
            add_game3_scores(int(user_id), list(self.scores))

        avg = self._avg_score()
        self.status_text = f"Finished! Game 3 Average: {avg}%"
        self._update_header()
        self._show_end_popup(avg)

    def _show_end_popup(self, avg: int):
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button

        msg = self._encouraging_message(avg)

        layout = BoxLayout(orientation="vertical", padding=20, spacing=16)
        layout.add_widget(Label(
            text=f"{msg}\n\nAverage Score: {avg}%",
            font_size=22,
            halign="center",
            valign="middle"
        ))

        btn_row = BoxLayout(size_hint_y=None, height=60, spacing=16)
        btn_try = Button(text="Try Again")
        btn_back = Button(text="Back to Menu")
        btn_row.add_widget(btn_try)
        btn_row.add_widget(btn_back)
        layout.add_widget(btn_row)

        popup = Popup(title="Great Work!", content=layout, size_hint=(0.75, 0.45), auto_dismiss=False)
        btn_try.bind(on_release=lambda *_: (popup.dismiss(), self.reset_game()))
        btn_back.bind(on_release=lambda *_: (popup.dismiss(), setattr(self.manager, "current", "menu")))
        popup.open()

    def _encouraging_message(self, avg: int) -> str:
        if avg >= 90:
            return "Amazing coloring! You were very careful! 🌟"
        if avg >= 75:
            return "Great job! You are improving! 😊"
        if avg >= 55:
            return "Nice try! Let’s practice again together! 💪😊"
        return "Good effort! It’s okay—practice makes it easier! 🌈"