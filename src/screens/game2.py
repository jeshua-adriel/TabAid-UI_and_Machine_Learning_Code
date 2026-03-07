# src/screens/game2.py
import os
import time
import threading

import cv2
import numpy as np

from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, ListProperty, StringProperty
from kivy.graphics import Color, Line, Rectangle
from kivy.graphics.stencil_instructions import StencilPush, StencilUse, StencilUnUse, StencilPop
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.app import App
from kivy.animation import Animation

from utils.database import add_game2_scores


# =========================================================
# CONSTANTS
# =========================================================

TARGET_W = 1152
TARGET_H = 648

# Match your ML refs (ref images) stroke thickness here.
# If your ref looks thinner, try 14 or 12.
STROKE_PX_AT_TARGET = 16

GAME2_STEPS = [
    {"id": 1, "type": "line", "guide": "g2_step1_line.png", "ref": "ref1.png"},
    {"id": 2, "type": "line", "guide": "g2_step2_line.png", "ref": "ref2.png"},
    {"id": 3, "type": "line", "guide": "g2_step3_line.png", "ref": "ref3.png"},
    {"id": 4, "type": "dots", "guide": "g2_step4_dots.png", "ref": "ref2.png"},
    {"id": 5, "type": "dots", "guide": "g2_step5_dots.png", "ref": "ref3.png"},
]


def _src_dir():
    # .../src/screens -> .../src
    return os.path.dirname(os.path.dirname(__file__))


REFS_DIR = os.path.join(_src_dir(), "ml", "refs", "game2")


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# =========================================================
# PAINT PAD (CLIPPED + STORES POINTS)
# =========================================================

class PaintPad(Widget):
    """
    Draws on screen using Kivy graphics,
    BUT for saving to ML we use the stored points and re-render using OpenCV
    at EXACT (1152x648) so:
      - no mirroring
      - stroke thickness matches ML refs
      - resolution-independent
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._lines = []         # Kivy Line objects
        self._strokes = []       # list[list[(lx, ly)]] in LOCAL widget coords
        self._min_dist = 2.5
        self._last_pos = None

        self._clip_rect = None
        self._clip_ready = False

        self.bind(pos=self._update_clip, size=self._update_clip)

    def _ensure_clip(self):
        if self._clip_ready:
            return

        with self.canvas.before:
            StencilPush()
            self._clip_rect = Rectangle(pos=self.pos, size=self.size)
            StencilUse()

        with self.canvas.after:
            StencilUnUse()
            StencilPop()

        self._clip_ready = True

    def _update_clip(self, *_):
        if self._clip_rect is not None:
            self._clip_rect.pos = self.pos
            self._clip_rect.size = self.size

    def clear(self):
        self.canvas.clear()
        self._lines.clear()
        self._strokes.clear()
        self._last_pos = None

        self._clip_rect = None
        self._clip_ready = False
        self._ensure_clip()
        self._update_clip()

    def _clamp_xy(self, x, y):
        return (
            _clamp(x, self.x, self.right),
            _clamp(y, self.y, self.top),
        )

    def _to_local(self, x, y):
        # local coords inside this widget
        return (x - self.x, y - self.y)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        self._ensure_clip()
        x, y = self._clamp_xy(touch.x, touch.y)

        with self.canvas:
            Color(0, 0, 0, 1)
            line = Line(points=[x, y], width=STROKE_PX_AT_TARGET, cap="round", joint="round")

        touch.grab(self)
        self._lines.append(line)
        self._last_pos = (x, y)

        # start new stroke in LOCAL coords
        lx, ly = self._to_local(x, y)
        self._strokes.append([(lx, ly)])

        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_move(touch)

        if not self._lines:
            return True

        x, y = self._clamp_xy(touch.x, touch.y)

        lx0, ly0 = self._last_pos if self._last_pos else (x, y)
        dx = x - lx0
        dy = y - ly0
        if (dx * dx + dy * dy) < (self._min_dist * self._min_dist):
            return True

        self._lines[-1].points += [x, y]
        self._last_pos = (x, y)

        # append local coord
        lx, ly = self._to_local(x, y)
        if self._strokes:
            self._strokes[-1].append((lx, ly))

        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._last_pos = None
            return True
        return super().on_touch_up(touch)

    # ---------------------------
    # Render to ML image (OpenCV)
    # ---------------------------
    def render_to_target_png(self, out_path: str, target_w=TARGET_W, target_h=TARGET_H):
        """
        Re-render stored strokes into an exact (target_w x target_h) PNG.
        This avoids export_to_png mirroring and removes any DPI/resolution scaling.
        """
        canvas = np.full((target_h, target_w, 3), 255, dtype=np.uint8)

        w = float(self.width) if self.width else 1.0
        h = float(self.height) if self.height else 1.0

        # map local Kivy coords (0..w, 0..h from bottom-left)
        # into image coords (0..target_w, 0..target_h from top-left)
        def map_pt(lx, ly):
            x = int(round((lx / w) * (target_w - 1)))
            y = int(round((1.0 - (ly / h)) * (target_h - 1)))  # flip Y for image coordinates
            x = max(0, min(target_w - 1, x))
            y = max(0, min(target_h - 1, y))
            return x, y

        for stroke in self._strokes:
            if len(stroke) < 2:
                continue
            pts = [map_pt(lx, ly) for (lx, ly) in stroke]
            for i in range(1, len(pts)):
                cv2.line(
                    canvas,
                    pts[i - 1],
                    pts[i],
                    (0, 0, 0),
                    thickness=int(STROKE_PX_AT_TARGET),
                    lineType=cv2.LINE_AA,
                )

        cv2.imwrite(out_path, canvas)


# =========================================================
# GAME 2 SCREEN
# =========================================================

class Game2Screen(Screen):
    step_index = NumericProperty(0)
    scores = ListProperty([0, 0, 0, 0, 0])
    status_text = StringProperty("Draw then press ✓")

    _busy = False
    _last_details = None

    def on_pre_enter(self):
        Clock.schedule_once(lambda dt: self.reset_game(), 0)

    def reset_game(self):
        self.step_index = 0
        self.scores = [0, 0, 0, 0, 0]
        self._busy = False
        self._last_details = None
        self._load_step()

    def _avg_score(self) -> int:
        return int(round(sum(self.scores) / 5.0))

    def _load_step(self):
        step = GAME2_STEPS[self.step_index]

        if "guide_img" in self.ids:
            self.ids.guide_img.source = os.path.join("assets/images/guides/game2", step["guide"])
            self.ids.guide_img.reload()

        if "paint_pad" in self.ids:
            self.ids.paint_pad.clear()

        self.status_text = f"Task {step['id']}/5 ({step['type']}): Draw then press ✓"
        self._update_header()

    def _update_header(self):
        if "step_label" in self.ids:
            self.ids.step_label.text = f"Task {self.step_index + 1} / 5"

        if "score_label" in self.ids:
            self.ids.score_label.text = f"Avg: {self._avg_score()}%"

        for i in range(1, 6):
            k = f"s{i}_label"
            if k in self.ids:
                self.ids[k].text = f"S{i}: {int(self.scores[i - 1])}%"

    def go_back(self):
        self.manager.current = "menu"

    def clear_drawing(self):
        if self._busy:
            return
        if "paint_pad" in self.ids:
            self.ids.paint_pad.clear()
        self.status_text = "Cleared. Draw again then press ✓"

    # =====================================================
    # SAVE DRAWING (NO export_to_png; ALWAYS SAME OUTPUT)
    # =====================================================
    def _save_child_drawing(self, step_id: int) -> str:
        app = App.get_running_app()
        user_id = getattr(app, "current_user_id", 0) or 0

        out_dir = os.path.join(_src_dir(), "data", "game2_submissions", f"user_{user_id}")
        os.makedirs(out_dir, exist_ok=True)

        ts = int(time.time())
        out_path = os.path.join(out_dir, f"step{step_id}_{ts}.png")

        # Render to exact ML resolution (fix mirroring + thickness)
        self.ids.paint_pad.render_to_target_png(out_path, TARGET_W, TARGET_H)

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

        step = GAME2_STEPS[self.step_index]
        activity_type = step["type"]

        self.status_text = "Checking..."

        ref_path = os.path.join(REFS_DIR, step["ref"])
        child_path = self._save_child_drawing(step["id"])

        app = App.get_running_app()
        grader = getattr(app, "game2_grader", None)

        threading.Thread(
            target=self._run_grading_thread,
            args=(grader, activity_type, ref_path, child_path, self.step_index),
            daemon=True
        ).start()

    def _run_grading_thread(self, grader, activity_type, ref_path, child_path, step_index):
        score, sim, details = 0, 0.0, {}
        err = None
        try:
            if grader is None:
                raise RuntimeError("No grader available (app.game2_grader).")
            score, sim, details = grader.grade_activity(activity_type, ref_path, child_path)
        except Exception as e:
            err = str(e)

        Clock.schedule_once(lambda dt: self._on_grade_done(step_index, score, sim, details, err), 0)

    def _on_grade_done(self, step_index, score, sim, details, err):
        self.scores[step_index] = int(score)
        self._last_details = details

        if err:
            self.status_text = "Couldn't grade. Please try again."
        else:
            self.status_text = f"Saved: {int(score)}%"

        if "score_label" in self.ids:
            try:
                w = self.ids.score_label
                Animation.cancel_all(w)
                (Animation(opacity=0.3, duration=0.06) + Animation(opacity=1.0, duration=0.10)).start(w)
            except Exception:
                pass

        self._busy = False
        self._update_header()

    # =====================================================
    # FLOW (Next/Finish)
    # =====================================================
    def next_step(self):
        if self._busy:
            return
        if self.step_index < 4:
            self.step_index += 1
            self._load_step()
        else:
            self.finish_game()

    def finish_game(self):
        app = App.get_running_app()
        user_id = getattr(app, "current_user_id", 0)

        if user_id:
            add_game2_scores(int(user_id), list(self.scores))

        avg = self._avg_score()
        self.status_text = f"Finished! Game 2 Average: {avg}%"
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
        btn_next = Button(text="Proceed to Game 3")
        btn_row.add_widget(btn_try)
        btn_row.add_widget(btn_next)
        layout.add_widget(btn_row)

        popup = Popup(
            title="Great Work!",
            content=layout,
            size_hint=(0.75, 0.45),
            auto_dismiss=False
        )

        btn_try.bind(on_release=lambda *_: (popup.dismiss(), self.reset_game()))
        btn_next.bind(on_release=lambda *_: (popup.dismiss(), setattr(self.manager, "current", "game3")))
        popup.open()

    def _encouraging_message(self, avg: int) -> str:
        if avg >= 90:
            return "Amazing work! You were very careful! 🌟"
        if avg >= 75:
            return "Great job! You are improving! 😊"
        if avg >= 55:
            return "Nice try! Let’s practice again together! 💪😊"
        return "Good effort! It’s okay—practice makes it easier! 🌈"