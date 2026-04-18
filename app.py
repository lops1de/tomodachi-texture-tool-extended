from __future__ import annotations

import os
import shutil
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

import converter

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── palette ───────────────────────────────────────────────────────────────────
BG = "#0b0b10"
SURF = "#14141f"
SURF2 = "#1c1c2a"
BORDER = "#26263a"
ACCENT = "#7c6af6"
ACCENTH = "#6a58e0"
SUCCESS = "#34d399"
ERROR = "#fb7185"
FG = "#dde0f5"
MUTED = "#4e4e70"
MUTED2 = "#8282a8"


def _lbl(parent, text, size=12, weight="normal", color=FG, **kw) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent,
        text=text,
        text_color=color,
        font=ctk.CTkFont(size=size, weight=weight),
        **kw,
    )


def _row(parent) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, fg_color="transparent")


def _card(parent, **kw) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent,
        fg_color=SURF,
        corner_radius=14,
        border_width=1,
        border_color=BORDER,
        **kw,
    )


def _preview_cache_root() -> Path:
    p = Path(tempfile.gettempdir()) / "TomodachiTextureTool" / "previews"
    p.mkdir(parents=True, exist_ok=True)
    return p


# Must match CTkOptionMenu values for item type (case-sensitive).
_MODE_LABELS = [
    "Facepaint",
    "Goods",
    "Clothes",
    "Exterior",
    "Interior",
    "MapObject",
    "MapFloor",
    "Food",
]


def _display_for_mode(mode_lower: str) -> str:
    for m in _MODE_LABELS:
        if m.lower() == mode_lower.lower():
            return m
    return mode_lower.title()


def _slot_preview_source(slot: dict) -> tuple[Path, str] | None:
    """Prefer ugctex, then canvas, then shop thumb for a visual preview."""
    if slot.get("ugctex"):
        return slot["ugctex"], "ugctex"
    if slot.get("canvas"):
        return slot["canvas"], "canvas"
    if slot.get("ugctext"):
        return slot["ugctext"], "ugctext"
    return None


_RYU_TAIL = ("ryujinx", "bis", "user", "save", "0000000000000001")


def _is_expected_ryujinx_slot_root(p: Path) -> bool:
    """True only for .../Ryujinx/bis/user/save/0000000000000001 (case-insensitive)."""
    if not p.is_dir():
        return False
    try:
        parts = tuple(x.lower() for x in p.resolve().parts)
    except OSError:
        return False
    return len(parts) >= len(_RYU_TAIL) and parts[-len(_RYU_TAIL) :] == _RYU_TAIL


def _candidate_default_ryujinx_save_roots() -> list[Path]:
    """Typical install paths; first match wins."""
    out: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        out.append(Path(appdata) / "Ryujinx" / "bis" / "user" / "save" / "0000000000000001")
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        out.append(Path(xdg) / "Ryujinx" / "bis" / "user" / "save" / "0000000000000001")
    out.append(Path.home() / ".config" / "Ryujinx" / "bis" / "user" / "save" / "0000000000000001")
    return out


def default_ryujinx_save_path_if_valid() -> Path | None:
    """Ryujinx primary user save slot when present and path matches the expected layout."""
    for c in _candidate_default_ryujinx_save_roots():
        if _is_expected_ryujinx_slot_root(c):
            try:
                return c.resolve()
            except OSError:
                continue
    return None


def thumb_needed_for_mode(mode_lower: str) -> bool:
    """Shop UIs use thumbnails for non-facepaint UGC; facepaint is Mii-only."""
    return mode_lower.strip().lower() != "facepaint"


# ── app ───────────────────────────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Tomodachi Texture Tool")
        self.geometry("640x740")
        self.minsize(560, 660)
        self.configure(fg_color=BG)

        self._png_path: Path | None = None
        self._converting = False
        self._browsing = False
        self._preview_dir = _preview_cache_root()
        self._replace_preview_job: str | None = None
        self._suppress_replace_trace = False

        self._build()
        self._try_enable_dnd()
        self._bind_replace_preview_traces()
        self._apply_default_save_path_if_present()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self._build_header()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=(14, 10))

        self._build_save_location(body)

        self._tabs = ctk.CTkTabview(
            body,
            fg_color=SURF2,
            segmented_button_fg_color=SURF,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENTH,
            text_color=FG,
        )
        self._tabs.pack(fill="both", expand=True, pady=(10, 0))

        tab_import = self._tabs.add("Import")
        tab_browse = self._tabs.add("Browse / Export")

        self._build_tab_import(tab_import)
        self._build_tab_browse(tab_browse)

        _lbl(body, "made by farbensplasch", size=10, color=MUTED).pack(anchor="e", pady=(6, 0))

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=SURF, corner_radius=0, border_width=0, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        stripe = ctk.CTkFrame(hdr, fg_color=ACCENT, corner_radius=0, width=4)
        stripe.pack(side="left", fill="y")

        _lbl(hdr, "Tomodachi Texture Tool", size=15, weight="bold").pack(side="left", padx=16)
        _lbl(hdr, "v1.0.0", size=11, color=MUTED).pack(side="right", padx=18)

    def _build_save_location(self, parent):
        c = _card(parent)
        c.pack(fill="x", pady=(0, 0))
        inner = ctk.CTkFrame(c, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

        r = _row(inner)
        r.pack(fill="x")
        _lbl(r, "Save / Ugc", size=11, color=MUTED2, width=88, anchor="w").pack(side="left")

        self._output_var = ctk.StringVar()
        ctk.CTkEntry(
            r,
            textvariable=self._output_var,
            placeholder_text="Ryujinx save folder, profile folder, or Ugc…",
            fg_color=SURF2,
            border_color=BORDER,
            text_color=FG,
            placeholder_text_color=MUTED,
            font=ctk.CTkFont(size=11),
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            r,
            text="Browse",
            width=72,
            height=30,
            fg_color=SURF2,
            hover_color=BORDER,
            border_width=1,
            border_color=BORDER,
            text_color=MUTED2,
            font=ctk.CTkFont(size=11),
            command=self._browse_output,
        ).pack(side="left", padx=(8, 0))

        r2 = _row(inner)
        r2.pack(fill="x", pady=(10, 0))
        _lbl(r2, "Profile", size=11, color=MUTED2, width=88, anchor="w").pack(side="left")
        self._profile_var = ctk.StringVar(value="—")
        self._profile_menu = ctk.CTkOptionMenu(
            r2,
            values=["—"],
            variable=self._profile_var,
            command=lambda _: self._on_profile_changed(),
            font=ctk.CTkFont(size=12),
            fg_color=SURF2,
            button_color=ACCENT,
            button_hover_color=ACCENTH,
            dropdown_fg_color=SURF2,
            dropdown_hover_color=ACCENT,
            text_color=FG,
            dropdown_text_color=FG,
            width=120,
        )
        self._profile_menu.pack(side="left")

        self._sync_all_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            r2,
            text="Sync exports to all profiles",
            variable=self._sync_all_var,
            font=ctk.CTkFont(size=11),
            text_color=MUTED2,
            fg_color=ACCENT,
            hover_color=ACCENTH,
            border_color=BORDER,
        ).pack(side="left", padx=(16, 0))

    def _build_tab_import(self, parent):
        self._build_top(parent)
        self._build_convert(parent)

    def _build_top(self, parent):
        top = _card(parent)
        top.pack(fill="x", pady=(0, 10))

        top.columnconfigure(0, minsize=360)
        top.columnconfigure(1, weight=1)

        previews = ctk.CTkFrame(top, fg_color="transparent")
        previews.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="n")

        self._build_preview_import(previews)
        self._build_preview_replace(previews)
        self._build_settings(top)

    def _build_preview_import(self, parent):
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.pack(side="left", padx=(0, 14))

        _lbl(col, "PNG to import", size=11, color=MUTED2).pack()
        self._drop_box = ctk.CTkFrame(
            col,
            width=162,
            height=162,
            fg_color=SURF2,
            corner_radius=12,
            cursor="hand2",
            border_width=1,
            border_color=BORDER,
        )
        self._drop_box.pack(pady=(4, 0))
        self._drop_box.pack_propagate(False)
        self._drop_box.bind("<Button-1>", self._browse_png)

        self._drop_hint = _lbl(self._drop_box, "click to\nbrowse", size=12, color=MUTED, justify="center")
        self._drop_hint.place(relx=0.5, rely=0.5, anchor="center")
        self._drop_hint.bind("<Button-1>", self._browse_png)

        self._preview_img_lbl = ctk.CTkLabel(self._drop_box, text="")
        self._preview_img_lbl.place(relx=0.5, rely=0.5, anchor="center")

        self._file_info = _lbl(col, "", size=10, color=MUTED2, wraplength=162, justify="center")
        self._file_info.pack(pady=(6, 4))

        ctk.CTkButton(
            col,
            text="Browse PNG",
            width=162,
            height=28,
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=MUTED2,
            hover_color=SURF2,
            font=ctk.CTkFont(size=11),
            command=self._browse_png,
        ).pack()

    def _build_preview_replace(self, parent):
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.pack(side="left")

        _lbl(col, "Current slot (save)", size=11, color=MUTED2).pack()
        self._replace_box = ctk.CTkFrame(
            col,
            width=120,
            height=120,
            fg_color=SURF2,
            corner_radius=12,
            border_width=1,
            border_color=BORDER,
        )
        self._replace_box.pack(pady=(4, 0))
        self._replace_box.pack_propagate(False)

        self._replace_hint = _lbl(
            self._replace_box,
            "Use “Use for\nimport” in\nBrowse, or set\nID + type",
            size=10,
            color=MUTED,
            justify="center",
        )
        self._replace_hint.place(relx=0.5, rely=0.5, anchor="center")

        self._replace_img_lbl = ctk.CTkLabel(self._replace_box, text="")
        self._replace_img_lbl.place(relx=0.5, rely=0.5, anchor="center")

        self._replace_info = _lbl(col, "", size=9, color=MUTED2, wraplength=118, justify="center")
        self._replace_info.pack(pady=(6, 0))

    def _build_settings(self, parent):
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.grid(row=0, column=1, padx=(0, 16), pady=20, sticky="nsew")

        _lbl(col, "Settings", size=13, weight="bold").pack(anchor="w", pady=(0, 14))

        r = _row(col)
        r.pack(fill="x", pady=(0, 10))
        _lbl(r, "Item Type", size=11, color=MUTED2, width=72, anchor="w").pack(side="left")
        self._mode_var = ctk.StringVar(value="Facepaint")
        ctk.CTkOptionMenu(
            r,
            values=list(_MODE_LABELS),
            variable=self._mode_var,
            command=lambda _: self._on_import_mode_changed(),
            font=ctk.CTkFont(size=12),
            fg_color=SURF2,
            button_color=ACCENT,
            button_hover_color=ACCENTH,
            dropdown_fg_color=SURF2,
            dropdown_hover_color=ACCENT,
            text_color=FG,
            dropdown_text_color=FG,
            width=170,
        ).pack(side="left")

        ctk.CTkFrame(col, fg_color=BORDER, height=1).pack(fill="x", pady=(0, 10))

        r2 = _row(col)
        r2.pack(fill="x")
        _lbl(r2, "Item ID", size=11, color=MUTED2, width=72, anchor="w").pack(side="left")
        self._id_var = ctk.StringVar(value="000")
        ctk.CTkEntry(
            r2,
            textvariable=self._id_var,
            width=72,
            placeholder_text="000",
            fg_color=SURF2,
            border_color=BORDER,
            text_color=FG,
            placeholder_text_color=MUTED,
            font=ctk.CTkFont(size=13),
        ).pack(side="left")

        self._highest_lbl = _lbl(r2, "", size=11, color=MUTED2)
        self._highest_lbl.pack(side="left", padx=(10, 0))

    def _build_convert(self, parent):
        self._convert_btn = ctk.CTkButton(
            parent,
            text="Convert & Export",
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=ACCENT,
            hover_color=ACCENTH,
            text_color="#ffffff",
            corner_radius=10,
            command=self._on_convert,
        )
        self._convert_btn.pack(fill="x", pady=(0, 8))

        self._progress = ctk.CTkProgressBar(
            parent,
            fg_color=SURF2,
            progress_color=ACCENT,
            height=4,
            corner_radius=2,
        )
        self._progress.pack(fill="x", pady=(0, 6))
        self._progress.set(0)

        self._status_lbl = _lbl(parent, "Ready", size=11, color=MUTED)
        self._status_lbl.pack(anchor="w")

    def _build_tab_browse(self, parent):
        hdr = _row(parent)
        hdr.pack(fill="x", pady=(8, 8))
        _lbl(hdr, "Preview existing UGC as PNG (export to edit or back up).", size=11, color=MUTED2).pack(
            anchor="w"
        )

        r = _row(parent)
        r.pack(fill="x", pady=(0, 8))
        _lbl(r, "Item Type", size=11, color=MUTED2, width=72, anchor="w").pack(side="left")
        self._browse_mode_var = ctk.StringVar(value="Facepaint")
        ctk.CTkOptionMenu(
            r,
            values=list(_MODE_LABELS),
            variable=self._browse_mode_var,
            font=ctk.CTkFont(size=12),
            fg_color=SURF2,
            button_color=ACCENT,
            button_hover_color=ACCENTH,
            dropdown_fg_color=SURF2,
            dropdown_hover_color=ACCENT,
            text_color=FG,
            dropdown_text_color=FG,
            width=170,
        ).pack(side="left")

        r2 = _row(parent)
        r2.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            r2,
            text="Refresh list",
            width=120,
            fg_color=ACCENT,
            hover_color=ACCENTH,
            font=ctk.CTkFont(size=12),
            command=self._on_refresh_browse,
        ).pack(side="left")
        ctk.CTkButton(
            r2,
            text="Clear preview cache",
            width=140,
            fg_color=SURF2,
            hover_color=BORDER,
            border_width=1,
            border_color=BORDER,
            text_color=MUTED2,
            font=ctk.CTkFont(size=11),
            command=self._clear_preview_cache,
        ).pack(side="left", padx=(8, 0))

        self._browse_scroll = ctk.CTkScrollableFrame(
            parent,
            fg_color=SURF2,
            corner_radius=10,
            border_width=1,
            border_color=BORDER,
            height=320,
        )
        self._browse_scroll.pack(fill="both", expand=True, pady=(0, 8))

        self._browse_hint = _lbl(
            self._browse_scroll,
            "Set Save / Ugc path and click Refresh list.",
            size=11,
            color=MUTED,
        )
        self._browse_hint.pack(pady=20)

    # ── paths ─────────────────────────────────────────────────────────────────

    def _on_profile_changed(self) -> None:
        self._refresh_highest_id()
        self._schedule_replace_slot_preview()

    def _on_import_mode_changed(self) -> None:
        self._refresh_highest_id()
        self._schedule_replace_slot_preview()

    def _apply_default_save_path_if_present(self) -> None:
        d = default_ryujinx_save_path_if_valid()
        if d is None:
            return
        self._suppress_replace_trace = True
        try:
            self._output_var.set(str(d))
            self._refresh_profile_options()
            self._refresh_highest_id()
        finally:
            self._suppress_replace_trace = False
        self._schedule_replace_slot_preview()

    def _bind_replace_preview_traces(self) -> None:
        def on_write(*_: object) -> None:
            if self._suppress_replace_trace:
                return
            self._schedule_replace_slot_preview()

        self._id_var.trace_add("write", on_write)
        self._output_var.trace_add("write", on_write)

    def _schedule_replace_slot_preview(self) -> None:
        if self._replace_preview_job is not None:
            try:
                self.after_cancel(self._replace_preview_job)
            except Exception:
                pass
        self._replace_preview_job = self.after(250, self._do_replace_slot_preview)

    def _do_replace_slot_preview(self) -> None:
        self._replace_preview_job = None
        ugc = self._get_active_ugc_folder()
        if not ugc:
            self._clear_replace_slot_preview("Set Save / Ugc\npath first")
            return
        raw = self._id_var.get().strip()
        try:
            item_id = int(raw) if raw else -1
        except ValueError:
            self._clear_replace_slot_preview("Invalid ID")
            return
        if not 0 <= item_id <= 999:
            self._clear_replace_slot_preview("ID: 0 – 999")
            return
        mode = self._mode_var.get().lower()
        slot = converter.scan_ugc_slot(ugc, mode, item_id)
        self._apply_replace_slot_preview(slot, mode, item_id)

    def _clear_replace_slot_preview(self, hint: str) -> None:
        self._replace_img_lbl.configure(image="")
        self._replace_hint.configure(text=hint)
        self._replace_hint.place(relx=0.5, rely=0.5, anchor="center")
        self._replace_info.configure(text="")

    def _apply_replace_slot_preview(self, slot: dict, mode: str, item_id: int) -> None:
        id_str = str(item_id).zfill(3)
        src = _slot_preview_source(slot)
        if not src:
            self._replace_img_lbl.configure(image="")
            self._replace_hint.configure(text="No texture\nin save\nfor this slot")
            self._replace_hint.place(relx=0.5, rely=0.5, anchor="center")
            self._replace_info.configure(text=f"ID {id_str}", text_color=MUTED)
            return
        path, kind = src
        try:
            pil = converter.zs_file_to_png(path, kind)
            disp = pil.copy()
            disp.thumbnail((112, 112), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=disp, dark_image=disp, size=(disp.width, disp.height))
            self._replace_hint.place_forget()
            self._replace_img_lbl.configure(image=ctk_img)
            self._replace_img_lbl.image = ctk_img
            self._replace_info.configure(
                text=f"ID {id_str}\n{kind}",
                text_color=MUTED2,
            )
        except Exception as e:
            self._replace_img_lbl.configure(image="")
            self._replace_hint.configure(text="Decode\nerror")
            self._replace_hint.place(relx=0.5, rely=0.5, anchor="center")
            self._replace_info.configure(text=str(e)[:80], text_color=ERROR)

    def _scroll_browse_to_top(self) -> None:
        """CTkScrollableFrame can leave the canvas scrolled mid-list after repopulating."""

        def scroll() -> None:
            self.update_idletasks()
            sf = self._browse_scroll
            canvas = getattr(sf, "_parent_canvas", None)
            if canvas is not None:
                try:
                    canvas.yview_moveto(0.0)
                except tk.TclError:
                    pass
            for w in sf.winfo_children():
                if isinstance(w, tk.Canvas):
                    try:
                        w.yview_moveto(0.0)
                    except tk.TclError:
                        pass

        self.after_idle(scroll)
        self.after(100, scroll)

    def _refresh_profile_options(self):
        folder = self._output_var.get().strip()
        if not folder:
            self._profile_menu.configure(values=["—"])
            self._profile_var.set("—")
            self._schedule_replace_slot_preview()
            return
        profs = converter.list_ugc_profiles(Path(folder))
        labels = [p[0] for p in profs] if profs else ["—"]
        self._profile_menu.configure(values=labels)
        self._profile_var.set(labels[0])
        self._schedule_replace_slot_preview()

    def _get_active_ugc_folder(self) -> Path | None:
        folder = self._output_var.get().strip()
        if not folder:
            return None
        base = Path(folder)
        profs = converter.list_ugc_profiles(base)
        if not profs:
            return None
        sel = self._profile_var.get()
        for label, ugc in profs:
            if label == sel:
                return ugc
        return profs[0][1]

    def _other_ugc_folders_for_sync(self, active: Path) -> list[Path]:
        folder = self._output_var.get().strip()
        if not folder:
            return []
        profs = converter.list_ugc_profiles(Path(folder))
        out: list[Path] = []
        for _, ugc in profs:
            if ugc.resolve() != active.resolve():
                out.append(ugc)
        return out

    # ── drag-and-drop ─────────────────────────────────────────────────────────

    def _try_enable_dnd(self):
        try:
            from tkinterdnd2 import DND_FILES

            self._drop_box.drop_target_register(DND_FILES)
            self._drop_box.dnd_bind("<<Drop>>", self._on_dnd_drop)
            self._drop_hint.configure(text="drop PNG\nor click")
        except Exception:
            pass

    def _on_dnd_drop(self, event):
        path = event.data.strip().strip("{}").strip('"').strip("'")
        if path.lower().endswith(".png"):
            self._load_png(Path(path))
        else:
            self._set_status("Please drop a PNG file.", error=True)

    # ── browsing ──────────────────────────────────────────────────────────────

    def _browse_png(self, _event=None):
        p = filedialog.askopenfilename(
            title="Select PNG Image",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
        )
        if p:
            self._load_png(Path(p))

    def _browse_output(self):
        p = filedialog.askdirectory(title="Select save folder, profile folder, or Ugc")
        if p:
            self._output_var.set(p)
            self._refresh_profile_options()
            self._refresh_highest_id()

    # ── image loading ─────────────────────────────────────────────────────────

    def _load_png(self, path: Path):
        try:
            img = Image.open(path)
            self._png_path = path

            thumb = img.copy()
            thumb.thumbnail((152, 152), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=(thumb.width, thumb.height))
            self._preview_img_lbl.configure(image=ctk_img)
            self._drop_hint.configure(text="")
            self._drop_box.configure(border_color=ACCENT)
            self._file_info.configure(
                text=f"{path.name}\n{img.size[0]}×{img.size[1]}",
                text_color=MUTED2,
            )
            self._set_status(f"Loaded: {path.name}")
        except Exception as e:
            self._set_status(f"Could not open image: {e}", error=True)

    # ── highest ID ────────────────────────────────────────────────────────────

    def _refresh_highest_id(self):
        path = self._get_active_ugc_folder()
        if not path or not path.is_dir():
            self._highest_lbl.configure(text="")
            return
        highest = converter.get_highest_id(path, self._mode_var.get().lower())
        if highest is None:
            self._highest_lbl.configure(text="— none found", text_color=MUTED)
        else:
            self._highest_lbl.configure(
                text=f"/ highest: {str(highest).zfill(3)}",
                text_color=ACCENT,
            )

    # ── conversion ────────────────────────────────────────────────────────────

    def _on_convert(self):
        if self._converting:
            return
        if not self._png_path:
            self._set_status("Select a PNG first.", error=True)
            return
        ugc = self._get_active_ugc_folder()
        if not ugc:
            self._set_status("Select a valid Save / Ugc folder first.", error=True)
            return
        try:
            item_id = int(self._id_var.get())
            if not 0 <= item_id <= 999:
                raise ValueError
        except ValueError:
            self._set_status("Item ID must be 0 – 999.", error=True)
            return

        mode = self._mode_var.get().lower()
        write_thumb = thumb_needed_for_mode(mode)
        sync = self._sync_all_var.get() and len(converter.list_ugc_profiles(Path(self._output_var.get()))) > 1

        self._converting = True
        self._convert_btn.configure(state="disabled", text="Converting…")
        self._progress.set(0)

        def run():
            try:
                cp, up, tp = converter.convert_and_export(
                    png_path=self._png_path,
                    output_dir=ugc,
                    item_id=item_id,
                    mode=mode,
                    use_srgb=False,
                    resize_mode=2,
                    write_thumb=write_thumb,
                    on_progress=lambda msg, pct: self.after(0, lambda m=msg, p=pct: self._on_progress(m, p)),
                )
                written = [cp, up]
                if tp:
                    written.append(tp)
                synced = False
                if sync:
                    others = self._other_ugc_folders_for_sync(ugc)
                    if others:
                        converter.copy_zs_to_folders(written, others)
                        synced = True
                self.after(0, lambda w=written, s=synced: self._on_success(w, s))
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_error(str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _on_progress(self, msg: str, pct: float):
        self._progress.set(pct)
        self._set_status(msg)

    def _on_success(self, paths: list[Path], synced: bool):
        self._converting = False
        self._convert_btn.configure(state="normal", text="Convert & Export")
        self._progress.set(1.0)
        names = "  +  ".join(p.name for p in paths)
        extra = " (synced to other profiles)" if synced else ""
        self._set_status(f"Done — {names}{extra}", success=True)
        self._refresh_highest_id()
        self._schedule_replace_slot_preview()

    def _on_error(self, msg: str):
        self._converting = False
        self._convert_btn.configure(state="normal", text="Convert & Export")
        self._progress.set(0)
        self._set_status(f"Error: {msg}", error=True)

    # ── browse / export ───────────────────────────────────────────────────────

    def _clear_preview_cache(self):
        try:
            if self._preview_dir.exists():
                for child in self._preview_dir.iterdir():
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
            self._set_status("Preview cache cleared.", success=True)
        except OSError as e:
            self._set_status(f"Could not clear cache: {e}", error=True)

    def _on_refresh_browse(self):
        if self._browsing:
            return
        ugc = self._get_active_ugc_folder()
        if not ugc or not ugc.is_dir():
            self._set_status("Select a valid Save / Ugc folder first.", error=True)
            return
        mode = self._browse_mode_var.get().lower()
        self._browsing = True
        self._set_status("Loading list…")

        def work():
            try:
                ids = converter.list_ugc_ids_for_mode(ugc, mode)
                self.after(0, lambda: self._populate_browse(ugc, mode, ids))
            except Exception as e:
                self.after(0, lambda: self._browse_error(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _browse_error(self, msg: str):
        self._browsing = False
        self._set_status(f"Browse error: {msg}", error=True)

    def _populate_browse(self, ugc: Path, mode: str, ids: list[int]):
        self._browsing = False
        for w in self._browse_scroll.winfo_children():
            w.destroy()

        if not ids:
            _lbl(
                self._browse_scroll,
                "No items found for this type in the selected Ugc folder.",
                size=11,
                color=MUTED,
            ).pack(pady=20)
            self._set_status("No items found.")
            self._scroll_browse_to_top()
            return

        for iid in ids:
            slot = converter.scan_ugc_slot(ugc, mode, iid)
            row = ctk.CTkFrame(self._browse_scroll, fg_color=SURF, corner_radius=8)
            row.pack(fill="x", padx=6, pady=4)

            id_str = str(iid).zfill(3)
            src = _slot_preview_source(slot)
            prev_path, kind = (src[0], src[1]) if src else (None, None)

            img_lbl = ctk.CTkLabel(row, text="", width=72, height=72)
            img_lbl.pack(side="left", padx=(8, 8), pady=8)

            if prev_path and kind:
                try:
                    pil = converter.zs_file_to_png(prev_path, kind)
                    disp = pil.copy()
                    disp.thumbnail((72, 72), Image.LANCZOS)
                    ctk_img = ctk.CTkImage(light_image=disp, dark_image=disp, size=(disp.width, disp.height))
                    img_lbl.configure(image=ctk_img)
                    img_lbl.image = ctk_img  # keep ref
                except Exception:
                    _lbl(row, "(preview error)", size=10, color=ERROR).pack(side="left")

            info = _lbl(
                row,
                f"ID {id_str}\n"
                f"canvas: {'yes' if slot['canvas'] else '—'}\n"
                f"ugctex: {'yes' if slot['ugctex'] else '—'}\n"
                f"thumb:  {'yes' if slot['ugctext'] else '—'}",
                size=10,
                color=MUTED2,
                justify="left",
            )
            info.pack(side="left", fill="x", expand=True)

            bf = _row(row)
            bf.pack(side="right", padx=8)
            ctk.CTkButton(
                bf,
                text="Export PNGs",
                width=100,
                height=28,
                fg_color=SURF2,
                hover_color=BORDER,
                border_width=1,
                border_color=BORDER,
                font=ctk.CTkFont(size=11),
                command=lambda s=slot, m=mode, ii=iid: self._export_slot_pngs(s, m, ii),
            ).pack(pady=2)
            ctk.CTkButton(
                bf,
                text="Use for import",
                width=100,
                height=28,
                fg_color=ACCENT,
                hover_color=ACCENTH,
                font=ctk.CTkFont(size=11),
                command=lambda s=slot, m=mode, ii=iid: self._use_for_import(ii, m, s),
            ).pack(pady=2)

        self._set_status(f"Listed {len(ids)} item(s).")
        self._scroll_browse_to_top()

    def _export_slot_pngs(self, slot: dict, mode: str, item_id: int):
        out = filedialog.askdirectory(title="Export PNGs to folder")
        if not out:
            return
        out_p = Path(out)
        id_str = str(item_id).zfill(3)
        t = converter.ITEM_TYPES[mode]
        stem = t["ugctex"].format(id=id_str).replace(".ugctex.zs", "")
        try:
            if slot["canvas"]:
                im = converter.zs_file_to_png(slot["canvas"], "canvas")
                im.save(out_p / f"{stem}.canvas.png")
            if slot["ugctex"]:
                im = converter.zs_file_to_png(slot["ugctex"], "ugctex")
                im.save(out_p / f"{stem}.ugctex.png")
            if slot["ugctext"]:
                im = converter.zs_file_to_png(slot["ugctext"], "ugctext")
                im.save(out_p / f"{stem}_Thumb.ugctext.png")
            self._set_status(f"Exported to {out_p}", success=True)
        except Exception as e:
            self._set_status(f"Export failed: {e}", error=True)

    def _use_for_import(self, item_id: int, mode: str, slot: dict) -> None:
        disp = _display_for_mode(mode)
        self._suppress_replace_trace = True
        try:
            self._id_var.set(str(item_id).zfill(3))
            self._mode_var.set(disp)
            self._browse_mode_var.set(disp)
        finally:
            self._suppress_replace_trace = False
        self._tabs.set("Import")
        self._refresh_highest_id()
        self._apply_replace_slot_preview(slot, mode, item_id)
        self._set_status(
            f"Replacing {disp} ID {str(item_id).zfill(3)} — pick a PNG, then export.",
            success=True,
        )

    def _set_status(self, msg: str, error=False, success=False):
        color = ERROR if error else (SUCCESS if success else MUTED2)
        self._status_lbl.configure(text=msg, text_color=color)

