#!/usr/bin/env python3
"""GUI app to convert DaVinci Resolve timeline marker EDL files into YouTube chapters."""

from __future__ import annotations

import re
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


MODERN_MARKER_RE = re.compile(
    r"\|C:(?P<color>[^|]*)"
    r"\s+\|M:(?P<name>[^|]*)"
    r"\s+\|D:(?P<comment>.*)$"
)
LEGACY_MARKER_RE = re.compile(r"\*?\s*MARKER:\s*(?P<value>.*)$", re.IGNORECASE)
TIMECODE_RE = re.compile(r"\d{2}:\d{2}:\d{2}:\d{2}")


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
        self.prepend_zero_var = tk.StringVar(value="Intro")
        self.status_var = tk.StringVar(value="Load an EDL file or paste EDL text, then generate chapters.")
        self._path_trace_id: str | None = None

        self._build_ui()
        if initial_path:
            self.file_path_var.set(initial_path)
            self._load_current_path_if_exists()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(3, weight=1)

        top = ttk.Frame(self.root, padding=12)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="EDL File").grid(row=0, column=0, sticky="w", padx=(0, 8))
        path_entry = ttk.Entry(top, textvariable=self.file_path_var)
        path_entry.grid(row=0, column=1, sticky="ew")
        path_entry.bind("<Return>", self._on_path_entry_commit)
        path_entry.bind("<FocusOut>", self._on_path_entry_commit)
        ttk.Button(top, text="Browse", command=self.open_file).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(top, text="Load File", command=self.load_file_into_input).grid(
            row=0, column=3, padx=(8, 0)
        )
        self._path_trace_id = self.file_path_var.trace_add("write", self._on_path_var_changed)

        options = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        options.grid(row=1, column=0, sticky="new")

        ttk.Label(options, text="Options").grid(row=0, column=0, sticky="w", pady=(0, 8))

        ttk.Label(options, text="FPS").grid(row=1, column=0, sticky="w")
        ttk.Entry(options, textvariable=self.fps_var, width=10).grid(row=1, column=1, sticky="w", padx=(8, 20))

        ttk.Checkbutton(options, text="Use marker comments", variable=self.use_comments_var).grid(
            row=1, column=2, sticky="w", padx=(0, 20)
        )
        ttk.Checkbutton(options, text="Dedupe consecutive lines", variable=self.dedupe_var).grid(
            row=1, column=3, sticky="w", padx=(0, 20)
        )

        ttk.Label(options, text="Prepend 0:00 title").grid(row=1, column=4, sticky="w")
        ttk.Entry(options, textvariable=self.prepend_zero_var, width=20).grid(
            row=1, column=5, sticky="w", padx=(8, 0)
        )

        editor_label = ttk.Label(self.root, text="EDL Input", padding=(12, 0, 12, 4))
        editor_label.grid(row=2, column=0, sticky="w")

        editor_frame = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        editor_frame.grid(row=3, column=0, sticky="nsew")
        editor_frame.columnconfigure(0, weight=1)
        editor_frame.rowconfigure(0, weight=1)

        self.input_text = tk.Text(editor_frame, wrap="none", undo=True, height=14)
        input_scroll_y = ttk.Scrollbar(editor_frame, orient="vertical", command=self.input_text.yview)
        input_scroll_x = ttk.Scrollbar(editor_frame, orient="horizontal", command=self.input_text.xview)
        self.input_text.configure(yscrollcommand=input_scroll_y.set, xscrollcommand=input_scroll_x.set)
        self.input_text.grid(row=0, column=0, sticky="nsew")
        input_scroll_y.grid(row=0, column=1, sticky="ns")
        input_scroll_x.grid(row=1, column=0, sticky="ew")

        actions = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        actions.grid(row=4, column=0, sticky="ew")

        ttk.Button(actions, text="Generate Chapters", command=self.generate_chapters).pack(side="left")
        ttk.Button(actions, text="Clear Input", command=self.clear_input).pack(side="left", padx=(8, 0))

        output_label = ttk.Label(self.root, text="YouTube Chapters", padding=(12, 0, 12, 4))
        output_label.grid(row=5, column=0, sticky="w")

        output_frame = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        output_frame.grid(row=6, column=0, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.root.rowconfigure(6, weight=1)

        self.output_text = tk.Text(output_frame, wrap="none", height=12)
        output_scroll_y = ttk.Scrollbar(output_frame, orient="vertical", command=self.output_text.yview)
        output_scroll_x = ttk.Scrollbar(output_frame, orient="horizontal", command=self.output_text.xview)
        self.output_text.configure(yscrollcommand=output_scroll_y.set, xscrollcommand=output_scroll_x.set)
        self.output_text.grid(row=0, column=0, sticky="nsew")
        output_scroll_y.grid(row=0, column=1, sticky="ns")
        output_scroll_x.grid(row=1, column=0, sticky="ew")

        export_actions = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        export_actions.grid(row=7, column=0, sticky="ew")
        ttk.Button(export_actions, text="Copy to Clipboard", command=self.copy_output).pack(side="left")
        ttk.Button(export_actions, text="Save as Text File", command=self.save_output).pack(
            side="left", padx=(8, 0)
        )

        status = ttk.Label(self.root, textvariable=self.status_var, padding=(12, 0, 12, 12))
        status.grid(row=8, column=0, sticky="ew")

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
        self.status_var.set(f"Loaded {path_text}")

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
        self.status_var.set(f"Loaded {path}")

    def _on_path_var_changed(self, *_args: object) -> None:
        self.root.after(150, self._load_current_path_if_exists)

    def _on_path_entry_commit(self, _event: tk.Event) -> None:
        self._load_current_path_if_exists()

    def clear_input(self) -> None:
        self.input_text.delete("1.0", tk.END)
        self.status_var.set("Cleared EDL input.")

    def generate_chapters(self) -> None:
        raw_edl = self.input_text.get("1.0", tk.END).strip()
        if not raw_edl:
            messagebox.showwarning("No Input", "Paste EDL text or load an EDL file first.")
            return

        try:
            fps = float(self.fps_var.get().strip())
            if fps <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid FPS", "FPS must be a positive number.")
            return

        markers = extract_markers(raw_edl, fps)
        if not markers:
            messagebox.showerror(
                "No Markers Found",
                "No Resolve markers were found in the provided EDL text.",
            )
            return

        chapter_lines = build_chapters(
            markers=markers,
            fps=fps,
            use_comments=self.use_comments_var.get(),
            prepend_zero_title=self.prepend_zero_var.get(),
            dedupe=self.dedupe_var.get(),
        )

        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", "\n".join(chapter_lines))
        self.status_var.set(f"Generated {len(chapter_lines)} chapter lines from {len(markers)} markers.")

    def copy_output(self) -> None:
        output = self.output_text.get("1.0", tk.END).strip()
        if not output:
            messagebox.showwarning("No Output", "Generate chapters before copying them.")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(output)
        self.root.update()
        self.status_var.set("Copied chapter lines to clipboard.")

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

        self.status_var.set(f"Saved chapter lines to {path}")


def main() -> None:
    initial_path = sys.argv[1] if len(sys.argv) > 1 else ""
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    app = ResolveEdlApp(root, initial_path=initial_path)
    root.mainloop()


if __name__ == "__main__":
    main()
