#!/usr/bin/env python3
"""
Strana — UI inspirat din 4K Downloader
Requires: pip install yt-dlp customtkinter Pillow
"""

import os
os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import subprocess
import sys
import io
import urllib.request

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    PIL_AVAILABLE = False

try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    yt_dlp = None
    YT_DLP_AVAILABLE = False


# ── Constante ─────────────────────────────────────────────────────────────────
ACCENT       = "#ff0033"
ACCENT_HOVER = "#cc0022"
BG_MAIN      = "#1a1a1a"
BG_CARD      = "#242424"
BG_INPUT     = "#1e1e1e"
BG_TOOLBAR   = "#111111"

if getattr(sys, "frozen", False):
    _BASE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
FFMPEG_PATH = os.path.join(_BASE, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")

QUALITY_OPTIONS = [
    ("4K  (2160p)",      "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best"),
    ("2K  (1440p)",      "bestvideo[height<=1440]+bestaudio/best[height<=1440]/best"),
    ("FHD (1080p) ★",   "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"),
    ("HD  (720p)",       "bestvideo[height<=720]+bestaudio/best[height<=720]/best"),
    ("SD  (480p)",       "bestvideo[height<=480]+bestaudio/best[height<=480]/best"),
    ("360p",             "bestvideo[height<=360]+bestaudio/best[height<=360]/best"),
    ("Audio only (MP3)", "bestaudio/best"),
]
QUALITY_LABELS = [q[0] for q in QUALITY_OPTIONS]

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_valid_url(url):
    return url.startswith(("http://", "https://"))

def human_size(n):
    if not n:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

def human_speed(bps):
    return f"{human_size(bps)}/s" if bps else ""


# ── Card descărcare ───────────────────────────────────────────────────────────
class DownloadCard(ctk.CTkFrame):
    def __init__(self, parent, title, quality_label, thumbnail_url=""):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=10, height=90)
        self.pack_propagate(False)

        self.is_active    = True
        self._cancel_flag = False
        self._output_dir  = ""
        self._ctk_img     = None

        # Thumbnail
        self._thumb = ctk.CTkLabel(
            self, text="", width=120, height=68,
            fg_color="#181818", corner_radius=6
        )
        self._thumb.pack(side="left", padx=(12, 10), pady=11)

        if thumbnail_url and PIL_AVAILABLE:
            threading.Thread(target=self._load_thumb, args=(thumbnail_url,), daemon=True).start()

        # Centru
        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.pack(side="left", fill="both", expand=True, pady=11)

        display_title = (title[:66] + "…") if len(title) > 66 else title
        ctk.CTkLabel(
            mid, text=display_title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#eeeeee", anchor="w"
        ).pack(fill="x", anchor="w")

        badge_row = ctk.CTkFrame(mid, fg_color="transparent")
        badge_row.pack(fill="x", anchor="w", pady=(3, 0))

        is_audio   = "Audio" in quality_label
        badge_col  = "#4a148c" if is_audio else "#1565c0"
        badge_text = "MP3" if is_audio else (quality_label.strip().split()[0] + " MP4")
        ctk.CTkLabel(
            badge_row, text=f"  {badge_text}  ",
            fg_color=badge_col, corner_radius=4,
            font=ctk.CTkFont(size=10, weight="bold"), text_color="white"
        ).pack(side="left")

        self._size_lbl = ctk.CTkLabel(
            badge_row, text="",
            font=ctk.CTkFont(size=11), text_color="#555555"
        )
        self._size_lbl.pack(side="left", padx=(8, 0))

        self._progress = ctk.CTkProgressBar(mid, height=5, progress_color=ACCENT, fg_color="#333333")
        self._progress.set(0)
        self._progress.pack(fill="x", pady=(6, 3))

        self._speed_lbl = ctk.CTkLabel(
            mid, text="Pregătire...",
            font=ctk.CTkFont(size=11), text_color="#555555", anchor="w"
        )
        self._speed_lbl.pack(fill="x", anchor="w")

        # Dreapta
        right = ctk.CTkFrame(self, fg_color="transparent", width=38)
        right.pack(side="right", padx=10, pady=11)
        right.pack_propagate(False)

        self._status_lbl = ctk.CTkLabel(right, text="●", font=ctk.CTkFont(size=18), text_color=ACCENT)
        self._status_lbl.pack()

        self._action_btn = ctk.CTkButton(
            right, text="✕", width=28, height=28,
            fg_color="#333333", hover_color="#cc0000",
            font=ctk.CTkFont(size=11), command=self._cancel
        )
        self._action_btn.pack(pady=(4, 0))

    def _load_thumb(self, url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read()
            img = Image.open(io.BytesIO(data))
            img = img.resize((120, 68), Image.LANCZOS if hasattr(Image, "LANCZOS") else Image.Resampling.LANCZOS)
            self._ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 68))
            self.after(0, lambda: self._thumb.configure(image=self._ctk_img, text=""))
        except Exception:
            pass

    def update_progress(self, pct, speed=0, eta=0, downloaded=0, total=0):
        self._progress.set(pct / 100)
        if total:
            self._size_lbl.configure(text=f"{human_size(downloaded)} / {human_size(total)}")
        parts = []
        if speed:
            parts.append(human_speed(speed))
        if eta:
            parts.append(f"ETA {int(eta)}s")
        self._speed_lbl.configure(text="  ".join(parts) or "Descărcare...")

    def set_done(self, output_dir=""):
        self.is_active   = False
        self._output_dir = output_dir
        self._progress.set(1)
        self._status_lbl.configure(text="✓", text_color="#4caf50")
        self._speed_lbl.configure(text="Complet")
        self._action_btn.configure(text="📁", command=self._open_folder)

    def set_error(self, msg=""):
        self.is_active = False
        self._progress.set(0)
        self._status_lbl.configure(text="✕", text_color="#f44336")
        self._speed_lbl.configure(text=f"Eroare: {msg[:70]}")
        self._action_btn.configure(state="disabled")

    def _cancel(self):
        self._cancel_flag = True
        self.is_active    = False
        self._status_lbl.configure(text="—", text_color="#666666")
        self._speed_lbl.configure(text="Anulat")
        self._action_btn.configure(state="disabled")

    def _open_folder(self):
        d = self._output_dir or os.path.expanduser("~/Downloads")
        if sys.platform == "darwin":
            subprocess.run(["open", d])
        elif sys.platform == "win32":
            subprocess.run(["explorer", d])
        else:
            subprocess.run(["xdg-open", d])


# ── Dialog Preferințe ─────────────────────────────────────────────────────────
class PrefsDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self._app = parent
        self.title("Preferințe")
        self.geometry("460x170")
        self.resizable(False, False)
        self.grab_set()

        ctk.CTkLabel(self, text="Folder descărcare:", font=ctk.CTkFont(size=12)).pack(padx=24, pady=(22, 5), anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24)

        self._dir = ctk.CTkEntry(row, height=36, fg_color=BG_INPUT)
        self._dir.insert(0, parent.download_dir)
        self._dir.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Alege", width=70, command=self._browse).pack(side="left", padx=(8, 0))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=18)
        ctk.CTkButton(btn_row, text="Salvează", command=self._save, width=100,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Renunță", command=self.destroy,
                      fg_color="#333333", hover_color="#444444", width=90).pack(side="left")

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self._app.download_dir)
        if d:
            self._dir.delete(0, "end")
            self._dir.insert(0, d)

    def _save(self):
        self._app.download_dir = self._dir.get()
        self._app._dir_entry.delete(0, "end")
        self._app._dir_entry.insert(0, self._app.download_dir)
        self._app._dir_lbl.configure(text=f"📁  {self._app.download_dir}")
        self.destroy()


# ── App principal ─────────────────────────────────────────────────────────────
class StranaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YTD by Mircea Carmanus")
        self.geometry("940x600")
        self.minsize(740, 480)
        self.configure(fg_color=BG_MAIN)

        self.download_dir = os.path.expanduser("~/Downloads")
        self._cards       = []

        self._build_ui()

        # fix macOS white window
        self.withdraw()
        self._after_fix_id = self.after(300, self._show_window)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if not YT_DLP_AVAILABLE:
            self.after(400, self._ask_install)

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Toolbar (logo + preferințe) ───────────────────────────────────────
        toolbar = ctk.CTkFrame(self, height=54, fg_color=BG_TOOLBAR, corner_radius=0)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        ctk.CTkLabel(toolbar, text="YTD",
                     font=ctk.CTkFont(size=12), text_color="#555555").pack(side="left", padx=(18, 0))

        yt_color = "#4caf50" if YT_DLP_AVAILABLE else "#f44336"
        yt_text  = "● yt-dlp" if YT_DLP_AVAILABLE else "● yt-dlp lipsește"
        ctk.CTkLabel(toolbar, text=yt_text,
                     font=ctk.CTkFont(size=10), text_color=yt_color).pack(side="left", padx=14)

        ctk.CTkButton(
            toolbar, text="⚙  Preferințe",
            command=lambda: PrefsDialog(self),
            fg_color="transparent", hover_color="#2a2a2a",
            text_color="#666666", font=ctk.CTkFont(size=12), width=120, height=34
        ).pack(side="right", padx=14)

        # ── Separator ─────────────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color="#2a2a2a", corner_radius=0).pack(fill="x")

        # ── Panou introducere URL ─────────────────────────────────────────────
        input_panel = ctk.CTkFrame(self, fg_color="#171717", corner_radius=0)
        input_panel.pack(fill="x", padx=0)

        inner = ctk.CTkFrame(input_panel, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=14)

        # Rând 1: etichetă URL
        ctk.CTkLabel(inner, text="URL VIDEO / PLAYLIST",
                     font=ctk.CTkFont(size=10, weight="bold"), text_color="#444444").pack(anchor="w")

        # Rând 2: câmp URL + buton DOWNLOAD
        url_row = ctk.CTkFrame(inner, fg_color="transparent")
        url_row.pack(fill="x", pady=(4, 10))

        self._url_entry = ctk.CTkEntry(
            url_row,
            placeholder_text="Lipește URL-ul video (YouTube, Facebook, Vimeo…)",
            height=42, fg_color=BG_INPUT,
            border_color="#2e2e2e", border_width=1,
            font=ctk.CTkFont(size=13),
            text_color="#dddddd"
        )
        self._url_entry.pack(side="left", fill="x", expand=True)
        self._url_entry.bind("<Return>", lambda _: self._on_download_click())

        ctk.CTkButton(
            url_row, text="Paste",
            command=self._paste_clipboard,
            fg_color="#2a2a2a", hover_color="#383838",
            text_color="#888888", font=ctk.CTkFont(size=12),
            width=62, height=42
        ).pack(side="left", padx=(6, 0))

        # Rând 3: calitate + folder + buton download
        options_row = ctk.CTkFrame(inner, fg_color="transparent")
        options_row.pack(fill="x")

        # Calitate
        q_frame = ctk.CTkFrame(options_row, fg_color="transparent")
        q_frame.pack(side="left")
        ctk.CTkLabel(q_frame, text="CALITATE",
                     font=ctk.CTkFont(size=9, weight="bold"), text_color="#3a3a3a").pack(anchor="w")
        self._quality_var = ctk.StringVar(value=QUALITY_LABELS[2])  # 1080p implicit
        self._quality_combo = ctk.CTkComboBox(
            q_frame,
            values=QUALITY_LABELS,
            variable=self._quality_var,
            width=185, height=36,
            fg_color=BG_INPUT, border_color="#2e2e2e",
            button_color="#2e2e2e", button_hover_color="#3a3a3a",
            dropdown_fg_color="#1e1e1e",
            font=ctk.CTkFont(size=12), text_color="#cccccc",
            state="readonly"
        )
        self._quality_combo.pack()

        # Folder
        dir_frame = ctk.CTkFrame(options_row, fg_color="transparent")
        dir_frame.pack(side="left", padx=(14, 0))
        ctk.CTkLabel(dir_frame, text="FOLDER SALVARE",
                     font=ctk.CTkFont(size=9, weight="bold"), text_color="#3a3a3a").pack(anchor="w")
        self._dir_entry = ctk.CTkEntry(
            dir_frame, width=280, height=36,
            fg_color=BG_INPUT, border_color="#2e2e2e",
            font=ctk.CTkFont(size=11), text_color="#666666"
        )
        self._dir_entry.insert(0, self.download_dir)
        self._dir_entry.pack(side="left")
        ctk.CTkButton(dir_frame, text="...", width=36, height=36,
                      fg_color="#2a2a2a", hover_color="#383838",
                      text_color="#888888",
                      command=self._choose_folder).pack(side="left", padx=(4, 0))

        # Playlist toggle
        pl_frame = ctk.CTkFrame(options_row, fg_color="transparent")
        pl_frame.pack(side="left", padx=(14, 0))
        ctk.CTkLabel(pl_frame, text="MOD",
                     font=ctk.CTkFont(size=9, weight="bold"), text_color="#3a3a3a").pack(anchor="w")
        self._playlist_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            pl_frame, text="Playlist complet",
            variable=self._playlist_var,
            font=ctk.CTkFont(size=12), text_color="#888888",
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=36, checkbox_width=18, checkbox_height=18
        ).pack(anchor="w", pady=(4, 0))

        # Buton DOWNLOAD
        self._dl_btn = ctk.CTkButton(
            options_row, text="⬇  DOWNLOAD",
            command=self._on_download_click,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
            width=160, height=36
        )
        self._dl_btn.pack(side="right")

        # Separator
        ctk.CTkFrame(self, height=1, fg_color="#222222", corner_radius=0).pack(fill="x")

        # ── Zona de descărcări ────────────────────────────────────────────────
        self._content = ctk.CTkFrame(self, fg_color=BG_MAIN, corner_radius=0)
        self._content.pack(fill="both", expand=True)

        # Empty state
        self._empty = ctk.CTkFrame(self._content, fg_color="transparent")
        self._empty.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(self._empty, text="⬇", font=ctk.CTkFont(size=60), text_color="#232323").pack()
        ctk.CTkLabel(self._empty, text="Nicio descărcare",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color="#303030").pack(pady=(6, 3))
        ctk.CTkLabel(self._empty, text="Lipește un URL și apasă  ⬇ DOWNLOAD",
                     font=ctk.CTkFont(size=12), text_color="#272727").pack()

        # Lista scrollabilă
        self._list = ctk.CTkScrollableFrame(
            self._content, fg_color=BG_MAIN, corner_radius=0,
            scrollbar_button_color="#2a2a2a", scrollbar_button_hover_color="#3a3a3a"
        )

        # ── Status bar ────────────────────────────────────────────────────────
        sbar = ctk.CTkFrame(self, height=28, fg_color="#0d0d0d", corner_radius=0)
        sbar.pack(fill="x", side="bottom")
        sbar.pack_propagate(False)

        self._status = ctk.CTkLabel(sbar, text="Gata.", font=ctk.CTkFont(size=11), text_color="#3a3a3a")
        self._status.pack(side="left", padx=14)

        self._dir_lbl = ctk.CTkLabel(sbar, text=f"📁  {self.download_dir}",
                                     font=ctk.CTkFont(size=11), text_color="#303030")
        self._dir_lbl.pack(side="right", padx=14)

    # ── Acțiuni UI ─────────────────────────────────────────────────────────────
    def _paste_clipboard(self):
        try:
            clip = self.clipboard_get().strip()
            if clip:
                self._url_entry.delete(0, "end")
                self._url_entry.insert(0, clip)
        except Exception:
            pass

    def _choose_folder(self):
        d = filedialog.askdirectory(initialdir=self.download_dir)
        if d:
            self.download_dir = d
            self._dir_entry.delete(0, "end")
            self._dir_entry.insert(0, d)
            self._dir_lbl.configure(text=f"📁  {d}")

    def _on_download_click(self):
        if not YT_DLP_AVAILABLE:
            self._ask_install()
            return

        url = self._url_entry.get().strip()
        if not url:
            messagebox.showwarning("URL lipsă", "Lipește un URL video sau playlist.", parent=self)
            return
        if not is_valid_url(url):
            messagebox.showwarning("URL invalid", "URL-ul trebuie să înceapă cu http:// sau https://", parent=self)
            return

        self.download_dir = self._dir_entry.get().strip() or self.download_dir
        self._dl_btn.configure(state="disabled", text="Se încarcă...")
        self._status.configure(text="Se preiau informații despre video...")
        self._fetch_info(url)

    # ── Fetch info ─────────────────────────────────────────────────────────────
    def _fetch_info(self, url):
        is_playlist = self._playlist_var.get()
        def worker():
            opts = {
                "quiet": True,
                "no_warnings": True,
                "nocheckcertificate": True,
                "noplaylist": not is_playlist,
                "extract_flat": "in_playlist" if is_playlist else False,
            }
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                self.after(0, lambda: self._on_info_ready(url, info))
            except Exception as e:
                err = str(e)
                if "Only images are available" in err or "images" in err.lower():
                    self.after(0, lambda: self._on_fetch_error("Videoclipul nu conține audio/video (doar imagini)."))
                elif "Requested format is not available" in err:
                    self.after(0, lambda: self._on_fetch_error("Niciun format audio/video disponibil. Actualizează yt-dlp:\npip install -U yt-dlp"))
                elif "login" in err.lower() or "log in" in err.lower() or "private" in err.lower():
                    self.after(0, lambda: self._on_fetch_error("Video privat sau necesită autentificare Facebook.\nDoar videoclipurile publice pot fi descărcate."))
                elif "not available" in err.lower() or "removed" in err.lower():
                    self.after(0, lambda: self._on_fetch_error("Videoclipul nu mai este disponibil sau a fost șters."))
                else:
                    self.after(0, lambda: self._on_fetch_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_fetch_error(self, err):
        self._dl_btn.configure(state="normal", text="⬇  DOWNLOAD")
        self._status.configure(text="Eroare la preluare.")
        messagebox.showerror("Eroare", f"Nu s-au putut prelua informații:\n{err}", parent=self)

    def _on_info_ready(self, url, info):
        self._dl_btn.configure(state="normal", text="⬇  DOWNLOAD")
        self._status.configure(text="Gata.")
        self._url_entry.delete(0, "end")

        quality_label = self._quality_var.get()
        fmt_str = next((f for lbl, f in QUALITY_OPTIONS if lbl == quality_label), QUALITY_OPTIONS[2][1])

        if info.get("_type") in ("playlist", "multi_video") and "entries" in info:
            entries = [e for e in info.get("entries", []) if e]
            self._status.configure(text=f"Playlist: {len(entries)} videoclipuri găsite. Se pornesc descărcările...")
            for entry in entries:
                video_url = entry.get("webpage_url") or entry.get("url")
                if not video_url:
                    continue
                self._start_download(video_url, entry, quality_label, fmt_str)
        else:
            self._start_download(url, info, quality_label, fmt_str)

    # ── Download ───────────────────────────────────────────────────────────────
    def _start_download(self, url, info, quality_label, fmt_str):
        if not self._cards:
            self._empty.place_forget()
            self._list.pack(fill="both", expand=True)

        card = DownloadCard(
            self._list,
            title=info.get("title") or "Video",
            quality_label=quality_label,
            thumbnail_url=info.get("thumbnail") or ""
        )
        card.pack(fill="x", padx=14, pady=(10, 0))
        self._cards.append(card)
        self._update_status()

        is_audio = "Audio" in quality_label
        out_dir  = self.download_dir
        outtmpl  = os.path.join(out_dir, "%(title)s.%(ext)s")

        ydl_opts = {
            "format":             fmt_str,
            "outtmpl":            outtmpl,
            "quiet":              True,
            "no_warnings":        True,
            "noplaylist":         True,
            "nocheckcertificate": True,
            "ffmpeg_location":    FFMPEG_PATH,
            "merge_output_format": "mp4",
        }
        if is_audio:
            ydl_opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"},
                {"key": "FFmpegMetadata"},
            ]
            del ydl_opts["merge_output_format"]

        def hook(d):
            if card._cancel_flag:
                raise Exception("Anulat")
            if d["status"] == "downloading":
                total  = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done   = d.get("downloaded_bytes", 0)
                speed  = d.get("speed") or 0
                eta    = d.get("eta") or 0
                pct    = (done / total * 100) if total else 0
                self.after(0, lambda p=pct, sp=speed, e=eta, dl=done, t=total:
                           card.update_progress(p, sp, e, dl, t))
            elif d["status"] == "finished":
                self.after(0, lambda: card.update_progress(99))

        ydl_opts["progress_hooks"] = [hook]

        def worker():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                if not card._cancel_flag:
                    self.after(0, lambda: card.set_done(out_dir))
            except Exception as e:
                err = str(e)
                if not card._cancel_flag and "Anulat" not in err:
                    self.after(0, lambda: card.set_error(err))
            self.after(0, self._update_status)

        threading.Thread(target=worker, daemon=True).start()

    def _update_status(self):
        active = sum(1 for c in self._cards if c.is_active)
        total  = len(self._cards)
        if active:
            self._status.configure(text=f"{active} descărcare(i) active  |  {total} total")
        elif total:
            self._status.configure(text=f"Toate cele {total} descărcare(i) sunt complete.")
        else:
            self._status.configure(text="Gata.")

    def _show_window(self):
        self.configure(fg_color=BG_MAIN)
        self.update_idletasks()
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_close(self):
        try:
            self.after_cancel(self._after_fix_id)
        except Exception:
            pass
        for card in self._cards:
            card._cancel_flag = True
        self.destroy()

    # ── yt-dlp install ─────────────────────────────────────────────────────────
    def _ask_install(self):
        if messagebox.askyesno("yt-dlp lipsește",
                               "yt-dlp nu este instalat.\n\nInstalezi acum via pip?", parent=self):
            threading.Thread(target=self._install_ytdlp, daemon=True).start()

    def _install_ytdlp(self):
        self.after(0, lambda: self._status.configure(text="Se instalează yt-dlp..."))
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "yt-dlp"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            global yt_dlp, YT_DLP_AVAILABLE
            import yt_dlp as _yt
            yt_dlp = _yt
            YT_DLP_AVAILABLE = True
            self.after(0, lambda: self._status.configure(text="yt-dlp instalat cu succes. Gata."))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._status.configure(text=f"Instalare eșuată: {err}"))


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = StranaApp()
    app.mainloop()