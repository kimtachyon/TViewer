import io
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path, PurePosixPath
from PIL import Image
from PIL.ExifTags import TAGS, IFD

from loader import ImageLoader, SUPPORTED
from archive import ArchiveReader, is_archive, ARCHIVE_EXTS
from theme import *


def _make_icon_btn(parent, text, command, bg=BG3, fg=TEXT,
                   hover_bg="#4a4a4c", font=None, padx=14, pady=7):
    """macOS에서 bg/fg를 존중하는 Label 기반 버튼."""
    lbl = tk.Label(parent, text=text, bg=bg, fg=fg,
                   font=font or FONT, cursor="hand2",
                   padx=padx, pady=pady)
    lbl.bind("<Button-1>", lambda e: command())
    lbl.bind("<Enter>",    lambda e: lbl.config(bg=hover_bg))
    lbl.bind("<Leave>",    lambda e: lbl.config(bg=bg))
    lbl._base_bg = bg
    lbl._hover_bg = hover_bg
    return lbl


class TViewerApp:
    def __init__(self, root: tk.Tk, initial_path: str | None = None):
        self.root = root
        self.root.title("TViewer")
        self.root.geometry("1280x800")
        self.root.configure(bg=BG)
        self.root.minsize(640, 480)

        # 앱 아이콘 적용
        try:
            _icon_path = Path(__file__).with_name("icon-tviewer.png")
            if _icon_path.exists():
                _ico = tk.PhotoImage(file=str(_icon_path))
                self.root.iconphoto(True, _ico)
        except Exception:
            pass

        self._loader = ImageLoader()
        self._images: list[Path] = []
        self._index: int = 0
        self._fit_mode: bool = True
        self._photo = None
        self._panel_visible: bool = True
        self._resize_job = None
        self._archive: ArchiveReader | None = None

        self._drag_start_x = 0
        self._drag_start_y = 0
        self._click_x = 0
        self._click_y = 0
        self._dragged = False
        self._img_x = 0
        self._img_y = 0

        self._build_ui()
        self._bind_keys()

        if initial_path:
            self.root.after(50, lambda: self._open_path(initial_path))

    # ── UI 빌드 ─────────────────────────────────────────────

    def _build_ui(self):
        menubar = tk.Menu(self.root, tearoff=0,
                          bg=BG2, fg=TEXT, activebackground=BG3,
                          activeforeground=TEXT)
        file_menu = tk.Menu(menubar, tearoff=0,
                            bg=BG2, fg=TEXT, activebackground=ACCENT,
                            activeforeground=TEXT)
        file_menu.add_command(label="열기...",
                              command=self._open_dialog,
                              accelerator="Command+O")
        menubar.add_cascade(label="파일", menu=file_menu)
        self.root.config(menu=menubar)

        self._main = tk.Frame(self.root, bg=BG)
        self._main.pack(fill=tk.BOTH, expand=True)

        self._canvas_wrap = tk.Frame(self._main, bg=BG)
        self._canvas_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_toolbar()  # pack BOTTOM first so canvas gets remaining space

        self._canvas = tk.Canvas(self._canvas_wrap, bg=BG,
                                 highlightthickness=0, cursor="arrow")
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._build_panel()

        self._toggle_lbl = tk.Label(
            self._canvas_wrap, text="›", bg=BG3, fg=TEXT2,
            font=("Helvetica Neue", 16), cursor="hand2",
            padx=3, pady=16)
        self._toggle_lbl.place(relx=1.0, rely=0.5, anchor="e", x=-1)
        self._toggle_lbl.bind("<Button-1>", lambda e: self._toggle_panel())

        self._canvas.bind("<Configure>",      self._on_canvas_resize)
        self._canvas.bind("<Double-Button-1>", lambda e: self._toggle_fit())
        self._canvas.bind("<ButtonPress-1>",   self._on_canvas_click)
        self._canvas.bind("<B1-Motion>",       self._drag_move)
        self._canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self._canvas.bind("<MouseWheel>",      self._on_scroll)

    def _build_toolbar(self):
        TBARBG = "#252527"
        self._toolbar = tk.Frame(self._canvas_wrap, bg=TBARBG,
                                 padx=6, pady=3)
        self._toolbar.pack(side=tk.BOTTOM, fill=tk.X)

        inner = tk.Frame(self._toolbar, bg=TBARBG)
        inner.pack()

        self._btn_prev = _make_icon_btn(
            inner, "◀", self._prev,
            bg=TBARBG, fg=TEXT, hover_bg=BG3, font=("Helvetica Neue", 11), pady=3)
        self._btn_prev.pack(side=tk.LEFT, padx=2)

        self._btn_100 = _make_icon_btn(
            inner, "100%", self._zoom_100,
            bg=TBARBG, fg=TEXT2, hover_bg=BG3, font=("Helvetica Neue", 10), pady=3)
        self._btn_100.pack(side=tk.LEFT, padx=2)

        self._btn_fit = _make_icon_btn(
            inner, "맞춤", self._zoom_fit,
            bg=TBARBG, fg=TEXT2, hover_bg=BG3, font=("Helvetica Neue", 10), pady=3)
        self._btn_fit.pack(side=tk.LEFT, padx=2)

        self._btn_next = _make_icon_btn(
            inner, "▶", self._next,
            bg=TBARBG, fg=TEXT, hover_bg=BG3, font=("Helvetica Neue", 11), pady=3)
        self._btn_next.pack(side=tk.LEFT, padx=2)

        self._update_toolbar_state()

    def _build_panel(self):
        self._panel = tk.Frame(self._main, bg=BG2, width=260, bd=0, highlightthickness=0)
        self._panel.pack(side=tk.RIGHT, fill=tk.Y)
        self._panel.pack_propagate(False)

        hdr = tk.Frame(self._panel, bg=BG3, pady=10)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="파일 정보", bg=BG3, fg=TEXT,
                 font=FONT_BOLD).pack(side=tk.LEFT, padx=12)
        close_lbl = tk.Label(hdr, text="✕", bg=BG3, fg=TEXT2,
                             font=FONT, cursor="hand2", padx=8)
        close_lbl.pack(side=tk.RIGHT)
        close_lbl.bind("<Button-1>", lambda e: self._toggle_panel())

        tk.Frame(self._panel, bg=BG3, height=1).pack(fill=tk.X)

        self._info_text = tk.Text(
            self._panel, bg=BG2, fg=TEXT, font=FONT_SM,
            relief=tk.FLAT, bd=0, highlightthickness=0,
            state=tk.DISABLED, wrap=tk.WORD,
            padx=14, pady=10, spacing1=1, spacing3=3,
            insertbackground=TEXT, selectbackground=ACCENT)
        self._info_text.pack(fill=tk.BOTH, expand=True)

        self._info_text.tag_configure("section",
            foreground=ACCENT, font=FONT_SM_BOLD, spacing1=8)
        self._info_text.tag_configure("key",
            foreground=TEXT2, font=FONT_SM)
        self._info_text.tag_configure("val",
            foreground=TEXT, font=FONT_SM)

    # ── 패널 토글 ────────────────────────────────────────────

    def _toggle_panel(self):
        if self._panel_visible:
            self._panel.pack_forget()
            self._toggle_lbl.config(text="‹")
            self._panel_visible = False
        else:
            self._panel.pack(side=tk.RIGHT, fill=tk.Y)
            self._toggle_lbl.config(text="›")
            self._panel_visible = True
        self.root.update_idletasks()
        self._show_image()

    # ── 키 바인딩 ────────────────────────────────────────────

    def _bind_keys(self):
        self.root.bind("<Escape>",    lambda e: self.root.destroy())
        self.root.bind("<Left>",      lambda e: self._prev())
        self.root.bind("<Right>",     lambda e: self._next())
        self.root.bind("<space>",     lambda e: (self._next(), "break"))
        self.root.bind("<BackSpace>", lambda e: self._delete_current())
        self.root.bind("<Delete>",    lambda e: self._delete_current())
        self.root.bind("+",           lambda e: self._zoom_100())
        self.root.bind("=",           lambda e: self._zoom_100())
        self.root.bind("-",           lambda e: self._zoom_fit())
        self.root.bind("<Meta-o>",    lambda e: self._open_dialog())

    # ── 파일 열기 ────────────────────────────────────────────

    def _open_dialog(self):
        img_exts = " ".join(f"*{e}" for e in SUPPORTED)
        arc_exts = " ".join(f"*{e}" for e in ARCHIVE_EXTS)
        path = filedialog.askopenfilename(
            parent=self.root,
            title="이미지 열기",
            filetypes=[("이미지 파일", img_exts),
                       ("압축 파일", arc_exts),
                       ("모든 파일", "*.*")])
        if path:
            self._open_path(path)

    def _open_path(self, path: str):
        p = Path(path).resolve()

        # 압축 파일이면 아카이브 모드로 전환
        if is_archive(p):
            self._open_archive(p)
            return

        # 기존 아카이브 정리
        if self._archive:
            self._archive.close()
            self._archive = None

        folder = p.parent
        self._images = sorted(
            [f for f in folder.iterdir()
             if f.suffix.lower() in SUPPORTED and f.is_file()],
            key=lambda f: f.name.lower())
        try:
            self._index = self._images.index(p)
        except ValueError:
            self._index = 0
        self._img_x = self._img_y = 0
        self._show_image()

    def _open_archive(self, archive_path: Path):
        """압축 파일을 폴더처럼 열어 내부 이미지 탐색."""
        if self._archive:
            self._archive.close()
        try:
            self._archive = ArchiveReader(archive_path)
        except Exception as e:
            messagebox.showerror("오류", f"압축 파일을 열 수 없습니다.\n{e}")
            return
        if not self._archive.entries:
            messagebox.showinfo("알림", "압축 파일에 이미지가 없습니다.")
            self._archive.close()
            self._archive = None
            return
        # 아카이브 엔트리 이름을 _images에 저장 (문자열을 Path로 감싸서 통일)
        self._images = [Path(name) for name in self._archive.entries]
        self._index = 0
        self._img_x = self._img_y = 0
        self._show_image()

    # ── 이미지 표시 ──────────────────────────────────────────

    def _show_image(self):
        self._canvas.delete("all")
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        if not self._images:
            self._canvas.create_text(
                cw // 2, ch // 2 - 28,
                text="이미지를 열어주세요",
                fill=TEXT2, font=FONT)
            open_btn = _make_icon_btn(
                self._canvas, "  열기  ", self._open_dialog,
                bg=ACCENT, fg="white", hover_bg="#0066cc",
                font=FONT_BOLD, padx=20, pady=10)
            self._canvas.create_window(cw // 2, ch // 2 + 24, window=open_btn)
            self.root.title("TViewer")
            return

        path = self._images[self._index]
        display_name = PurePosixPath(path).name if self._archive else path.name
        if self._archive:
            self.root.title(
                f"TViewer  —  {self._archive.path.name} / {display_name}"
                f"  ({self._index + 1} / {len(self._images)})")
        else:
            self.root.title(
                f"TViewer  —  {display_name}  ({self._index + 1} / {len(self._images)})")

        if self._archive:
            img = self._archive.get_image(str(path))
        else:
            img = self._loader.get(path)
        if img is None:
            self._canvas.create_text(
                cw // 2, ch // 2,
                text="이미지를 열 수 없습니다", fill=TEXT2, font=FONT)
            return

        iw, ih = img.size

        if self._fit_mode:
            scale = min(cw / iw, ch / ih)
            nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
            resample = Image.LANCZOS if scale < 0.8 else Image.BILINEAR
            display = img.resize((nw, nh), resample)
            x, y = cw // 2, ch // 2
        else:
            display = img
            nw, nh = iw, ih
            if self._img_x == 0 and self._img_y == 0:
                self._img_x = cw // 2
                self._img_y = ch // 2
            x, y = self._img_x, self._img_y

        self._photo = self._to_photo(display)
        self._canvas.create_image(x, y, image=self._photo, anchor=tk.CENTER)

        self._update_toolbar_state()
        self._update_info(path, img)
        self._preload_neighbors()

    @staticmethod
    def _to_photo(img: Image.Image) -> tk.PhotoImage:
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PPM")
        photo = tk.PhotoImage()
        photo.put(buf.getvalue())
        return photo

    # ── 내비게이션 ───────────────────────────────────────────

    def _prev(self):
        if not self._images:
            return
        self._index = (self._index - 1) % len(self._images)
        self._img_x = self._img_y = 0
        self._show_image()

    def _next(self):
        if not self._images:
            return
        self._index = (self._index + 1) % len(self._images)
        self._img_x = self._img_y = 0
        self._show_image()

    def _zoom_fit(self):
        self._fit_mode = True
        self._img_x = self._img_y = 0
        self._show_image()

    def _zoom_100(self):
        self._fit_mode = False
        self._img_x = self._img_y = 0
        self._show_image()

    def _toggle_fit(self):
        if self._fit_mode:
            self._zoom_100()
        else:
            self._zoom_fit()

    def _update_toolbar_state(self):
        TBARBG = "#252527"
        self._btn_fit.config(
            fg=ACCENT if self._fit_mode else TEXT2,
            bg=TBARBG)
        self._btn_100.config(
            fg=ACCENT if not self._fit_mode else TEXT2,
            bg=TBARBG)

    # ── 드래그 (100% 모드 패닝) ──────────────────────────────

    def _on_canvas_click(self, event):
        self._click_x = event.x
        self._click_y = event.y
        self._dragged = False
        if not self._fit_mode:
            self._drag_start_x = event.x
            self._drag_start_y = event.y
            self._canvas.config(cursor="fleur")

    def _on_canvas_release(self, event):
        self._canvas.config(cursor="arrow")
        if self._dragged or not self._images:
            return
        cw = self._canvas.winfo_width()
        if cw < 10:
            return
        if self._click_x < cw / 3:
            self._prev()
        elif self._click_x > cw * 2 / 3:
            self._next()

    def _drag_move(self, event):
        self._dragged = True
        if not self._fit_mode and self._images:
            dx = event.x - self._drag_start_x
            dy = event.y - self._drag_start_y
            self._drag_start_x = event.x
            self._drag_start_y = event.y
            self._img_x += dx
            self._img_y += dy
            self._canvas.move("all", dx, dy)

    def _on_scroll(self, event):
        if event.delta < -30:
            self._next()
        elif event.delta > 30:
            self._prev()

    # ── 삭제 ─────────────────────────────────────────────────

    def _delete_current(self):
        if not self._images or self._archive:
            return
        path = self._images[self._index]
        if not messagebox.askyesno(
                "파일 삭제",
                f"삭제하시겠습니까?\n\n{path.name}",
                icon="warning"):
            return
        try:
            path.unlink()
            self._loader.invalidate(path)
            self._images.pop(self._index)
            if self._images:
                self._index = min(self._index, len(self._images) - 1)
                self._img_x = self._img_y = 0
                self._show_image()
            else:
                self._index = 0
                self._canvas.delete("all")
                self.root.title("TViewer")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    # ── 프리로드 ─────────────────────────────────────────────

    def _preload_neighbors(self):
        if not self._images or self._archive:
            return
        n = len(self._images)
        targets = [
            self._images[(self._index + 1) % n],
            self._images[(self._index - 1) % n],
            self._images[(self._index + 2) % n],
            self._images[(self._index - 2) % n],
        ]
        self._loader.preload(targets)

    # ── 캔버스 리사이즈 ──────────────────────────────────────

    def _on_canvas_resize(self, event):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(80, self._show_image)

    # ── EXIF / 파일 정보 패널 ────────────────────────────────

    def _update_info(self, path: Path, img: Image.Image):
        if not self._panel_visible:
            return

        t = self._info_text
        t.config(state=tk.NORMAL)
        t.delete("1.0", tk.END)

        def row(key, val):
            t.insert(tk.END, f"{key}\n", "key")
            t.insert(tk.END, f"{val}\n", "val")

        def section(title):
            t.insert(tk.END, f"\n{title}\n", "section")

        # 파일 정보
        section("파일")
        display_name = PurePosixPath(path).name if self._archive else path.name
        row("이름", display_name)
        if self._archive:
            row("압축파일", self._archive.path.name)
            size_b = self._archive.get_entry_size(str(path))
            if size_b is not None:
                size_str = (f"{size_b / 1_048_576:.1f} MB"
                            if size_b >= 1_048_576
                            else f"{size_b / 1024:.0f} KB")
            else:
                size_str = "—"
        else:
            try:
                size_b = path.stat().st_size
                size_str = (f"{size_b / 1_048_576:.1f} MB"
                            if size_b >= 1_048_576
                            else f"{size_b / 1024:.0f} KB")
            except Exception:
                size_str = "—"
        row("크기", size_str)
        row("해상도", f"{img.width} × {img.height} px")
        row("형식", img.format or PurePosixPath(path).suffix.upper().lstrip("."))
        row("위치", f"{self._index + 1} / {len(self._images)}")

        # EXIF — 기본 태그 + ExifIFD (카메라 설정값)
        exif_data = {}
        try:
            _base = img.getexif()
            for tag_id, val in _base.items():
                exif_data[TAGS.get(tag_id, tag_id)] = val
            try:
                for tag_id, val in _base.get_ifd(IFD.Exif).items():
                    exif_data[TAGS.get(tag_id, tag_id)] = val
            except Exception:
                pass
        except Exception:
            pass

        if exif_data:
            section("촬영 정보")

            def ex(tag, label, fmt=None):
                v = exif_data.get(tag)
                if v is None:
                    return
                try:
                    row(label, fmt(v) if fmt else str(v))
                except Exception:
                    pass

            ex("DateTimeOriginal", "촬영일시")
            ex("Make", "제조사")
            ex("Model", "카메라")
            ex("LensModel", "렌즈")

            fl = exif_data.get("FocalLength")
            if fl is not None:
                try:
                    row("초점거리", f"{float(fl):.0f} mm")
                except Exception:
                    pass

            fn = exif_data.get("FNumber")
            if fn is not None:
                try:
                    row("조리개", f"f/{float(fn):.1f}")
                except Exception:
                    pass

            et = exif_data.get("ExposureTime")
            if et is not None:
                try:
                    f = float(et)
                    row("셔터", f"1/{round(1/f)}" if f < 1 else f"{f:.1f}s")
                except Exception:
                    pass

            iso = exif_data.get("ISOSpeedRatings") or exif_data.get("PhotographicSensitivity")
            if iso:
                row("ISO", str(iso))

        t.config(state=tk.DISABLED)
