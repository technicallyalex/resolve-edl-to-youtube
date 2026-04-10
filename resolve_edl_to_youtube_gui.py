#!/usr/bin/env python3
"""GUI app to convert DaVinci Resolve timeline marker EDL files into YouTube chapters."""

from __future__ import annotations

import ctypes
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    import winreg
except ImportError:
    winreg = None


MODERN_MARKER_RE = re.compile(
    r"\|C:(?P<color>[^|]*)"
    r"\s+\|M:(?P<name>[^|]*)"
    r"\s+\|D:(?P<comment>.*)$"
)
LEGACY_MARKER_RE = re.compile(r"\*?\s*MARKER:\s*(?P<value>.*)$", re.IGNORECASE)
TIMECODE_RE = re.compile(r"\d{2}:\d{2}:\d{2}:\d{2}")


def configure_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return

    user32 = ctypes.windll.user32
    shcore = getattr(ctypes.windll, "shcore", None)

    try:
        # Per-monitor v2 awareness keeps Tk text crisp on mixed-DPI displays.
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except (AttributeError, OSError):
        pass

    if shcore is not None:
        try:
            shcore.SetProcessDpiAwareness(1)
            return
        except OSError:
            pass

    try:
        user32.SetProcessDPIAware()
    except OSError:
        pass


def configure_tk_scaling(root: tk.Tk) -> None:
    try:
        scaling = root.winfo_fpixels("1i") / 72.0
    except tk.TclError:
        return

    if scaling > 0:
        root.tk.call("tk", "scaling", scaling)


class ThinScrollbar(tk.Canvas):
    def __init__(self, master: tk.Misc, orient: str, command, thickness: int = 12) -> None:
        width = thickness if orient == "vertical" else 0
        height = 0 if orient == "vertical" else thickness
        super().__init__(
            master,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            relief="flat",
            takefocus=0,
            cursor="arrow",
        )
        self.orient = orient
        self.command = command
        self.thickness = thickness
        self.thumb_margin = 3
        self.first = 0.0
        self.last = 1.0
        self.thumb_id = self.create_rectangle(0, 0, 0, 0, outline="", tags="thumb")
        self._drag_offset = 0.0
        self._palette = {
            "track": "#1d2229",
            "thumb": "#6d7682",
            "thumb_active": "#8b95a3",
        }
        self._hover = False
        self._grid_kwargs: dict[str, object] | None = None
        self._visible = False

        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.tag_bind("thumb", "<Button-1>", self._on_press)
        self.tag_bind("thumb", "<B1-Motion>", self._on_drag)
        self._draw()

    def configure_palette(self, *, track: str, thumb: str, thumb_active: str) -> None:
        self._palette = {"track": track, "thumb": thumb, "thumb_active": thumb_active}
        self._draw()

    def grid(self, **kwargs) -> None:  # type: ignore[override]
        self._grid_kwargs = dict(kwargs)
        super().grid(**kwargs)
        self._visible = True

    def set(self, first: str | float, last: str | float) -> None:
        self.first = max(0.0, min(1.0, float(first)))
        self.last = max(self.first, min(1.0, float(last)))
        should_show = (self.last - self.first) < 0.999
        if should_show and not self._visible and self._grid_kwargs is not None:
            super().grid(**self._grid_kwargs)
            self._visible = True
        elif not should_show and self._visible:
            super().grid_remove()
            self._visible = False
        self._draw()

    def _track_span(self) -> float:
        span = self.winfo_height() if self.orient == "vertical" else self.winfo_width()
        return max(span - (self.thumb_margin * 2), 1.0)

    def _thumb_bounds(self) -> tuple[float, float]:
        span = self._track_span()
        start = self.thumb_margin + (span * self.first)
        end = self.thumb_margin + (span * self.last)
        min_size = 28.0
        if end - start < min_size:
            end = min(start + min_size, self.thumb_margin + span)
            start = max(self.thumb_margin, end - min_size)
        return start, end

    def _draw(self) -> None:
        self.configure(background=self._palette["track"])
        fill = self._palette["thumb_active"] if self._hover else self._palette["thumb"]
        start, end = self._thumb_bounds()
        if self.orient == "vertical":
            x0 = self.thumb_margin
            x1 = max(self.winfo_width() - self.thumb_margin, x0 + 1)
            self.coords(self.thumb_id, x0, start, x1, end)
        else:
            y0 = self.thumb_margin
            y1 = max(self.winfo_height() - self.thumb_margin, y0 + 1)
            self.coords(self.thumb_id, start, y0, end, y1)
        self.itemconfigure(self.thumb_id, fill=fill)

    def _on_enter(self, _event: tk.Event) -> None:
        self._hover = True
        self._draw()

    def _on_leave(self, _event: tk.Event) -> None:
        self._hover = False
        self._draw()

    def _on_press(self, event: tk.Event) -> None:
        start, end = self._thumb_bounds()
        position = event.y if self.orient == "vertical" else event.x
        if not (start <= position <= end):
            span = self._track_span()
            new_first = (position - self.thumb_margin) / span
            thumb_size = self.last - self.first
            self.command("moveto", max(0.0, min(1.0 - thumb_size, new_first - (thumb_size / 2))))
            return
        self._drag_offset = position - start

    def _on_drag(self, event: tk.Event) -> None:
        span = self._track_span()
        thumb_size = self.last - self.first
        position = event.y if self.orient == "vertical" else event.x
        new_first = (position - self._drag_offset - self.thumb_margin) / span
        self.command("moveto", max(0.0, min(1.0 - thumb_size, new_first)))


@dataclass
class Marker:
    start_frames: int
    color: str
    name: str
    comment: str

    def label(self, use_comments: bool) -> str:
        raw = self.comment if use_comments else self.name
        cleaned = " ".join(raw.split())
        return cleaned or "Chapter"


def timecode_to_frames(timecode: str, fps: float) -> int:
    hours, minutes, seconds, frames = (int(part) for part in timecode.split(":"))
    total_seconds = (hours * 3600) + (minutes * 60) + seconds
    return int(round(total_seconds * fps + frames))


def frames_to_youtube_timestamp(frame_count: int, fps: float) -> str:
    total_seconds = int(frame_count / fps)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def parse_legacy_marker(text: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in text.split("|")]
    name = parts[0] if parts else ""
    color = parts[1] if len(parts) > 1 else ""
    comment = parts[2] if len(parts) > 2 else ""
    return color, name, comment


def extract_markers(edl_text: str, fps: float) -> list[Marker]:
    markers: list[Marker] = []
    pending_start_frames: int | None = None

    for raw_line in edl_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        timecodes = TIMECODE_RE.findall(line)
        if len(timecodes) >= 4:
            pending_start_frames = timecode_to_frames(timecodes[2], fps)
            continue

        modern_match = MODERN_MARKER_RE.search(line)
        if modern_match and pending_start_frames is not None:
            markers.append(
                Marker(
                    start_frames=pending_start_frames,
                    color=modern_match.group("color").strip(),
                    name=modern_match.group("name").strip(),
                    comment=modern_match.group("comment").strip(),
                )
            )
            pending_start_frames = None
            continue

        legacy_match = LEGACY_MARKER_RE.match(line)
        if legacy_match and pending_start_frames is not None:
            color, name, comment = parse_legacy_marker(legacy_match.group("value"))
            markers.append(
                Marker(
                    start_frames=pending_start_frames,
                    color=color,
                    name=name,
                    comment=comment,
                )
            )
            pending_start_frames = None

    return markers


def build_chapters(
    markers: list[Marker],
    fps: float,
    use_comments: bool,
    prepend_zero_title: str,
    dedupe: bool,
) -> list[str]:
    lines: list[str] = []
    sorted_markers = sorted(markers, key=lambda item: item.start_frames)

    if prepend_zero_title.strip() and sorted_markers and sorted_markers[0].start_frames > 0:
        lines.append(f"0:00 {prepend_zero_title.strip()}")

    for marker in sorted_markers:
        lines.append(
            f"{frames_to_youtube_timestamp(marker.start_frames, fps)} {marker.label(use_comments)}"
        )

    if not dedupe:
        return lines

    deduped: list[str] = []
    for line in lines:
        if not deduped or deduped[-1] != line:
            deduped.append(line)
    return deduped


class ResolveEdlApp:
    def __init__(self, root: tk.Tk, initial_path: str = "") -> None:
        self.root = root
        self.root.title("Resolve EDL to YouTube Chapters")
        self.root.geometry("1100x760")
        self.root.minsize(900, 620)

        self.file_path_var = tk.StringVar()
        self.fps_var = tk.StringVar(value="24")
        self.use_comments_var = tk.BooleanVar(value=False)
        self.dedupe_var = tk.BooleanVar(value=True)
        self.prepend_zero_enabled_var = tk.BooleanVar(value=True)
        self.prepend_zero_var = tk.StringVar(value="Intro")
        self.status_var = tk.StringVar(value="")
        self._path_trace_id: str | None = None
        self._option_trace_ids: list[tuple[tk.Variable, str]] = []
        self._auto_generate_after_id: str | None = None
        self._theme_after_id: str | None = None
        self._current_theme_mode: str | None = None
        self.theme_mode_var = tk.StringVar(value="light")
        self._fonts_configured = False
        self._thin_scrollbars: list[ThinScrollbar] = []

        self._build_ui()
        self._register_auto_generate_hooks()
        self.apply_selected_theme()
        self.schedule_theme_poll()
        if initial_path:
            self.file_path_var.set(initial_path)
            self._load_current_path_if_exists()

    def _build_ui(self) -> None:
        self._build_menu()
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(3, weight=1)

        top = ttk.Frame(self.root, padding=12, style="App.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="EDL File", style="App.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        path_entry = ttk.Entry(top, textvariable=self.file_path_var)
        path_entry.grid(row=0, column=1, sticky="ew")
        path_entry.bind("<Return>", self._on_path_entry_commit)
        path_entry.bind("<FocusOut>", self._on_path_entry_commit)
        ttk.Button(top, text="Browse", command=self.open_file).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(top, text="Load File", command=self.load_file_into_input).grid(
            row=0, column=3, padx=(8, 0)
        )
        self._path_trace_id = self.file_path_var.trace_add("write", self._on_path_var_changed)

        options = ttk.Frame(self.root, padding=(12, 0, 12, 12), style="App.TFrame")
        options.grid(row=1, column=0, sticky="new")

        ttk.Label(options, text="Options", style="App.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))

        ttk.Label(options, text="FPS", style="App.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Entry(options, textvariable=self.fps_var, width=10).grid(row=1, column=1, sticky="w", padx=(8, 20))

        ttk.Checkbutton(options, text="Use marker comments", variable=self.use_comments_var).grid(
            row=1, column=2, sticky="w", padx=(0, 20)
        )
        ttk.Checkbutton(options, text="Dedupe consecutive lines", variable=self.dedupe_var).grid(
            row=1, column=3, sticky="w", padx=(0, 20)
        )

        editor_label = ttk.Label(self.root, text="EDL Input", padding=(12, 0, 12, 4), style="App.TLabel")
        editor_label.grid(row=2, column=0, sticky="w")

        editor_frame = ttk.Frame(self.root, padding=(12, 0, 12, 12), style="App.TFrame")
        editor_frame.grid(row=3, column=0, sticky="nsew")
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(0, weight=1)

        self.input_text = tk.Text(editor_frame, wrap="none", undo=True, height=14)
        input_scroll_y = ThinScrollbar(editor_frame, orient="vertical", command=self.input_text.yview)
        input_scroll_x = ThinScrollbar(editor_frame, orient="horizontal", command=self.input_text.xview)
        self._thin_scrollbars.extend((input_scroll_y, input_scroll_x))
        self.input_text.configure(yscrollcommand=input_scroll_y.set, xscrollcommand=input_scroll_x.set)
        self.input_text.grid(row=0, column=0, sticky="nsew")
        input_scroll_y.grid(row=0, column=1, sticky="ns")
        input_scroll_x.grid(row=1, column=0, sticky="ew")
        input_scroll_y.set(0.0, 1.0)
        input_scroll_x.set(0.0, 1.0)

        actions = ttk.Frame(self.root, padding=(12, 0, 12, 12), style="App.TFrame")
        actions.grid(row=4, column=0, sticky="ew")

        ttk.Checkbutton(
            actions,
            text="Prepend 0:00 chapter",
            variable=self.prepend_zero_enabled_var,
            command=self._sync_prepend_zero_state,
        ).pack(side="left", padx=(0, 12))
        self.prepend_zero_entry = ttk.Entry(actions, textvariable=self.prepend_zero_var, width=14)
        self.prepend_zero_entry.pack(side="left", padx=(0, 16))
        ttk.Button(actions, text="Generate Chapters", command=self.generate_chapters).pack(side="left")
        self._sync_prepend_zero_state()

        output_label = ttk.Label(self.root, text="YouTube Chapters", padding=(12, 0, 12, 4), style="App.TLabel")
        output_label.grid(row=5, column=0, sticky="w")

        output_frame = ttk.Frame(self.root, padding=(12, 0, 12, 12), style="App.TFrame")
        output_frame.grid(row=6, column=0, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.root.rowconfigure(6, weight=1)

        self.output_text = tk.Text(output_frame, wrap="none", height=12)
        output_scroll_y = ThinScrollbar(output_frame, orient="vertical", command=self.output_text.yview)
        output_scroll_x = ThinScrollbar(output_frame, orient="horizontal", command=self.output_text.xview)
        self._thin_scrollbars.extend((output_scroll_y, output_scroll_x))
        self.output_text.configure(yscrollcommand=output_scroll_y.set, xscrollcommand=output_scroll_x.set)
        self.output_text.grid(row=0, column=0, sticky="nsew")
        output_scroll_y.grid(row=0, column=1, sticky="ns")
        output_scroll_x.grid(row=1, column=0, sticky="ew")
        output_scroll_y.set(0.0, 1.0)
        output_scroll_x.set(0.0, 1.0)

        export_actions = ttk.Frame(self.root, padding=(12, 0, 12, 12), style="App.TFrame")
        export_actions.grid(row=7, column=0, sticky="ew")
        ttk.Button(export_actions, text="Copy to Clipboard", command=self.copy_output).pack(side="left")
        ttk.Button(export_actions, text="Save as Text File", command=self.save_output).pack(
            side="left", padx=(8, 0)
        )

        self.status_label = ttk.Label(
            self.root,
            textvariable=self.status_var,
            padding=(12, 0, 12, 8),
            style="App.TLabel",
        )
        self._set_status("")

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_radiobutton(
            label="System",
            variable=self.theme_mode_var,
            value="system",
            command=self.apply_selected_theme,
        )
        view_menu.add_radiobutton(
            label="Dark",
            variable=self.theme_mode_var,
            value="dark",
            command=self.apply_selected_theme,
        )
        view_menu.add_radiobutton(
            label="Light",
            variable=self.theme_mode_var,
            value="light",
            command=self.apply_selected_theme,
        )
        menubar.add_cascade(label="View", menu=view_menu)
        self.root.configure(menu=menubar)

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Resolve Marker EDL",
            filetypes=[("EDL files", "*.edl"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.file_path_var.set(path)
            self.load_file_into_input()

    def load_file_into_input(self) -> None:
        path_text = self.file_path_var.get().strip()
        if not path_text:
            self.open_file()
            path_text = self.file_path_var.get().strip()
            if not path_text:
                return

        try:
            content = Path(path_text).read_text(encoding="utf-8-sig")
        except OSError as exc:
            messagebox.showerror("Load Failed", f"Could not read file:\n{exc}")
            return

        self.input_text.delete("1.0", tk.END)
        self.input_text.insert("1.0", content)
        self._set_status(f"Loaded {path_text}")
        self.schedule_auto_generate()

    def _load_current_path_if_exists(self) -> None:
        path_text = self.file_path_var.get().strip()
        if not path_text:
            return

        path = Path(path_text)
        if not path.is_file():
            return

        try:
            content = path.read_text(encoding="utf-8-sig")
        except OSError:
            return

        existing = self.input_text.get("1.0", tk.END).strip()
        new_content = content.strip()
        if existing == new_content:
            return

        self.input_text.delete("1.0", tk.END)
        self.input_text.insert("1.0", content)
        self._set_status(f"Loaded {path}")
        self.schedule_auto_generate()

    def _on_path_var_changed(self, *_args: object) -> None:
        self.root.after(150, self._load_current_path_if_exists)

    def _on_path_entry_commit(self, _event: tk.Event) -> None:
        self._load_current_path_if_exists()

    def _register_auto_generate_hooks(self) -> None:
        for variable in (
            self.fps_var,
            self.use_comments_var,
            self.dedupe_var,
            self.prepend_zero_enabled_var,
            self.prepend_zero_var,
        ):
            trace_id = variable.trace_add("write", self._on_option_changed)
            self._option_trace_ids.append((variable, trace_id))

    def _sync_prepend_zero_state(self) -> None:
        state = "normal" if self.prepend_zero_enabled_var.get() else "disabled"
        self.prepend_zero_entry.configure(state=state)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        if text:
            self.status_label.grid(row=8, column=0, sticky="ew")
        else:
            self.status_label.grid_remove()

    def detect_system_theme_mode(self) -> str:
        if sys.platform != "win32" or winreg is None:
            return "light"

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        except OSError:
            return "light"

        return "light" if value else "dark"

    def get_requested_theme_mode(self) -> str:
        selected = self.theme_mode_var.get()
        if selected in {"dark", "light"}:
            return selected
        return self.detect_system_theme_mode()

    def apply_selected_theme(self) -> None:
        mode = self.get_requested_theme_mode()
        if mode == self._current_theme_mode:
            return

        self._current_theme_mode = mode
        self._configure_fonts()
        self._apply_theme_palette(mode)

    def apply_system_theme(self) -> None:
        if self.theme_mode_var.get() != "system":
            return

        self.apply_selected_theme()

    def schedule_theme_poll(self) -> None:
        if self._theme_after_id is not None:
            self.root.after_cancel(self._theme_after_id)
        self._theme_after_id = self.root.after(1500, self._poll_theme_mode)

    def _poll_theme_mode(self) -> None:
        self._theme_after_id = None
        self.apply_system_theme()
        self.schedule_theme_poll()

    def _apply_theme_palette(self, mode: str) -> None:
        if mode == "dark":
            palette = {
                "bg": "#171a1f",
                "panel": "#1d2229",
                "surface": "#242a32",
                "text": "#e6ebf2",
                "muted": "#aeb7c3",
                "field": "#20252d",
                "border": "#2d3440",
                "button": "#2a313a",
                "button_active": "#323a45",
                "accent": "#8aa4ff",
                "selection": "#314564",
            }
        else:
            palette = {
                "bg": "#eef2f6",
                "panel": "#eef2f6",
                "surface": "#ffffff",
                "text": "#1b2430",
                "muted": "#5b6778",
                "field": "#ffffff",
                "border": "#d7dee8",
                "button": "#ffffff",
                "button_active": "#f3f6fb",
                "accent": "#4d6fff",
                "selection": "#dce7ff",
            }

        style = ttk.Style(self.root)
        if sys.platform == "win32" and "vista" in style.theme_names():
            style.theme_use("vista")
        else:
            style.theme_use("clam")
        self.root.configure(background=palette["bg"])

        style.configure("App.TFrame", background=palette["panel"])
        style.configure("App.TLabel", background=palette["panel"], foreground=palette["text"])

        for widget in (self.input_text, self.output_text):
            widget.configure(
                background=palette["field"],
                foreground=palette["text"],
                insertbackground=palette["text"],
                selectbackground=palette["selection"],
                selectforeground=palette["text"],
                highlightbackground=palette["border"],
                highlightcolor=palette["accent"],
                highlightthickness=1,
                relief="flat",
                borderwidth=0,
                padx=14,
                pady=12,
            )

        for scrollbar in self._thin_scrollbars:
            scrollbar.configure_palette(
                track=palette["panel"],
                thumb="#8b94a1" if mode == "dark" else "#a9b4c3",
                thumb_active=palette["accent"],
            )

    def _configure_fonts(self) -> None:
        if self._fonts_configured:
            return

        ui_family = "Segoe UI"
        mono_family = "Cascadia Mono"

        try:
            available = set(tkfont.families(self.root))
        except tk.TclError:
            available = set()

        if mono_family not in available:
            mono_family = "Consolas" if "Consolas" in available else "Courier New"
        if ui_family not in available and available:
            ui_family = "Arial" if "Arial" in available else next(iter(available))

        tkfont.nametofont("TkDefaultFont").configure(family=ui_family, size=10)
        tkfont.nametofont("TkTextFont").configure(family=ui_family, size=10)
        tkfont.nametofont("TkHeadingFont").configure(family=ui_family, size=11, weight="bold")

        mono_font = tkfont.Font(self.root, family=mono_family, size=11)
        self.input_text.configure(font=mono_font)
        self.output_text.configure(font=mono_font)
        self._fonts_configured = True

    def _on_option_changed(self, *_args: object) -> None:
        self.schedule_auto_generate()

    def schedule_auto_generate(self) -> None:
        if self._auto_generate_after_id is not None:
            self.root.after_cancel(self._auto_generate_after_id)
        self._auto_generate_after_id = self.root.after(150, self.generate_chapters_silently)

    def generate_chapters_silently(self) -> None:
        self._auto_generate_after_id = None
        self.generate_chapters(show_errors=False)

    def clear_input(self) -> None:
        self.input_text.delete("1.0", tk.END)
        self.output_text.delete("1.0", tk.END)
        self._set_status("Cleared EDL input.")

    def generate_chapters(self, show_errors: bool = True) -> bool:
        raw_edl = self.input_text.get("1.0", tk.END).strip()
        if not raw_edl:
            self.output_text.delete("1.0", tk.END)
            if show_errors:
                messagebox.showwarning("No Input", "Paste EDL text or load an EDL file first.")
            else:
                self._set_status("")
            return False

        try:
            fps = float(self.fps_var.get().strip())
            if fps <= 0:
                raise ValueError
        except ValueError:
            self.output_text.delete("1.0", tk.END)
            if show_errors:
                messagebox.showerror("Invalid FPS", "FPS must be a positive number.")
            else:
                self._set_status("FPS must be a positive number.")
            return False

        markers = extract_markers(raw_edl, fps)
        if not markers:
            self.output_text.delete("1.0", tk.END)
            if show_errors:
                messagebox.showerror(
                    "No Markers Found",
                    "No Resolve markers were found in the provided EDL text.",
                )
            else:
                self._set_status("No Resolve markers were found in the current EDL input.")
            return False

        chapter_lines = build_chapters(
            markers=markers,
            fps=fps,
            use_comments=self.use_comments_var.get(),
            prepend_zero_title=self.prepend_zero_var.get() if self.prepend_zero_enabled_var.get() else "",
            dedupe=self.dedupe_var.get(),
        )

        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", "\n".join(chapter_lines))
        self._set_status(f"Generated {len(chapter_lines)} chapter lines from {len(markers)} markers.")
        return True

    def copy_output(self) -> None:
        output = self.output_text.get("1.0", tk.END).strip()
        if not output:
            messagebox.showwarning("No Output", "Generate chapters before copying them.")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(output)
        self.root.update()
        self._set_status("Copied chapter lines to clipboard.")

    def save_output(self) -> None:
        output = self.output_text.get("1.0", tk.END).strip()
        if not output:
            messagebox.showwarning("No Output", "Generate chapters before saving them.")
            return

        path = filedialog.asksaveasfilename(
            title="Save YouTube Chapters",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            Path(path).write_text(output + "\n", encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Save Failed", f"Could not save file:\n{exc}")
            return

        self._set_status(f"Saved chapter lines to {path}")


def main() -> None:
    initial_path = sys.argv[1] if len(sys.argv) > 1 else ""
    configure_windows_dpi_awareness()
    root = tk.Tk()
    configure_tk_scaling(root)
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    app = ResolveEdlApp(root, initial_path=initial_path)
    root.mainloop()


if __name__ == "__main__":
    main()
