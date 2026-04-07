import os
import sys
import threading
import difflib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance, ImageDraw

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except Exception:
    HAS_DND = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BG = "#F5F5F3"
ACCENT = "#2D6A4F"
BTN_BG = "#E8E8E6"
BTN_FG = "#1A1A1A"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)

SUPPORTED_FORMATS = [
    ("Obrazy", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp"),
    ("JPEG", "*.jpg *.jpeg"),
    ("PNG", "*.png"),
    ("BMP", "*.bmp"),
    ("TIFF", "*.tiff *.tif"),
    ("WEBP", "*.webp"),
    ("Wszystkie pliki", "*.*"),
]


class ImagePanel(tk.Frame):
    def __init__(self, master, label, **kwargs):
        super().__init__(master, bg=BG, **kwargs)
        self.label = label
        self.pil_image = None
        self.display_image = None
        self.photo = None
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self._drag_start = None
        self.overlay_items = []
        self.on_zoom_change = None
        self.on_pan_change = None
        self.sync_var = None

        self._build()

    def _build(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill=tk.X, padx=4, pady=(4, 0))

        tk.Label(header, text=self.label, font=FONT_BOLD, bg=BG, fg=ACCENT).pack(side=tk.LEFT)
        tk.Button(header, text="Otwórz", font=FONT_SMALL, bg=BTN_BG, fg=BTN_FG,
                  relief=tk.FLAT, padx=8, command=self.open_file).pack(side=tk.RIGHT)

        canvas_frame = tk.Frame(self, bg="#CCCCCA", bd=1, relief=tk.SUNKEN)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.canvas = tk.Canvas(canvas_frame, bg="#DDDDD8", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.info_var = tk.StringVar(value="Brak obrazu")
        tk.Label(self, textvariable=self.info_var, font=FONT_SMALL, bg=BG,
                 fg="#555555").pack(fill=tk.X, padx=4, pady=(0, 4))

        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self.canvas.bind("<Double-Button-1>", lambda e: self.fit())
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<Button-4>", self._on_scroll)
        self.canvas.bind("<Button-5>", self._on_scroll)
        self.canvas.bind("<Configure>", lambda e: self.redraw())

        if HAS_DND:
            self.canvas.drop_target_register(DND_FILES)
            self.canvas.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event):
        path = event.data.strip().strip("{}")
        if path:
            self.load_image(path)

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=SUPPORTED_FORMATS,
                                          title=f"Otwórz obraz - {self.label}")
        if path:
            self.load_image(path)

    def load_image(self, path):
        try:
            img = Image.open(path)
            img.load()
            self.pil_image = img
            self.filepath = path
            self.fit()
            size_kb = os.path.getsize(path) / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
            self.info_var.set(
                f"{os.path.basename(path)}  |  {img.width}×{img.height}  |  {size_str}"
            )
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można otworzyć pliku:\n{e}", parent=self)

    def fit(self):
        if self.pil_image is None:
            return
        cw = self.canvas.winfo_width() or 400
        ch = self.canvas.winfo_height() or 400
        iw, ih = self.pil_image.size
        self.zoom = min(cw / iw, ch / ih, 1.0)
        self.offset_x = (cw - iw * self.zoom) / 2
        self.offset_y = (ch - ih * self.zoom) / 2
        self.redraw()

    def reset(self):
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.redraw()

    def zoom_in(self, factor=1.2):
        self._zoom_by(factor)

    def zoom_out(self, factor=1.2):
        self._zoom_by(1.0 / factor)

    def _zoom_by(self, factor, cx=None, cy=None):
        if self.pil_image is None:
            return
        cw = self.canvas.winfo_width() or 400
        ch = self.canvas.winfo_height() or 400
        if cx is None:
            cx = cw / 2
        if cy is None:
            cy = ch / 2
        new_zoom = max(0.05, min(self.zoom * factor, 40.0))
        ratio = new_zoom / self.zoom
        self.offset_x = cx - ratio * (cx - self.offset_x)
        self.offset_y = cy - ratio * (cy - self.offset_y)
        self.zoom = new_zoom
        self.redraw()
        if self.sync_var and self.sync_var.get() and self.on_zoom_change:
            self.on_zoom_change(self.zoom, self.offset_x, self.offset_y)

    def _on_scroll(self, event):
        if event.num == 4 or event.delta > 0:
            factor = 1.15
        else:
            factor = 1 / 1.15
        self._zoom_by(factor, event.x, event.y)

    def _on_drag_start(self, event):
        self._drag_start = (event.x, event.y)

    def _on_drag(self, event):
        if self._drag_start is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._drag_start = (event.x, event.y)
        self.offset_x += dx
        self.offset_y += dy
        self.redraw()
        if self.sync_var and self.sync_var.get() and self.on_pan_change:
            self.on_pan_change(self.offset_x, self.offset_y)

    def _on_drag_end(self, event):
        self._drag_start = None

    def redraw(self):
        self.canvas.delete("all")
        if self.pil_image is None:
            return
        iw, ih = self.pil_image.size
        nw = max(1, int(iw * self.zoom))
        nh = max(1, int(ih * self.zoom))
        try:
            resized = self.pil_image.resize((nw, nh), Image.LANCZOS)
        except Exception:
            return

        if self.overlay_items:
            draw = ImageDraw.Draw(resized)
            for item in self.overlay_items:
                x1, y1, x2, y2, color = item
                sx1 = int(x1 * self.zoom)
                sy1 = int(y1 * self.zoom)
                sx2 = int(x2 * self.zoom)
                sy2 = int(y2 * self.zoom)
                for t in range(2):
                    draw.rectangle([sx1-t, sy1-t, sx2+t, sy2+t], outline=color)

        self.photo = ImageTk.PhotoImage(resized)
        self.canvas.create_image(
            int(self.offset_x), int(self.offset_y),
            anchor=tk.NW, image=self.photo
        )

    def clear_overlays(self):
        self.overlay_items = []
        self.redraw()

    def add_overlay(self, x1, y1, x2, y2, color):
        self.overlay_items.append((x1, y1, x2, y2, color))

    def set_sync(self, zoom, ox, oy):
        self.zoom = zoom
        self.offset_x = ox
        self.offset_y = oy
        self.redraw()


class App(TkinterDnD.Tk if HAS_DND else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ImageCompare - Porównywanie dokumentów")
        self.geometry("1280x800")
        self.configure(bg=BG)
        self.minsize(900, 600)

        base = get_base_path()
        tess_exe = os.path.join(base, "tesseract", "tesseract.exe")
        tess_data = os.path.join(base, "tessdata")

        if HAS_TESSERACT:
            if os.path.isfile(tess_exe):
                pytesseract.pytesseract.tesseract_cmd = tess_exe
            if os.path.isdir(tess_data):
                os.environ["TESSDATA_PREFIX"] = tess_data

        self.sync_var = tk.BooleanVar(value=True)
        self._build_ui()

    def _build_ui(self):
        toolbar = tk.Frame(self, bg=BTN_BG, pady=4)
        toolbar.pack(fill=tk.X)

        def tbtn(text, cmd, sep=False):
            if sep:
                tk.Label(toolbar, text="|", bg=BTN_BG, fg="#AAAAAA").pack(side=tk.LEFT, padx=2)
            b = tk.Button(toolbar, text=text, font=FONT_SMALL, bg=BTN_BG, fg=BTN_FG,
                          relief=tk.FLAT, padx=10, pady=2, command=cmd,
                          activebackground="#D0D0CE")
            b.pack(side=tk.LEFT, padx=1)
            return b

        tbtn("Zoom +", self.zoom_in)
        tbtn("Zoom -", self.zoom_out)
        tbtn("Dopasuj", self.fit_all)
        tbtn("Reset", self.reset_all, sep=True)
        tbtn("PORÓWNAJ OCR", self.start_ocr, sep=True)
        tbtn("Wyczyść", self.clear_results)

        tk.Checkbutton(toolbar, text="Synchronizuj", variable=self.sync_var,
                       bg=BTN_BG, font=FONT_SMALL, fg=BTN_FG,
                       activebackground=BTN_BG).pack(side=tk.RIGHT, padx=10)

        panels_frame = tk.Frame(self, bg=BG)
        panels_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.panel_a = ImagePanel(panels_frame, "Zdjęcie A  ·  Wzór")
        self.panel_a.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Frame(panels_frame, bg="#CCCCCA", width=2).pack(side=tk.LEFT, fill=tk.Y)

        self.panel_b = ImagePanel(panels_frame, "Zdjęcie B  ·  Porównywane")
        self.panel_b.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.panel_a.sync_var = self.sync_var
        self.panel_b.sync_var = self.sync_var
        self.panel_a.on_zoom_change = lambda z, ox, oy: self.panel_b.set_sync(z, ox, oy)
        self.panel_a.on_pan_change = lambda ox, oy: self.panel_b.set_sync(
            self.panel_b.zoom, ox, oy)
        self.panel_b.on_zoom_change = lambda z, ox, oy: self.panel_a.set_sync(z, ox, oy)
        self.panel_b.on_pan_change = lambda ox, oy: self.panel_a.set_sync(
            self.panel_a.zoom, ox, oy)

        bottom = tk.Frame(self, bg=BG, height=180)
        bottom.pack(fill=tk.X, padx=4, pady=(0, 4))
        bottom.pack_propagate(False)

        tk.Label(bottom, text="Lista różnic:", font=FONT_BOLD, bg=BG).pack(anchor=tk.W)

        diff_frame = tk.Frame(bottom, bg=BG)
        diff_frame.pack(fill=tk.BOTH, expand=True)

        self.diff_text = tk.Text(diff_frame, font=FONT_SMALL, bg="#FAFAF8", fg=BTN_FG,
                                 relief=tk.FLAT, wrap=tk.WORD, height=8,
                                 state=tk.DISABLED)
        sb = ttk.Scrollbar(diff_frame, orient=tk.VERTICAL, command=self.diff_text.yview)
        self.diff_text.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.diff_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.diff_text.tag_configure("red", foreground="#CC0000")
        self.diff_text.tag_configure("green", foreground="#007700")
        self.diff_text.tag_configure("gray", foreground="#777777")

        status_frame = tk.Frame(self, bg="#E0E0DE")
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_var = tk.StringVar(value="Gotowy. Wczytaj obrazy i kliknij PORÓWNAJ OCR.")
        tk.Label(status_frame, textvariable=self.status_var, font=FONT_SMALL,
                 bg="#E0E0DE", anchor=tk.W, padx=8).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress = ttk.Progressbar(status_frame, length=200, mode="determinate")
        self.progress.pack(side=tk.RIGHT, padx=8, pady=2)

    def zoom_in(self):
        self.panel_a.zoom_in()
        self.panel_b.zoom_in()

    def zoom_out(self):
        self.panel_a.zoom_out()
        self.panel_b.zoom_out()

    def fit_all(self):
        self.panel_a.fit()
        self.panel_b.fit()

    def reset_all(self):
        self.panel_a.reset()
        self.panel_b.reset()

    def clear_results(self):
        self.panel_a.clear_overlays()
        self.panel_b.clear_overlays()
        self._set_diff_text("")
        self.status_var.set("Wyczyszczono wyniki.")

    def _set_diff_text(self, text, segments=None):
        self.diff_text.configure(state=tk.NORMAL)
        self.diff_text.delete("1.0", tk.END)
        if segments:
            for seg_text, tag in segments:
                self.diff_text.insert(tk.END, seg_text, tag)
        else:
            self.diff_text.insert(tk.END, text)
        self.diff_text.configure(state=tk.DISABLED)

    def start_ocr(self):
        if not HAS_TESSERACT:
            messagebox.showerror("Błąd",
                "Biblioteka pytesseract nie jest zainstalowana.\n"
                "Uruchom: pip install pytesseract")
            return
        if self.panel_a.pil_image is None or self.panel_b.pil_image is None:
            messagebox.showwarning("Brak obrazów",
                "Wczytaj oba obrazy przed porównaniem.")
            return

        self.status_var.set("Trwa OCR... proszę czekać.")
        self.progress["value"] = 0
        t = threading.Thread(target=self._run_ocr, daemon=True)
        t.start()

    def _run_ocr(self):
        try:
            self._ocr_task()
        except Exception as e:
            self.after(0, lambda: messagebox.showerror(
                "Błąd OCR", f"Wystąpił błąd podczas OCR:\n{e}"))
            self.after(0, lambda: self.status_var.set("Błąd OCR."))
            self.after(0, lambda: self.progress.configure(value=0))

    def _preprocess(self, img):
        gray = img.convert("L")
        enhanced = ImageEnhance.Contrast(gray).enhance(2.0)
        return enhanced

    def _ocr_image(self, img, label):
        processed = self._preprocess(img)
        try:
            data = pytesseract.image_to_data(
                processed,
                lang="pol+eng",
                output_type=pytesseract.Output.DICT,
                config="--psm 3"
            )
        except pytesseract.TesseractNotFoundError:
            raise RuntimeError(
                "Nie znaleziono Tesseract.\n"
                "Upewnij się, że folder tesseract/ jest w katalogu programu."
            )
        except Exception as e:
            raise RuntimeError(f"Błąd OCR ({label}): {e}")
        return data

    def _ocr_task(self):
        self.after(0, lambda: self.progress.configure(value=10))
        self.after(0, lambda: self.status_var.set("OCR: Obraz A..."))

        data_a = self._ocr_image(self.panel_a.pil_image, "A")
        self.after(0, lambda: self.progress.configure(value=40))
        self.after(0, lambda: self.status_var.set("OCR: Obraz B..."))

        data_b = self._ocr_image(self.panel_b.pil_image, "B")
        self.after(0, lambda: self.progress.configure(value=70))
        self.after(0, lambda: self.status_var.set("Porównywanie tekstu..."))

        words_a = self._extract_words(data_a)
        words_b = self._extract_words(data_b)

        text_a = [w["text"] for w in words_a]
        text_b = [w["text"] for w in words_b]

        matcher = difflib.SequenceMatcher(None, text_a, text_b, autojunk=False)
        opcodes = matcher.get_opcodes()

        self.after(0, lambda: self.panel_a.clear_overlays())
        self.after(0, lambda: self.panel_b.clear_overlays())

        segments = []
        diff_count = 0

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal":
                continue
            if tag in ("delete", "replace"):
                for w in words_a[i1:i2]:
                    self.after(0, lambda bx=w: self.panel_a.add_overlay(
                        bx["x"], bx["y"], bx["x"] + bx["w"], bx["y"] + bx["h"], "#FF0000"))
                    seg = f'[BRAK W B] "{w["text"]}"\n'
                    segments.append((seg, "red"))
                    diff_count += 1
            if tag in ("insert", "replace"):
                for w in words_b[j1:j2]:
                    self.after(0, lambda bx=w: self.panel_b.add_overlay(
                        bx["x"], bx["y"], bx["x"] + bx["w"], bx["y"] + bx["h"], "#00AA00"))
                    seg = f'[DODANO W B] "{w["text"]}"\n'
                    segments.append((seg, "green"))
                    diff_count += 1

        self.after(0, lambda: self.panel_a.redraw())
        self.after(0, lambda: self.panel_b.redraw())
        self.after(0, lambda: self.progress.configure(value=100))

        if diff_count == 0:
            self.after(0, lambda: self._set_diff_text(
                "Dokumenty sa identyczne - brak roznic w tekscie OCR."))
            self.after(0, lambda: self.status_var.set(
                "Gotowe. Dokumenty sa identyczne."))
        else:
            self.after(0, lambda: self._set_diff_text("", segments))
            self.after(0, lambda: self.status_var.set(
                f"Gotowe. Znaleziono {diff_count} roznic."))

    def _extract_words(self, data):
        words = []
        n = len(data["text"])
        for i in range(n):
            word = data["text"][i].strip()
            conf = int(data["conf"][i]) if str(data["conf"][i]).lstrip("-").isdigit() else -1
            if word and conf > 30:
                words.append({
                    "text": word,
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "w": data["width"][i],
                    "h": data["height"][i],
                })
        return words


if __name__ == "__main__":
    app = App()
    app.mainloop()
