# src/utils/platform_config.py
from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Project paths resolved relative to /src"""
    SRC_DIR: Path
    ROOT_DIR: Path
    ASSETS_DIR: Path
    DATA_DIR: Path
    ML_DIR: Path
    REFS_DIR: Path
    SUB_GAME2_DIR: Path
    SUB_GAME3_DIR: Path
    DB_PATH: Path


@dataclass(frozen=True)
class AppConfig:
    """Cross-platform runtime configuration."""
    # Screen behavior
    TARGET_W: int
    TARGET_H: int
    FULLSCREEN_ON_PI: bool
    BORDERLESS_ON_PI: bool
    FORCE_WINDOW_SIZE_ON_WINDOWS: bool

    # Export/grading
    EXPORT_W: int
    EXPORT_H: int

    # Platform flags
    IS_WINDOWS: bool
    IS_LINUX: bool
    IS_RASPI: bool

    # Paths
    PATHS: AppPaths


def _detect_platform() -> tuple[bool, bool, bool]:
    sysname = platform.system().lower()
    is_windows = sysname == "windows"
    is_linux = sysname == "linux"

    # Robust-ish Raspberry Pi detection:
    # - Linux + /proc/device-tree/model contains "Raspberry Pi"
    is_raspi = False
    if is_linux:
        try:
            model_path = Path("/proc/device-tree/model")
            if model_path.exists():
                txt = model_path.read_text(errors="ignore").lower()
                if "raspberry pi" in txt:
                    is_raspi = True
        except Exception:
            pass

    return is_windows, is_linux, is_raspi


def get_paths() -> AppPaths:
    # platform_config.py is in src/utils -> SRC_DIR is src/
    src_dir = Path(__file__).resolve().parents[1]
    root_dir = src_dir.parent

    assets_dir = src_dir / "assets"
    data_dir = src_dir / "data"
    ml_dir = src_dir / "ml"
    refs_dir = ml_dir / "refs"

    sub_game2 = data_dir / "game2_submissions"
    sub_game3 = data_dir / "game3_submissions"

    # Single source of truth DB should be in src/data/tabaid.db
    db_path = data_dir / "tabaid.db"

    return AppPaths(
        SRC_DIR=src_dir,
        ROOT_DIR=root_dir,
        ASSETS_DIR=assets_dir,
        DATA_DIR=data_dir,
        ML_DIR=ml_dir,
        REFS_DIR=refs_dir,
        SUB_GAME2_DIR=sub_game2,
        SUB_GAME3_DIR=sub_game3,
        DB_PATH=db_path,
    )


def get_config() -> AppConfig:
    is_windows, is_linux, is_raspi = _detect_platform()
    paths = get_paths()

    # ---------------------------------------------------------
    # TARGET_W/H = "UI design resolution" (tablet simulation)
    #
    # Your refs are 1152x648, which is 16:9-ish.
    # We’ll use this as the safe default so UI + grading align.
    # You can change later if your real LCD is 1280x800 etc.
    # ---------------------------------------------------------
    target_w = int(os.environ.get("TABAID_TARGET_W", "1152"))
    target_h = int(os.environ.get("TABAID_TARGET_H", "648"))

    # ---------------------------------------------------------
    # EXPORT_W/H = what we force images to before grading
    # Must match your refs right now: 1152x648
    # ---------------------------------------------------------
    export_w = int(os.environ.get("TABAID_EXPORT_W", "1152"))
    export_h = int(os.environ.get("TABAID_EXPORT_H", "648"))

    # On Pi: fullscreen + borderless; On Windows: fixed window size
    fullscreen_on_pi = os.environ.get("TABAID_FULLSCREEN_PI", "1") == "1"
    borderless_on_pi = os.environ.get("TABAID_BORDERLESS_PI", "1") == "1"
    force_window_size_on_windows = os.environ.get("TABAID_FORCE_WIN_SIZE", "1") == "1"

    return AppConfig(
        TARGET_W=target_w,
        TARGET_H=target_h,
        FULLSCREEN_ON_PI=fullscreen_on_pi,
        BORDERLESS_ON_PI=borderless_on_pi,
        FORCE_WINDOW_SIZE_ON_WINDOWS=force_window_size_on_windows,
        EXPORT_W=export_w,
        EXPORT_H=export_h,
        IS_WINDOWS=is_windows,
        IS_LINUX=is_linux,
        IS_RASPI=is_raspi,
        PATHS=paths,
    )