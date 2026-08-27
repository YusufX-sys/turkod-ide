"""Basit breakpoint vurgulayici."""
from tkinter import messagebox


class BasitDebugger:
    """Basit satır satır hata ayıklayıcı"""
    
    def __init__(self, ide):
        self.ide = ide
        self.breakpoints = set()  # {satir_no}
        self.calistiriliyor = False
        self.mevcut_satir = 0
        self._highlight_tag = "breakpoint"
        self._current_tag = "debug_current"
    
    def breakpoint_toggle(self, satir):
        """Satırda breakpoint aç/kapat"""
        if satir in self.breakpoints:
            self.breakpoints.remove(satir)
            self.ide.kod_alani.tag_remove(self._highlight_tag, f"{satir}.0", f"{satir}.end")
        else:
            self.breakpoints.add(satir)
            self.ide.kod_alani.tag_add(self._highlight_tag, f"{satir}.0", f"{satir}.end")
            renk = "#ffdcdc" if self.ide.tema == "Açık" else "#5a1d1d"
            self.ide.kod_alani.tag_config(self._highlight_tag, background=renk)
    def baslat(self):
        """Debugger'ı başlat"""
        if not self.breakpoints:
            messagebox.showwarning("Debugger", "Önce breakpoint ekleyin! (Satır numarasına tıklayın)")
            return
        
        self.calistiriliyor = True
        self.mevcut_satir = min(self.breakpoints)
        self._vurgula(self.mevcut_satir)
        self.ide.status_left.configure(text=f"  ⏸ Hata Ayıklayıcı: Satır {self.mevcut_satir}")
    
    def adim(self):
        """Bir sonraki satıra geç"""
        if not self.calistiriliyor:
            return
        
        self._vurgula_kaldir(self.mevcut_satir)
        
        # Sonraki breakpoint veya satır
        sonraki = sorted([b for b in self.breakpoints if b > self.mevcut_satir])
        if sonraki:
            self.mevcut_satir = sonraki[0]
            self._vurgula(self.mevcut_satir)
            self.ide.status_left.configure(text=f"  ⏸ Debugger: Satır {self.mevcut_satir}")
        else:
            self.durdur()
    
    def devam_et(self):
        """Sonraki breakpoint'e kadar çalıştır"""
        if not self.calistiriliyor:
            self.baslat()
            return
        self.adim()
    
    def durdur(self):
        """Debugger'ı durdur"""
        self.calistiriliyor = False
        if self.mevcut_satir:
            self._vurgula_kaldir(self.mevcut_satir)
        self.ide.status_left.configure(text="  ■ Hata Ayıklayıcı durduruldu")
    
    def _vurgula(self, satir):
        """Mevcut satırı vurgula"""
        self.ide.kod_alani.tag_add(self._current_tag, f"{satir}.0", f"{satir}.end")
        self.ide.kod_alani.tag_config(self._current_tag, background="#264f78")
        self.ide.kod_alani.see(f"{satir}.0")
    
    def _vurgula_kaldir(self, satir):
        """Vurguyu kaldır"""
        self.ide.kod_alani.tag_remove(self._current_tag, f"{satir}.0", f"{satir}.end")
