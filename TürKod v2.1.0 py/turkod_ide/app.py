"""TurKod IDE ana penceresi."""
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
import math

import customtkinter as ctk

from .ai import AI_MODELLERI, anthropic, genai, Groq, openai, groq_modelleri_guncelle, openai_modelleri_guncelle
from .converter import python_kodu_turkceye_cevir, turkce_kodu_donustur
from .debugger import BasitDebugger
from .dictionary import (
    FONKSIYON_KW,
    SINIF_KW,
    SOZLUK,
    TERS_SOZLUK,
    TURKCE_KELIMELER,
    TURKOD_BLOK_RE,
    TURKOD_BUILTIN_RE,
    TURKOD_KEYWORD_RE,
    _builtin_words,
    _keyword_words,
    kullanici_tanimlari,
)
from .paths import calisma_yolu, kaynak_yolu
from .runner import RUNNER_KODU
from .settings import AyarlarYoneticisi
from .signing import DijitalImza
from .themes import TEMA_RENKLERI
from .ui import ICON_FONT, WIN11_IKON, ui_font, win11_uygula


class TurkceIDE(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._kapatildi = False  # Uygulama kapatılıyor mu?
        # === DEBUGGER ===
        self.debugger = BasitDebugger(self)
        self.withdraw()
        self.ayarlar = AyarlarYoneticisi()
        self.tema = self.ayarlar.get("tema") or "Modern Koyu"
        self.colors = TEMA_RENKLERI.get(self.tema, TEMA_RENKLERI["Modern Koyu"])

        self.title("TürKod IDE - Profesyonel Türkçe Python Editorü")
        self.geometry("1600x900")
        self.minsize(1200, 700)

        # SEKME SISTEMI
        self.sekmeler = []
        self.aktif_sekme_id = None
        self.sekme_id_sayac = 0
        self._active_tooltip = None  # Tekil tooltip penceresi
        self.proje_dizini = self.ayarlar.get("son_proje_dizini")
        self.ai_mesajlar = []
        self.ai_mesaj_gecmisi = []

        self.grid_columnconfigure(1, minsize=220)
        self.grid_columnconfigure(2, minsize=4)
        self.grid_columnconfigure(4, minsize=12)
        self.grid_columnconfigure(5, minsize=480)

        self.configure(fg_color=self.colors["bg"])
        self.grid_columnconfigure(3, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._arayuz_olustur()
        self._resize_timer = None
        self._resize_aktif = False
        self.bind("<Configure>", self._pencere_configure, add="+")
        self._baglayicilari_ayarla()
        self.after(100, self._oturum_ac)
        self._otomatik_kaydetme_baslat()
        self.after(200, self._pencere_goster)
        
        # En kolay ve güvenli ikon ekleme yöntemi:
        try:
            if getattr(sys, 'frozen', False):
                ikon_yolu = os.path.join(sys._MEIPASS, "turkod.ico")
            else:
                ikon_yolu = os.path.join(os.path.dirname(os.path.abspath(__file__)), "turkod.ico")
            self.iconbitmap(ikon_yolu)
        except:
            pass
        self.after(500, self._modelleri_guncelle)
        self.protocol("WM_DELETE_WINDOW", self._pencere_kapat)
        self._kod_tanimlari_cache = []
        self._calistirma_process = None
        self._term_buf = []
        self._term_buf_len = 0
        self._term_lock = threading.Lock()
        self._term_flush_planli = False
        self._son_kod_hash = ""

        # ← BURAYA TAŞI! __init__ bitti, metodlar buraya başlıyor
    def _pencere_configure(self, event):
        if event.widget is not self:
            return
        boyut = (event.width, event.height)
        if boyut == getattr(self, "_son_boyut", None):
            return  # yalnızca konum değişti
        self._son_boyut = boyut
        self._resize_aktif = True
        # ← DÜZELTME: ai_chat_frame'e pack_propagate(False) YAPMA!
        # CTkScrollableFrame'in iç canvas'ı bozuluyor, scrollbar çalışmıyor.
        # Sadece animasyonları durdurmak yeterli.
        for attr in ("_sb_anim", "_ai_anim", "_term_anim", "_yildiz_after",
                     "_sekme_layout_timer", "_ai_wrap_timer"):
            aid = getattr(self, attr, None)
            if aid:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._resize_timer:
            try:
                self.after_cancel(self._resize_timer)
            except Exception:
                pass
        self._resize_timer = self.after(250, self._resize_bitti)

    def _resize_bitti(self):
        self._resize_timer = None
        self._resize_aktif = False
        # ← DÜZELTME: pack_propagate çağrısını kaldır
        # CTkScrollableFrame kendi propagation'ını yönetir
        self._animasyonlari_sabitle()
        self.update_idletasks()
        self._sekme_layout_guncelle()
        self._ai_wrap_guncelle()
        if getattr(self, "yildiz_canvas", None) and self.yildiz_canvas.winfo_exists():
            self._yildiz_anim_aktif = True
            self._parlak_yildiz_ciz()

    def _animasyonlari_sabitle(self):
        """Yarıda kalmış kaydırma animasyonlarını nihai konumuna ışınla."""
        try:
            if self.sidebar.winfo_viewable():
                self.sidebar.place_configure(x=0, relwidth=1.0, relheight=1.0)
                self._sb_x = 0
        except Exception:
            pass
        try:
            if getattr(self, "ai_panel_visible", True):
                self.ai_panel.place_configure(x=0, relwidth=1.0, relheight=1.0)
                self._ai_x = 0
        except Exception:
            pass
        try:
            if getattr(self, "terminal_visible", False):
                self.terminal_frame.place_configure(y=0, relwidth=1.0)
                self._term_y = 0
        except Exception:
            pass

    def _sekme_layout_zamanla(self, event=None):
        if getattr(self, "_resize_aktif", False):
            return
        if getattr(self, "_sekme_layout_timer", None):
            try:
                self.after_cancel(self._sekme_layout_timer)
            except Exception:
                pass
        self._sekme_layout_timer = self.after(30, self._sekme_layout_guncelle)

    def _ai_wrap_zamanla(self, event=None):
        if getattr(self, "_resize_aktif", False):
            return
        if getattr(self, "_ai_wrap_timer", None):
            try:
                self.after_cancel(self._ai_wrap_timer)
            except Exception:
                pass
        self._ai_wrap_timer = self.after(50, self._ai_wrap_guncelle)
    def _tooltip(self, widget, metin):
        """Hover paneli: tek pencere, anında göster, çıkınca gizle."""
        def goster():
            try:
                if not widget.winfo_exists():
                    return
                if not getattr(self, "_tip_win", None) or not self._tip_win.winfo_exists():
                    self._tip_win = tk.Toplevel(self)
                    self._tip_win.wm_overrideredirect(True)
                    self._tip_win.attributes("-topmost", True)
                    self._tip_label = tk.Label(
                        self._tip_win, font=("Segoe UI", 10),
                        bg="#2b2b2b", fg="#e0e0e0",
                        padx=10, pady=5, relief="solid", borderwidth=1)
                    self._tip_label.pack()
                self._tip_label.configure(text=metin)
                self._tip_win.update_idletasks()
                self._tip_win.geometry(
                    f"+{widget.winfo_rootx()}+{widget.winfo_rooty() + widget.winfo_height() + 6}")
                self._tip_win.deiconify()
                self._tip_win.lift()
            except Exception:
                pass

        def gizle():
            try:
                w = getattr(self, "_tip_win", None)
                if w is not None and w.winfo_exists():
                    w.withdraw()
            except Exception:
                pass

        def gir(e):
            try:
                t = getattr(self, "_tip_gizle_timer", None)
                if t:
                    self.after_cancel(t)
                    self._tip_gizle_timer = None
            except Exception:
                pass
            goster()  # anında, gecikmesiz

        def cik(e):
            # 25ms sonra gizle; aynı anda bir Enter gelirse (buton içi geçiş) iptal olur
            try:
                t = getattr(self, "_tip_gizle_timer", None)
                if t:
                    self.after_cancel(t)
                self._tip_gizle_timer = self.after(25, gizle)
            except Exception:
                pass

        # Olayları butona VE tüm alt pencerelerine bağla:
        # kenar/orta ayrımı kalmaz, her pikselde tetiklenir.
        def topla(w):
            liste = [w]
            for c in w.winfo_children():
                liste.extend(topla(c))
            return liste

        for w in topla(widget):
            w.bind("<Enter>", gir, add="+")
            w.bind("<Leave>", cik, add="+")

    def _koddan_tanimlari_cikar(self, kod):
        """Koddan fonksiyon, sınıf ve değişken isimlerini çıkar"""
        return sorted(kullanici_tanimlari(kod))

    def _tamamlama_kelime_listesi_al(self):
        """Otomatik tamamlama için kelime listesini oluştur (sözlük + kod içi tanımlar)"""
        # 1. Sabit sözlük kelimeleri
        sabit_kelimeler = set(TURKCE_KELIMELER)
        
        # 2. Kod içi tanımlar
        mevcut_kod = self.kod_alani.get("1.0", "end-1c")
        kod_tanimlari = set(self._koddan_tanimlari_cikar(mevcut_kod))
        
        # 3. Birleştir (kod tanımları önce gelsin)
        tum_kelimeler = list(kod_tanimlari) + [k for k in sabit_kelimeler if k not in kod_tanimlari]
        
        return tum_kelimeler
    def _resize_kapak_ac(self):
        """CTk'nin gecikmeli yeniden çizimini gizleyen tek renkli örtü."""
        kapak = getattr(self, "_resize_kapak", None)
        if kapak is None or not kapak.winfo_exists():
            self._resize_kapak = tk.Frame(self, bg=self.colors["bg"],
                                          bd=0, highlightthickness=0)
        else:
            self._resize_kapak.configure(bg=self.colors["bg"])
        self._resize_kapak.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        self._resize_kapak.lift()

    def _resize_kapak_kapat(self):
        kapak = getattr(self, "_resize_kapak", None)
        if kapak is not None and kapak.winfo_exists():
            kapak.place_forget()
    def _pencere_goster(self):
        win11_uygula(self)
        self.deiconify()
        self.update_idletasks()
        self._sekme_layout_guncelle()
    def _ai_durum_hazir(self):
        """Durum etiketini ai_aktif ayarına göre günceller."""
        if not hasattr(self, "ai_durum"):
            return
        if self.ayarlar.get("ai_aktif"):
            self.ai_durum.configure(text="● Hazır", text_color="#4caf50")
        else:
            self.ai_durum.configure(text="● Kapalı", text_color="#888")
    def _arayuz_olustur(self):
        # === AKTIVITE BAR (sol en dar) ===
        self.activity_bar = ctk.CTkFrame(self, width=48, fg_color=self.colors["activity_bar"])
        self.activity_bar.grid(row=0, column=0, rowspan=5, sticky="nsew")
        self.activity_bar.grid_propagate(False)

        # Explorer butonu 
        self.explorer_btn = ctk.CTkButton(
            self.activity_bar,
            text="◀",
            width=36,
            height=36,
            fg_color="transparent",
            text_color=self.colors["text"],
            hover_color=self.colors.get("button_bg", "#313131"),
            corner_radius=8,
            border_width=0,
            font=("Segoe UI", 16, "bold"),
            command=self._gezgin_ac
        )
        self.explorer_btn.pack(pady=(15, 5))
        
        # AI panel butonu 
        self.ai_toggle_btn = ctk.CTkButton(
            self.activity_bar,
            text="▶",
            width=36,
            height=36,
            fg_color="transparent",
            text_color=self.colors["text"],
            hover_color=self.colors.get("button_bg", "#313131"),
            corner_radius=8,
            border_width=0,
            font=("Segoe UI", 16, "bold"),
            command=self._ai_panel_toggle
        )
        self.ai_toggle_btn.pack(pady=5)
        # === KOD ARAMA BUTONU (Büyüteç) ===
        self.kod_arama_btn = ctk.CTkButton(
            self.activity_bar,
            text="🔍",
            width=36,
            height=36,
            fg_color="transparent",
            text_color=self.colors["text"],
            hover_color=self.colors.get("button_bg", "#313131"),
            corner_radius=8,
            border_width=0,
            font=("Segoe UI", 16),
            command=self._kod_arama_ac
        )
        self.kod_arama_btn.pack(pady=5)
        self._tooltip(self.kod_arama_btn, "Kod Arama (Python ⇄ TürKod)")

        # === SIDEBAR (Dosya Gezgini) ===
        # Sabit kap: sütun bir kez boyutlanır, kayma animasyonu içinde place ile yapılır
        self.sidebar_wrapper = ctk.CTkFrame(self, fg_color="transparent")
        self.sidebar_wrapper.grid_propagate(False)
        self.sidebar_wrapper.grid(row=0, column=1, rowspan=5, sticky="nsew", padx=(0, 8))
        self._sb_hedef_w = 220
        self._sb_x = 0
        self.sidebar = ctk.CTkFrame(self.sidebar_wrapper, fg_color=self.colors["sidebar"],
                                    border_width=1, border_color=self.colors["border"], corner_radius=8)
        self.sidebar.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self.sidebar_title = ctk.CTkLabel(self.sidebar, text="GEZGİN", font=("Segoe UI", 9, "bold"),
                                  text_color=self.colors["panel_fg"])
        self.sidebar_title.pack(pady=(15, 5), padx=15, anchor="w")

        self.proje_ac_btn = ctk.CTkButton(
            self.sidebar,
            text="Proje Aç",
            width=180,
            height=30,
            fg_color=self.colors["button_bg"],
            hover_color=self.colors["button_hover"],
            text_color=self.colors["text"],
            corner_radius=8,
            border_width=0,
            font=("Segoe UI", 10, "bold"),
            command=self._proje_ac
        )
        self.proje_ac_btn.pack(pady=(0, 10), padx=15)

        # Treeview için frame
        self.dosya_tree_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.dosya_tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.dosya_tree_frame.grid_columnconfigure(0, weight=1)  
        self.dosya_tree_frame.grid_rowconfigure(0, weight=1)     

        # Treeview
        self.dosya_tree = ttk.Treeview(self.dosya_tree_frame, style="Custom.Treeview", show="tree")
        self.dosya_tree.grid(row=0, column=0, sticky="nsew")

        # Scrollbar 
        self.tree_scrollbar = ctk.CTkScrollbar(self.dosya_tree_frame, command=self.dosya_tree.yview,
                                                orientation="vertical", width=12)
        self.tree_scrollbar.grid(row=0, column=1, sticky="ns")

        self.dosya_tree.configure(yscrollcommand=self.tree_scrollbar.set)

        # Treeview stil ayarları
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Custom.Treeview",
            background=self.colors["sidebar"],
            foreground=self.colors["panel_fg"],
            fieldbackground=self.colors["sidebar"],
            font=("Segoe UI", 10),
            rowheight=24
        )
        style.configure("Custom.Treeview.Heading",
            background=self.colors["sidebar"],
            foreground=self.colors["panel_fg"],
            font=("Segoe UI", 9, "bold")
        )
        style.map("Custom.Treeview",
            background=[("selected", self.colors.get("selection", "#264f78"))],
            foreground=[("selected", self._secim_metin_rengi())]
        )

        self.dosya_tree.bind("<Double-1>", self._dosya_tree_cift_tik)
        self.dosya_tree.bind("<<TreeviewOpen>>", self._tree_acildi)

        # === TAB BAR ===
        self.tab_bar = ctk.CTkFrame(self, height=38, fg_color=self.colors["tab_inactive"])
        self.tab_bar.grid(row=0, column=3, sticky="ew")
        self.tab_bar.grid_propagate(False)
        self.tab_bar.grid_columnconfigure(0, weight=1)
        self.tab_bar.grid_rowconfigure(0, weight=1)

        # Taşma okları (gereksizse gizlenir)
        self.tab_left_btn = ctk.CTkButton(self.tab_bar, text="‹", width=22, corner_radius=0,
            fg_color="transparent", hover_color=self.colors["tab_active"],
            text_color=self.colors["text"], command=lambda: self._sekme_kaydir(120))
        self.tab_right_btn = ctk.CTkButton(self.tab_bar, text="›", width=22, corner_radius=0,
            fg_color="transparent", hover_color=self.colors["tab_active"],
            text_color=self.colors["text"], command=lambda: self._sekme_kaydir(-120))

        # Sekme şeridi (kaydırılabilir alan)
        self.tab_strip = ctk.CTkFrame(self.tab_bar, fg_color="transparent", height=38)
        self.tab_strip.grid(row=0, column=0, sticky="nsew")
        self.tab_strip.grid_propagate(False)
        self.tab_strip.bind("<MouseWheel>", self._sekme_wheel)
        self.tab_strip.bind("<Button-4>", lambda e: self._sekme_kaydir(120))
        self.tab_strip.bind("<Button-5>", lambda e: self._sekme_kaydir(-120))

        self.sekmeler_container = ctk.CTkFrame(self.tab_strip, fg_color="transparent",
                                       height=38, width=176)
        self.sekmeler_container.pack_propagate(False)
        self.sekmeler_container.place(x=0, y=0, relheight=1.0)
        self._sekme_offset = 0
        self._sekme_genisligi = 170
        # + butonu: son sekmenin hemen sağına place ile konumlanır
        self.yeni_sekme_btn = ctk.CTkButton(
            self.sekmeler_container,
            text="+",
            width=24, height=24,
            fg_color="transparent",
            hover_color=self.colors["tab_active"],
            text_color=self.colors["text"],
            font=("Segoe UI", 13, "bold"),
            corner_radius=6, border_width=0,
            command=self._yeni_sekme_olustur
        )
        self.yeni_sekme_btn.place(x=176, y=7)
        self.yeni_sekme_btn.bind("<MouseWheel>", self._sekme_wheel)
        self._tooltip(self.yeni_sekme_btn, "Yeni Sekme (Ctrl+T)")
        # Butonlar artık ayrı sütunda, sekmelerle çakışamaz
        self.tab_buttons = ctk.CTkFrame(self.tab_bar, fg_color="transparent")
        self.tab_buttons.grid(row=0, column=3, sticky="e", padx=(5, 10))
        self.calistir_btn = ctk.CTkButton(self.tab_buttons, text=WIN11_IKON["calistir"], width=40, height=32,
            command=self.kodu_calistir, font=ICON_FONT,
            fg_color="transparent",
            hover_color="#313131", text_color=self.colors.get("accent", "#4CC2FF"),
            corner_radius=6, border_width=0)
        self.calistir_btn.pack(side="left", padx=2)
        self._tooltip(self.calistir_btn, "Çalıştır (Ctrl+R)")

        self.ac_btn = ctk.CTkButton(self.tab_buttons, text=WIN11_IKON["ac"], width=40, height=32,
            command=self.dosya_ac, font=ICON_FONT,
            fg_color="transparent", hover_color="#313131",
            text_color=self.colors["text"], corner_radius=6, border_width=0)
        self.ac_btn.pack(side="left", padx=2)
        self._tooltip(self.ac_btn, "Aç (Ctrl+O)")

        self.kaydet_btn = ctk.CTkButton(self.tab_buttons, text=WIN11_IKON["kaydet"], width=40, height=32,
            command=self.dosya_kaydet, font=ICON_FONT,
            fg_color="transparent", hover_color="#313131",
            text_color=self.colors["text"], corner_radius=6, border_width=0)
        self.kaydet_btn.pack(side="left", padx=2)
        self._tooltip(self.kaydet_btn, "Kaydet (Ctrl+S)")

        self.cevir_btn = ctk.CTkButton(self.tab_buttons, text=WIN11_IKON["cevir"], width=40, height=32,
            command=self._kodu_cevir, font=ICON_FONT,
            fg_color="transparent", hover_color="#313131",
            text_color=self.colors["text"], corner_radius=6, border_width=0)
        self.cevir_btn.pack(side="left", padx=2)
        self._tooltip(self.cevir_btn, "TürKod ⇄ Python Çevir")

        self.tab_bar.bind("<Configure>", lambda e: self._sekme_layout_zamanla())
        
        # === EDITOR FRAME ===
        self.editor_frame = ctk.CTkFrame(self, fg_color=self.colors["bg"])
        self.editor_frame.grid(row=1, column=3, sticky="nsew")
        self.editor_frame.grid_columnconfigure(1, weight=1)
        self.editor_frame.grid_rowconfigure(0, weight=1)

        # Line Numbers (Izgaraya yalnızca ayar açıksa eklenir)
        self.line_numbers = ctk.CTkTextbox(
            self.editor_frame,
            width=56,
            font=(self.ayarlar.get("yazi_tipi"), self.ayarlar.get("yazi_boyutu")),
            fg_color=self.colors["bg"],
            text_color=self.colors["line_number"],
            activate_scrollbars=False,
            state="disabled",
            wrap="none"
        )
        if self.ayarlar.get("satir_numaralari"):
            self.line_numbers.grid(row=0, column=0, sticky="nsew")
            
        # Code Editor
        self.kod_alani = ctk.CTkTextbox(
            self.editor_frame,
            font=(self.ayarlar.get("yazi_tipi"), self.ayarlar.get("yazi_boyutu")),
            corner_radius=0, fg_color=self.colors["bg"], text_color=self.colors["text"],
            wrap="none" if not self.ayarlar.get("kelime_sar") else "word",
            undo=True, maxundo=100
        )
        self.kod_alani.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        
        # Minimap (Küçük Harita) - Yeni Eklenti
        self.minimap = ctk.CTkTextbox(
            self.editor_frame, width=120,
            font=(self.ayarlar.get("yazi_tipi"), 4), # Kucuk font boyutu
            fg_color=self.colors["sidebar"], text_color=self.colors["text"],
            activate_scrollbars=False, state="disabled", wrap="none"
        )
        if self.ayarlar.get("minimap"):
            self.minimap.grid(row=0, column=2, sticky="nsew", padx=(2, 0))

        # === AI PANEL (sağ) ===
        self.ai_wrapper = ctk.CTkFrame(self, fg_color="transparent")
        self.ai_wrapper.grid_propagate(False)
        self.ai_wrapper.grid(row=0, column=5, rowspan=5, sticky="nsew", padx=(8, 0))
        self._ai_hedef_w = 480
        self._ai_x = 0
        self.ai_panel = ctk.CTkFrame(self.ai_wrapper, fg_color=self.colors["ai_panel"],
                                     corner_radius=10, border_width=1,
                                     border_color=self.colors["border"])
        self.ai_panel.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self.ai_panel.grid_propagate(False)
        self.ai_panel_visible = True

        # === ÜST BAR (Başlık + Butonlar) ===
        ai_header = ctk.CTkFrame(self.ai_panel, fg_color="transparent", height=40)
        ai_header.pack(fill="x", padx=12, pady=(10, 0))
        ai_header.pack_propagate(False)

        self.ai_baslik = ctk.CTkLabel(
            ai_header,
            text="AI Asistan",
            font=("Segoe UI", 13, "bold"),
            text_color=self.colors["text"]
        )
        self.ai_baslik.pack(side="left")

        self.ai_durum = ctk.CTkLabel(ai_header, text="",
            font=("Segoe UI", 10), text_color="#4caf50")
        self._ai_durum_hazir()
        self.ai_durum.pack(side="left", padx=(8, 0))
        kirmizi = "#c0392b" if self.tema == "Açık" else "#ff6b6b"
        self.ai_yeni_btn = ctk.CTkButton(ai_header, text="🗑 Yeni", width=60, height=24,
                                 fg_color="transparent", hover_color="#c75450",
                                 text_color=kirmizi, font=("Segoe UI", 10),
                                 command=self._ai_temizle)
        self.ai_yeni_btn.pack(side="right")

        ctk.CTkFrame(self.ai_panel, fg_color=self.colors["border"], height=1).pack(fill="x", padx=12, pady=5)

        # === MESAJ ALANI (Scrollable) ===
        # Not: "transparent" yerine doğrudan panel rengini vermek scrollbar'ın 
        # görünmesini ve canvas'ın doğru render edilmesini sağlar.
        self.ai_chat_frame = ctk.CTkScrollableFrame(
            self.ai_panel, 
            fg_color=self.colors["ai_panel"],
            scrollbar_button_color=self.colors.get("button_bg", "#3c3c3c"),
            scrollbar_button_hover_color=self.colors.get("button_hover", "#555555")
        )
        self.ai_chat_frame.pack(fill="both", expand=True, padx=8, pady=5)
        self._ai_wrap_labellari = []
        self.ai_chat_frame.bind("<Configure>", self._ai_wrap_zamanla)

        self.ai_typing_frame = ctk.CTkFrame(self.ai_chat_frame, fg_color=self.colors["ai_assistant"],
                                             corner_radius=12, height=32)
        self.ai_typing_label = ctk.CTkLabel(self.ai_typing_frame, text="● ● ●",
                                             font=("Segoe UI", 12), text_color="#888")
        self.ai_typing_label.pack(padx=12, pady=6)
        self.ai_typing_frame.pack_forget()
        self._ai_welcome_kur()

        # === ALT GİRİŞ ALANI ===
        self.ai_input_frame = ctk.CTkFrame(self.ai_panel, fg_color=self.colors["ai_input"],
                                            height=100, corner_radius=8)
        self.ai_input_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.ai_input_frame.pack_propagate(False)

        self.ai_input = ctk.CTkTextbox(
            self.ai_input_frame, font=("Segoe UI", 12),
            fg_color="transparent", text_color=self.colors["text"],
            height=60, wrap="word", activate_scrollbars=True
        )
        self.ai_input.pack(fill="both", expand=True, padx=8, pady=(6, 2))
        self.ai_input.insert("1.0", "Bir şey sor...")
        self.ai_input.bind("<FocusIn>", self._ai_input_focus)
        self.ai_input.bind("<FocusOut>", self._ai_input_blur)
        self.ai_input.bind("<Return>", self._ai_gonder_event)
        self.ai_input.bind("<Shift-Return>", lambda e: None)
        
        input_bar = ctk.CTkFrame(self.ai_input_frame, fg_color="transparent", height=28)
        input_bar.pack(fill="x", padx=8, pady=(0, 4))
        input_bar.pack_propagate(False)

        ctk.CTkLabel(input_bar, text="↵ Gönder  |  Shift+↵ Yeni Satır",
                     font=("Segoe UI", 8), text_color="#666").pack(side="left")

        self.ai_gonder_btn = ctk.CTkButton(input_bar, text="⬆ Gönder", width=70, height=22,
                                            fg_color=self.colors["button_bg"],
                                            hover_color=self.colors["button_hover"],
                                            font=("Segoe UI", 10, "bold"),
                                            command=self._ai_gonder)
        self.ai_gonder_btn.pack(side="right")

        # === HIZLI AKSIYONLAR ===
        self.ai_aksiyonlar = ctk.CTkFrame(self.ai_panel, fg_color="transparent", height=32)
        self.ai_aksiyonlar.pack(fill="x", padx=10, pady=(0, 8))
        self.ai_aksiyonlar.pack_propagate(False)
        aksiyonlar = [
            ("🔧 Düzelt", self._ai_kodu_duzelt),
            ("📖 Açıkla", self._ai_kodu_acikla),
            ("⚡ Optimize", self._ai_kodu_optimize),
        ]
        self.ai_aksiyon_btnlari = []
        for text, cmd in aksiyonlar:
            b = ctk.CTkButton(self.ai_aksiyonlar, text=text, width=70, height=26,
                              fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"],
                              text_color=self.colors["text"],
                              font=("Segoe UI", 10), command=cmd)
            b.pack(side="left", padx=2)
            self.ai_aksiyon_btnlari.append(b)
        b = ctk.CTkButton(self.ai_aksiyonlar, text="📝 TODO", width=70, height=26,
                          fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"],
                          text_color=self.colors["text"],
                          font=("Segoe UI", 10), command=self._todo_panel_ac)
        b.pack(side="left", padx=2)
        self.ai_aksiyon_btnlari.append(b)                          
        # === STATUS BAR ===
        self.status_bar = ctk.CTkFrame(
            self,
            height=32,
            fg_color=self.colors["status_bar"],
            corner_radius=0
        )
        self.status_bar.grid(row=4, column=3, sticky="ew")
        self.status_bar.grid_propagate(False)

        self.status_left = ctk.CTkLabel(self.status_bar,
                                text="  Python 3.x | TürKod Hazır",
                                font=ui_font(9),
                                text_color=self._status_metin_rengi())
        self.status_left.place(rely=0.5, anchor="w")

        # Sağ grup: istatistik butonu + dosya bilgisi yan yana
        self.status_right_frame = ctk.CTkFrame(self.status_bar, fg_color="transparent")
        self.status_right_frame.place(relx=1.0, rely=0.5, anchor="e")

        self.stats_btn = ctk.CTkButton(self.status_right_frame, text="ℹ", width=30, height=30,
                               fg_color="transparent",
                               hover_color=self.colors.get("button_hover", "#1177bb"),
                               text_color=self._status_metin_rengi(), corner_radius=4,
                               font=("Segoe UI", 17), command=self._istatistik_goster)
        self.stats_btn.pack(side="left", padx=(0, 6))

        self.status_right = ctk.CTkLabel(
            self.status_right_frame,
            text="UTF-8",
            font=ui_font(9),
            text_color=self._status_metin_rengi()
        )
        self.status_right.pack(side="left")
        # === ENTEGRE TERMİNAL ===
        self.terminal_visible = False
        # Sabit kap: grid bir kez boyutlanır, animasyon bunun İÇİNDE place ile yapılır
        self.terminal_wrapper = ctk.CTkFrame(self, fg_color=self.colors["bg"])
        self.terminal_wrapper.grid_propagate(False)
        self.terminal_frame = ctk.CTkFrame(self.terminal_wrapper, height=220, fg_color=self.colors["panel_bg"])
        self.terminal_frame.place(x=0, y=220, relwidth=1.0)
        self._term_y = 220
        # --- Üstten yeniden boyutlandırma çizgisi ---
        self.terminal_grip = tk.Frame(
            self.terminal_frame,
            bg=self.colors["border"],
            height=6,
            cursor="sb_v_double_arrow"
        )
        self.terminal_grip.pack(fill="x", side="top")
        self.terminal_grip.bind("<Button-1>", self._terminal_grip_basla)
        self.terminal_grip.bind("<B1-Motion>", self._terminal_grip_surukle)
        self.terminal_grip.bind("<ButtonRelease-1>", self._terminal_grip_birak)
        # Başlangıçta gizli; _terminal_toggle ile açılır

        term_header = ctk.CTkFrame(self.terminal_frame, fg_color=self.colors["sidebar"], height=36)
        term_header.pack(fill="x", side="top")
        term_header.pack_propagate(False)
        self.terminal_durdur_btn = ctk.CTkButton(
            term_header, text="■ Durdur", width=70, height=24,
            fg_color="transparent", hover_color="#c75450",
            text_color="#f48771", font=("Segoe UI", 9, "bold"),
            command=self._kodu_durdur)
        self.terminal_durdur_btn.pack(side="right", padx=2)
        ctk.CTkLabel(term_header, text="TERMİNAL", font=("Segoe UI", 10, "bold"), text_color=self.colors["panel_fg"]).pack(side="left", padx=12)

        ctk.CTkButton(term_header, text=WIN11_IKON.get("kapat", "×"), width=28, height=24,
                      fg_color="transparent", hover_color=self.colors["button_hover"],
                      text_color=self.colors["line_number"], command=self._terminal_toggle).pack(side="right", padx=4)
        ctk.CTkButton(term_header, text="Temizle", width=60, height=24,
              fg_color="transparent", hover_color=self.colors["button_hover"],
              text_color=self.colors["line_number"], font=("Segoe UI", 9),
              command=self._terminal_temizle).pack(side="right", padx=2)
        self.terminal_output = ctk.CTkTextbox(
            self.terminal_frame, font=("Consolas", 10),
            fg_color=self.colors["bg"], text_color=self.colors["text"],
            corner_radius=0, state="disabled"
        )
        self.terminal_output.pack(fill="both", expand=True, padx=2, pady=(2, 0))

        self.terminal_input = ctk.CTkEntry(
            self.terminal_frame, font=("Consolas", 11), height=28,
            fg_color=self.colors["ai_input"], text_color=self.colors["text"],
            border_color=self.colors["border"]
        )
        self.terminal_input.pack(fill="x", padx=2, pady=2)
        self.terminal_input.bind("<Return>", self._terminal_enter)
        # === AYARLAR BUTONU (sol alt) ===
        self.ayarlar_btn = ctk.CTkButton(self.activity_bar, text="⚙", width=36, height=36,
            fg_color="transparent",
            text_color=self.colors["text"],
            hover_color=self.colors.get("button_bg", "#313131"),
            corner_radius=8,
            border_width=0,
            font=("Segoe UI", 16, "bold"),
            command=self._ayarlar_penceresi_ac)
        self.ayarlar_btn.pack(side="bottom", pady=15)
        self._grip_olustur()
        self.fold_regions = {}  # {satir_no: (bas_idx, bit_idx, collapsed)}
        self.fold_indicators = {}  # Satır numaralarındaki fold ikonları
        self.fold_states = {}
        self.renk_ayarlarini_yap()
        self._tree_tagleri_ayarla()
        if self.proje_dizini and os.path.exists(self.proje_dizini):
            self.after(200, self._dosya_tree_guncelle)
        # ttk, uygulama sökümü sırasında <<ThemeChanged>> üretip yok olmuş
        # pencereye event generate ediyor. Prosedürü ve onu tetikleyen
        # trace'i ttk yüklendiği anda etkisizleştir. Runtime'da ttk teması
        # değiştirmiyoruz (renkler style.configure ile), bu yüzden güvenli.
        try:
            self.tk.eval("""
                catch {
                    foreach t [trace vinfo variable ::ttk::currentTheme] {
                        trace remove variable ::ttk::currentTheme {*}$t
                    }
                }
                catch { proc ttk::ThemeChanged args {} }
            """)
        except Exception:
            pass
    def _tree_acildi(self, event=None):
        """Ok işaretine tek tıkla açılan klasörleri de senkron doldur"""
        try:
            item = self.dosya_tree.focus()
            if not item:
                return

            values = self.dosya_tree.item(item, "values")
            if not values or len(values) < 2 or values[1] != "directory":
                return

            durum = values[2] if len(values) > 2 else "collapsed"
            if durum != "collapsed":
                return  # zaten yüklü, tekrar doldurma

            # "⏳ Yükleniyor..." dummy'sini temizle, gerçek içeriği koy
            for child in self.dosya_tree.get_children(item):
                self.dosya_tree.delete(child)

            self._tree_doldur(values[0], item)
            self.dosya_tree.item(item, values=(values[0], "directory", "expanded"))
        except Exception:
            pass
    def _gezgin_ac(self, event=None):
        if getattr(self, "_sb_anim", None):
            try:
                self.after_cancel(self._sb_anim)
            except Exception:
                pass
            self._sb_anim = None

        hedef_w = getattr(self, "_sb_hedef_w", 220)
        if self.sidebar.winfo_viewable():
            # KAPAT: sola kay
            self.explorer_btn.configure(text="▶")
            self._gezgin_adimla(getattr(self, "_sb_x", 0), -hedef_w, hedef_w, kapat=True)
        else:
            # AÇ: sütunu bir kez ayır, panel soldan kaysın
            self.sidebar_grip.grid(row=0, column=2, rowspan=5, sticky="ns")
            self.sidebar_wrapper.grid(row=0, column=1, rowspan=5, sticky="nsew", padx=(0, 8))
            self.grid_columnconfigure(1, minsize=hedef_w)
            self.sidebar.place(x=-hedef_w, y=0, relwidth=1.0, relheight=1.0)
            self._sb_x = -hedef_w
            self.explorer_btn.configure(text="◀")
            self._gezgin_adimla(-hedef_w, 0, hedef_w, kapat=False)

    def _gezgin_adimla(self, x_bas, x_son, hedef_w, adim=0, kapat=False):
        TOPLAM = 16
        t = (adim + 1) / TOPLAM
        e = 1 - (1 - t) ** 3
        x = int(x_bas + (x_son - x_bas) * e)
        self._sb_x = x
        try:
            self.sidebar.place_configure(x=x)
        except Exception:
            return
        if adim < TOPLAM - 1:
            self._sb_anim = self.after(16, lambda: self._gezgin_adimla(x_bas, x_son, hedef_w, adim + 1, kapat))
        else:
            self._sb_anim = None
            if kapat:
                self.sidebar_wrapper.grid_remove()
                self.sidebar_grip.grid_remove()
                self.grid_columnconfigure(1, minsize=0)
    def _ai_panel_toggle(self, event=None):
        if getattr(self, "_ai_anim", None):
            try:
                self.after_cancel(self._ai_anim)
            except Exception:
                pass
            self._ai_anim = None

        hedef_w = getattr(self, "_ai_hedef_w", 480)
        if getattr(self, "ai_panel_visible", True):
            # KAPAT: sağa kay
            self.ai_panel_visible = False
            self.ai_toggle_btn.configure(text="◀")
            self._ai_adimla(getattr(self, "_ai_x", 0), hedef_w, hedef_w, kapat=True)
        else:
            # AÇ: sütunu bir kez ayır, panel sağdan kaysın
            self.ai_grip.grid(row=0, column=4, rowspan=5, sticky="ns")
            self.ai_wrapper.grid(row=0, column=5, rowspan=5, sticky="nsew", padx=(8, 0))
            self.grid_columnconfigure(5, minsize=hedef_w)
            self.ai_panel.place(x=hedef_w, y=0, relwidth=1.0, relheight=1.0)
            self._ai_x = hedef_w
            self.ai_panel_visible = True
            self.ai_toggle_btn.configure(text="▶")
            self._ai_adimla(hedef_w, 0, hedef_w, kapat=False)

    def _ai_adimla(self, x_bas, x_son, hedef_w, adim=0, kapat=False):
        TOPLAM = 16
        t = (adim + 1) / TOPLAM
        e = 1 - (1 - t) ** 3
        x = int(x_bas + (x_son - x_bas) * e)
        self._ai_x = x
        try:
            self.ai_panel.place_configure(x=x)
        except Exception:
            return
        if adim < TOPLAM - 1:
            self._ai_anim = self.after(16, lambda: self._ai_adimla(x_bas, x_son, hedef_w, adim + 1, kapat))
        else:
            self._ai_anim = None
            if kapat:
                self.ai_wrapper.grid_remove()
                self.ai_grip.grid_remove()
                self.grid_columnconfigure(5, minsize=0)
        # ============ KOD ARAMA PANELİ ============
    def _kod_arama_ac(self, event=None):
        """Python kodunun TürKod karşılığını gösteren arama/çevirici panel"""
        if hasattr(self, '_kod_arama_pencere') and self._kod_arama_pencere.winfo_exists():
            self._kod_arama_pencere.lift()
            self._kod_arama_entry.focus()
            return

        pencere = ctk.CTkToplevel(self)
        pencere.title("Kod Arama - Python ⇄ TürKod")
        pencere.geometry("480x550")
        pencere.transient(self)
        pencere.resizable(False, False)
        pencere.configure(fg_color=self.colors["bg"])
        self._kod_arama_pencere = pencere

        # Başlık
        ctk.CTkLabel(pencere, text="🔍 Kod Arama Çevirici",
                     font=("Segoe UI", 16, "bold"),
                     text_color=self.colors["text"]).pack(pady=(15, 5))

        ctk.CTkLabel(pencere, text="Python kodu veya kelime yazın, TürKod karşılığını görün",
                     font=("Segoe UI", 10),
                     text_color=self.colors.get("line_number", "#888")).pack(pady=(0, 10))

        # Giriş satırı
        giris_frame = ctk.CTkFrame(pencere, fg_color="transparent")
        giris_frame.pack(fill="x", padx=20, pady=5)

        self._kod_arama_entry = ctk.CTkEntry(
            giris_frame,
            font=("Consolas", 12),
            height=35,
            fg_color=self.colors.get("ai_input", "#3c3c3c"),
            text_color=self.colors["text"],
            border_color=self.colors["border"],
            placeholder_text="örn: print, def, if, while..."
        )
        self._kod_arama_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self._kod_arama_entry.focus()

        cevir_btn = ctk.CTkButton(
            giris_frame, text="Çevir", width=80, height=35,
            fg_color=self.colors.get("button_bg", "#0e639c"),
            hover_color=self.colors.get("button_hover", "#1177bb"),
            text_color="#ffffff",
            font=("Segoe UI", 11, "bold"),
            command=self._kod_ara_cevir
        )
        cevir_btn.pack(side="right")

        # Sonuç başlığı
        ctk.CTkLabel(pencere, text="Sonuç:", font=("Segoe UI", 11, "bold"),
                     text_color=self.colors["text"]).pack(anchor="w", padx=20, pady=(10, 0))

        # Sonuç alanı
        self._kod_arama_sonuc = ctk.CTkTextbox(
            pencere,
            font=("Consolas", 12),
            fg_color=self.colors.get("bg", "#1e1e1e"),
            text_color=self.colors["text"],
            corner_radius=6,
            height=220,
            wrap="word"
        )
        self._kod_arama_sonuc.pack(fill="both", expand=True, padx=20, pady=5)
        self._kod_arama_sonuc.configure(state="disabled")

        # Bilgi etiketi
        self._kod_arama_bilgi = ctk.CTkLabel(
            pencere, text="",
            font=("Segoe UI", 9),
            text_color=self.colors.get("line_number", "#888")
        )
        self._kod_arama_bilgi.pack(pady=(0, 5))

        # Hızlı örnek butonları
        ornek_frame = ctk.CTkFrame(pencere, fg_color="transparent")
        ornek_frame.pack(fill="x", padx=20, pady=(0, 5))
        ctk.CTkLabel(ornek_frame, text="Hızlı örnekler:",
                     font=("Segoe UI", 9),
                     text_color=self.colors.get("line_number", "#888")).pack(anchor="w")

        ornekler_frame = ctk.CTkFrame(ornek_frame, fg_color="transparent")
        ornekler_frame.pack(fill="x", pady=2)

        ornekler = ["print", "def", "if", "for", "while", "import", "return", "class"]
        for ornek in ornekler:
            b = ctk.CTkButton(
                ornekler_frame, text=ornek, width=50, height=24,
                fg_color=self.colors.get("button_bg", "#3c3c3c"),
                hover_color=self.colors.get("button_hover", "#1177bb"),
                text_color=self.colors["text"],
                font=("Consolas", 9),
                corner_radius=4,
                command=lambda k=ornek: self._kod_arama_hizli(k)
            )
            b.pack(side="left", padx=2)

        # Alt bilgi
        ctk.CTkLabel(pencere, text="Enter: Çevir  |  Esc: Kapat",
                     font=("Segoe UI", 8),
                     text_color="#666").pack(pady=(0, 10))

        # Olay bağlama
        self._kod_arama_entry.bind("<Return>", lambda e: self._kod_ara_cevir())
        pencere.bind("<Escape>", lambda e: pencere.destroy())

    def _kod_ara_cevir(self):
        """Girilen Python ifadesini TürKod'a çevirir"""
        giris = self._kod_arama_entry.get().strip()
        if not giris:
            self._kod_arama_sonuc.configure(state="normal")
            self._kod_arama_sonuc.delete("1.0", "end")
            self._kod_arama_sonuc.insert("1.0", "⚠️ Lütfen bir Python kodu veya kelime yazın.")
            self._kod_arama_sonuc.configure(state="disabled")
            self._kod_arama_bilgi.configure(text="", text_color="#888")
            return

        self._kod_arama_sonuc.configure(state="normal")
        self._kod_arama_sonuc.delete("1.0", "end")

        # Kelime kelime sözlük araması
        kelimeler = re.findall(r'[a-zA-Z_]\w*', giris)
        eslesme_bulundu = False

        sonuc_satirlari = []
        sonuc_satirlari.append("━" * 46)
        sonuc_satirlari.append("  📖 KELİME KARŞILIKLARI")
        sonuc_satirlari.append("━" * 46)
        sonuc_satirlari.append("")

        for kelime in kelimeler:
            kl = kelime.lower()
            bulundu = False

            if kl == "for":
                sonuc_satirlari.append(f"  {kelime}  →  döngü ... içinde ...")
                sonuc_satirlari.append(f"        (örn: for i in x: → döngü i içinde x:)")
                bulundu = True
                eslesme_bulundu = True

            elif kl in TERS_SOZLUK:
                sonuc_satirlari.append(f"  {kelime}  →  {TERS_SOZLUK[kl]}")
                bulundu = True
                eslesme_bulundu = True
            elif kelime in TERS_SOZLUK:
                sonuc_satirlari.append(f"  {kelime}  →  {TERS_SOZLUK[kelime]}")
                bulundu = True
                eslesme_bulundu = True

            if not bulundu:
                for desen, karsilik in SOZLUK.items():
                    temiz = str(desen).replace(r"\b", "").strip().strip('"').strip("'")
                    if temiz and temiz.lower() == kl:
                        sonuc_satirlari.append(f"  {kelime}  →  {karsilik}")
                        eslesme_bulundu = True
                        bulundu = True
                        break

        if not eslesme_bulundu:
            sonuc_satirlari.append("  (Sözlükte eşleşme bulunamadı)")

        sonuc_satirlari.append("")
        sonuc_satirlari.append("━" * 46)
        sonuc_satirlari.append("  🔄 TAM KOD ÇEVRİSİ")
        sonuc_satirlari.append("━" * 46)
        sonuc_satirlari.append("")

        try:
            turkce_kod = python_kodu_turkceye_cevir(giris)
            if turkce_kod.strip():
                sonuc_satirlari.append(turkce_kod)
            else:
                sonuc_satirlari.append("(Çevrilemedi)")
        except Exception as e:
            sonuc_satirlari.append(f"  Çeviri hatası: {e}")

        sonuc_metni = "\n".join(sonuc_satirlari)
        self._kod_arama_sonuc.insert("1.0", sonuc_metni)
        self._kod_arama_sonuc.configure(state="disabled")

        if eslesme_bulundu:
            self._kod_arama_bilgi.configure(text="✓ Çeviri tamamlandı", text_color="#4caf50")
        else:
            self._kod_arama_bilgi.configure(text="⚠ Sözlükte eşleşme yok, tam çeviri denendi", text_color="#ff9800")

    def _kod_arama_hizli(self, kelime):
        """Hızlı örnek butonuna tıklandığında entry'ye yazar ve çevirir"""
        self._kod_arama_entry.delete(0, "end")
        self._kod_arama_entry.insert(0, kelime)
        self._kod_ara_cevir()
    def _istatistik_goster(self, event=None):
        """Kod istatistiklerini göster"""
        kod = self.kod_alani.get("1.0", "end-1c")
        satirlar = kod.split('\n')
        
        toplam_satir = len(satirlar)
        bos_satir = sum(1 for s in satirlar if not s.strip())
        yorum_satir = sum(1 for s in satirlar if s.strip().startswith('#'))
        kod_satir = toplam_satir - bos_satir - yorum_satir
        karakter = len(kod)
        karakter_bosluksuz = len(kod.replace(' ', '').replace('\n', '').replace('\t', ''))
        
        import re
        fonksiyon_sayisi = len(re.findall(rf'\b{re.escape(FONKSIYON_KW)}\s+\w+', kod))
        sinif_sayisi = len(re.findall(rf'\b{re.escape(SINIF_KW)}\s+\w+', kod))
        degisken_sayisi = len(set(re.findall(r'^([a-zA-Z_çğıöşüÇĞİÖŞÜ][a-zA-Z0-9_çğıöşüÇĞİÖŞÜ]*)\s*=', kod, re.MULTILINE)))
        
        mesaj = f"""📊 Kod İstatistikleri

    Toplam Satır: {toplam_satir}
      ├─ Kod Satırı: {kod_satir}
      ├─ Yorum Satırı: {yorum_satir}
      └─ Boş Satır: {bos_satir}

    Karakter: {karakter} (Boşluksuz: {karakter_bosluksuz})

    Fonksiyon: {fonksiyon_sayisi}
    Sınıf: {sinif_sayisi}
    Değişken: {degisken_sayisi}"""
        
        messagebox.showinfo("Kod İstatistikleri", mesaj)
    # ============ SEKME ŞERİDİ YÖNETİMİ ============
    def _sekme_wheel(self, event):
        self._sekme_kaydir(120 if event.delta > 0 else -120)
        return "break"

    def _sekme_kaydir(self, delta):
        gorunur = self.tab_strip.winfo_width()
        icerik = self.sekmeler_container.winfo_width()
        min_offset = min(0, gorunur - icerik)
        self._sekme_offset = max(min_offset, min(0, self._sekme_offset + delta))
        self.sekmeler_container.place_configure(x=self._sekme_offset)
        self._sekme_ok_guncelle()

    def _sekme_ok_guncelle(self):
        gorunur = self.tab_strip.winfo_width()
        icerik = self.sekmeler_container.winfo_width()
        gerekli = icerik > gorunur  # sadece gerçekten taşınca
        eski = getattr(self, "_sekme_ok_gorunur", False)

        if gerekli:
            self.tab_left_btn.grid(row=0, column=1, sticky="ns")
            self.tab_right_btn.grid(row=0, column=2, sticky="ns")
        else:
            self.tab_left_btn.grid_remove()
            self.tab_right_btn.grid_remove()
            self._sekme_offset = 0
            self.sekmeler_container.place_configure(x=0)

        self._sekme_ok_gorunur = gerekli
        if gerekli != eski:
            self.after(0, self._sekme_layout_guncelle)

    def _sekme_layout_guncelle(self):
        gorunur = self.tab_strip.winfo_width()
        n = len(self.sekmeler)
        PLUS_PAY = 30  # + butonu (24px) + boşluklar
        OK_PAY = 44    # taşma oklarının kapladığı alan

        if n == 0:
            self.sekmeler_container.configure(width=PLUS_PAY)
            self.yeni_sekme_btn.place(x=0, y=7)
            self._sekme_ok_guncelle()
            return
        if gorunur < 50:
            try:
                self.after(50, self._sekme_layout_guncelle)
            except Exception:
                pass
            return

        min_w, max_w = 90, 170
        # Sekmeler minimumda bile + butonuyla sığmıyorsa oklar gerekir
        taslacak = n * (min_w + 2) + PLUS_PAY > gorunur
        kullanilabilir = gorunur - (OK_PAY if taslacak else 0)

        genislik = min(max_w, max(min_w, (kullanilabilir - PLUS_PAY) // n - 2))
        self._sekme_genisligi = genislik
        for s in self.sekmeler:
            s["frame"].configure(width=genislik)
            self._sekme_etiket_kirp(s, genislik)

        # + butonu her zaman son sekmenin hemen sağında
        tabs_w = n * (genislik + 2)
        self.yeni_sekme_btn.place(x=tabs_w + 2, y=7)
        self.sekmeler_container.configure(width=tabs_w + PLUS_PAY)
        self._sekme_ok_guncelle()

    def _sekme_etiket_kirp(self, sekme, genislik):
        isim = sekme["isim"]
        if sekme["degisti"]:
            isim += " ●"
        max_karakter = max(4, (genislik - 46) // 7)
        if len(isim) > max_karakter:
            isim = isim[:max_karakter - 1] + "…"
        sekme["label"].configure(text=isim)
    def _todo_panel_ac(self):
        """TODO/FIXME/HACK yorumlarını listeleyen panel aç"""
        if hasattr(self, '_todo_pencere') and self._todo_pencere.winfo_exists():
            self._todo_pencere.lift()
            return
        
        pencere = ctk.CTkToplevel(self)
        pencere.title("TODO Listesi")
        pencere.geometry("500x400")
        pencere.transient(self)
        self._todo_pencere = pencere
        
        # Başlık
        ctk.CTkLabel(pencere, text="📝 Kod İçi Notlar", font=("Segoe UI", 14, "bold"),
                     text_color=self.colors["text"]).pack(pady=10)
        
        # Liste çerçevesi
        liste_frame = ctk.CTkScrollableFrame(pencere, fg_color="transparent")
        liste_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        import re
        kod = self.kod_alani.get("1.0", "end-1c")
        satirlar = kod.split('\n')
        
        todo_bulundu = False
        for i, satir in enumerate(satirlar, 1):
            # TODO, FIXME, HACK, XXX, BUG ara
            match = re.search(r'#.*?(TODO|FIXME|HACK|XXX|BUG)[\s:]*(.*)', satir, re.IGNORECASE)
            if match:
                todo_bulundu = True
                tip = match.group(1).upper()
                aciklama = match.group(2).strip() or "(açıklama yok)"
                
                # Renk
                renk = {"TODO": "#4caf50", "FIXME": "#ff9800", "HACK": "#f44336", 
                        "XXX": "#9c27b0", "BUG": "#e91e63"}.get(tip, "#888")
                
                frame = ctk.CTkFrame(liste_frame, fg_color=self.colors["sidebar"], corner_radius=6)
                frame.pack(fill="x", pady=2)
                
                ctk.CTkLabel(frame, text=f"{tip}", font=("Segoe UI", 9, "bold"),
                             text_color=renk, width=60).pack(side="left", padx=8)
                ctk.CTkLabel(frame, text=f"Satır {i}:", font=("Segoe UI", 9),
                             text_color="#888", width=50).pack(side="left")
                ctk.CTkLabel(frame, text=aciklama[:50], font=("Segoe UI", 10),
                             text_color=self.colors["text"]).pack(side="left", padx=5)
                
                # Tıklayınca o satıra git
                def git(satir_no=i):
                    self.kod_alani.see(f"{satir_no}.0")
                    self.kod_alani.mark_set("insert", f"{satir_no}.0")
                    self.kod_alani.tag_remove("sel", "1.0", "end")
                    self.kod_alani.tag_add("sel", f"{satir_no}.0", f"{satir_no}.end")
                
                ctk.CTkButton(frame, text="Git", width=40, height=20,
                              fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"],
                              font=("Segoe UI", 9), command=git).pack(side="right", padx=5)
        
        if not todo_bulundu:
            ctk.CTkLabel(liste_frame, text="Hiç TODO/FIXME/HACK/XXX/BUG bulunamadı.",
                         font=("Segoe UI", 11), text_color="#666").pack(pady=20)
    def _fold_bolgeleri_bul(self):
        kod = self.kod_alani.get("1.0", "end-1c")
        satirlar = kod.splitlines()
        bolgeler = []
        yigin = []

        def kapat(bas_satir, bit_satir):
            if bit_satir <= bas_satir:
                return
            govde_var = any(s.strip() for s in satirlar[bas_satir:bit_satir])
            if govde_var:
                bolgeler.append((bas_satir, bit_satir))

        for i, satir in enumerate(satirlar, 1):
            bosluksuz = satir.lstrip()
            if not bosluksuz or bosluksuz.startswith("#"):
                continue

            indent = len(satir) - len(bosluksuz)

            # Mevcut satırın indent'i üstteki bloktan küçük/eşitse blokları kapat
            while yigin and indent <= yigin[-1][1]:
                bas_satir, _ = yigin.pop()
                kapat(bas_satir, i - 1)

            # Yorum kısmını temizle, sonra : ile bitip bitmediğine bak
            temiz = bosluksuz.split('#')[0].rstrip()
            if temiz.endswith(':'):
                yigin.append((i, indent))

        son_satir = len(satirlar)
        while yigin:
            bas_satir, _ = yigin.pop()
            kapat(bas_satir, son_satir)

        return bolgeler
    def _fold_satir_numaralari_guncelle(self):
        try:
            self._satir_numaralarini_ciz()
        except Exception:
            pass
    def _fold_guncelle(self):
        editor = getattr(self.kod_alani, "_textbox", self.kod_alani)
        for tag in editor.tag_names():
            if tag.startswith("fold_"):
                editor.tag_delete(tag)
        self.fold_regions = {}
        self.fold_indicators = {}
        eski_states = getattr(self, "fold_states", {})
        self.fold_states = {}
        for bas, bit in self._fold_bolgeleri_bul():
            if bit <= bas:
                continue
            tag_adi = f"fold_{bas}"
            editor.tag_add(tag_adi, f"{bas + 1}.0", f"{bit}.end")
            folded = eski_states.get(bas, False)
            self.fold_states[bas] = folded
            self.fold_regions[bas] = (bas, bit)
            self.fold_indicators[bas] = "▶" if folded else "▼"
            editor.tag_config(tag_adi, elide=folded)
            editor.tag_raise(tag_adi)  # ← EKLE: fold tag'i en yüksek önceliğe taşı
        self._satir_numaralarini_ciz()
    def _gizli_satirlar(self):
        """Katlanmış bölgelerde editörde görünmeyen satır numaraları"""
        gizli = set()
        for bas, (b0, b1) in getattr(self, "fold_regions", {}).items():
            if self.fold_states.get(bas):
                gizli.update(range(b0 + 1, b1 + 1))
        return gizli
    def _fold_tikla(self, event=None):
        try:
            ln = getattr(self.line_numbers, "_textbox", self.line_numbers)
            idx = ln.index(f"@{event.x},{event.y}")
            g_satir, sutun = idx.split(".")
            g_satir = int(g_satir)
            sutun = int(sutun)
            
            metin = ln.get(f"{g_satir}.0", f"{g_satir}.end")
            if not metin:
                return None

            # Tıklanan karakteri doğrudan kontrol et
            if sutun < len(metin) and metin[sutun] in ("▼", "▶"):
                m = re.search(r"\d+", metin)
                if not m:
                    return None
                satir = int(m.group(0))

                if satir not in getattr(self, "fold_indicators", {}):
                    return None

                editor = getattr(self.kod_alani, "_textbox", self.kod_alani)
                tag_adi = f"fold_{satir}"
                if tag_adi not in editor.tag_names():
                    return None

                if self.fold_indicators[satir] == "▼":
                    self.fold_indicators[satir] = "▶"
                    self.fold_states[satir] = True
                    editor.tag_config(tag_adi, elide=True)
                else:
                    self.fold_indicators[satir] = "▼"
                    self.fold_states[satir] = False
                    editor.tag_config(tag_adi, elide=False)

                editor.tag_raise(tag_adi)  # ← EKLE: önceliği yükselt
                self._satir_numaralarini_ciz()
                self._senkronize_scroll()
                return "break"

            return None
        except Exception as e:
            print(f"[Fold Hatası] _fold_tikla: {e}")
            return None

    def _sidebar_grip_basla(self, event):
        self._sg_baslangic_x = event.x_root
        self._sg_baslangic_w = self.sidebar.winfo_width()
        self._grip_aktif = True

    def _sidebar_grip_surukle(self, event):   # sidebar artık wrapper çocuğu, root koordinatı değişti
        if not self._grip_aktif:
            return
        delta = event.x_root - self._sg_baslangic_x
        yeni = max(150, min(450, self._sg_baslangic_w + delta))
        x_pos = self.sidebar_wrapper.winfo_rootx() + yeni   # ← DÜZELT
        self._ghost_line.place(x=x_pos, y=0, relheight=1.0)
        self._ghost_line.lift()
        self._ghost_line_w = yeni

    def _sidebar_grip_birak(self, event):
        if not self._grip_aktif:
            return
        self._grip_aktif = False
        self._ghost_line.place_forget()
        yeni = getattr(self, '_ghost_line_w', self.sidebar.winfo_width())
        self.grid_columnconfigure(1, minsize=int(yeni))
        self._sb_hedef_w = int(yeni)          # ← EKLE
        self.update_idletasks()


    def _ai_grip_birak(self, event):
        if not self._grip_aktif:
            return
        self._grip_aktif = False
        self._ghost_line.place_forget()
        yeni = getattr(self, '_ghost_line_w', self.ai_panel.winfo_width())
        self.grid_columnconfigure(5, minsize=int(yeni))
        self._ai_hedef_w = int(yeni)          # ← EKLE
        self.update_idletasks()

    def _ai_grip_basla(self, event):
        self._ag_baslangic_x = event.x_root
        self._ag_baslangic_w = self.ai_panel.winfo_width()
        self._grip_aktif = True

    def _ai_grip_surukle(self, event):
        if not self._grip_aktif:
            return
        delta = self._ag_baslangic_x - event.x_root
        yeni = max(320, min(800, self._ag_baslangic_w + delta))
        
        x_pos = self.winfo_width() - yeni
        self._ghost_line.place(x=x_pos, y=0, relheight=1.0)
        self._ghost_line.lift()
        self._ghost_line_w = yeni

    def _grip_olustur(self):
        self._grip_bg = self.colors.get("border", "#3c3c3c")
        self._grip_hover = self.colors.get("accent", "#007acc")
        self._ghost_line = tk.Frame(self, bg=self._grip_hover, width=2)
        self._ghost_line_y = tk.Frame(self, bg=self._grip_hover, height=2)

        self.sidebar_grip = ctk.CTkFrame(self, width=4, fg_color=self._grip_bg)
        self.ai_grip = ctk.CTkFrame(self, width=4, fg_color=self._grip_bg)
        self.terminal_grip = ctk.CTkFrame(self, height=5, fg_color=self._grip_bg)
        self._ghost_line = tk.Frame(self, bg="#007acc", width=2)
        self._ghost_line.place_forget()
        self._grip_aktif = False
        
        self.sidebar_grip = ctk.CTkFrame(self, width=4, fg_color="#3c3c3c")
        self.sidebar_grip.grid(row=0, column=2, rowspan=5, sticky="ns")
        self.sidebar_grip.configure(cursor="sb_h_double_arrow")
        
        self.sidebar_grip.bind("<Button-1>", self._sidebar_grip_basla)
        self.sidebar_grip.bind("<B1-Motion>", self._sidebar_grip_surukle)
        self.sidebar_grip.bind("<ButtonRelease-1>", self._sidebar_grip_birak)
        self.sidebar_grip.bind("<Enter>", lambda e: self.sidebar_grip.configure(fg_color=self._grip_hover))
        self.sidebar_grip.bind("<Leave>", lambda e: self.sidebar_grip.configure(fg_color=self._grip_bg))
        
        self.ai_grip = ctk.CTkFrame(self, width=4, fg_color="#3c3c3c")
        self.ai_grip.grid(row=0, column=4, rowspan=5, sticky="ns")
        self.ai_grip.configure(cursor="sb_h_double_arrow")
        
        self.ai_grip.bind("<Button-1>", self._ai_grip_basla)
        self.ai_grip.bind("<B1-Motion>", self._ai_grip_surukle)
        self.ai_grip.bind("<ButtonRelease-1>", self._ai_grip_birak)
        self.ai_grip.bind("<Enter>", lambda e: self.ai_grip.configure(fg_color=self._grip_hover))
        self.ai_grip.bind("<Leave>", lambda e: self.ai_grip.configure(fg_color=self._grip_bg))

        self._ghost_line_y = tk.Frame(self, bg="#007acc", height=2)
        self._ghost_line_y.place_forget()

        self.terminal_grip = ctk.CTkFrame(self, height=5, fg_color="#3c3c3c")
        self.terminal_grip.configure(cursor="sb_v_double_arrow")
        self.terminal_grip.bind("<Button-1>", self._terminal_grip_basla)
        self.terminal_grip.bind("<B1-Motion>", self._terminal_grip_surukle)
        self.terminal_grip.bind("<ButtonRelease-1>", self._terminal_grip_birak)
        self.terminal_grip.bind("<Enter>", lambda e: self.sidebar_grip.configure(fg_color=self._grip_hover))
        self.terminal_grip.bind("<Leave>", lambda e: self.sidebar_grip.configure(fg_color=self._grip_bg))
        self.terminal_grip.bind("<Enter>", lambda e: self.terminal_grip.configure(fg_color=self._grip_hover))
        self.terminal_grip.bind("<Leave>", lambda e: self.terminal_grip.configure(fg_color=self._grip_bg))

    def _ai_input_focus(self, event=None):
        if self.ai_input.get("1.0", "end-1c").strip() == "Bir şey sor...":
            self.ai_input.delete("1.0", "end")

    def _ai_input_blur(self, event=None):
        if not self.ai_input.get("1.0", "end-1c").strip():
            self.ai_input.insert("1.0", "Bir şey sor...")

    def renk_ayarlarini_yap(self):
        for tag in ["keyword", "builtin", "string", "comment", "number"]:
            self.kod_alani.tag_config(tag, foreground=self.colors.get(tag, "#d4d4d4"))
        # fstring artık string ile aynı renkte (5 renk kuralı)
        self.kod_alani.tag_config("fstring", foreground=self.colors.get("string", "#ce9178"))

        # ODAK KAYBINDA SEÇİMİN SİLİNMEMESİ İÇİN
        tb = getattr(self.kod_alani, "_textbox", self.kod_alani)
        tb.configure(
            exportselection=False,
            selectbackground=self.colors["selection"],
            selectforeground=self.colors["text"],
            inactiveselectbackground=self.colors["selection"],
        )
    def _line_numbers_scroll(self, event):
        kod_tb = getattr(self.kod_alani, "_textbox", self.kod_alani)
        if getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0:
            kod_tb.yview_scroll(-3, "units")
        else:
            kod_tb.yview_scroll(3, "units")
        self._senkronize_scroll()
        return "break"
    def _senkronize_scroll(self, event=None):
        if event and getattr(event, "state", 0) & 0x0004:
            return None
        try:
            kod_tb = getattr(self.kod_alani, "_textbox", self.kod_alani)
            first, last = kod_tb.yview()
            if self.ayarlar.get("satir_numaralari"):
                getattr(self.line_numbers, "_textbox", self.line_numbers).yview_moveto(first)
            if hasattr(self, "minimap") and self.ayarlar.get("minimap"):
                getattr(self.minimap, "_textbox", self.minimap).yview_moveto(first)
        except Exception:
            pass

    def _baglayicilari_ayarla(self):
        txt = getattr(self.kod_alani, "_textbox", self.kod_alani)
        ctk_sb = getattr(self.kod_alani, "_y_scrollbar", None)

        def _editor_yscroll(*args):
            if ctk_sb is not None:
                try:
                    ctk_sb.set(*args)
                except Exception:
                    pass
            self._senkronize_scroll()
        
        txt.configure(yscrollcommand=_editor_yscroll)
        ln = getattr(self.line_numbers, "_textbox", self.line_numbers)
        def _guvenli_undo(event=None):
            try:
                self.kod_alani.edit_undo()
            except Exception:
                pass
            return "break"

        txt.bind("<Control-Z>", _guvenli_undo)
        txt.bind("<Control-z>", _guvenli_undo)
        def _guvenli_redo(event=None):
            try:
                self.kod_alani.edit_redo()
            except Exception:
                pass
            return "break"

        txt.bind("<Control-Y>", _guvenli_redo)
        txt.bind("<Control-y>", _guvenli_redo)
        txt.bind("<Control-S>", lambda e: self.dosya_kaydet())
        txt.bind("<Control-t>", lambda e: self._yeni_sekme_olustur())
        txt.bind("<Control-T>", lambda e: self._yeni_sekme_olustur())
        txt.bind("<Control-Shift-V>", self._alta_yapistir)
        txt.bind("<Control-F>", self._bul_penceresi_ac)
        txt.bind("<Control-O>", lambda e: self.dosya_ac())
        txt.bind("<Control-R>", lambda e: self.kodu_calistir())
        txt.bind("<KeyRelease>", self.on_key_release)
        txt.bind("<Tab>", self._tab_indent)
        txt.bind("<Shift-ISO_Left_Tab>", self._shift_tab_outdent)
        txt.bind("<Shift-Tab>", self._shift_tab_outdent)
        txt.bind("<Return>", self.on_return_key)
        txt.bind("<Down>", self.on_arrow_down)
        txt.bind("<Control-j>", self._terminal_toggle)
        txt.bind("<Up>", self.on_arrow_up)
        txt.bind("<Escape>", lambda e: self.popup_kapat())
        txt.bind("<FocusOut>", lambda e: self.popup_kapat())
        txt.bind("<Button-1>", lambda e: self.popup_kapat(), add="+")
        txt.bind("<Key>", lambda e: self.after_idle(self.sync_line_numbers), add="+")
        txt.bind("<ButtonRelease>", lambda e: self.after_idle(self.sync_line_numbers))
        txt.bind("<Control-s>", lambda e: self.dosya_kaydet())
        txt.bind("<Control-o>", lambda e: self.dosya_ac())
        txt.bind("<Control-r>", lambda e: self.kodu_calistir())
        txt.bind("<F5>", lambda e: self.debugger.devam_et() if getattr(self.debugger, 'calistiriliyor', False) else self.kodu_calistir())
        txt.bind("<Key>", self._dosya_degisti_kontrol, add="+")
        txt.bind("<MouseWheel>", self._senkronize_scroll)
        txt.bind("<Button-4>", self._senkronize_scroll)
        txt.bind("<Button-5>", self._senkronize_scroll)
        
        # Parantez/braket otomatik kapatma
        txt.bind("<Key>", self._parantez_kapat, add="+")
        
        # Seçili metni tırnak içine al
        txt.bind("<Control-quotedbl>", self._seciliyi_tirnak_icine_al)
    
        
        # Font büyüt/küçült
        txt.bind("<Control-plus>", self._font_buyut)
        txt.bind("<Control-minus>", self._font_kucult)
        txt.bind("<Control-KP_Add>", self._font_buyut)
        txt.bind("<Control-KP_Subtract>", self._font_kucult)
        
        # Yorum satırı
        txt.bind("<Control-slash>", self._yorum_toggle)
        
        # Bul/Değiştir
        txt.bind("<Control-f>", self._bul_penceresi_ac)
        txt.bind("<Control-h>", lambda e: self._bul_penceresi_ac(e, degistir=True))
        
        # Satır çoğaltma
        txt.bind("<Control-Shift-D>", self._satir_cogalt)
        
        # Boş satır ekleme
        txt.bind("<Control-Return>", self._bos_satir_ekle_alt)      # ← Düzelt
        txt.bind("<Control-Shift-Return>", self._bos_satir_ekle_ust) # ← Düzelt
        
        # Satır taşıma
        txt.bind("<Alt-Up>", self._satir_yukari_tasi)
        txt.bind("<Alt-Down>", self._satir_asagi_tasi)
        
        # Komut paleti
        txt.bind("<Control-Shift-P>", self._komut_paleti_ac)
        
        # Debugger
        ln.bind("<Button-1>", self._line_number_click)
        txt.bind("<F9>", lambda e: self.debugger.baslat())
        txt.bind("<F10>", lambda e: self.debugger.adim())
        
        if self.ayarlar.get("satir_numaralari"):
            ln.bind("<MouseWheel>", self._line_numbers_scroll)
            ln.bind("<Button-4>", self._line_numbers_scroll)
            ln.bind("<Button-5>", self._line_numbers_scroll)
        
        if self.ayarlar.get("minimap") and hasattr(self, 'minimap'):
            self.minimap.bind("<MouseWheel>", lambda e: self._senkronize_scroll())
            self.minimap.bind("<Button-4>", lambda e: self._senkronize_scroll())
            self.minimap.bind("<Button-5>", lambda e: self._senkronize_scroll())
        # Ctrl + " ile seçili metni tırnak içine alma
        txt.bind("<Key>", self._ctrl_shift_tirnak_kontrol, add="+")

        # Ctrl + tekerlek ile font zoom
        txt.bind("<Control-MouseWheel>", self._zoom_mousewheel, add="+")
        txt.bind("<Control-Button-4>", self._zoom_in_event, add="+")
        txt.bind("<Control-Button-5>", self._zoom_out_event, add="+")

        ln.bind("<Control-MouseWheel>", self._zoom_mousewheel, add="+")
        ln.bind("<Control-Button-4>", self._zoom_in_event, add="+")
        ln.bind("<Control-Button-5>", self._zoom_out_event, add="+")

        if hasattr(self, "minimap") and self.minimap is not None:
            mm = getattr(self.minimap, "_textbox", self.minimap)

            # Minimap tıklama
            mm.bind("<ButtonRelease-1>", self._minimap_tikla, add="+")

            # Minimap üzerinde Ctrl + tekerlek zoom
            mm.bind("<Control-MouseWheel>", self._zoom_mousewheel, add="+")
            mm.bind("<Control-Button-4>", self._zoom_in_event, add="+")
            mm.bind("<Control-Button-5>", self._zoom_out_event, add="+")

        self.popup = None
        self.listbox = None
        # === AI Panel Scrollbar Mousewheel Yönetimi ===
        # Fare tekerleği olayını global yakalayıp, eğer AI sohbeti üzerindeyse oraya yönlendir
        self.bind_all("<MouseWheel>", self._global_mousewheel_yonet, add="+")
        self.bind_all("<Button-4>", self._global_mousewheel_yonet, add="+")
        self.bind_all("<Button-5>", self._global_mousewheel_yonet, add="+")
    def _global_mousewheel_yonet(self, event):
        """Fare tekerleği olaylarını ilgili bölümlere (AI Chat vs.) yönlendirir"""
        try:
            x, y = event.x_root, event.y_root
            widget = self.winfo_containing(x, y)
            if not widget:
                return None

            # Scrollbar üzerindeyse native davranışa izin ver
            if hasattr(self.ai_chat_frame, '_scrollbar') and widget == self.ai_chat_frame._scrollbar:
                return None

            parent = widget
            is_ai_chat = False
            while parent:
                if parent == self.ai_chat_frame:
                    is_ai_chat = True
                    break
                try:
                    parent = parent.master
                except Exception:
                    break

            if is_ai_chat:
                canvas = self.ai_chat_frame._parent_canvas
                
                # Windows/Mac: event.delta, Linux: event.num
                if hasattr(event, 'delta') and event.delta != 0:
                    scroll_amount = int(-1 * (event.delta / 120)) * 5
                elif hasattr(event, 'num'):
                    scroll_amount = -5 if event.num == 4 else 5
                else:
                    return None

                canvas.yview_scroll(scroll_amount, "units")
                return "break"
        except Exception:
            pass
        return None
    def _line_number_click(self, event=None):
        try:
            ln = getattr(self.line_numbers, "_textbox", self.line_numbers)
            idx = ln.index(f"@{event.x},{event.y}")
            g_satir = int(idx.split(".")[0])
            metin = ln.get(f"{g_satir}.0", f"{g_satir}.end")

            # Fold göstergesi varsa sadece fold işle
            if metin and ("▼" in metin or "▶" in metin):
                sonuc = self._fold_tikla(event)
                if sonuc == "break":
                    return "break"
                # Fold tıklaması başarısız olduysa breakpoint'e geçme
                return "break"
        except Exception as e:
            print(f"[Fold Hatası] _line_number_click: {e}")

        self._breakpoint_toggle(event)
        return "break"

    def _ctrl_shift_tirnak_kontrol(self, event=None):
        if not event:
            return None

        state = getattr(event, "state", 0)

        # Ctrl basılı değilse işlem yapma
        if not (state & 0x0004):
            return None

        keysym = str(getattr(event, "keysym", "")).lower()
        char = getattr(event, "char", "")

        if keysym == "quotedbl" or char == '"':
            return self._seciliyi_tirnak_icine_al(event)

        return None

    def _zoom_mousewheel(self, event=None):
        if getattr(event, "delta", 0) > 0:
            self._font_buyut()
        else:
            self._font_kucult()
        return "break"

    def _zoom_in_event(self, event=None):
        self._font_buyut()
        return "break"

    def _zoom_out_event(self, event=None):
        self._font_kucult()
        return "break"
    def _minimap_tikla(self, event=None):
        try:
            if not hasattr(self, "minimap") or not self.minimap.winfo_exists():
                return None

            mm = getattr(self.minimap, "_textbox", self.minimap)
            hedef = mm.index(f"@{event.x},{event.y}")
            hedef_satir = int(hedef.split(".")[0])

            self.kod_alani.see(f"{hedef_satir}.0")
            self.kod_alani.mark_set("insert", f"{hedef_satir}.0")
            self.kod_alani.focus_set()

            return "break"
        except Exception:
            return None
    def _breakpoint_toggle(self, event=None):
        try:
            satir, _ = self._gutter_rakamini_oku(event)
            if satir is None:
                return
            self.debugger.breakpoint_toggle(satir)
        except Exception:
            pass
    def _satir_yukari_tasi(self, event=None):
        try:
            imlec = self.kod_alani.index("insert")
            satir, sutun = imlec.split(".")
            satir = int(satir)
            sutun = int(sutun)

            if satir <= 1:
                return "break"

            mevcut = self.kod_alani.get(f"{satir}.0", f"{satir}.end")
            ust = self.kod_alani.get(f"{satir - 1}.0", f"{satir - 1}.end")

            self.kod_alani.delete(f"{satir}.0", f"{satir}.end")
            self.kod_alani.insert(f"{satir}.0", ust)

            self.kod_alani.delete(f"{satir - 1}.0", f"{satir - 1}.end")
            self.kod_alani.insert(f"{satir - 1}.0", mevcut)

            self.kod_alani.mark_set("insert", f"{satir - 1}.{sutun}")

            self._dosya_degisti_kontrol()
            self.sync_line_numbers()
            self.kod_renklendir()

            return "break"
        except Exception:
            return None
    def _komut_paleti_ac(self, event=None):
        """Ctrl+Shift+P ile komut paleti aç"""
        if hasattr(self, '_palet_pencere') and self._palet_pencere.winfo_exists():
            self._palet_pencere.lift()
            self._palet_entry.focus()
            return "break"
        
        pencere = ctk.CTkToplevel(self)
        pencere.title("Komut Paleti")
        pencere.geometry("500x400")
        pencere.transient(self)
        pencere.resizable(False, False)
        self._palet_pencere = pencere
        
        # Komut listesi
        self.komutlar = [
            ("Dosya: Yeni Sekme", self._yeni_sekme_olustur, "Ctrl+T"),
            ("Dosya: Aç", self.dosya_ac, "Ctrl+O"),
            ("Dosya: Kaydet", self.dosya_kaydet, "Ctrl+S"),
            ("Kod: Çalıştır", self.kodu_calistir, "Ctrl+R / F5"),
            ("Kod: Yorum Satırı Aç/Kapat", self._yorum_toggle, "Ctrl+/"),
            ("Kod: Satırı Yukarı Taşı", self._satir_yukari_tasi, "Alt+↑"),
            ("Kod: Satırı Aşağı Taşı", self._satir_asagi_tasi, "Alt+↓"),
            ("Kod: Satırı Çoğalt", self._satir_cogalt, "Ctrl+Shift+D"),
            ("Editör: Bul", lambda: self._bul_penceresi_ac(degistir=False), "Ctrl+F"),
            ("Editör: Değiştir", lambda: self._bul_penceresi_ac(degistir=True), "Ctrl+H"),
            ("Editör: Font Büyüt", self._font_buyut, "Ctrl++"),
            ("Editör: Font Küçült", self._font_kucult, "Ctrl+-"),
            ("AI: Kodu Düzelt", self._ai_kodu_duzelt, ""),
            ("AI: Kodu Açıkla", self._ai_kodu_acikla, ""),
            ("AI: Kodu Optimize Et", self._ai_kodu_optimize, ""),
            ("Görünüm: Gezgin Aç/Kapat", self._gezgin_ac, ""),
            ("Görünüm: AI Panel Aç/Kapat", self._ai_panel_toggle, ""),
            ("Ayarlar: Pencere Aç", self._ayarlar_penceresi_ac, ""),
            ("Görünüm: Terminal Aç/Kapat", self._terminal_toggle, "Ctrl+J"),
            ("Kod: TürKod ⇄ Python Çevir", self._kodu_cevir, ""),
            ("Kod: Python ⇄ TürKod Arama", self._kod_arama_ac, ""),
        ]
        
        # Arama kutusu
        self._palet_entry = ctk.CTkEntry(pencere, font=("Segoe UI", 12), height=35)
        self._palet_entry.pack(fill="x", padx=10, pady=10)
        self._palet_entry.focus()
        
        # Sonuç listesi
        self._palet_liste = ctk.CTkScrollableFrame(pencere, fg_color="transparent")
        self._palet_liste.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        def _palet_filtrele(*args):
            arama = self._palet_entry.get().lower()

            for widget in self._palet_liste.winfo_children():
                widget.destroy()

            self._palet_butonlari = []
            self._palet_secim = 0

            for isim, cmd, kisa in self.komutlar:
                if arama in isim.lower():
                    btn = ctk.CTkButton(
                        self._palet_liste,
                        text=isim if not kisa else f"{isim}  ({kisa})",
                        anchor="w",
                        fg_color="transparent",
                        hover_color=self.colors.get("button_hover", "#313131"),
                        text_color=self.colors["text"],
                        command=lambda c=cmd: (pencere.destroy(), c())
                    )
                    btn.pack(fill="x", pady=1)
                    self._palet_butonlari.append((btn, cmd))

            _palet_secim_guncelle()
        def _palet_secim_guncelle():
            if not getattr(self, "_palet_butonlari", None):
                return
            secim_bg = self.colors.get("selection", "#264f78")
            secim_fg = self._secim_metin_rengi()
            for i, (btn, _) in enumerate(self._palet_butonlari):
                if i == self._palet_secim:
                    btn.configure(fg_color=secim_bg, text_color=secim_fg)
                else:
                    btn.configure(fg_color="transparent", text_color=self.colors["text"])

        def _palet_key(event):
            if not getattr(self, "_palet_butonlari", None):
                return None

            if event.keysym == "Down":
                self._palet_secim = min(self._palet_secim + 1, len(self._palet_butonlari) - 1)
                _palet_secim_guncelle()
                return "break"

            if event.keysym == "Up":
                self._palet_secim = max(self._palet_secim - 1, 0)
                _palet_secim_guncelle()
                return "break"

            if event.keysym == "Return":
                _, cmd = self._palet_butonlari[self._palet_secim]
                pencere.destroy()
                cmd()
                return "break"

            return None

        self._palet_entry.bind("<KeyRelease>", _palet_filtrele)
        self._palet_entry.bind("<Key>", _palet_key)
        
        # İlk listeyi doldur
        _palet_filtrele()
        
        return "break"
    def _satir_asagi_tasi(self, event=None):
        try:
            imlec = self.kod_alani.index("insert")
            satir, sutun = imlec.split(".")
            satir = int(satir)
            sutun = int(sutun)

            son_satir = int(self.kod_alani.index("end-1c").split(".")[0])

            if satir >= son_satir:
                return "break"

            mevcut = self.kod_alani.get(f"{satir}.0", f"{satir}.end")
            alt = self.kod_alani.get(f"{satir + 1}.0", f"{satir + 1}.end")

            self.kod_alani.delete(f"{satir}.0", f"{satir}.end")
            self.kod_alani.insert(f"{satir}.0", alt)

            self.kod_alani.delete(f"{satir + 1}.0", f"{satir + 1}.end")
            self.kod_alani.insert(f"{satir + 1}.0", mevcut)

            self.kod_alani.mark_set("insert", f"{satir + 1}.{sutun}")

            self._dosya_degisti_kontrol()
            self.sync_line_numbers()
            self.kod_renklendir()

            return "break"
        except Exception:
            return None
    def _bos_satir_ekle_alt(self, event=None):
        """Ctrl+Enter → İmleç hareket etmeden alt satıra boş satır ekle"""
        try:
            satir = self.kod_alani.index("insert").split(".")[0]
            self.kod_alani.insert(f"{satir}.end", "\n")
            self.sync_line_numbers()
            return "break"
        except Exception:
            pass
        return None

    def _bos_satir_ekle_ust(self, event=None):
        """Ctrl+Shift+Enter → İmleç hareket etmeden üst satıra boş satır ekle"""
        try:
            satir = self.kod_alani.index("insert").split(".")[0]
            self.kod_alani.insert(f"{satir}.0", "\n")
            self.sync_line_numbers()
            return "break"
        except Exception:
            pass
        return None
    def _satir_cogalt(self, event=None):
        """Ctrl+Shift+D ile mevcut satırı altına kopyala"""
        try:
            satir = self.kod_alani.index("insert").split(".")[0]
            satir_metni = self.kod_alani.get(f"{satir}.0", f"{satir}.end")
            self.kod_alani.insert(f"{satir}.end", f"\n{satir_metni}")
            self.sync_line_numbers()
            self.kod_renklendir()
            return "break"
        except Exception:
            pass
        return None
    def _bul_penceresi_ac(self, event=None, degistir=False):
        # Panel açıksa: aynı modsa öne getir, farklı modsa yeniden kur
        if hasattr(self, '_bul_pencere') and self._bul_pencere.winfo_exists():
            if getattr(self, '_bul_modu', None) == degistir:
                self._bul_pencere.lift()
                return "break"
            self._bul_pencere.destroy()

        pencere = ctk.CTkToplevel(self)
        pencere.title("Değiştir" if degistir else "Bul")
        pencere.geometry("400x160" if degistir else "400x100")
        pencere.transient(self)
        pencere.resizable(False, False)
        self._bul_pencere = pencere
        self._bul_modu = degistir

        def _kapat():
            self.kod_alani.tag_remove("sel", "1.0", "end")
            pencere.destroy()

        pencere.protocol("WM_DELETE_WINDOW", _kapat)
        pencere.bind("<Escape>", lambda e: _kapat())

        # Bul satırı
        ctk.CTkLabel(pencere, text="Bul:", font=("Segoe UI", 11)).grid(row=0, column=0, padx=10, pady=8, sticky="e")
        bul_var = ctk.StringVar()
        bul_entry = ctk.CTkEntry(pencere, textvariable=bul_var, width=280)
        bul_entry.grid(row=0, column=1, padx=5, pady=8, sticky="w")
        bul_entry.focus()

        # Değiştir satırı (SADECE Ctrl+H)
        degis_var = ctk.StringVar()
        degis_entry = None
        if degistir:
            ctk.CTkLabel(pencere, text="Değiştir:", font=("Segoe UI", 11)).grid(row=1, column=0, padx=10, pady=5, sticky="e")
            degis_entry = ctk.CTkEntry(pencere, textvariable=degis_var, width=280)
            degis_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        def bul_sonraki():
            aranan = bul_var.get()
            if not aranan:
                return
            bas = self.kod_alani.index("insert")
            pos = self.kod_alani.search(aranan, bas, stopindex="end")
            if not pos:
                pos = self.kod_alani.search(aranan, "1.0", stopindex=bas)
            if pos:
                bit = f"{pos}+{len(aranan)}c"
                self.kod_alani.tag_remove("sel", "1.0", "end")
                self.kod_alani.tag_add("sel", pos, bit)
                self.kod_alani.mark_set("insert", bit)
                self.kod_alani.see(pos)

        def secili_degistir():
            aranan = bul_var.get()
            degisen = degis_var.get()
            if not aranan:
                return
            if self.kod_alani.tag_ranges("sel"):
                secili = self.kod_alani.get("sel.first", "sel.last")
                if secili == aranan:
                    self.kod_alani.delete("sel.first", "sel.last")
                    self.kod_alani.insert("insert", degisen)
            bul_sonraki()

        def tumunu_degistir():
            aranan = bul_var.get()
            degisen = degis_var.get()
            if not aranan:
                return
            icerik = self.kod_alani.get("1.0", "end-1c")
            self.kod_alani.delete("1.0", "end")
            self.kod_alani.insert("1.0", icerik.replace(aranan, degisen))
            self.sync_line_numbers()
            self.kod_renklendir()

        btn_frame = ctk.CTkFrame(pencere, fg_color="transparent")
        btn_frame.grid(row=2 if degistir else 1, column=0, columnspan=2, pady=10)

        ctk.CTkButton(btn_frame, text="Sonraki", width=80, command=bul_sonraki,
            fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"]).pack(side="left", padx=3)

        # Değiştir butonları SADECE degistir=True ise (Ctrl+H)
        if degistir:
            ctk.CTkButton(btn_frame, text="Değiştir", width=80, command=secili_degistir,
                fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"]).pack(side="left", padx=3)
            ctk.CTkButton(btn_frame, text="Tümünü Değiştir", width=110, command=tumunu_degistir,
                fg_color="#c75450", hover_color="#a03030").pack(side="left", padx=3)

        ctk.CTkButton(btn_frame, text="Kapat", width=60, command=_kapat,
            fg_color="transparent", hover_color="#c75450").pack(side="left", padx=3)

        bul_entry.bind("<Return>", lambda e: bul_sonraki())
        if degistir and degis_entry is not None:
            degis_entry.bind("<Return>", lambda e: secili_degistir())

        return "break"
    def _yorum_toggle(self, event=None):
        """Ctrl+/ ile seçili satırları yorumla veya yorumdan çıkar"""
        try:
            if self.kod_alani.tag_ranges("sel"):
                bas = self.kod_alani.index("sel.first")
                bit = self.kod_alani.index("sel.last")
            else:
                satir = self.kod_alani.index("insert").split(".")[0]
                bas = f"{satir}.0"
                bit = f"{satir}.end"
            
            bas_satir = int(bas.split(".")[0])
            bit_satir = int(bit.split(".")[0])
            
            # Tüm satırlar yorumlu mu kontrol et
            hepsi_yorumlu = True
            for satir_no in range(bas_satir, bit_satir + 1):
                satir_metni = self.kod_alani.get(f"{satir_no}.0", f"{satir_no}.end")
                if satir_metni.strip() and not satir_metni.strip().startswith("#"):
                    hepsi_yorumlu = False
                    break
            
            for satir_no in range(bas_satir, bit_satir + 1):
                satir_metni = self.kod_alani.get(f"{satir_no}.0", f"{satir_no}.end")
                if hepsi_yorumlu:
                    # Yorumdan çıkar
                    if satir_metni.strip().startswith("# "):
                        yeni = satir_metni.replace("# ", "", 1)
                    elif satir_metni.strip().startswith("#"):
                        yeni = satir_metni.replace("#", "", 1)
                    else:
                        continue
                    self.kod_alani.delete(f"{satir_no}.0", f"{satir_no}.end")
                    self.kod_alani.insert(f"{satir_no}.0", yeni)
                else:
                    # Yorum yap
                    if satir_metni.strip():
                        self.kod_alani.insert(f"{satir_no}.0", "# ")
            
            self.sync_line_numbers()
            self.kod_renklendir()
            return "break"
        except Exception:
            pass
        return None
    def _parantez_kapat(self, event=None):
        if not event or len(getattr(event, "char", "")) != 1:
            return None

        # Ctrl basılıysa özel kısayolları bozma
        if getattr(event, "state", 0) & 0x0004:
            return None
        
        acilis = {'(': ')', '[': ']', '{': '}', '"': '"', "'": "'"}
        kapanis = {')', ']', '}', '"', "'"}
        
        # Kapanış karakteri yazıldıysa ve sağda aynısı varsa sadece sağa geç
        if event.char in kapanis:
            try:
                sag = self.kod_alani.get("insert", "insert+1c")
                if sag == event.char:
                    self.kod_alani.mark_set("insert", "insert+1c")
                    return "break"  # ← Ekle
            except:
                pass
            return None  # Normal karakter, default handler çalışsın
        
        if event.char not in acilis:
            return None
        
        kapat = acilis[event.char]
        
        try:
            if self.kod_alani.tag_ranges("sel"):
                secili = self.kod_alani.get("sel.first", "sel.last")
                self.kod_alani.delete("sel.first", "sel.last")
                self.kod_alani.insert("insert", f"{event.char}{secili}{kapat}")
                # Seçili metni tekrar seç (açılış ve kapanış hariç)
                bitis = f"insert-{len(kapat)}c"
                baslangic = f"insert-{len(kapat) + len(secili)}c"
                self.kod_alani.tag_remove("sel", "1.0", "end")
                self.kod_alani.tag_add("sel", baslangic, bitis)
                self.kod_alani.mark_set("insert", bitis)
                return "break"
            else:
                self.kod_alani.insert("insert", f"{event.char}{kapat}")
                self.kod_alani.mark_set("insert", "insert-1c")
                return "break"  # ← Ekle
        except:
            return None
    def _alta_yapistir(self, event=None):
        """Ctrl+V ile panodaki metni yeni satıra yapıştırır"""
        try:
            icerik = self.clipboard_get()
            # İmleci satır sonuna götür, yeni satır aç, yapıştır
            satir = self.kod_alani.index("insert").split(".")[0]
            satir_sonu = f"{satir}.end"
            self.kod_alani.mark_set("insert", satir_sonu)
            self.kod_alani.insert("insert", "\n" + icerik)
            self.sync_line_numbers()
            self.kod_renklendir()
            return "break"
        except Exception:
            # Normal yapıştırma davranışı (panoda metin yoksa vs.)
            return None
    def _font_buyut(self, event=None):
        """Ctrl++ → Font boyutunu 1 artır"""
        mevcut = self.ayarlar.get("yazi_boyutu")
        if mevcut < 32:
            yeni = mevcut + 1
            self.ayarlar.set("yazi_boyutu", yeni)
            self.kod_alani.configure(font=(self.ayarlar.get("yazi_tipi"), yeni))
            self.line_numbers.configure(font=(self.ayarlar.get("yazi_tipi"), yeni))
            self.status_left.configure(text=f"  Font boyutu: {yeni}px")
        return "break"

    def _font_kucult(self, event=None):
        """Ctrl+- → Font boyutunu 1 azalt"""
        mevcut = self.ayarlar.get("yazi_boyutu")
        if mevcut > 8:
            yeni = mevcut - 1
            self.ayarlar.set("yazi_boyutu", yeni)
            self.kod_alani.configure(font=(self.ayarlar.get("yazi_tipi"), yeni))
            self.line_numbers.configure(font=(self.ayarlar.get("yazi_tipi"), yeni))
            self.status_left.configure(text=f"  Font boyutu: {yeni}px")
        return "break"
    def _shift_tab_outdent(self, event=None):
        """Shift+Tab: Seçili satırları sola kaydır"""
        try:
            if self.kod_alani.tag_ranges("sel"):
                bas = self.kod_alani.index("sel.first")
                bit = self.kod_alani.index("sel.last")
                bas_satir = int(bas.split(".")[0])
                bit_satir = int(bit.split(".")[0])
                for satir_no in range(bas_satir, bit_satir + 1):
                    # 2 karakterlik kontrol yeterli (2 boşluk veya tab veya 4 boşluğun ilk 2'si)
                    satir_metni = self.kod_alani.get(f"{satir_no}.0", f"{satir_no}.2")
                    if satir_metni.startswith("  "): # 2 veya 4 boşluk fark etmez, baştaki 2'yi siler
                        self.kod_alani.delete(f"{satir_no}.0", f"{satir_no}.2")
                    elif satir_metni.startswith("\t"):
                        self.kod_alani.delete(f"{satir_no}.0", f"{satir_no}.1")
                
                yeni_bas = f"{bas_satir}.0"
                yeni_bit = f"{bit_satir}.end"
                self.kod_alani.tag_remove("sel", "1.0", "end")
                self.kod_alani.tag_add("sel", yeni_bas, yeni_bit)
                self.sync_line_numbers()
                return "break"
        except Exception:
            pass
        return None
    def _seciliyi_tirnak_icine_al(self, event=None):
        try:
            if self.kod_alani.tag_ranges("sel"):
                bas = self.kod_alani.index("sel.first")
                bit = self.kod_alani.index("sel.last")
                secili = self.kod_alani.get(bas, bit)

                self.kod_alani.delete(bas, bit)
                self.kod_alani.insert(bas, f'"{secili}"')

                self.kod_alani.tag_remove("sel", "1.0", "end")
                self.kod_alani.tag_add(
                    "sel",
                    f"{bas}+1c",
                    f"{bas}+{len(secili) + 1}c"
                )
                self.kod_alani.mark_set("insert", f"{bas}+{len(secili) + 1}c")

                self._dosya_degisti_kontrol()
                self.sync_line_numbers()
                self.kod_renklendir()
                return "break"

            kelime, bas, bit = self.mevcut_kelimeyi_al()
            if kelime:
                self.kod_alani.delete(bas, bit)
                self.kod_alani.insert(bas, f'"{kelime}"')
                self.kod_alani.mark_set("insert", f"{bas}+{len(kelime) + 1}c")

                self._dosya_degisti_kontrol()
                self.sync_line_numbers()
                self.kod_renklendir()
                return "break"

        except Exception:
            pass

        return None
    def _dosya_degisti_kontrol(self, event=None):
        if event is not None:
            # Sadece metni gerçekten değiştiren tuşlar
            if not event.char and event.keysym not in ("Return", "BackSpace", "Delete", "Tab"):
                return
        sekme = self._aktif_sekme()
        if sekme and not sekme["degisti"]:
            sekme["degisti"] = True
            self._sekme_baslik_guncelle()

    def _ornek_kod_yukle(self):
        ornek_kod = 'yazdır("Merhaba Dünya")'
        self._yeni_sekme_olustur(isim="main.trpy", icerik=ornek_kod)
    def _oturum_ac(self):
        """Kapanıştaki sekmeleri geri yükle; dosya yoksa atla."""
        oturum = self.ayarlar.get("son_oturum") or []
        aktif_sira = self.ayarlar.get("son_oturum_aktif") or 0
        acilan = []  # (orijinal_sira, sid)
        for sira, kayit in enumerate(oturum):
            try:
                yol = kayit.get("yol")
                if yol:
                    if not os.path.exists(yol):
                        continue  # dosya bulunamadıysa yükleme
                    sid = self._yeni_sekme_olustur(yol=yol)
                else:
                    sid = self._yeni_sekme_olustur(
                        isim=kayit.get("isim") or "Untitled.trpy",
                        icerik=kayit.get("icerik") or "")
                acilan.append((sira, sid))
            except Exception:
                continue
        if not acilan:
            self._ornek_kod_yukle()  # oturum yoksa örnek kod
            return
        hedef_sid = acilan[-1][1]
        for sira, sid in acilan:
            if sira == aktif_sira:
                hedef_sid = sid
                break
        self._sekme_aktif_yap(hedef_sid)
    def _modelleri_guncelle(self):
        """Ayarlarla model listesini güncelle ve eski modeli düzelt"""
        saglayici = self.ayarlar.get("ai_saglayici")
        api_key = self.ayarlar.get("ai_api_key")
        mevcut_model = self.ayarlar.get("ai_model")

        # API key varsa dinamik güncelle
        if api_key:
            if saglayici == "Groq":
                threading.Thread(
                    target=groq_modelleri_guncelle,
                    args=(api_key,),
                    daemon=True
                ).start()
            elif saglayici == "OpenAI":
                threading.Thread(
                    target=openai_modelleri_guncelle,
                    args=(api_key,),
                    daemon=True
                ).start()

        # ← EKLE: Kayıtlı model listede yoksa ilk modele düzelt
        self.after(3000, lambda: self._model_dogrula(saglayici, mevcut_model))

    def _model_dogrula(self, saglayici, mevcut_model):
        """Kayıtlı model hala geçerli mi kontrol et, değilse düzelt"""
        try:
            if saglayici in AI_MODELLERI:
                gecerli_modeller = AI_MODELLERI[saglayici]
                if mevcut_model not in gecerli_modeller and gecerli_modeller:
                    yeni_model = gecerli_modeller[0]
                    self.ayarlar.set("ai_model", yeni_model)
                    print(f"[TurKod] Model otomatik guncellendi: "
                          f"{mevcut_model} → {yeni_model}")
                    # Durum çubuğunda bildir
                    if hasattr(self, 'status_left'):
                        self.status_left.configure(
                            text=f"  ⚠ Model güncellendi: {yeni_model}"
                        )
        except Exception:
            pass
    def _otomatik_kaydetme_baslat(self):
        def kontrol():
            while not self._kapatildi:
                time.sleep(self.ayarlar.get("otomatik_kaydetme_aralik"))
                if self._kapatildi:
                    break
                if self.ayarlar.get("otomatik_kaydetme"):
                    try:
                        self.after(0, self._otomatik_kaydet)
                    except Exception:
                        break  # uygulama yok edildi, thread'i bitir
        threading.Thread(target=kontrol, daemon=True).start()
    def _ai_welcome_kur(self):
        """Sohbet boşken gösterilen karşılama ekranı"""
        # Eski animasyonu durdur
        self._yildiz_anim_aktif = False
        if getattr(self, "_yildiz_after", None):
            try:
                self.after_cancel(self._yildiz_after)
            except Exception:
                pass
            self._yildiz_after = None

        if getattr(self, "ai_welcome", None) and self.ai_welcome.winfo_exists():
            self.ai_welcome.destroy()

        w = ctk.CTkFrame(self.ai_chat_frame, fg_color="transparent")

        # Parlayan sarı yıldız: Canvas + katmanlı glow
        zemin = self.colors.get("ai_panel", "#252526")
        self.yildiz_canvas = tk.Canvas(
            w, width=150, height=150, bg=zemin,
            highlightthickness=0, bd=0
        )
        self.yildiz_canvas.pack(pady=(30, 4))

        ctk.CTkLabel(w, text="Size nasıl yardımcı olabilirim?",
                     font=("Segoe UI", 14, "bold"),
                     text_color=self.colors["text"]).pack(pady=(0, 2))
        ctk.CTkLabel(w, text="Bir soru yazın veya alttaki hızlı aksiyonları kullanın.",
                     font=("Segoe UI", 10),
                     text_color=self.colors.get("line_number", "#888")).pack()
        w.pack(fill="x")
        self.ai_welcome = w

        self._yildiz_faz = 0.0
        self._yildiz_anim_aktif = True
        self._parlak_yildiz_ciz()
    def _renk_rgb(self, renk):
        """Hex veya isimli tk rengini 0-255 RGB'ye çevirir"""
        try:
            r, g, b = self.winfo_rgb(renk)
            return r >> 8, g >> 8, b >> 8
        except Exception:
            return (37, 37, 37)
    def _kontrast_metin(self, zemin, acik="#ffffff", koyu="#1e1e1e"):
        r, g, b = self._renk_rgb(zemin)
        parlaklik = (r * 299 + g * 587 + b * 114) / 1000
        return acik if parlaklik < 160 else koyu

    def _status_metin_rengi(self):
        return self._kontrast_metin(self.colors.get("status_bar", "#007acc"))

    def _secim_metin_rengi(self):
        return self._kontrast_metin(self.colors.get("selection", "#264f78"))
    def _renk_karisim(self, c1, c2, t):
        """c1'den c2'ye t (0..1) oranında lineer geçiş"""
        a = self._renk_rgb(c1)
        b = self._renk_rgb(c2)
        return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

    def _yildiz_noktalari(self, cx, cy, R, r, donme=0.0):
        """5 köşeli yıldızın polygon noktaları"""
        pts = []
        for i in range(10):
            aci = -math.pi / 2 + i * math.pi / 5 + donme
            rad = R if i % 2 == 0 else r
            pts.extend((cx + rad * math.cos(aci), cy + rad * math.sin(aci)))
        return pts

    def _parlak_yildiz_ciz(self):
        if getattr(self, "_resize_aktif", False):
            return
        canvas = getattr(self, "yildiz_canvas", None)
        if not getattr(self, "_yildiz_anim_aktif", False):
            return
        if canvas is None or not canvas.winfo_exists():
            self._yildiz_anim_aktif = False
            return
        canvas.delete("all")
        zemin = self.colors.get("ai_panel", "#252526")
        SARI = "#FFD700"
        cx = cy = 75
        faz = getattr(self, "_yildiz_faz", 0.0)
        donme = getattr(self, "_yildiz_donme", 0.0)   # ← YENİ
        nabiz = (math.sin(faz) + 1) / 2
        R = 26 + 3 * nabiz
        r = R * 0.42
        KATMAN = 12
        for i in range(KATMAN, 0, -1):
            t = i / KATMAN
            skala = 1.0 + 1.2 * t
            yogunluk = ((1 - t) ** 2) * (0.45 + 0.25 * nabiz)
            renk = self._renk_karisim(zemin, SARI, min(1.0, yogunluk))
            canvas.create_polygon(
                self._yildiz_noktalari(cx, cy, R * skala, r * skala, donme),
                fill=renk, outline=""
            )
        canvas.create_polygon(self._yildiz_noktalari(cx, cy, R, r, donme),
                              fill=SARI, outline="")
        canvas.create_polygon(
            self._yildiz_noktalari(cx, cy, R * 0.55, r * 0.55, donme),
            fill=self._renk_karisim(SARI, "#FFFFFF", 0.35 + 0.3 * nabiz),
            outline=""
        )
        self._yildiz_faz = faz + 0.12
        self._yildiz_donme = donme + 0.3   # ← YENİ: dönme hızı (rad/tik)
        self._yildiz_after = self.after(70, self._parlak_yildiz_ciz)
    def _otomatik_kaydet(self):
        if self._kapatildi or not self.winfo_exists():
            return
        sekme = self._aktif_sekme()
        if sekme and sekme["yol"] and sekme["degisti"]:
            try:
                with open(sekme["yol"], "w", encoding="utf-8") as f:
                    f.write(self.kod_alani.get("1.0", "end"))
                sekme["degisti"] = False
                self._sekme_baslik_guncelle()
                self.status_left.configure(text=f"  Otomatik kaydedildi: {sekme['isim']}")
            except Exception:
                pass

    # ============ DOSYA GEZGINI ============
    def _proje_ac(self):
        dizin = filedialog.askdirectory(title="Proje Dizini Seç",
                                         initialdir=self.proje_dizini)
        if dizin:
            self.proje_dizini = dizin
            self.ayarlar.set("son_proje_dizini", dizin)
            self._dosya_tree_guncelle()

    def _dosya_tree_guncelle(self):
        self.dosya_tree.delete(*self.dosya_tree.get_children())
        
        if not self.proje_dizini or not os.path.exists(self.proje_dizini):
            return

        proje_adi = os.path.basename(self.proje_dizini) or "Proje"
        root_node = self.dosya_tree.insert(
            "", "end", 
            text=f"📁 {proje_adi}", 
            values=(self.proje_dizini, "directory", "expanded"),
            open=True, 
            tags=("directory",)
        )
        
        self._tree_doldur(self.proje_dizini, root_node)

    def _tree_doldur(self, dizin, parent_node):
        try:
            with os.scandir(dizin) as entries:
                tum_girdiler = list(entries)
                
                MAX_OGE = 300
                fazla_mesaj = None
                
                tum_sayi = len(tum_girdiler)
                if tum_sayi > MAX_OGE:
                    tum_girdiler = tum_girdiler[:MAX_OGE]
                    fazla_mesaj = f"... ({tum_sayi - MAX_OGE} öğe daha var)"
                
                klasorler = []
                dosyalar = []
                
                for entry in tum_girdiler:
                    if entry.name.startswith('.'):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        klasorler.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        dosyalar.append(entry)
                
                klasorler.sort(key=lambda e: e.name.lower())
                dosyalar.sort(key=lambda e: e.name.lower())

                for entry in klasorler:
                    tam_yol = entry.path
                    node = self.dosya_tree.insert(
                        parent_node, "end",
                        text=f"📁 {entry.name}",
                        values=(tam_yol, "directory", "collapsed"),
                        tags=("directory",)
                    )
                    self.dosya_tree.insert(node, "end", text="⏳ Yükleniyor...", 
                                           values=("", "dummy"), tags=("dummy",))

                for entry in dosyalar:
                    tam_yol = entry.path
                    uzanti = os.path.splitext(entry.name)[1].lower()
                    
                    if uzanti == ".trpy":
                        icon, tag = "📄", "trpy"
                    elif uzanti == ".py":
                        icon, tag = "🐍", "python"
                    else:
                        icon, tag = "📄", "other"

                    self.dosya_tree.insert(
                        parent_node, "end",
                        text=f"{icon} {entry.name}",
                        values=(tam_yol, "file"),
                        tags=(tag,)
                    )
                
                if fazla_mesaj:
                    self.dosya_tree.insert(
                        parent_node, "end",
                        text=fazla_mesaj,
                        values=("", "dummy"),
                        tags=("dummy",)
                    )
                    
        except PermissionError:
            pass
        except Exception as e:
            print(f"[TurKod] Ağaç doldurma hatası: {e}")

    def _tree_node_ac_kapat(self, event=None, item=None):
        if item is None:
            item = self.dosya_tree.selection()
            if not item:
                return
            item = item[0]

        values = self.dosya_tree.item(item, "values")
        if not values or len(values) < 2:
            return

        tam_yol, tip = values[0], values[1]

        if tip == "file":
            if os.path.exists(tam_yol):
                self._dosya_ac_yol(tam_yol)
            return

        if tip != "directory":
            return

        durum = values[2] if len(values) > 2 else "collapsed"

        if durum == "collapsed":
            for child in self.dosya_tree.get_children(item):
                self.dosya_tree.delete(child)

            # Thread/after YOK: ana thread'de doğrudan doldur
            self._tree_doldur(tam_yol, item)
            self.dosya_tree.item(item, values=(tam_yol, "directory", "expanded"))
            self.dosya_tree.item(item, open=True)
        else:
            for child in self.dosya_tree.get_children(item):
                self.dosya_tree.delete(child)
            self.dosya_tree.insert(item, "end", text="⏳ Yükleniyor...",
                                   values=("", "dummy"), tags=("dummy",))
            self.dosya_tree.item(item, values=(tam_yol, "directory", "collapsed"))
            self.dosya_tree.item(item, open=False)

    def _tree_tagleri_ayarla(self):
        if hasattr(self, '_tree_tags_ayarlandi'):
            return
        
        self.dosya_tree.tag_configure("directory", foreground="#569cd6")
        self.dosya_tree.tag_configure("trpy", foreground="#ce9178")
        self.dosya_tree.tag_configure("python", foreground="#dcdcaa")
        self.dosya_tree.tag_configure("other", foreground="#d4d4d4")
        self.dosya_tree.tag_configure("dummy", foreground="#666666", font=("Segoe UI", 9, "italic"))
        
        self._tree_tags_ayarlandi = True

    def _dosya_tree_cift_tik(self, event):
        item = self.dosya_tree.identify_row(event.y)
        if not item:
            return
        
        values = self.dosya_tree.item(item, "values")
        if not values:
            return
        
        tip = values[1] if len(values) > 1 else ""
        
        if tip == "directory":
            self._tree_node_ac_kapat(item=item)
        elif tip == "file":
            tam_yol = values[0]
            if os.path.exists(tam_yol):
                self._dosya_ac_yol(tam_yol)


    # ============ AI PANEL ============
    def _ai_kodu_acikla(self):
        kod = self.kod_alani.get("1.0", "end-1c").strip()

        if not kod:
            self._ai_mesaj_ekle("assistant", "⚠️ Açıklanacak kod bulunamadı.")
            return

        prompt = f"""Aşağıdaki TürKod kodunu satır satır açıkla ve ne yaptığını özetle:

    ```TürKod
    {kod}
    ```"""

        self._ai_gonder_prompt(prompt)
    def _ai_kodu_uygula(self, kod):
        # Kod zaten TürKod (program çevirdi), direkt uygula
        mevcut_kod = self.kod_alani.get("1.0", "end-1c").strip()
            
        if mevcut_kod:
            cevap = messagebox.askyesnocancel(
                "✏️ Kodu Uygula",
                "AI'in verdiği kod mevcut kodunuzun yerine geçsin mi?\n\n"
                "• Evet = Mevcut kodun üstüne yaz\n"
                "• Hayır = Kodu imlecin olduğu yere ekle\n"
                "• İptal = Hiçbir şey yapma",
                icon='question'
            )
                
            if cevap is None:  
                return
            elif cevap is True:  
                self.kod_alani.delete("1.0", "end")
                self.kod_alani.insert("1.0", kod)
            else:  
                self.kod_alani.insert("insert", kod)
        else:
            self.kod_alani.delete("1.0", "end")
            self.kod_alani.insert("1.0", kod)
            
        self._dosya_degisti_kontrol()
        self.sync_line_numbers()
        self.kod_renklendir()
        self.status_left.configure(text="  AI kodu editöre uygulandı ✓")

    def _yeni_sekme_olustur(self, yol=None, isim=None, icerik=None):
        self.sekme_id_sayac += 1
        sid = self.sekme_id_sayac

        if yol and os.path.exists(yol):
            isim = os.path.basename(yol)
            try:
                with open(yol, "r", encoding="utf-8") as f:
                    icerik = f.read()
            except Exception as e:
                messagebox.showerror("Hata", f"Dosya okunamadı: {e}")
                icerik = ""
        else:
            isim = isim or f"Untitled-{sid}.trpy"
            icerik = icerik or ""
            yol = None

        frame = ctk.CTkFrame(
            self.sekmeler_container,
            width=170, height=26,
            fg_color=self.colors["tab_inactive"],
            corner_radius=16,
            border_width=0
        )
        frame.pack(side="left", padx=(0, 2))
        frame.grid_propagate(False)
        frame.columnconfigure(0, weight=1)

        lbl = ctk.CTkLabel(frame, text=isim, font=("Segoe UI", 9, "bold"),
                           text_color=self.colors["text"], anchor="w")
        lbl.grid(row=0, column=0, sticky="w", padx=(10, 2), pady=0)

        kapat_btn = ctk.CTkButton(
            frame,
            text="×",
            width=18, height=18,
            fg_color="transparent",
            hover_color=self.colors["button_hover"],
            text_color=self.colors["line_number"],
            font=("Segoe UI", 11),
            corner_radius=6,
            command=lambda id=sid: self._sekme_kapat(id)
        )
        kapat_btn.grid(row=0, column=1, padx=(0, 5), pady=5)

        for widget in [frame, lbl]:
            widget.bind("<Button-1>", lambda e, id=sid: self._sekme_aktif_yap(id))
        for widget in (frame, lbl, kapat_btn):
            widget.bind("<MouseWheel>", self._sekme_wheel)
            widget.bind("<Button-4>", lambda e: self._sekme_kaydir(120))
            widget.bind("<Button-5>", lambda e: self._sekme_kaydir(-120))

        sekme = {
            "id": sid,
            "frame": frame,
            "label": lbl,
            "kapat_btn": kapat_btn,
            "isim": isim,
            "yol": yol,
            "icerik": icerik,
            "degisti": False
        }
        self.sekmeler.append(sekme)
        self._sekme_aktif_yap(sid)
        self._sekme_layout_guncelle()
        self._sekme_acilis_animasyonu(sekme)
        return sid
    def _sekme_acilis_animasyonu(self, sekme, adim=0):
        """Yeni sekme soldan sağa açılarak belirir"""
        TOPLAM = 7
        PLUS_PAY = 30
        try:
            if not sekme["frame"].winfo_exists():
                return
        except Exception:
            return

        hedef = max(90, getattr(self, "_sekme_genisligi", 170))
        t = (adim + 1) / TOPLAM
        t = 1 - (1 - t) ** 3  # ease-out cubic
        w = max(24, int(hedef * t))

        n = len(self.sekmeler)
        base = (n - 1) * (hedef + 2)  # diğer sekmelerin kapladığı alan
        sekme["frame"].configure(width=w)

        tabs_w = base + w + 2
        self.yeni_sekme_btn.place(x=tabs_w + 2, y=7)
        self.sekmeler_container.configure(width=tabs_w + PLUS_PAY)

        if adim < TOPLAM - 1:
            self.after(16, lambda s=sekme, a=adim + 1: self._sekme_acilis_animasyonu(s, a))
        else:
            self._sekme_layout_guncelle()  # normalize et
    def _sekme_bul(self, sid):
        for s in self.sekmeler:
            if s["id"] == sid:
                return s
        return None

    def _aktif_sekme(self):
        return self._sekme_bul(self.aktif_sekme_id)

    def _sekme_aktif_yap(self, sid):
        if self.aktif_sekme_id == sid:
            return

        if self.aktif_sekme_id is not None:
            eski = self._sekme_bul(self.aktif_sekme_id)
            if eski:
                eski["icerik"] = self.kod_alani.get("1.0", "end-1c")
                eski["frame"].configure(fg_color=self.colors["tab_inactive"])

        yeni = self._sekme_bul(sid)
        if not yeni:
            return

        self.aktif_sekme_id = sid
        self.kod_alani.delete("1.0", "end")
        self.kod_alani.insert("1.0", yeni["icerik"])

        yeni["frame"].configure(fg_color=self.colors["tab_active"])

        self.sync_line_numbers()
        self.after(150, self.kod_renklendir)
        self._status_guncelle()

    def _sekme_kapat(self, sid):
        sekme = self._sekme_bul(sid)
        if not sekme:
            return

        if self.aktif_sekme_id == sid:
            sekme["icerik"] = self.kod_alani.get("1.0", "end-1c")

        if sekme["degisti"]:
            cevap = messagebox.askyesnocancel("Kaydet?", f"'{sekme['isim']}' kaydedilsin mi?")
            if cevap is None:
                return
            if cevap:
                self._sekme_aktif_yap(sid)
                self.dosya_kaydet()

        sekme["frame"].destroy()
        self.sekmeler.remove(sekme)
        self._sekme_layout_guncelle()

        if self.sekmeler:
            self._sekme_aktif_yap(self.sekmeler[-1]["id"])
        else:
            self.aktif_sekme_id = None
            self.kod_alani.delete("1.0", "end")
            self._yeni_sekme_olustur()

    def _sekme_baslik_guncelle(self, sid=None):
        sekme = self._aktif_sekme() if sid is None else self._sekme_bul(sid)
        if not sekme:
            return
        self._sekme_etiket_kirp(sekme, getattr(self, "_sekme_genisligi", 170))

    def _status_guncelle(self):
        sekme = self._aktif_sekme()
        if sekme and sekme["yol"]:
            self.status_right.configure(text=f"UTF-8 | {sekme['isim']} ")
        else:
            self.status_right.configure(text="UTF-8 | Yeni Dosya ")

    def _ai_kod_kopyala(self, kod):
        self.clipboard_clear()
        self.clipboard_append(kod)
        self.status_left.configure(text="  Kod panoya kopyalandı ✓")

    def _ai_kod_bloju_olustur(self, parent, kod, dil=""):
        frame = ctk.CTkFrame(parent, fg_color=self.colors.get("bg", "#1e1e1e"), corner_radius=6,
                     border_width=1, border_color=self.colors["border"])
        
        bar = ctk.CTkFrame(frame, fg_color=self.colors.get("sidebar", "#252526"), height=32, corner_radius=0)
        bar.pack(fill="x", padx=0, pady=0)
        bar.pack_propagate(False)
            
        gosterilen_dil = "TÜRKOD" if not dil else dil.upper()
        
        dil_label = ctk.CTkLabel(bar, text=gosterilen_dil, 
                                     font=("Segoe UI", 8, "bold"), text_color="#858585")
        dil_label.pack(side="left", padx=8)
            
        btn_frame = ctk.CTkFrame(bar, fg_color="transparent")
        btn_frame.pack(side="right", padx=5)
            
        kopyala_ikon = WIN11_IKON.get("kopyala")

        kopyala_btn = ctk.CTkButton(
            btn_frame,
            text=kopyala_ikon if kopyala_ikon else "Kopyala",
            width=70,
            height=22,
            fg_color="transparent",
            hover_color=self.colors["button_hover"],
            text_color=self.colors["panel_fg"],
            font=ICON_FONT if kopyala_ikon else ("Segoe UI", 9),
            command=lambda: self._ai_kod_kopyala(kod)
        )
        kopyala_btn.pack(side="left", padx=2)
            
        uygula_btn = ctk.CTkButton(
            btn_frame,
            text="Uygula",
            width=70,
            height=22,
            fg_color=self.colors.get("accent", "#0e639c"),
            hover_color=self.colors.get("accent_hover", self.colors.get("button_hover", "#1177bb")),
            text_color="#00202F",
            font=("Segoe UI", 9, "bold"),
            command=lambda: self._ai_kodu_uygula(kod)
        )
        uygula_btn.pack(side="left", padx=2)   # ← EKSİK OLAN SATIR!
            
        satir_sayisi = kod.count('\n') + 1
        yukseklik = min(250, satir_sayisi * 18 + 20)  
            
        kod_text = ctk.CTkTextbox(
            frame, font=("Consolas", 11),
            fg_color=self.colors.get("bg", "#1e1e1e"),
            text_color=self.colors.get("text", "#d4d4d4"),
            wrap="none", height=yukseklik,
            activate_scrollbars=True
        )
        kod_text.pack(fill="x", padx=5, pady=5)
        kod_text.insert("1.0", kod)
        kod_text.configure(state="disabled") 
            
        return frame

    def _ai_mesaj_parse_et(self, mesaj):
        """AI mesajını kod ve metin parçalarına ayır.
        
        ← DÜZELTME: re.search döngüsü yerine re.finditer kullanılır.
        Her kod bloğu için ayrı try-except, bir hata diğerlerini etkilemesin.
        """
        parcalar = []
        son_pos = 0
        
        for match in re.finditer(r'```(\w*)\s*\n?(.*?)```', mesaj, re.DOTALL):
            # Match'ten önceki metni ekle
            if match.start() > son_pos:
                metin = mesaj[son_pos:match.start()].strip()
                if metin:
                    parcalar.append(("metin", metin, ""))
            
            dil = match.group(1).strip()
            kod = match.group(2).strip()
            
            # Python kodunu güvenli şekilde çevir
            if dil.lower() == 'python':
                try:
                    kod = python_kodu_turkceye_cevir(kod)
                    dil = "TürKod"
                except Exception:
                    # Çeviri başarısız olursa orijinal Python kodu göster
                    pass
            
            parcalar.append(("kod", kod, dil))
            son_pos = match.end()
        
        # Kalan metni ekle
        if son_pos < len(mesaj):
            kalan = mesaj[son_pos:].strip()
            if kalan:
                parcalar.append(("metin", kalan, ""))
        
        if not parcalar and mesaj.strip():
            parcalar.append(("metin", mesaj.strip(), ""))
        
        return parcalar

    def _ai_mesaj_ekle(self, gonderen, mesaj):
        if getattr(self, "ai_welcome", None) and self.ai_welcome.winfo_exists():
            self.ai_welcome.destroy()
        is_user = gonderen == "user"
        if not hasattr(self, 'ai_mesajlar'):
            self.ai_mesajlar = []
        
        row_frame = ctk.CTkFrame(self.ai_chat_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2, padx=4)

        msg_container = ctk.CTkFrame(row_frame, fg_color="transparent")
        msg_container.pack(side="right" if is_user else "left")

        avatar_text = "Sen" if is_user else "AI"
        avatar = ctk.CTkLabel(
            msg_container,
            text=avatar_text,
            font=("Segoe UI", 10, "bold"),
            text_color=self.colors.get("line_number", "#888")
        )
        avatar.pack(side="left" if not is_user else "right", padx=4, anchor="n")
        
        if gonderen == "assistant":
            pass
            
        bg_color = self.colors["ai_user"] if is_user else self.colors["ai_assistant"]
        bubble = ctk.CTkFrame(msg_container, fg_color=bg_color, corner_radius=14)
        bubble.pack(side="left" if not is_user else "right", padx=2)

        header = ctk.CTkFrame(bubble, fg_color="transparent", height=18)
        header.pack(fill="x", padx=(12, 12), pady=(6, 0))
        header.pack_propagate(False)
        
        name = "Sen" if is_user else "AI"
        # İsim etiketi
        ctk.CTkLabel(
            header, 
            text=name, 
            font=("Segoe UI", 9, "bold"), 
            text_color=self.colors["line_number"]
        ).pack(side="left")

        # Saat etiketi
        ctk.CTkLabel(
            header,
            text=datetime.now().strftime("%H:%M"),
            font=("Segoe UI", 8),
            text_color=self.colors.get("line_number", "#666")
        ).pack(side="right")

        parcalar = self._ai_mesaj_parse_et(mesaj)
        self.update_idletasks()
        wrap_length = self._ai_wrap_genisligi()
        for parca in parcalar:
            if parca[0] == "metin":
                text = parca[1]
                text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
                text = re.sub(r'\*(.*?)\*', r'\1', text)
                
                msg_lbl = ctk.CTkLabel(bubble, text=text,
                                        font=("Segoe UI", 11),
                                        text_color=self.colors["text"],
                                        wraplength=wrap_length, justify="left")
                msg_lbl.pack(anchor="w", padx=12, pady=(2, 6))
                self._ai_wrap_labellari.append(msg_lbl)
            else:
                kod_frame = self._ai_kod_bloju_olustur(bubble, parca[1], parca[2])
                kod_frame.pack(fill="x", padx=8, pady=(2, 8))

        self.ai_mesajlar.append({"gonderen": gonderen, "mesaj": mesaj})
        def _scroll_to_bottom():
            try:
                canvas = self.ai_chat_frame._parent_canvas
                canvas.update_idletasks()
                # KRİTİK: Scrollregion'ı manuel güncelle
                canvas.configure(scrollregion=canvas.bbox("all"))
                canvas.yview_moveto(1.0)
            except Exception:
                pass
        self.after(150, _scroll_to_bottom)
        self.after(100, lambda: self.ai_chat_frame._parent_canvas.yview_moveto(1.0))
    
    def _ai_wrap_genisligi(self):
        """Mesaj etiketleri için güvenli sarma genişliği"""
        g = self.ai_chat_frame.winfo_width()
        if g < 100:
            g = self.ai_panel.winfo_width() - 40
        if g < 100:
            g = 420
        # avatar + iç boşluklar + scrollbar payı
        return max(150, g - 90)

    def _ai_wrap_guncelle(self, event=None):
        if event is not None and event.width < 100:
            return
        wrap = self._ai_wrap_genisligi()
        for lbl in getattr(self, "_ai_wrap_labellari", []):
            try:
                if lbl.winfo_exists():
                    lbl.configure(wraplength=wrap)
            except Exception:
                pass
    def _python_bloklarini_turkceye_cevir(self, mesaj):
        """Mesajdaki ```python bloklarını ```TürKod'a çevir"""
        import re
        
        def cevir_blok(match):
            dil = match.group(1)
            kod = match.group(2)
            
            if dil.lower() == 'python':
                turkce_kod = python_kodu_turkceye_cevir(kod)
                return f'```TürKod\n{turkce_kod}\n```'
            
            return match.group(0)
        
        # ```dil\nkod\n``` patternini bul ve çevir
        return re.sub(r'```(\w+)\n?(.*?)```', cevir_blok, mesaj, flags=re.DOTALL)
    def _ai_yaziyor_goster(self):
        self.ai_durum.configure(text="● Yazıyor...", text_color="#ff9800")
        
        if not self.ai_typing_frame.winfo_exists():
            self.ai_typing_frame = ctk.CTkFrame(self.ai_chat_frame, fg_color=self.colors["ai_assistant"],
                                                 corner_radius=12, height=32)
            self.ai_typing_label = ctk.CTkLabel(self.ai_typing_frame, text="● ● ●",
                                                 font=("Segoe UI", 12), text_color="#888")
            self.ai_typing_label.pack(padx=12, pady=6)
        else:
            self.ai_typing_frame.configure(fg_color=self.colors["ai_assistant"])
        
        self.ai_typing_frame.pack(fill="x", padx=40, pady=5)
        self._typing_animasyon()

    def _typing_animasyon(self, step=0):
        if not self.ai_typing_frame.winfo_viewable():
            return
        dots = ["● ○ ○", "○ ● ○", "○ ○ ●", "○ ● ○"]
        self.ai_typing_label.configure(text=dots[step % 4])
        self.after(400, lambda: self._typing_animasyon(step + 1))

    def _ai_yaziyor_gizle(self):
        self._ai_durum_hazir()
        if self.ai_typing_frame.winfo_exists():
            self.ai_typing_frame.pack_forget()

    def _ai_gonder_event(self, event):
        if not event.state & 0x1:
            self._ai_gonder()
            return "break"

    def _ai_gonder(self):
        if not self.ayarlar.get("ai_aktif"):
            self._ai_mesaj_ekle("assistant", "AI aktif değil.")
            return

        mesaj = self.ai_input.get("1.0", "end-1c").strip()
        if not mesaj:
            return

        mevcut_kod = self.kod_alani.get("1.0", "end-1c").strip()

        # ← DÜZELTME: turkce_kodu_donustur hata fırlatabilir, koru
        python_kodu = ""
        if mevcut_kod:
            try:
                python_kodu = turkce_kodu_donustur(mevcut_kod)
            except Exception:
                python_kodu = ""

            satirlar = python_kodu.split('\n')
            if len(satirlar) > 25:
                python_kodu = '\n'.join(satirlar[-20:])
                python_kodu = f"[Kod son 20 satır]:\n```python\n{python_kodu}\n```"
            else:
                python_kodu = f"[Kod:\n```python\n{python_kodu}\n```]"

        if python_kodu:
            tam_mesaj = f"{mesaj}\n\n{python_kodu}"
        else:
            tam_mesaj = mesaj

        if len(tam_mesaj) > 2000:
            tam_mesaj = tam_mesaj[:2000] + "\n[...kısaltıldı]"

        self.ai_input.delete("1.0", "end")
        self._ai_mesaj_ekle("user", mesaj)
        self._ai_yaziyor_goster()
        self.ai_durum.configure(text="Yazıyor...")
        self.ai_gonder_btn.configure(state="disabled")

        threading.Thread(target=self._ai_api_cagri, args=(tam_mesaj,), daemon=True).start()

    def _ai_kodu_optimize(self):
        kod = self.kod_alani.get("1.0", "end-1c").strip()
        if not kod:
            self._ai_mesaj_ekle("assistant", "⚠️ Optimize edilecek kod bulunamadı.")
            return
        prompt = f"""Aşağıdaki TürKod kodunu optimize et ve daha verimli hale getir:

```TürKod
{kod}
Yapacakların:
- Yapılan iyileştirmeleri kısaca açıkla
- Optimize edilmiş kodu Türkod bloğunda ver"""
        self._ai_gonder_prompt(prompt)
    def _yerel_duzelt_sozluk(self):
        """Yerel düzeltme için sözlük kelime listesini üret"""
        if hasattr(self, "_yerel_duzelt_sozluk_cache"):
            return self._yerel_duzelt_sozluk_cache

        kelimeler = set()

        try:
            for kelime in TURKCE_KELIMELER:
                kelime = str(kelime).strip()
                if kelime and " " not in kelime:
                    kelimeler.add(kelime)
        except Exception:
            pass

        try:
            for desen in SOZLUK.keys():
                temiz = str(desen).replace(r"\b", "").strip()
                temiz = temiz.strip('"').strip("'")

                if temiz and " " not in temiz and "." not in temiz:
                    kelimeler.add(temiz)
        except Exception:
            pass

        # Sözlük yüklenmezse temel kelimeler yine çalışsın
        kelimeler.update([
            "yazdır", "girdi_al", "fonksiyon", "sınıf", "eğer", "değilse",
            "değilse_eğer", "döngü", "kır", "devam_et", "geç", "dene",
            "hata_yakala", "sonunda", "içe_aktar", "döndür", "ve", "veya", "değil"
        ])
        try:
            kelimeler.update(_keyword_words)
            kelimeler.update(_builtin_words)
        except Exception:
            pass
        self._yerel_duzelt_sozluk_cache = sorted(kelimeler)
        return self._yerel_duzelt_sozluk_cache

    def _yerel_duzelt_sozluk_haritasi(self):
        """Küçük harf tabanlı sözlük haritasını üret"""
        if hasattr(self, "_yerel_duzelt_sozluk_map") and hasattr(self, "_yerel_duzelt_sozluk_kucuk_listesi"):
            return self._yerel_duzelt_sozluk_map, self._yerel_duzelt_sozluk_kucuk_listesi

        sozluk = self._yerel_duzelt_sozluk()
        sozluk_map = {}

        for kelime in sozluk:
            kucuk = kelime.lower()
            if kucuk not in sozluk_map:
                sozluk_map[kucuk] = kelime

        self._yerel_duzelt_sozluk_map = sozluk_map
        self._yerel_duzelt_sozluk_kucuk_listesi = sorted(sozluk_map.keys())

        return self._yerel_duzelt_sozluk_map, self._yerel_duzelt_sozluk_kucuk_listesi

    def _kodu_yerel_duzelt(self, kod):
        """Koddaki bilinmeyen kelimeleri sözlükteki en yakın kelimeyle düzeltir"""
        import difflib

        sozluk_map, sozluk_kucuk_listesi = self._yerel_duzelt_sozluk_haritasi()

        if not sozluk_kucuk_listesi:
            return kod, set()

        try:
            tanimli_kelimeler = set(self._koddan_tanimlari_cikar(kod))
        except Exception:
            tanimli_kelimeler = set()

        tanimli_kucuk = {str(k).lower() for k in tanimli_kelimeler}
        # Nokta sonrası kullanılan isimler (öznitelik/metot) kullanıcıya aittir, düzeltme
        attr_adlari = re.findall(r'\.\s*([a-zA-Z_][a-zA-Z0-9_ÇŞĞÜÖİçşğüöı]*)', kod)
        tanimli_kucuk |= {a.lower() for a in attr_adlari}

        degisiklikler = set()
        cache = {}

        string_ve_yorum = r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|#.*)'
        parcalar = re.split(string_ve_yorum, kod)
        kelime_deseni = r"[A-Za-z_ÇŞĞÜÖİçşğüöı][A-Za-z0-9_ÇŞĞÜÖİçşğüöı]*"

        def bitisik_takasla_duzelt(kelime):
            """
            Bitişik iki harfin yer değiştirdiği yazım hatalarını yakalar.
            Örnek:
            egre -> eger
            yazidr -> yazdir
            """
            for i in range(len(kelime) - 1):
                takas = kelime[:i] + kelime[i + 1] + kelime[i] + kelime[i + 2:]
                if takas in sozluk_map:
                    return sozluk_map[takas]
            return None

        def duzelt(match):
            token = match.group(0)

            # Çok kısa kelimeleri düzeltme
            if len(token) < 4:
                return token

            kucuk = token.lower()

            # Zaten sözlükte varsa veya kod içinde tanımlıysa dokunma
            if kucuk in sozluk_map or kucuk in tanimli_kucuk:
                return token

            if kucuk in cache:
                return cache[kucuk]

            # 1) Bitişik harf takası: egre -> eger
            takas = bitisik_takasla_duzelt(kucuk)
            if takas and takas != token:
                degisiklikler.add((token, takas))
                cache[kucuk] = takas
                return takas

            # 2) Kısa kelimelerde daha esnek, uzun kelimelerde daha güvenli
            if len(kucuk) <= 5:
                cutoff = 0.60
            elif len(kucuk) <= 8:
                cutoff = 0.70
            else:
                cutoff = 0.78

            oneri = difflib.get_close_matches(
                kucuk,
                sozluk_kucuk_listesi,
                n=1,
                cutoff=cutoff
            )

            if oneri:
                # Kısa kelimelerde yanlış düzeltmeyi azaltmak için ilk 2 harf kontrolü
                if len(kucuk) <= 5 and len(oneri[0]) >= 2 and kucuk[:2] != oneri[0][:2]:
                    cache[kucuk] = token
                    return token

                yeni = sozluk_map[oneri[0]]

                if yeni != token:
                    degisiklikler.add((token, yeni))
                    cache[kucuk] = yeni
                    return yeni

            cache[kucuk] = token
            return token

        for i, parca in enumerate(parcalar):
            if not parca:
                continue

            # String ve yorum parçalarını değiştirme
            if re.fullmatch(string_ve_yorum, parca):
                continue

            parcalar[i] = re.sub(kelime_deseni, duzelt, parca)

        return "".join(parcalar), degisiklikler
    def _ai_kodu_duzelt(self):
        """Düzelt butonu: AI yerine sözlük tabanlı yerel düzeltme yapar"""
        kod = self.kod_alani.get("1.0", "end-1c")

        if not kod.strip():
            self._ai_mesaj_ekle("assistant", "⚠️ Düzeltilecek kod bulunamadı.")
            return

        yeni_kod, degisiklikler = self._kodu_yerel_duzelt(kod)

        if not degisiklikler:
            self._ai_mesaj_ekle(
                "assistant",
                "✅ Sözlüğe göre düzeltilecek belirgin yazım hatası bulunamadı."
            )
            return

        self.kod_alani.delete("1.0", "end")
        self.kod_alani.insert("1.0", yeni_kod)

        self._dosya_degisti_kontrol()
        self.sync_line_numbers()
        self.kod_renklendir()

        satirlar = ["🔧 AI yerine yerel sözlük düzeltmesi yapıldı:", ""]
        for eski, yeni in sorted(degisiklikler):
            satirlar.append(f"• {eski} → {yeni}")

        self._ai_mesaj_ekle("assistant", "\n".join(satirlar))
    
    def _ai_gonder_prompt(self, prompt):
        if not self.ayarlar.get("ai_aktif"):
            self._ai_mesaj_ekle("assistant", "AI aktif değil. Ayarlardan API Anahtarı girin.")
            return
        self._ai_mesaj_ekle("user", "[Kod analizi istendi]")
        self.ai_durum.configure(text="Yazıyor...")
        self.ai_gonder_btn.configure(state="disabled")
        threading.Thread(target=self._ai_api_cagri, args=(prompt,), daemon=True).start()

    def _ai_temizle(self):
        for widget in self.ai_chat_frame.winfo_children():
            if widget is not self.ai_typing_frame:
                widget.destroy()
        self.ai_mesajlar.clear()
        self.ai_mesaj_gecmisi.clear()
        self.ai_typing_frame.pack_forget()
        self._ai_wrap_labellari.clear()
        self._ai_welcome_kur()
        
    def _ai_api_cagri(self, mesaj):
        saglayici = self.ayarlar.get("ai_saglayici")
        api_key = self.ayarlar.get("ai_api_key")
        model = self.ayarlar.get("ai_model")
        sicaklik = self.ayarlar.get("ai_sicaklik")
        max_token = self.ayarlar.get("ai_max_token")
        # ← DÜZELTME 1: sistem_mesaji None ise string birleştirme hatası verir
        sistem_mesaji = self.ayarlar.get("ai_sistem_mesaji") or ""

        try:
            if saglayici == "OpenAI" and openai:
                client = openai.OpenAI(api_key=api_key)
                self.ai_mesaj_gecmisi.append({"role": "user", "content": mesaj})
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": sistem_mesaji}] + self.ai_mesaj_gecmisi[-2:],
                    temperature=sicaklik,
                    max_tokens=max_token
                )
                cevap = response.choices[0].message.content
                self.ai_mesaj_gecmisi.append({"role": "assistant", "content": cevap})

            elif saglayici == "Groq" and Groq:
                client = Groq(api_key=api_key)
                self.ai_mesaj_gecmisi.append({"role": "user", "content": mesaj})
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": sistem_mesaji}] + self.ai_mesaj_gecmisi[-2:],
                    temperature=sicaklik,
                    max_tokens=max_token
                )
                cevap = response.choices[0].message.content
                self.ai_mesaj_gecmisi.append({"role": "assistant", "content": cevap})

            elif saglayici == "Gemini" and genai:
                client = genai.Client(api_key=api_key)
                self.ai_mesaj_gecmisi.append({"role": "user", "content": mesaj})
                # ← DÜZELTME 1b: sistem_mesaji boşsa sadece mesajı gönder
                icerik = f"{sistem_mesaji}\n\n{mesaj}" if sistem_mesaji else mesaj
                response = client.models.generate_content(
                    model=model,
                    contents=[icerik]
                )
                # ← DÜZELTME 1c: response.text güvenlik filtresi nedeniyle hata fırlatabilir
                try:
                    cevap = response.text
                except (ValueError, AttributeError):
                    cevap = "⚠️ AI yanıtı alınamadı (güvenlik filtresi engellemiş olabilir)."
                self.ai_mesaj_gecmisi.append({"role": "assistant", "content": cevap})

            elif saglayici == "Claude" and anthropic:
                client = anthropic.Anthropic(api_key=api_key)
                self.ai_mesaj_gecmisi.append({"role": "user", "content": mesaj})
                response = client.messages.create(
                    model=model,
                    max_tokens=max_token,
                    system=sistem_mesaji,
                    messages=[{"role": "user", "content": mesaj}]
                )
                cevap = response.content[0].text
                self.ai_mesaj_gecmisi.append({"role": "assistant", "content": cevap})

            else:
                import traceback
                print("\n" + "="*60)
                print("  ❌ AI HATASI: Kütüphane Yüklenmemiş")
                print("="*60)
                print(f"\n  Sağlayıcı: {saglayici}")
                print(f"  Durum: İlgili Python kütüphanesi içe aktarılamadı!")
                print(f"\n  Çözüm: Aşağıdaki komutu CMD'de çalıştırın:")

                kutuphane_adi = {
                    "OpenAI": "openai",
                    "Groq": "groq",
                    "Gemini": "google-genai",
                    "Claude": "anthropic"
                }.get(saglayici, saglayici.lower())

                print(f"\n    pip install {kutuphane_adi}")
                print("\n" + "="*60)
                print("  Detaylı Hata Bilgisi (İzleme):")
                print("="*60 + "\n")

                traceback.print_exc()

                cevap = f"⚠️ {saglayici} kütüphanesi yüklü değil!\n\nYüklemek için:\npip install {kutuphane_adi}"

                self.after(0, lambda: self._ai_mesaj_ekle("assistant", cevap))
                self.after(0, self._ai_yaziyor_gizle)
                return

            cevap = self._cevabi_turkceye_cevir(cevap)
            self.after(0, lambda c=cevap: self._ai_mesaj_ekle("assistant", c))
            self.after(0, self._ai_yaziyor_gizle)
            self.after(0, lambda: self.ai_gonder_btn.configure(state="normal"))
        except Exception as e:
            hata = str(e).lower()
            hata_kodu = getattr(e, 'status_code', None) or getattr(e, 'code', None)

            # 413 = Payload Too Large
            if hata_kodu == 413 or "too large for model" in hata:
                hata_msg = "İstek çok uzun! Kodu kısaltın."
            elif "tokens per minute" in hata or "rate limit" in hata or "limit exceeded" in hata:
                hata_msg = "Limitiniz bitti. Lütfen başka bir API anahtarı alın veya daha sonra tekrar deneyin."
            elif "authentication" in hata or "api key" in hata or "api_key" in hata:
                hata_msg = "API Anahtarı geçersiz!"
            # ← EKLE: Model kullanımdan kaldırılmış
            elif "decommissioned" in hata or "model_decommissioned" in hata:
                hata_msg = (f"⚠️ Model kullanımdan kaldırılmış: {model}\n\n"
                            "Lütfen Ayarlar → AI Asistan'dan başka bir model seçin.\n"
                            "Önerilen: llama-3.3-70b-versatile")
            elif "model" in hata and ("not found" in hata or "not_found" in hata):
                hata_msg = f"Model bulunamadı: {model}"
            elif "connection" in hata or "timeout" in hata:
                hata_msg = "Bağlantı hatası! İnternetinizi kontrol edin."
            else:
                import traceback
                print("\n" + "="*60)
                print(f"  ❌ AI HATASI")
                print("="*60)
                print(f"  Sağlayıcı: {saglayici}")
                print(f"  Model: {model}")
                print(f"  Hata: {str(e)}")
                print("\n  Detaylı İzleme:")
                traceback.print_exc()
                print("="*60 + "\n")
                hata_msg = f"Bir hata oluştu: {str(e)[:200]}"

            self.after(0, lambda: self._ai_mesaj_ekle("assistant", f"❌ {hata_msg}"))
            self.after(0, self._ai_yaziyor_gizle)
            self.after(0, lambda: self.ai_durum.configure(text="Hazır"))
            self.after(0, lambda: self.ai_gonder_btn.configure(state="normal"))

        self.after(0, lambda: self.ai_durum.configure(text="Hazır"))
        self.after(0, lambda: self.ai_gonder_btn.configure(state="normal"))
        
    def _cevabi_turkceye_cevir(self, cevap):
        """AI yanıtındaki Python kod bloklarını GÜVENLI şekilde TürKod'a çevir.
        
        ← DÜZELTME: re.sub + fonksiyon yerine re.finditer kullanılır.
        Çünkü re.sub, çevrilmiş kodda ``` varsa sonraki eşleşmeleri bozar.
        """
        import re
        
        # Blokları tek tek bul ve çevir
        sonuc = []
        son_pos = 0
        
        for match in re.finditer(r'```(\w*)\s*\n?(.*?)```', cevap, re.DOTALL):
            # Match'ten önceki metni ekle
            sonuc.append(cevap[son_pos:match.start()])
            
            dil = match.group(1).strip().lower()
            kod = match.group(2)
            
            if dil == 'python':
                try:
                    turkce_kod = python_kodu_turkceye_cevir(kod)
                    sonuc.append(f'```TürKod\n{turkce_kod}\n```')
                except Exception:
                    # Çeviri başarısız olursa orijinal kodu bırak
                    sonuc.append(match.group(0))
            else:
                sonuc.append(match.group(0))
            
            son_pos = match.end()
        
        # Kalan metni ekle
        sonuc.append(cevap[son_pos:])
        cevap = ''.join(sonuc)
        
        # Inline kod çevirisi (tek tırnaklı)
        for py, tr in sorted(TERS_SOZLUK.items(), key=lambda x: len(x[0]), reverse=True):
            cevap = re.sub(rf'`{re.escape(py)}`', f'`{tr}`', cevap)
        
        return cevap
    # ============ AYARLAR PENCERESI ============
    def _ayarlar_penceresi_ac(self):
        def _switch(parent, text, variable):
            return ctk.CTkSwitch(
                parent,
                text=text,
                variable=variable,
                text_color=self.colors["text"],
                progress_color=self.colors.get("accent", self.colors.get("button_bg", "#0e639c")),
                fg_color=self.colors.get("button_bg", "#3c3c3c"),
                button_color=self.colors.get("text", "#d4d4d4")
            )
        pencere = ctk.CTkToplevel(self)
        pencere.configure(fg_color=self.colors["bg"])
        pencere.title("Ayarlar")
        pencere.geometry("600x800")
        pencere.transient(self)
        pencere.grab_set()
        self.ayarlar_penceresi = pencere

        self.notebook = ctk.CTkTabview(pencere, width=560, height=620, fg_color=self.colors["bg"])
        self.notebook.pack(padx=20, pady=20)
        self.notebook._segmented_button.configure(
            fg_color=self.colors.get("tab_inactive", self.colors["sidebar"]),
            selected_color=self.colors.get("button_bg", "#0e639c"),
            selected_hover_color=self.colors.get("button_hover", "#1177bb"),
            unselected_color=self.colors.get("tab_inactive", self.colors["sidebar"]),
            unselected_hover_color=self.colors.get("tab_active", self.colors["bg"]),
            text_color=self.colors["text"]
        )

        # === GENEL AYARLAR ===
        self.notebook.add("Genel")
        genel = self.notebook.tab("Genel")

        ctk.CTkLabel(genel, text="Tema:", font=("Segoe UI", 12, "bold"), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        tema_var = ctk.StringVar(value=self.ayarlar.get("tema"))
        tema_combo = ctk.CTkOptionMenu(
            genel, 
            values=list(TEMA_RENKLERI.keys()), 
            variable=tema_var,
            fg_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_hover", "#1177bb"),
            button_hover_color=self.colors.get("button_hover", "#1177bb"),
            dropdown_fg_color=self.colors.get("sidebar", "#252526"),
            dropdown_hover_color=self.colors.get("selection", "#264f78"),
            text_color=self.colors["text"],
            dropdown_text_color=self.colors["text"]
        )
        tema_combo.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(genel, text="Yazı Tipi:", font=("Segoe UI", 12, "bold"), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        yazi_var = ctk.StringVar(value=self.ayarlar.get("yazi_tipi"))

        # Tüm kurulu fontları al, önerilenleri üste taşı
        onerilen_fontlar = ["Consolas", "Courier New", "Fira Code", "JetBrains Mono", "Source Code Pro", "Segoe UI", "Arial"]
        tum_fontlar = sorted(set(tkfont.families()))
        font_listesi = [f for f in onerilen_fontlar if f in tum_fontlar] + [f for f in tum_fontlar if f not in onerilen_fontlar]
        if not font_listesi:
            font_listesi = ["Consolas"]

        def _font_secici_ac():
            if hasattr(self, '_font_popup') and self._font_popup.winfo_exists():
                self._font_popup.lift()
                return
            popup = ctk.CTkToplevel(pencere)
            popup.title("Yazı Tipi Seç")
            popup.geometry("320x340")
            popup.transient(pencere)
            popup.grab_set()
            popup.configure(fg_color=self.colors["bg"])
            self._font_popup = popup

            # Arama çubuğu
            arama_var = ctk.StringVar()
            arama_entry = ctk.CTkEntry(popup, textvariable=arama_var, placeholder_text="🔍 Yazı tipi ara...",
                                       height=32, fg_color=self.colors.get("ai_input", "#3c3c3c"),
                                       text_color=self.colors["text"], border_color=self.colors["border"])
            arama_entry.pack(fill="x", padx=10, pady=(10, 5))
            arama_entry.focus_set()

            # Liste çerçevesi
            liste_frame = tk.Frame(popup, bg=self.colors["bg"])
            liste_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

            scrollbar = ctk.CTkScrollbar(liste_frame, orientation="vertical")
            scrollbar.pack(side="right", fill="y")

            listbox = tk.Listbox(liste_frame, bg=self.colors.get("sidebar", "#252526"),
                                 fg=self.colors["text"], selectbackground=self.colors.get("selection", "#264f78"),
                                 selectforeground=self._secim_metin_rengi(), font=("Segoe UI", 11), bd=0,
                                 highlightthickness=1, highlightbackground=self.colors["border"],
                                 activestyle="none", yscrollcommand=scrollbar.set)
            listbox.pack(side="left", fill="both", expand=True)
            scrollbar.configure(command=listbox.yview)

            def _doldur(filtre_metni=""):
                listbox.delete(0, tk.END)
                filtre_metni = filtre_metni.lower()
                for f in font_listesi:
                    if filtre_metni in f.lower():
                        listbox.insert(tk.END, f)
                # Mevcut seçimi vurgula
                mevcut = yazi_var.get()
                for i in range(listbox.size()):
                    if listbox.get(i) == mevcut:
                        listbox.selection_set(i)
                        listbox.see(i)
                        break

            def _sec(event=None):
                secim = listbox.curselection()
                if secim:
                    yazi_var.set(listbox.get(secim[0]))
                    font_btn.configure(text=yazi_var.get())
                    popup.destroy()

            def _tekerlek(event):
                delta = getattr(event, "delta", 0)
                if delta:
                    listbox.yview_scroll(int(-1 * (delta / 120)), "units")
                return "break"

            # Orta tekerlek ile kaydırma (Windows/Linux)
            listbox.bind("<MouseWheel>", _tekerlek)
            listbox.bind("<Button-4>", lambda e: (listbox.yview_scroll(-3, "units"), "break"))
            listbox.bind("<Button-5>", lambda e: (listbox.yview_scroll(3, "units"), "break"))
            
            # Orta tuş basılı tutarak kaydırma (Sıfıra bölünmeyi önlemek için güvenli hale getirildi)
            def _b2_hareket(event):
                try:
                    h = listbox.winfo_height()
                    if h > 0:
                        listbox.yview_moveto(event.y / h)
                except Exception:
                    pass
                return "break"
            listbox.bind("<B2-Motion>", _b2_hareket)

            arama_var.trace_add("write", lambda *a: _doldur(arama_var.get()))
            listbox.bind("<Double-Button-1>", _sec)
            listbox.bind("<Return>", _sec)
            arama_entry.bind("<Return>", lambda e: (listbox.focus_set(), listbox.select_set(0) if listbox.size() else None))
            arama_entry.bind("<Down>", lambda e: listbox.focus_set())

            _doldur()

        # Seçim butonu (OptionMenu yerine)
        font_btn = ctk.CTkButton(genel, text=yazi_var.get(), command=_font_secici_ac,
                                 fg_color=self.colors.get("button_bg", "#0e639c"),
                                 hover_color=self.colors.get("button_hover", "#1177bb"),
                                 text_color=self.colors["text"], anchor="w")
        font_btn.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(genel, text="Yazı Boyutu:", font=("Segoe UI", 12, "bold"), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        boyut_var = ctk.IntVar(value=self.ayarlar.get("yazi_boyutu"))
        self.slider_boyut = ctk.CTkSlider(
            genel, 
            from_=8, 
            to=32, 
            number_of_steps=24, 
            variable=boyut_var,
            fg_color=self.colors.get("sidebar", self.colors["bg"]),
            progress_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_bg", "#0e639c"),
            button_hover_color=self.colors.get("button_hover", "#1177bb")
        )
        self.slider_boyut.pack(fill="x", padx=10, pady=5)
        self.label_boyut = ctk.CTkLabel(genel, textvariable=boyut_var, text_color=self.colors["text"])
        self.label_boyut.pack(anchor="w", padx=10)

        satir_var = ctk.BooleanVar(value=self.ayarlar.get("satir_numaralari"))
        satir_cb = ctk.CTkSwitch(
            genel,
            text="Satır Numaraları",
            variable=satir_var,
            text_color=self.colors["text"],
            progress_color=self.colors["accent"],
            fg_color=self.colors["button_bg"],
            button_color=self.colors["text"]
        )
        satir_cb.pack(anchor="w", pady=5, padx=10)

        sar_var = ctk.BooleanVar(value=self.ayarlar.get("kelime_sar"))
        sar_cb = _switch(genel, "Kelime Sarma", sar_var)
        sar_cb.pack(anchor="w", pady=5, padx=10)

        # === EDITOR AYARLARI ===
        self.notebook.add("Editor")
        editor = self.notebook.tab("Editor")

        tamamlama_var = ctk.BooleanVar(value=self.ayarlar.get("otomatik_tamamlama"))
        tamamlama_cb = _switch(editor, "Otomatik Tamamlama", tamamlama_var)
        tamamlama_cb.pack(anchor="w", pady=10, padx=10)

        oto_kaydet_var = ctk.BooleanVar(value=self.ayarlar.get("otomatik_kaydetme"))
        oto_kaydet_cb = _switch(editor, "Otomatik Kaydetme", oto_kaydet_var)
        oto_kaydet_cb.pack(anchor="w", pady=5, padx=10)

        ctk.CTkLabel(editor, text="Oto. Kaydetme Aralığı (sn):", font=("Segoe UI", 11), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        aralik_var = ctk.IntVar(value=self.ayarlar.get("otomatik_kaydetme_aralik"))
        self.slider_aralik = ctk.CTkSlider(
            editor,
            from_=5,
            to=300,
            number_of_steps=59,
            variable=aralik_var,
            fg_color=self.colors.get("sidebar", self.colors["bg"]),
            progress_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_bg", "#0e639c"),
            button_hover_color=self.colors.get("button_hover", "#1177bb")
        )
        self.slider_aralik.pack(fill="x", padx=10, pady=5)
        self.label_aralik = ctk.CTkLabel(editor, textvariable=aralik_var, text_color=self.colors["text"])
        self.label_aralik.pack(anchor="w", padx=10)

        bosluk_var = ctk.BooleanVar(value=self.ayarlar.get("bosluk_gostergesi"))
        bosluk_cb = _switch(editor, "Boşluk Göstergesi", bosluk_var)
        bosluk_cb.pack(anchor="w", pady=5, padx=10)

        minimap_var = ctk.BooleanVar(value=self.ayarlar.get("minimap"))
        minimap_cb = _switch(editor, "Minimap", minimap_var)
        minimap_cb.pack(anchor="w", pady=5, padx=10)
        
        # === AI AYARLARI ===
        self.notebook.add("AI Asistan")
        ai_tab = self.notebook.tab("AI Asistan")

        ai_aktif_var = ctk.BooleanVar(value=self.ayarlar.get("ai_aktif"))
        ai_aktif_cb = _switch(ai_tab, "AI Asistanı Aktif", ai_aktif_var)
        ai_aktif_cb.pack(anchor="w", pady=10, padx=10)

        ctk.CTkLabel(ai_tab, text="AI Sağlayıcı:", font=("Segoe UI", 12, "bold"), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        saglayici_var = ctk.StringVar(value=self.ayarlar.get("ai_saglayici"))
        saglayici_combo = ctk.CTkOptionMenu(
            ai_tab, 
            values=list(AI_MODELLERI.keys()), 
            variable=saglayici_var,
            fg_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_hover", "#1177bb"),
            button_hover_color=self.colors.get("button_hover", "#1177bb"),
            dropdown_fg_color=self.colors.get("sidebar", "#252526"),
            dropdown_hover_color=self.colors.get("selection", "#264f78"),
            text_color=self.colors["text"],
            dropdown_text_color=self.colors["text"]
        )
        saglayici_combo.pack(fill="x", padx=10, pady=5)

        model_var = ctk.StringVar(value=self.ayarlar.get("ai_model"))
        model_combo = ctk.CTkOptionMenu(
            ai_tab, 
            values=AI_MODELLERI.get(saglayici_var.get(), ["gpt-4o-mini"]), 
            variable=model_var,
            fg_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_hover", "#1177bb"),
            button_hover_color=self.colors.get("button_hover", "#1177bb"),
            dropdown_fg_color=self.colors.get("sidebar", "#252526"),
            dropdown_hover_color=self.colors.get("selection", "#264f78"),
            text_color=self.colors["text"],
            dropdown_text_color=self.colors["text"]
        )
        model_combo.pack(fill="x", padx=10, pady=5)

        def saglayici_degisti(*args):
            model_combo.configure(values=AI_MODELLERI.get(saglayici_var.get(), ["gpt-4o-mini"]))
            model_var.set(AI_MODELLERI.get(saglayici_var.get(), ["gpt-4o-mini"])[0])
        saglayici_var.trace_add("write", saglayici_degisti)

        ctk.CTkLabel(ai_tab, text="API Anahtarı:", font=("Segoe UI", 12, "bold"), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        api_key_var = ctk.StringVar(value=self.ayarlar.get("ai_api_key"))
        api_key_entry = ctk.CTkEntry(ai_tab, textvariable=api_key_var, show="*", width=500,
            fg_color=self.colors.get("ai_input", "#3c3c3c"),
            text_color=self.colors["text"],
            border_color=self.colors.get("border", "#3c3c3c"))
        api_key_entry.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(ai_tab, text="Sistem Mesajı:", font=("Segoe UI", 12, "bold"), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        sistem_var = ctk.StringVar(value=self.ayarlar.get("ai_sistem_mesaji"))
        sistem_entry = ctk.CTkEntry(ai_tab, textvariable=sistem_var, width=500,
            fg_color=self.colors.get("ai_input", "#3c3c3c"),
            text_color=self.colors["text"],
            border_color=self.colors.get("border", "#3c3c3c"))
        sistem_entry.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(ai_tab, text="Sıcaklık (0-2):", font=("Segoe UI", 11), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        sicaklik_var = ctk.DoubleVar(value=self.ayarlar.get("ai_sicaklik"))
        self.slider_sicaklik = ctk.CTkSlider(
            ai_tab,
            from_=0,
            to=2,
            number_of_steps=20,
            variable=sicaklik_var,
            fg_color=self.colors.get("sidebar", self.colors["bg"]),
            progress_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_bg", "#0e639c"),
            button_hover_color=self.colors.get("button_hover", "#1177bb")
        )
        self.slider_sicaklik.pack(fill="x", padx=10, pady=5)
        self.label_sicaklik = ctk.CTkLabel(ai_tab, textvariable=sicaklik_var, text_color=self.colors["text"])
        self.label_sicaklik.pack(anchor="w", padx=10)

        ctk.CTkLabel(ai_tab, text="Maksimum Jeton:", font=("Segoe UI", 11), text_color=self.colors["text"]).pack(anchor="w", pady=(10, 0), padx=10)
        token_var = ctk.IntVar(value=self.ayarlar.get("ai_max_token"))
        self.slider_token = ctk.CTkSlider(
            ai_tab,
            from_=4096,
            to=32768,
            number_of_steps=30,
            variable=token_var,
            fg_color=self.colors.get("sidebar", self.colors["bg"]),
            progress_color=self.colors.get("button_bg", "#0e639c"),
            button_color=self.colors.get("button_bg", "#0e639c"),
            button_hover_color=self.colors.get("button_hover", "#1177bb")
        )
        self.slider_token.pack(fill="x", padx=10, pady=5)
        self.label_token = ctk.CTkLabel(ai_tab, textvariable=token_var, text_color=self.colors["text"])
        self.label_token.pack(anchor="w", padx=10)
        # === HAKKIMDA ===
        self.notebook.add("Hakkımda")
        hakkinda = self.notebook.tab("Hakkımda")

        # ===== BAŞLIK =====
        ctk.CTkLabel(hakkinda, text="TürKod IDE", 
                     font=("Segoe UI", 24, "bold"),
                     text_color=self.colors["text"]).pack(pady=(20, 5))
        
        ctk.CTkLabel(hakkinda, text="Profesyonel Türkçe Python Editörü", 
                     font=("Segoe UI", 12), text_color="#888").pack()

        # Çizgi
        ctk.CTkFrame(hakkinda, fg_color=self.colors["border"], 
                     height=2).pack(fill="x", padx=40, pady=15)

        # ===== GELİŞTİRİCİ =====
        ctk.CTkLabel(hakkinda, text="Geliştirici", 
                     font=("Segoe UI", 10, "bold"), text_color="#666").pack()
        
        # ↓↓↓ ADIN SOYADIN ↓↓↓
        ctk.CTkLabel(hakkinda, text="YUSUF TANDOĞAN",  
                     font=("Segoe UI", 14, "bold"),
                     text_color=self.colors["text"]).pack(pady=(2, 5))

        ctk.CTkLabel(hakkinda, text="yusuftndgn.2@gmail.com",  
                     font=("Segoe UI", 10), text_color="#888").pack()

        ctk.CTkLabel(hakkinda, text="Versiyon 2.1  |  © 2026 Tüm Hakları Saklıdır", 
                     font=("Segoe UI", 10), text_color="#666").pack(pady=(0, 10))

        # ===== RSA DİJİTAL İMZA KUTUSU =====
        self.rsa_frame = ctk.CTkFrame(hakkinda, fg_color=self.colors["sidebar"],
                                       corner_radius=8, border_width=1,
                                       border_color=self.colors["border"])
        self.rsa_frame.pack(fill="x", padx=40, pady=10)

        ctk.CTkLabel(self.rsa_frame, text="🔐 RSA Dijital İmza", 
                     font=("Segoe UI", 10, "bold"),
                     text_color="#4caf50").pack(anchor="w", padx=12, pady=(10, 0))

        self.rsa_durum = ctk.CTkLabel(self.rsa_frame, 
                     text="Doğrulanıyor...",
                     font=("Segoe UI", 9),
                     text_color=self.colors["panel_fg"])
        self.rsa_durum.pack(anchor="w", padx=12, pady=(5, 2))

        self.rsa_detay = ctk.CTkLabel(self.rsa_frame, 
                     text="",
                     font=("Consolas", 8),
                     text_color="#666")
        self.rsa_detay.pack(anchor="w", padx=12, pady=(0, 10))

        # ===== GITHUB KANITI =====
        github_frame = ctk.CTkFrame(hakkinda, fg_color=self.colors["sidebar"],
                                     corner_radius=8, border_width=1,
                                     border_color=self.colors["border"])
        github_frame.pack(fill="x", padx=40, pady=(0, 10))

        ctk.CTkLabel(github_frame, text="📁 Kaynak Kod Kanıtı", 
                     font=("Segoe UI", 10, "bold"),
                     text_color="#569cd6").pack(anchor="w", padx=12, pady=(10, 0))

        ctk.CTkLabel(github_frame, 
                     text="github.com/YusufX-sys/turkod-ide",
                     font=("Consolas", 9),
                     text_color="#ce9178").pack(anchor="w", padx=12, pady=(5, 2))

        ctk.CTkLabel(github_frame, 
                     text="İlk gönderim: 8 Ağustos 2026",
                     font=("Segoe UI", 8),
                     text_color="#666").pack(anchor="w", padx=12, pady=(0, 10))

        # ===== DOSYA BİLGİSİ =====
        dosya_frame = ctk.CTkFrame(hakkinda, fg_color=self.colors["sidebar"],
                                    corner_radius=8, border_width=1,
                                    border_color=self.colors["border"])
        dosya_frame.pack(fill="x", padx=40, pady=(0, 20))

        ctk.CTkLabel(dosya_frame, text="📄 Dosya Bilgisi", 
                     font=("Segoe UI", 10, "bold"),
                     text_color="#666").pack(anchor="w", padx=12, pady=(10, 0))

        # Çalışan dosya tipi
        tip = "EXE" if getattr(sys, 'frozen', False) else "PY"
        ctk.CTkLabel(dosya_frame, 
                     text=f"Çalışan format: {tip}",
                     font=("Segoe UI", 9),
                     text_color="#888").pack(anchor="w", padx=12, pady=(5, 2))

        # Hash değeri
        basarili, mesaj, detay = DijitalImza.dogrula()

        # Hash gösterimi: başarılıysa manifest hash'i, değilse hata mesajı
        if basarili:
            from pathlib import Path
            _manifest_yol = Path(__file__).resolve().parent / "turkod_ide.manifest.json"
            _dosya_hash = DijitalImza.hash_hesapla(str(_manifest_yol)) if _manifest_yol.exists() else None
            hash_kisa = (_dosya_hash[:20] + "..." + _dosya_hash[-10:]) if _dosya_hash and len(_dosya_hash) > 30 else str(_dosya_hash or "N/A")
        else:
            hash_kisa = mesaj
        
        ctk.CTkLabel(dosya_frame, 
                     text=f"SHA-256: {hash_kisa}",
                     font=("Consolas", 8),
                     text_color="#666").pack(anchor="w", padx=12, pady=(0, 10))

        # ===== DOĞRULAMAYI BAŞLAT =====
        self.after(500, self._hakkimda_imza_kontrol)
        # ===== KAYDET BUTONU =====
        def kaydet_ayarlar():
            self.ayarlar.set("tema", tema_combo.get())
            self.ayarlar.set("yazi_tipi", yazi_var.get())
            self.ayarlar.set("yazi_boyutu", int(self.slider_boyut.get()))
            self.ayarlar.set("satir_numaralari", satir_var.get())
            self.ayarlar.set("kelime_sar", sar_var.get())
            self.ayarlar.set("otomatik_tamamlama", tamamlama_var.get())
            self.ayarlar.set("otomatik_kaydetme", oto_kaydet_var.get())
            self.ayarlar.set("otomatik_kaydetme_aralik", int(self.slider_aralik.get()))
            self.ayarlar.set("bosluk_gostergesi", bosluk_var.get())
            self.ayarlar.set("minimap", minimap_var.get())
            self.ayarlar.set("ai_aktif", ai_aktif_var.get())
            self._ai_durum_hazir()
            self.ayarlar.set("ai_saglayici", saglayici_var.get())
            self.ayarlar.set("ai_model", model_var.get())
            self.ayarlar.set("ai_api_key", api_key_var.get())
            self.ayarlar.set("ai_sistem_mesaji", sistem_var.get())
            self.ayarlar.set("ai_sicaklik", float(self.slider_sicaklik.get()))
            self.ayarlar.set("ai_max_token", int(self.slider_token.get()))

            self.tema = tema_combo.get()
            self.colors = TEMA_RENKLERI.get(self.tema, TEMA_RENKLERI["Modern Koyu"])
            # === WORD WRAP GÜNCELLEME ===
            self.kod_alani.configure(
                wrap="word" if self.ayarlar.get("kelime_sar") else "none"
            )
            
            # Ayarlari aninda UI grid'e yansit
            if satir_var.get():
                self.line_numbers.grid(row=0, column=0, sticky="nsew")
            else:
                self.line_numbers.grid_forget()
                
            if minimap_var.get():
                self.minimap.grid(row=0, column=2, sticky="nsew", padx=(2, 0))
                self._sync_minimap()
            else:
                self.minimap.grid_forget()
            self.after(100, self._modelleri_guncelle)
            self.sync_line_numbers()
            self._tema_uygula()
            pencere.destroy()

        ctk.CTkButton(pencere, text="Kaydet ve Uygula", command=kaydet_ayarlar,
                       fg_color="#28a745", hover_color="#218838",
                       border_color=self.colors["border"],
                       border_width=2,
                       font=("Segoe UI", 14, "bold")).pack(pady=15)

    def _tema_uygula(self):
        if self._kapatildi or not self.winfo_exists():
            return
        self.configure(fg_color=self.colors["bg"])
        self._grip_bg = self.colors.get("border", "#3c3c3c")
        self._grip_hover = self.colors.get("accent", "#007acc")
        
        if hasattr(self, "_ghost_line"):
            self._ghost_line.configure(bg=self._grip_hover)

        if hasattr(self, "_ghost_line_y"):
            self._ghost_line_y.configure(bg=self._grip_hover)

        for grip in ("sidebar_grip", "ai_grip", "terminal_grip"):
            if hasattr(self, grip):
                getattr(self, grip).configure(fg_color=self._grip_bg)
        if hasattr(self, "terminal_grip"):
            self.terminal_grip.configure(fg_color=self.colors["border"])
        # Aktivite Çubuğu (Activity Bar)
        if hasattr(self, 'activity_bar'):
            self.activity_bar.configure(fg_color=self.colors.get("activity_bar", self.colors["sidebar"]))
        
        # Aktivite barı butonları
        for btn in [self.explorer_btn, self.ai_toggle_btn, self.kod_arama_btn, self.ayarlar_btn]:
            btn.configure(
                fg_color="transparent",
                text_color=self.colors["text"],
                hover_color=self.colors.get("button_bg", "#313131"),
                border_width=0
            )
        
        # SOL PANEL (Sidebar) & Treeview
        self.sidebar.configure(fg_color=self.colors["sidebar"])
        self.sidebar_title.configure(text_color=self.colors["panel_fg"])
        self.proje_ac_btn.configure(fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"])
        
        style = ttk.Style()
        style.configure("Custom.Treeview",
            background=self.colors["sidebar"],
            foreground=self.colors["panel_fg"],
            fieldbackground=self.colors["sidebar"]
        )
        style.map("Custom.Treeview",
            background=[("selected", self.colors.get("selection", "#264f78"))],
            foreground=[("selected", self._secim_metin_rengi())]
        )

        self.dosya_tree.tag_configure("directory", foreground=self.colors.get("keyword", "#569cd6"))
        self.dosya_tree.tag_configure("trpy", foreground=self.colors.get("string", "#ce9178"))
        self.dosya_tree.tag_configure("python", foreground=self.colors.get("builtin", "#dcdcaa"))
        self.dosya_tree.tag_configure("other", foreground=self.colors["panel_fg"])

        # TAB BAR & SEKMELER
        for btn in (getattr(self, "tab_left_btn", None), getattr(self, "tab_right_btn", None)):
            if btn:
                btn.configure(text_color=self.colors["text"],
                              hover_color=self.colors["tab_active"])
        self.tab_bar.configure(fg_color=self.colors.get("tab_inactive", "#f3f3f3"))
        
        for sekme in self.sekmeler:
            is_active = (sekme["id"] == self.aktif_sekme_id)
            sekme["frame"].configure(
                fg_color=self.colors["tab_active"] if is_active else self.colors["tab_inactive"],
                border_color=self.colors["border"]
            )
            sekme["label"].configure(text_color=self.colors["text"])
            sekme["kapat_btn"].configure(text_color=self.colors["text"])

        # === TERMİNAL ===
        if hasattr(self, 'terminal_frame') and self.terminal_frame.winfo_exists():
            self.terminal_frame.configure(fg_color=self.colors["panel_bg"])

            for child in self.terminal_frame.winfo_children():
                # Üst başlık çubuğu
                if isinstance(child, ctk.CTkFrame):
                    child.configure(fg_color=self.colors["sidebar"])
                    for w in child.winfo_children():
                        if isinstance(w, ctk.CTkLabel):
                            w.configure(text_color=self.colors["panel_fg"])
                        elif isinstance(w, ctk.CTkButton):
                            w.configure(text_color=self.colors["text"])
                # Çıktı alanı
                elif isinstance(child, ctk.CTkTextbox):
                    child.configure(fg_color=self.colors["bg"],
                                    text_color=self.colors["text"])
                # Komut satırı
                elif isinstance(child, ctk.CTkEntry):
                    child.configure(fg_color=self.colors["ai_input"],
                                    text_color=self.colors["text"],
                                    border_color=self.colors["border"])
        if hasattr(self, "terminal_durdur_btn"):
            self.terminal_durdur_btn.configure(text_color="#f48771")
        # EDİTÖR FONT GÜNCELLEME
        yazi_tipi = self.ayarlar.get("yazi_tipi")
        if yazi_tipi not in set(tkfont.families()):
            yazi_tipi = "Consolas"
            self.ayarlar.set("yazi_tipi", yazi_tipi)

        yeni_font = (yazi_tipi, self.ayarlar.get("yazi_boyutu"))
        self.kod_alani.configure(font=yeni_font)
        self.line_numbers.configure(font=yeni_font)
            
        # Tab Butonları
        self.yeni_sekme_btn.configure(fg_color="transparent",
                              hover_color=self.colors["tab_active"],
                              text_color=self.colors["text"], border_width=0)
        self.ac_btn.configure(fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"], border_color=self.colors["border"])
        self.kaydet_btn.configure(fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"], border_color=self.colors["border"])
        self.calistir_btn.configure(border_color=self.colors["border"],
                            text_color=self.colors.get("accent", "#4CC2FF"))
        self.cevir_btn.configure(fg_color=self.colors["button_bg"],
        hover_color=self.colors["button_hover"], border_color=self.colors["border"])
        
        # EDİTÖR ALANI
        self.editor_frame.configure(fg_color=self.colors["bg"])
        self.line_numbers.configure(fg_color=self.colors["bg"], text_color=self.colors["line_number"])
        self.kod_alani.configure(fg_color=self.colors["bg"], text_color=self.colors["text"])
        
        if hasattr(self, 'minimap') and self.minimap.winfo_exists():
            self.minimap.configure(fg_color=self.colors["sidebar"], text_color=self.colors["text"])
        
        # AI PANEL
        self.ai_panel.configure(fg_color=self.colors["ai_panel"])
        self.ai_baslik.configure(text_color=self.colors["text"])
        
        for attr in ['ai_chat_area', 'ai_chat_frame', 'ai_messages_frame', 'chat_display']:
            if hasattr(self, attr):
                getattr(self, attr).configure(fg_color="transparent") 

        # Girdi Kutusu ve Butonlar
        self.ai_input_frame.configure(fg_color=self.colors["ai_input"])
        self.ai_input.configure(fg_color="transparent", text_color=self.colors["text"])
        self.ai_gonder_btn.configure(fg_color=self.colors["button_bg"], hover_color=self.colors["button_hover"])
        # AI sohbetini yeni temayla yeniden çiz
        if hasattr(self, 'ai_chat_frame') and self.ai_chat_frame.winfo_exists():
            kayitli = list(getattr(self, 'ai_mesajlar', []))
            for widget in self.ai_chat_frame.winfo_children():
                if widget is not getattr(self, 'ai_typing_frame', None):
                    widget.destroy()
            self.ai_mesajlar = []
            for m in kayitli:
                self._ai_mesaj_ekle(m["gonderen"], m["mesaj"])
            if not kayitli:
                self._ai_welcome_kur()
        if hasattr(self, 'ai_typing_frame') and self.ai_typing_frame.winfo_exists():
            self.ai_typing_frame.configure(fg_color=self.colors["ai_assistant"])
        # Alt Durum Çubuğu (Status Bar)
        self.status_bar.configure(fg_color=self.colors["status_bar"])
        durum_rengi = self._status_metin_rengi()
        if hasattr(self, 'status_left'):
            self.status_left.configure(text_color=durum_rengi)
        if hasattr(self, 'status_right'):
            self.status_right.configure(text_color=durum_rengi)
        if hasattr(self, 'stats_btn'):
            self.stats_btn.configure(text_color=durum_rengi)
        if hasattr(self, 'ai_hint_label'):
            self.ai_hint_label.configure(text_color=durum_rengi)
        if hasattr(self, 'ai_yeni_btn'):
            self.ai_yeni_btn.configure(
                text_color="#c0392b" if self.tema == "Açık" else "#ff6b6b")
        for btn in getattr(self, 'ai_aksiyon_btnlari', []):
            btn.configure(fg_color=self.colors["button_bg"],
                          hover_color=self.colors["button_hover"],
                          text_color=self.colors["text"])
        self.renk_ayarlarini_yap()
        self.kod_renklendir()
        # === AYARLAR PENCERESI DE GUNCELLENSIN ===
        if hasattr(self, 'ayarlar_penceresi') and self.ayarlar_penceresi.winfo_exists():
            self.ayarlar_penceresi.configure(fg_color=self.colors["bg"])
        # === AYARLAR PENCERESI NOTEBOOK TAB'LARI GUNCELLEME ===
        if hasattr(self, 'notebook') and self.notebook.winfo_exists():
            # Notebook'un kendisi
            self.notebook.configure(fg_color=self.colors["bg"])
            
            # Segmented button (tab başlıkları)
            if hasattr(self.notebook, '_segmented_button') and self.notebook._segmented_button:
                self.notebook._segmented_button.configure(
                    fg_color=self.colors.get("tab_inactive", self.colors["sidebar"]),
                    selected_color=self.colors.get("button_bg", "#0e639c"),
                    selected_hover_color=self.colors.get("button_hover", "#1177bb"),
                    unselected_color=self.colors.get("tab_inactive", self.colors["sidebar"]),
                    unselected_hover_color=self.colors.get("tab_active", self.colors["bg"]),
                    text_color=self.colors["text"],
                    text_color_disabled=self.colors.get("line_number", "#858585")
                )
            
            # Her bir tab'ın içeriği (frame)
            if hasattr(self.notebook, '_tab_dict'):
                for tab in self.notebook._tab_dict.values():
                    tab.configure(fg_color=self.colors["bg"])
            
            def _widget_renk_guncelle(widget, derinlik=0):
                if derinlik > 6:
                    return
                try:
                    if isinstance(widget, ctk.CTkFrame):
                        # Tab içeriği mi kontrol et (CTkTabview'in _tab_dict içinde mi?)
                        is_tab_content = False
                        try:
                            parent = widget.master
                            while parent:
                                if isinstance(parent, ctk.CTkTabview):
                                    is_tab_content = True
                                    break
                                parent = parent.master
                        except:
                            pass
                        
                        if is_tab_content:
                            # Tab içeriği = arka plan rengi
                            widget.configure(
                                fg_color=self.colors["bg"],
                                border_color=self.colors["border"]
                            )
                        else:
                            # Normal frame = sidebar rengi
                            widget.configure(
                                fg_color=self.colors.get("sidebar", self.colors["bg"]),
                                border_color=self.colors["border"]
                            )
                    elif isinstance(widget, ctk.CTkLabel):
                        widget.configure(text_color=self.colors["text"])
                    elif isinstance(widget, ctk.CTkCheckBox):
                        widget.configure(
                            text_color=self.colors["text"],
                            fg_color=self.colors.get("button_bg", "#0e639c"),
                            hover_color=self.colors.get("button_hover", "#1177bb")
                        )
                    elif isinstance(widget, ctk.CTkEntry):
                        widget.configure(
                            fg_color=self.colors.get("ai_input", "#3c3c3c"),
                            text_color=self.colors["text"],
                            border_color=self.colors["border"]
                        )
                    elif isinstance(widget, ctk.CTkOptionMenu):
                        widget.configure(
                            fg_color=self.colors.get("button_bg", "#0e639c"),
                            text_color=self.colors["text"],
                            button_color=self.colors.get("button_hover", "#1177bb"),
                            button_hover_color=self.colors.get("button_hover", "#1177bb")
                        )
                    elif isinstance(widget, ctk.CTkSlider):
                        widget.configure(
                            fg_color=self.colors.get("sidebar", self.colors["bg"]),
                            progress_color=self.colors.get("button_bg", "#0e639c"),
                            button_color=self.colors.get("button_bg", "#0e639c"),
                            button_hover_color=self.colors.get("button_hover", "#1177bb")
                        )
                    elif isinstance(widget, ctk.CTkButton):
                        widget.configure(
                            fg_color=self.colors.get("button_bg", "#0e639c"),
                            hover_color=self.colors.get("button_hover", "#1177bb"),
                            text_color=self.colors["text"],
                            border_color=self.colors["border"]
                        )
                    elif isinstance(widget, ctk.CTkSwitch):
                        widget.configure(
                            text_color=self.colors["text"],
                            progress_color=self.colors.get("accent", self.colors.get("button_bg", "#0e639c")),
                            fg_color=self.colors.get("button_bg", "#3c3c3c"),
                            button_color=self.colors.get("text", "#d4d4d4")
                        )
                except Exception:
                    pass
                for child in widget.winfo_children():
                    _widget_renk_guncelle(child, derinlik + 1)
            
            _widget_renk_guncelle(self.ayarlar_penceresi)
            # === AYARLAR PENCERESI NOTEBOOK TAB'LARI GUNCELLEME ===
            if hasattr(self, 'notebook') and self.notebook.winfo_exists():
                self.notebook.configure(fg_color=self.colors["bg"])
                if hasattr(self.notebook, '_segmented_button') and self.notebook._segmented_button:
                    self.notebook._segmented_button.configure(
                        fg_color=self.colors.get("tab_inactive", self.colors["sidebar"]),
                        selected_color=self.colors.get("button_bg", "#0e639c"),
                        selected_hover_color=self.colors.get("button_hover", "#1177bb"),
                        unselected_color=self.colors.get("tab_inactive", self.colors["sidebar"]),
                        unselected_hover_color=self.colors.get("tab_active", self.colors["bg"]),
                        text_color=self.colors["text"],
                        text_color_disabled=self.colors.get("line_number", "#858585")
                    )
                if hasattr(self.notebook, '_tab_dict'):
                    for tab in self.notebook._tab_dict.values():
                        tab.configure(fg_color=self.colors["bg"])
            # === SLIDER'LARI DOĞRUDAN GÜNCELLE ===
            # CTkTabview içinde oldukları için recursive bulunamayabilirler
            slider_renkleri = {
                "fg_color": self.colors.get("sidebar", self.colors["bg"]),
                "progress_color": self.colors.get("button_bg", "#0e639c"),
                "button_color": self.colors.get("button_bg", "#0e639c"),
                "button_hover_color": self.colors.get("button_hover", "#1177bb")
            }
            for attr in ['slider_boyut', 'slider_aralik', 'slider_sicaklik', 'slider_token']:
                if hasattr(self, attr):
                    try:
                        getattr(self, attr).configure(**slider_renkleri)
                    except Exception:
                        pass
                    
            # === DEĞER LABEL'LARINI DOĞRUDAN GÜNCELLE ===
            for attr in ['label_boyut', 'label_aralik', 'label_sicaklik', 'label_token']:
                if hasattr(self, attr):
                    try:
                        getattr(self, attr).configure(text_color=self.colors["text"])
                    except Exception:
                        pass
    def _hakkimda_imza_kontrol(self):
        """Hakkımda sekmesindeki RSA imzasını kontrol et ve göster"""
        try:
            print(f"\n{'='*70}")
            print("  HAKKIMDA - İMZA KONTROL BAŞLATILIYOR")
            print(f"{'='*70}")
            
            basarili, mesaj, detay = DijitalImza.dogrula()
            
            print(f"\n  Sonuç: basarili={basarili}, mesaj='{mesaj}', detay='{detay}'")
            print(f"{'='*70}\n")
            
            self.rsa_durum.configure(text=mesaj)
            self.rsa_detay.configure(text=detay)
            
            if basarili:
                self.rsa_durum.configure(text_color="#4caf50")
            elif "GEÇERSİZ" in mesaj:
                self.rsa_durum.configure(text_color="#f44336")
            else:
                self.rsa_durum.configure(text_color="#ff9800")
                
        except Exception as e:
            import traceback
            print(f"\n{'='*70}")
            print("  İMZA KONTROL EXCEPTION (HAKKIMDA)")
            print(f"{'='*70}")
            print(f"  Hata: {str(e)}")
            print("  Traceback:")
            traceback.print_exc()
            print(f"{'='*70}\n")
            
            self.rsa_durum.configure(
                text="⚠️ Kontrol hatası",
                text_color="#ff9800"
            )
            self.rsa_detay.configure(
                text=str(e)[:80],
                text_color="#666"
            )
    # ============ EDITOR FONKSIYONLARI ============
    def _gorsel_satir_adedi(self, satir):
        kod_tb = getattr(self.kod_alani, "_textbox", self.kod_alani)
        try:
            n = kod_tb.count(f"{satir}.0", f"{satir + 1}.0", "displaylines")
            if isinstance(n, (tuple, list)):
                n = n[0]
            return max(1, int(n or 1))
        except Exception:
            return 1

    def _satir_numaralarini_ciz(self):
        gizli = self._gizli_satirlar()
        self.line_numbers.configure(state="normal")
        self.line_numbers.delete("1.0", "end")
        satir_sayisi = int(self.kod_alani.index("end-1c").split(".")[0])
        for i in range(1, satir_sayisi + 1):
            if i in gizli:
                continue                      # katlanmış satırın numarası çizilmez
            ikon = ""
            if i in getattr(self, "fold_indicators", {}):
                ikon = self.fold_indicators[i] + " "
            self.line_numbers.insert("end", f"{ikon}{i}\n")
            for _ in range(self._gorsel_satir_adedi(i) - 1):
                self.line_numbers.insert("end", "\n")
        self.line_numbers.configure(state="disabled")
    def _gutter_rakamini_oku(self, event):
        """Tıklanan gutter satırındaki gerçek satır numarasını ve sütunu döndürür"""
        ln = getattr(self.line_numbers, "_textbox", self.line_numbers)
        idx = ln.index(f"@{event.x},{event.y}")
        g_satir, sutun = idx.split(".")
        metin = ln.get(f"{g_satir}.0", f"{g_satir}.end")
        m = re.search(r"\d+", metin)
        if not m:
            return None, None
        return int(m.group(0)), int(sutun)

    def sync_line_numbers(self):
        try:
            self._fold_guncelle()          # numaraları da yeniden çizer
            self._senkronize_scroll()      # çizimden SONRA senkron
            self._sync_minimap()
        except Exception as e:
            print(f"[Fold Hatası] sync_line_numbers: {e}")
    def _sync_minimap(self):
        """Minimap textini ana editorle senkronize et"""
        if not self.ayarlar.get("minimap") or not hasattr(self, 'minimap'):
            return
            
        try:
            icerik = self.kod_alani.get("1.0", "end")
            self.minimap.configure(state="normal")
            self.minimap.delete("1.0", "end")
            self.minimap.insert("1.0", icerik)
            self.minimap.configure(state="disabled")
            
            first, last = self.kod_alani.yview()
            self.minimap.yview_moveto(first)
        except Exception:
            pass
    
    def kod_renklendir(self):
        try:
            tb = getattr(self.kod_alani, "_textbox", self.kod_alani)

            # 1) Eski tag'leri temizle (fstring ve bosluk dahil)
            for tag in ("keyword", "builtin", "string", "comment", "number", "fstring", "bosluk"):
                tb.tag_remove(tag, "1.0", "end")

            metin = self.kod_alani.get("1.0", "end-1c")
            if not metin:
                return

            def tk_idx(pos):
                satir = metin.count("\n", 0, pos) + 1
                sutun = pos - metin.rfind("\n", 0, pos) - 1
                return f"{satir}.{sutun}"

            string_pattern = (
                r'(?<![A-Za-z0-9_])'
                r'([fF]?(\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\''
                r'|"(?:[^"\\\n]|\\.)*"?|\'(?:[^\'\\\n]|\\.)*\'?))'
            )
            comment_pattern = r'#[^\n]*'
            number_pattern = r'\b\d+(?:\.\d+)?\b'

            # 2) String'ler ve f-string'ler (üçlü tırnak dahil)
            string_araliklari = []
            for m in re.finditer(string_pattern, metin):
                string_araliklari.append((m.start(), m.end()))
                tag = "fstring" if m.group(1)[:1] in "fF" else "string"
                tb.tag_add(tag, tk_idx(m.start()), tk_idx(m.end()))

            # 3) Yorumlar (string içindeki # yok sayılır)
            korunacak = list(string_araliklari)
            for m in re.finditer(comment_pattern, metin):
                if any(s <= m.start() < e for s, e in string_araliklari):
                    continue
                korunacak.append((m.start(), m.end()))
                tb.tag_add("comment", tk_idx(m.start()), tk_idx(m.end()))

            def disinda(a, b):
                return not any(s <= a and b <= e for s, e in korunacak)

            # 4) Keyword / builtin / sayı (string ve yorum dışındakiler)
            for m in TURKOD_KEYWORD_RE.finditer(metin):
                if disinda(m.start(), m.end()):
                    tb.tag_add("keyword", tk_idx(m.start()), tk_idx(m.end()))
            for m in TURKOD_BUILTIN_RE.finditer(metin):
                if disinda(m.start(), m.end()):
                    tb.tag_add("builtin", tk_idx(m.start()), tk_idx(m.end()))
            for m in re.finditer(number_pattern, metin):
                if disinda(m.start(), m.end()):
                    tb.tag_add("number", tk_idx(m.start()), tk_idx(m.end()))

            # 5) Boşluk göstergesi (ayar açıksa)
            if self.ayarlar.get("bosluk_gostergesi"):
                tb.tag_config("bosluk", underline=True,
                              foreground=self.colors.get("line_number", "#858585"))
                for m in re.finditer(r'[ \t]+', metin):
                    tb.tag_add("bosluk", tk_idx(m.start()), tk_idx(m.end()))
        except Exception:
            pass

    def mevcut_kelimeyi_al(self):
        cursor_pos = self.kod_alani.index("insert")
        satir, sutun = cursor_pos.split(".")
        satir_metni = self.kod_alani.get(f"{satir}.0", cursor_pos)
        match = re.search(r"([a-zA-Z0-9_ÇŞĞÜÖİçşğüöı]+)$", satir_metni)
        if match:
            baslangic_col = match.start(1)
            return match.group(1), f"{satir}.{baslangic_col}", cursor_pos
        return "", cursor_pos, cursor_pos

    def popup_goster(self, kelime, bas_idx, bit_idx):
        if not self.ayarlar.get("otomatik_tamamlama"):
            return
        
        tum_kelimeler = self._tamamlama_kelime_listesi_al()
        if not tum_kelimeler:
            return
        
        # Eşleşmeleri bul
        eslesmeler = []
        kod_tanimlari = self._koddan_tanimlari_cikar(self.kod_alani.get("1.0", "end-1c"))
        for k in kod_tanimlari:
            if k.lower().startswith(kelime.lower()) and k.lower() != kelime.lower():
                eslesmeler.append(("📌", k))
        for k in TURKCE_KELIMELER:
            if k.lower().startswith(kelime.lower()) and k.lower() != kelime.lower():
                if k not in [x[1] for x in eslesmeler]:
                    eslesmeler.append(("📚", k))
        
        if not eslesmeler or len(kelime) < 2:
            self.popup_kapat()
            return

        # Tema renklerini al
        bg_color = self.colors.get("sidebar", "#252526")
        fg_color = self.colors.get("text", "#d4d4d4")
        select_bg = self.colors.get("selection", "#04395e")
        select_fg = self._secim_metin_rengi()
        border_color = self.colors.get("border", "#3c3c3c")

        if not self.popup:
            self.popup = tk.Toplevel(self)
            self.popup.wm_overrideredirect(True)
            self.popup.wm_attributes("-topmost", True)

            self.listbox = tk.Listbox(
                self.popup, 
                bg=bg_color, 
                fg=fg_color, 
                selectbackground=select_bg,
                selectforeground=select_fg, 
                font=("Consolas", 11), 
                bd=1, 
                relief="solid",
                highlightbackground=border_color,
                highlightcolor=border_color
            )
            self.listbox.pack(fill="both", expand=True)
            self.listbox.bind("<Double-Button-1>", lambda e: self.kelime_tamamla())
            self.listbox.bind("<Return>", lambda e: self.kelime_tamamla())

        # Renkleri güncelle (tema değişiminde)
        self.listbox.configure(
            bg=bg_color,
            fg=fg_color,
            selectbackground=select_bg,
            highlightbackground=border_color
        )
        self.popup.configure(bg=bg_color)

        self.listbox.delete(0, tk.END)
        for ikon, item in eslesmeler[:15]:
            self.listbox.insert(tk.END, f"{ikon} {item}")
        self.listbox.select_set(0)
        
        try:
            bbox = self.kod_alani._textbox.bbox("insert")
            if bbox:
                x = self.kod_alani.winfo_rootx() + bbox[0] + 10
                y = self.kod_alani.winfo_rooty() + bbox[1] + bbox[3] + 25
                self.popup.geometry(f"260x180+{x}+{y}")
                self.popup.deiconify()
                self.popup.lift()
            else:
                x = self.kod_alani.winfo_rootx() + 50
                y = self.kod_alani.winfo_rooty() + 50
                self.popup.geometry(f"260x180+{x}+{y}")
                self.popup.deiconify()
        except Exception as e:
            self.popup_kapat()

    def popup_kapat(self):
        if self.popup:
            self.popup.destroy()
            self.popup = None
            self.listbox = None

    def kelime_tamamla(self):
        if self.popup and self.listbox and self.listbox.curselection():
            secilen = self.listbox.get(self.listbox.curselection()[0])
            secilen = secilen.replace("📌 ", "").replace("📚 ", "")
            
            kelime, bas, bit = self.mevcut_kelimeyi_al()
            if kelime:
                self.kod_alani.delete(bas, bit)
                self.kod_alani.insert(bas, secilen)
                self.popup_kapat()
                self.after(50, self.kod_renklendir)
                return "break"
        self.popup_kapat()
        return None
    def _turkce_karakter_kontrol(self):
        """Türkçe karakter içeren değişken/fonksiyon isimlerini uyarı olarak işaretle"""
        try:
            self.kod_alani.tag_remove("turkce_uyari", "1.0", "end")
            
            turkce_harfler = "çğıöşüÇĞİÖŞÜ"
            kod = self.kod_alani.get("1.0", "end-1c")
            
            # Değişken/fonksiyon tanımlarını bul
            import re
            
            # fonksiyon isim(...)
            for match in re.finditer(r'fonksiyon\s+([a-zA-Z_çğıöşüÇĞİÖŞÜ][a-zA-Z0-9_çğıöşüÇĞİÖŞÜ]*)', kod):
                isim = match.group(1)
                if any(h in isim for h in turkce_harfler):
                    # Satır ve sütun bul
                    satir = kod[:match.start(1)].count('\n') + 1
                    satir_bas = kod.rfind('\n', 0, match.start(1)) + 1
                    sutun = match.start(1) - satir_bas
                    self.kod_alani.tag_add("turkce_uyari", f"{satir}.{sutun}", f"{satir}.{sutun + len(isim)}")
            
            # değişken = ...
            for match in re.finditer(r'^([a-zA-Z_çğıöşüÇĞİÖŞÜ][a-zA-Z0-9_çğıöşüÇĞİÖŞÜ]*)\s*=', kod, re.MULTILINE):
                isim = match.group(1)
                if any(h in isim for h in turkce_harfler):
                    satir = kod[:match.start(1)].count('\n') + 1
                    satir_bas = kod.rfind('\n', 0, match.start(1)) + 1
                    sutun = match.start(1) - satir_bas
                    self.kod_alani.tag_add("turkce_uyari", f"{satir}.{sutun}", f"{satir}.{sutun + len(isim)}")
            
            # Stil
            self.kod_alani.tag_config("turkce_uyari", underline=True, foreground="#ff9800")
            
        except Exception:
            pass
    def on_key_release(self, event):
        if event.keysym in ["Up", "Down", "Return", "Tab", "Escape"]:
            return
        
        self.kod_renklendir()
        kelime, bas, bit = self.mevcut_kelimeyi_al()
        if kelime:
            self.popup_goster(kelime, bas, bit)
        else:
            self.popup_kapat()
        
        # Syntax kontrolü - önceki timer'ı iptal et
        if hasattr(self, '_syntax_timer') and self._syntax_timer:
            self.after_cancel(self._syntax_timer)
        self._syntax_timer = self.after(500, self._syntax_kontrol)
        
    def _syntax_kontrol(self):
        """Kodu AST ile kontrol et, hatalı satırları kırmızı alt çizgi ile işaretle"""
        try:
            # Önceki hata etiketlerini temizle
            self.kod_alani.tag_remove("syntax_hata", "1.0", "end")
            
            turkce_kod = self.kod_alani.get("1.0", "end-1c")
            if not turkce_kod.strip():
                return
            
            # TürKod'u Python'a çevir
            python_kodu = turkce_kodu_donustur(turkce_kod)
            
            # AST parse dene
            import ast
            try:
                ast.parse(python_kodu)
                self.status_left.configure(text="  ✓ Sözdizimi doğru")
                return
            except SyntaxError as e:
                if e.lineno:
                    hata_satir = e.lineno
                    self.kod_alani.tag_add("syntax_hata", f"{hata_satir}.0", f"{hata_satir}.end")
                    self.status_left.configure(text=f"  ⚠ Sözdizimi hatası: Satır {hata_satir}")
            
            # Hata etiketi stili
            renk = "#ffdcdc" if self.tema == "Açık" else "#5a1d1d"
            self.kod_alani.tag_config("syntax_hata", background=renk, underline=True)
            
        except Exception:
            pass
    def _tab_indent(self, event=None):
        """Tab: Seçili satırları sağa kaydır, yoksa otomatik tamamlama veya boşluk"""
        try:
            if self.popup:
                return self.kelime_tamamla()
                
            BOSLUK_SAYISI = "  " # 2 Boşluk
                
                # Seçili metin var mı?
            if self.kod_alani.tag_ranges("sel"):
                bas = self.kod_alani.index("sel.first")
                bit = self.kod_alani.index("sel.last")
                bas_satir = int(bas.split(".")[0])
                bit_satir = int(bit.split(".")[0])
                # Her satırın başına 2 boşluk ekle
                for satir_no in range(bas_satir, bit_satir + 1):
                    self.kod_alani.insert(f"{satir_no}.0", BOSLUK_SAYISI)
                # Seçimi güncelle
                yeni_bas = f"{bas_satir}.0"
                yeni_bit = f"{bit_satir}.end"
                self.kod_alani.tag_remove("sel", "1.0", "end")
                self.kod_alani.tag_add("sel", yeni_bas, yeni_bit)
                self.sync_line_numbers()
                return "break"
            else:
                    # Normal tab davranışı (otomatik tamamlama veya 2 boşluk)
                self.kod_alani.insert("insert", BOSLUK_SAYISI)
                return "break"
        except Exception:
            self.kod_alani.insert("insert", "  ")
            return "break"
    def on_return_key(self, event):
        if self.popup:
            return self.kelime_tamamla()

    def on_arrow_down(self, event):
        if self.popup and self.listbox:
            idx = self.listbox.curselection()
            if idx:
                sonraki = min(idx[0] + 1, self.listbox.size() - 1)
                self.listbox.select_clear(0, tk.END)
                self.listbox.select_set(sonraki)
            return "break"
        return None  # ← Ekle: Popup yoksa imleç normal hareket etsin

    def on_arrow_up(self, event):
        if self.popup and self.listbox:
            idx = self.listbox.curselection()
            if idx:
                onceki = max(idx[0] - 1, 0)
                self.listbox.select_clear(0, tk.END)
                self.listbox.select_set(onceki)
            return "break"
        return None  # ← Ekle

    def dosya_ac(self):
        path = filedialog.askopenfilename(title="Dosya Seç", filetypes=[("Türkçe Python", "*.trpy")])
        if path:
            self._yeni_sekme_olustur(yol=path)
    def _kod_dili_tespit(self, kod):
        """Puanlama ile tespit: TürKod mu Python mu?"""
        turkod = len(TURKOD_KEYWORD_RE.findall(kod))
        turkod += len(TURKOD_BUILTIN_RE.findall(kod))

        python = len(re.findall(
            r"\b(def|return|class|if|elif|else|for|while|print|input|import|"
            r"from|try|except|finally|break|continue)\b",
            kod
        ))

        if turkod == python:
            return "turkod"
        return "turkod" if turkod > python else "python"

    def _kodu_cevir(self, event=None):
        kod = self.kod_alani.get("1.0", "end-1c")
        if not kod.strip():
            self.status_left.configure(text="  Çevrilecek kod yok.")
            return "break"

        dil = self._kod_dili_tespit(kod)

        if dil == "turkod":
            sonuc = turkce_kodu_donustur(kod)
            kaynak, hedef, uzanti = "TürKod", "Python", ".py"
        else:
            sonuc = python_kodu_turkceye_cevir(kod)
            kaynak, hedef, uzanti = "Python", "TürKod", ".trpy"

        # Orijinal bozulmasın diye sonucu yeni sekmede aç
        sekme = self._aktif_sekme()
        taban = os.path.splitext(sekme["isim"])[0] if sekme else "cevrilmis"
        self._yeni_sekme_olustur(isim=taban + uzanti, icerik=sonuc)

        self.status_left.configure(text=f"  {kaynak} → {hedef} çevrildi, yeni sekmede açıldı.")
        return "break"
    def dosya_kaydet(self):
        sekme = self._aktif_sekme()
        if not sekme:
            return

        sekme["icerik"] = self.kod_alani.get("1.0", "end")

        if sekme["yol"]:
            with open(sekme["yol"], "w", encoding="utf-8") as f:
                f.write(sekme["icerik"])
            sekme["degisti"] = False
            sekme["isim"] = os.path.basename(sekme["yol"])
            self._sekme_baslik_guncelle()
            self.status_left.configure(text=f"  Kaydedildi: {sekme['isim']}")
        else:
            path = filedialog.asksaveasfilename(title="Kaydet", defaultextension=".trpy",
                                                 filetypes=[("Türkçe Python", "*.trpy")])
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(sekme["icerik"])
                sekme["yol"] = path
                sekme["isim"] = os.path.basename(path)
                sekme["degisti"] = False
                self._sekme_baslik_guncelle()
                self._status_guncelle()

    def kodu_calistir(self):
        # Önceki çalışan process'i kapat
        if self._calistirma_process is not None:
            try:
                self._calistirma_process.terminate()
                self._calistirma_process.wait(timeout=2)
            except:
                try:
                    self._calistirma_process.kill()
                except:
                    pass
            self._calistirma_process = None
        turkce_kod = self.kod_alani.get("1.0", "end")
        python_kodu = turkce_kodu_donustur(turkce_kod)

        temp_dir = tempfile.gettempdir()
        kod_path = os.path.join(temp_dir, "turkce_kod_calisma.py")
        runner_path = os.path.join(temp_dir, "runner.py")

        with open(kod_path, "w", encoding="utf-8") as f:
            f.write(python_kodu)

        with open(runner_path, "w", encoding="utf-8") as f:
            f.write(RUNNER_KODU)

        # ==================== PYTHON BULMA ====================
        python_exe = None
        
        if getattr(sys, 'frozen', False):
            # 1. Önce _internal/python_embed/ var mı? (taşınabilir Python)
            exe_dir = os.path.dirname(sys.executable)
            embed_python = os.path.join(exe_dir, "_internal", "python_embed", "python.exe")
            if os.path.exists(embed_python):
                python_exe = embed_python
            
            # 2. Yoksa sistemdeki Python'u dene
            if not python_exe:
                import shutil
                python_exe = shutil.which("python.exe") or shutil.which("python")
                
            # 3. Hala yoksa hata ver
            if not python_exe:
                messagebox.showerror(
                    "Python Gerekli",
                    "Kodu çalıştırmak için Python 3.x gerekli.\n\n"
                    "Python kurulu olmayan bilgisayarlarda:\n"
                    "1. https://python.org/downloads adresinden indirin\n"
                    "2. Kurulumda 'Add Python to PATH' seçeneğini işaretleyin\n\n"
                    "Veya geliştirici modunda taşınabilir Python paketini "
                    "_internal/python_embed/ klasörüne ekleyin."
                )
                return
        else:
            python_exe = sys.executable
            if python_exe.endswith("pythonw.exe"):
                python_exe = python_exe.replace("pythonw.exe", "python.exe")

        # ==================== CALISTIRMA ====================
        if not self.terminal_visible:
            self._terminal_toggle()
        self._terminal_yazdir(f"\n> python -u runner.py\n")

        cf = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self._calistirma_process = subprocess.Popen(
            [python_exe, "-X", "utf8", "-u", runner_path],
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=cf
        )
        threading.Thread(target=self._terminal_oku, args=(self._calistirma_process,), daemon=True).start()
        self.status_left.configure(text="  Kod Çalıştırılıyor...")
    # ============ ENTEGRE TERMİNAL ============
    def _terminal_toggle(self, event=None):
        if getattr(self, "_term_anim", None):
            try:
                self.after_cancel(self._term_anim)
            except Exception:
                pass
            self._term_anim = None

        hedef_h = getattr(self, "_terminal_hedef_h", 220)

        if getattr(self, "terminal_visible", False):
            self.terminal_visible = False
            # KAPAT: mevcut konumdan aşağı kay
            self._terminal_adimla(getattr(self, "_term_y", 0), hedef_h, hedef_h, kapat=True)
        else:
            # AÇ: satırı TEK seferde ayır (tek relayout), sonra içinde kaydır
            self.terminal_grip.grid(row=2, column=3, sticky="ew")
            self.terminal_wrapper.grid(row=3, column=3, sticky="nsew")
            self.grid_rowconfigure(3, minsize=hedef_h)
            self.terminal_frame.configure(height=hedef_h)
            self.terminal_frame.place(x=0, y=hedef_h, relwidth=1.0)
            self._term_y = hedef_h
            self.terminal_visible = True
            self._terminal_adimla(hedef_h, 0, hedef_h, kapat=False)
        return "break"

    def _terminal_adimla(self, y_bas, y_son, hedef_h, adim=0, kapat=False):
        """Wrapper içinde ease-out ile kaydır; grid'e dokunmaz"""
        TOPLAM = 16
        t = (adim + 1) / TOPLAM
        e = 1 - (1 - t) ** 3
        y = int(y_bas + (y_son - y_bas) * e)
        self._term_y = y
        try:
            self.terminal_frame.place_configure(y=y)
        except Exception:
            return
        if adim < TOPLAM - 1:
            self._term_anim = self.after(
                16, lambda: self._terminal_adimla(y_bas, y_son, hedef_h, adim + 1, kapat))
        else:
            self._term_anim = None
            if kapat:
                self.terminal_wrapper.grid_remove()
                self.terminal_grip.grid_remove()
                self.grid_rowconfigure(3, minsize=0)
    def _terminal_grip_basla(self, event):
        self._tg_baslangic_y = event.y_root
        self._tg_baslangic_h = self.terminal_frame.winfo_height()
        self._grip_aktif = True

    def _terminal_grip_surukle(self, event):
        if not self._grip_aktif:
            return
        delta = self._tg_baslangic_y - event.y_root
        yeni = max(80, min(600, self._tg_baslangic_h + delta))
        y_pos = self.terminal_wrapper.winfo_y() - (yeni - self._tg_baslangic_h)
        self._ghost_line_y.place(x=self.editor_frame.winfo_x(), y=y_pos,
                                 width=self.editor_frame.winfo_width(), height=2)
        self._ghost_line_y.lift()
        self._tg_yeni = yeni

    def _terminal_grip_birak(self, event):
        if not self._grip_aktif:
            return
        self._grip_aktif = False
        self._ghost_line_y.place_forget()
        yeni = int(getattr(self, "_tg_yeni", getattr(self, "_terminal_hedef_h", 220)))
        self._terminal_hedef_h = yeni
        self.grid_rowconfigure(3, minsize=yeni)
        self.terminal_frame.configure(height=yeni)
        self.terminal_frame.place_configure(y=0)
        self._term_y = 0
        self.update_idletasks()

    def _terminal_yazdir(self, metin):
        self.terminal_output.configure(state="normal")
        self.terminal_output.insert("end", metin)
        self.terminal_output.see("end")
        self.terminal_output.configure(state="disabled")
    def _terminal_limit(self):
        """Sonsuz döngüde widget'ın şişip yavaşlamasını önler."""
        MAX = 1000
        try:
            n = int(self.terminal_output.index("end-1c").split(".")[0])
            if n > MAX:
                self.terminal_output.delete("1.0", f"{n - MAX}.0")
        except Exception:
            pass

    def _terminal_bufere_ekle(self, metin):
        """Worker thread çıktısını biriktirir; UI'yi flood etmez."""
        with self._term_lock:
            self._term_buf.append(metin)
            self._term_buf_len += len(metin)
            # Bellek de sınırsız büyümesin; eskiden at, yeniyi tut
            while self._term_buf_len > 300000 and self._term_buf:
                ilk = self._term_buf.pop(0)
                self._term_buf_len -= len(ilk)
            planla = not self._term_flush_planli
            if planla:
                self._term_flush_planli = True
        if planla:
            try:
                self.after(80, self._terminal_flush)
            except Exception:
                pass

    def _terminal_flush(self):
        with self._term_lock:
            parcalar = self._term_buf
            self._term_buf = []
            self._term_buf_len = 0
        metin = "".join(parcalar) if parcalar else ""
        if metin:
            try:
                if len(metin) > 20000:   # tek seferde dev insert yapma
                    metin = metin[-20000:]
                self.terminal_output.configure(state="normal")
                self.terminal_output.insert("end", metin)
                self._terminal_limit()
                self.terminal_output.see("end")
                self.terminal_output.configure(state="disabled")
            except Exception:
                pass
        with self._term_lock:
            devam = bool(self._term_buf)
            if not devam:
                self._term_flush_planli = False
        if devam:
            try:
                self.after(80, self._terminal_flush)
            except Exception:
                pass
    def _terminal_temizle(self):
        self.terminal_output.configure(state="normal")
        self.terminal_output.delete("1.0", "end")
        self.terminal_output.configure(state="disabled")
    def _kodu_durdur(self, event=None):
        proc = getattr(self, "_calistirma_process", None)
        if proc is None or proc.poll() is not None:
            self.status_left.configure(text="  Çalışan süreç yok.")
            return
        try:
            if os.name == "nt":
                # /T: çocuk process'leri de öldürür (runner'ın başlattığı kod dahil)
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                proc.terminate()
        except Exception:
            pass
        self.status_left.configure(text="  Kod durduruldu.")
    def _terminal_enter(self, event=None):
        komut = self.terminal_input.get().strip()
        self.terminal_input.delete(0, "end")
        if not komut:
            return "break"

        self._terminal_yazdir(f"> {komut}\n")

        proc = getattr(self, "_calistirma_process", None)
        # Kod çalışıyorsa yazılanı input()'a gönder
        if proc is not None and proc.poll() is None and proc.stdin:
            try:
                proc.stdin.write(komut + "\n")
                proc.stdin.flush()
            except Exception:
                pass
            return "break"

        # Kod çalışmıyorsa sistem komutu olarak çalıştır
        threading.Thread(target=self._terminal_komut_calistir, args=(komut,), daemon=True).start()
        return "break"

    def _terminal_komut_calistir(self, komut):
        try:
            cf = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            cwd = self.proje_dizini if self.proje_dizini and os.path.exists(self.proje_dizini) else os.getcwd()
            sonuc = subprocess.run(
                komut, shell=True, cwd=cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=cf
            )
            self.after(0, self._terminal_yazdir, (sonuc.stdout or "") + "\n")
        except Exception as e:
            self.after(0, self._terminal_yazdir, f"[Hata: {e}]\n")

    def _terminal_oku(self, process):
        import codecs
        cozucu = codecs.getincrementaldecoder("utf-8")("replace")
        fd = process.stdout.fileno()
        try:
            while True:
                ham = os.read(fd, 4096)
                if not ham:
                    break
                metin = cozucu.decode(ham)
                if metin:
                    self._terminal_bufere_ekle(metin)
            kalan = cozucu.decode(b"", final=True)
            if kalan:
                self._terminal_bufere_ekle(kalan)
            kod = process.wait()
            self._terminal_bufere_ekle(f"\n[Process {kod} koduyla çıktı]\n")
        except Exception as e:
            self._terminal_bufere_ekle(f"[Terminal okuma hatası: {e}]\n")
        finally:
            self._calistirma_process = None
    def _pencere_kapat(self):
        self._kapatildi = True  # thread ve after callback'leri için bayrak
        cevap = True

        degisikler = [s for s in self.sekmeler if s["degisti"]]
        if degisikler:
            isimler = ", ".join(s["isim"] for s in degisikler)
            cevap = messagebox.askyesnocancel(
                "Çıkış",
                f"Kaydedilmemiş dosyalar: {isimler}\nKaydedilsin mi?")
            if cevap is None:
                self._kapatildi = False  # kullanıcı iptal etti
                return
            if cevap:
                for s in degisikler:
                    if s["yol"]:
                        icerik = s["icerik"]
                        if s["id"] == self.aktif_sekme_id:
                            icerik = self.kod_alani.get("1.0", "end-1c")
                        try:
                            with open(s["yol"], "w", encoding="utf-8") as f:
                                f.write(icerik)
                        except Exception:
                            pass

        # === OTURUMU KAYDET — metod seviyesinde, if'lerin DIŞINDA ===
        oturum = []
        aktif_sira = 0
        for i, s in enumerate(self.sekmeler):
            if s["id"] == self.aktif_sekme_id:
                aktif_sira = i
                icerik = self.kod_alani.get("1.0", "end-1c")
            else:
                icerik = s["icerik"]
            
            # Kullanıcı "Hayır" dediyse ve dosya kaydedilmemişse (yol yoksa) içeriği çöpe at
            if not cevap and s["degisti"] and not s["yol"]:
                icerik = ""

            oturum.append({
                "yol": s["yol"],
                "isim": s["isim"],
                "icerik": None if s["yol"] else icerik,
            })
        try:
            self.ayarlar.set("son_oturum", oturum)
            self.ayarlar.set("son_oturum_aktif", aktif_sira)
        except Exception:
            pass

        # ttk kapanış hatasını sustur
        try:
            self.tk.eval("proc ttk::ThemeChanged args {}")
        except Exception:
            pass
        try:
            self.quit()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
