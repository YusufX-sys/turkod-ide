"""TürKod backend'ini Flutter arayüzünün kullandığı WebSocket protokolüyle,
gerçek kullanıcı akışları üzerinden test eder. Kullanım (proje kökünde):
    python tests/e2e_backend.py
Gereksinim: websockets, uvicorn, fastapi (backend bağımlılıkları).
Ayarlar/geçici dosyalar sandbox klasörüne yönlendirilir; AI kapalıdır."""
import asyncio
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import websockets

PROJE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SANDBOX = tempfile.mkdtemp(prefix="turkod_e2e_")
os.makedirs(os.path.join(SANDBOX, "tmp"))
sys.stdout.reconfigure(encoding="utf-8")

# İzole backend: port dosyası yazmaz, verilen portta çalışır.
SUNUCU = (
    "import sys; sys.path.insert(0, sys.argv[1]); import uvicorn; "
    "from turkod_ide.server import app; "
    "uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[2]), log_level='warning')"
)

SONUCLAR = []  # (ad, durum, ayrinti)


def kaydet(ad, ok, ayrinti=""):
    SONUCLAR.append((ad, "GEÇTİ" if ok else "KALDI", ayrinti))
    print(f"[{'OK ' if ok else 'XX '}] {ad}  {ayrinti}", flush=True)


def bos_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Istemci:
    def __init__(self, ws):
        self.ws = ws
        self.sayac = 0
        self.bekleyen = {}
        self.olaylar = asyncio.Queue()
        self.olay_say = {}

    async def dinle(self):
        try:
            async for raw in self.ws:
                m = json.loads(raw)
                if "event" in m:
                    self.olay_say[m["event"]] = self.olay_say.get(m["event"], 0) + 1
                    await self.olaylar.put(m)
                elif m.get("id") in self.bekleyen:
                    self.bekleyen.pop(m["id"]).set_result(m)
        except websockets.ConnectionClosed:
            pass

    async def cagir(self, komut, params=None, zaman=30):
        self.sayac += 1
        fut = asyncio.get_running_loop().create_future()
        self.bekleyen[self.sayac] = fut
        await self.ws.send(json.dumps({"id": self.sayac, "command": komut,
                                       "params": params or {}}))
        return await asyncio.wait_for(fut, zaman)

    def olaylari_bosalt(self):
        while not self.olaylar.empty():
            self.olaylar.get_nowait()

    async def olay_bekle(self, ad, zaman=15, kosul=None):
        """'ad' olayını bekler; arada gelen çıktı olaylarını toplar."""
        cikti = []
        son = time.time() + zaman
        while True:
            kalan = son - time.time()
            if kalan <= 0:
                return None, "".join(cikti)
            try:
                m = await asyncio.wait_for(self.olaylar.get(), kalan)
            except asyncio.TimeoutError:
                return None, "".join(cikti)
            if m["event"] in ("calistirma_cikti", "terminal_cikti"):
                cikti.append(m["data"].get("metin", ""))
            if m["event"] == ad and (kosul is None or kosul(m["data"], "".join(cikti))):
                return m, "".join(cikti)


async def calistir_ve_bekle(c, kod, girdiler=(), zaman=20, dosya=None):
    c.olaylari_bosalt()
    r = await c.cagir("calistir", {"kod": kod, "dosya": dosya})
    if not r.get("ok"):
        return r, None, ""
    for g in girdiler:
        await asyncio.sleep(0.6)
        await c.cagir("terminal_komut", {"komut": g})
    bitti, cikti = await c.olay_bekle("calistirma_bitti", zaman)
    return r, bitti, cikti


def python_surecleri():
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Select-Object -ExpandProperty CommandLine"],
            capture_output=True, text=True, timeout=30).stdout
        return [s for s in out.splitlines() if "turkod_calisma_" in s and SANDBOX in s]
    except Exception:
        return []


async def senaryolar(c):
    # 1) Bağlantı
    r = await c.cagir("ping")
    kaydet("ping", r.get("ok") and r["result"].get("pong"))

    # 2) Sözdizimi kontrolü: kullanıcının editörde gördüğü durum
    for ad, kod, beklenen in [
        ("geçerli kod", 'yazdır("Merhaba")', True),
        ("eksik girinti", 'için i içinde aralık(3):\nyazdır(i)', False),
        ("kapanmamış parantez", 'yazdır("a"', False),
        ("boş dosya", "", True),
    ]:
        r = await c.cagir("syntax_kontrol", {"kod": kod})
        sonuc = r.get("result", {})
        gecerli = sonuc.get("basarili")
        kaydet(f"syntax: {ad}", bool(gecerli) == beklenen, json.dumps(sonuc, ensure_ascii=False)[:160])

    # 3) Çeviri (TürKod -> Python)
    r = await c.cagir("kodu_cevir", {"kod": 'için i içinde aralık(3):\n    yazdır(i)'})
    kaydet("kodu_cevir", "for i in range(3)" in json.dumps(r, ensure_ascii=False),
           str(r.get("result", r))[:160])

    # 4) Basit çalıştırma
    r, bitti, cikti = await calistir_ve_bekle(c, 'yazdır("Merhaba Dünya")')
    kaydet("çalıştır: merhaba", bitti is not None and "Merhaba Dünya" in cikti,
           f"çıkış={bitti and bitti['data']} çıktı={cikti!r}"[:200])

    # 5) Girdi alan program (Türkçe karakterli girdi)
    kod = 'isim = girdi_al("Adın ne? ")\nyaş = tamsayı(girdi_al("Yaşın? "))\nyazdır("Merhaba", isim, yaş + 1)'
    r, bitti, cikti = await calistir_ve_bekle(c, kod, girdiler=["Çağrı Öztürk", "29"])
    kaydet("çalıştır: girdi_al + Türkçe", bitti is not None and "Çağrı Öztürk 30" in cikti,
           f"çıktı={cikti!r}"[:200])

    # 6) Sık yapılan yazım: 'girdi' (doğrusu girdi_al) -> öneri var mı?
    r, bitti, cikti = await calistir_ve_bekle(c, 'x = girdi("?")')
    kaydet("hata mesajı 'girdi' için 'girdi_al' önerir mi", "'girdi_al'" in cikti,
           f"çıktı={cikti.strip()!r}"[:220])

    # 7) 'döngü doğru:' / 'döngü Doğru:' — sözdizimi kontrolü ile çalıştırma tutarlı mı?
    for yazim in ("doğru", "Doğru"):
        kod = f'i = 0\ndöngü {yazim}:\n    i += 1\n    eğer i > 3:\n        kır\nyazdır("bitti", i)'
        s = (await c.cagir("syntax_kontrol", {"kod": kod})).get("result", {})
        r, bitti, cikti = await calistir_ve_bekle(c, kod)
        kaydet(f"'döngü {yazim}:' çalışır ya da 'Doğru' önerilir", "bitti 4" in cikti or "'Doğru'" in cikti,
               f"syntax={s.get('basarili')} çıktı={cikti.strip()!r}"[:220])

    # 8) Çalışma zamanı hatası: satır numarası + Türkçe açıklama
    r, bitti, cikti = await calistir_ve_bekle(c, 'a = 1\nb = 0\nyazdır(a / b)')
    kaydet("sıfıra bölme hatası anlaşılır", bitti is not None and "3" in cikti and bitti["data"]["cikis_kodu"] != 0,
           f"çıktı={cikti.strip()!r}"[:220])

    # 9) Hızlı çıktı + Durdur (sonsuz döngü)
    c.olaylari_bosalt()
    await c.cagir("calistir", {"kod": 'i = 0\ndöngü Doğru:\n    i += 1\n    yazdır("satır", i)'})
    await asyncio.sleep(3)
    bayt = 0
    while not c.olaylar.empty():
        m = c.olaylar.get_nowait()
        bayt += len(m["data"].get("metin", "")) if "data" in m else 0
    t1 = time.time()
    r = await c.cagir("calistir_durdur")
    bitti, _ = await c.olay_bekle("calistirma_bitti", 10)
    durma = time.time() - t1
    await asyncio.sleep(1)
    kalan = python_surecleri()
    kaydet("sonsuz döngü: durdur", bitti is not None and durma < 3 and not kalan,
           f"3 sn'de ~{bayt/1e6:.1f} MB çıktı; durma {durma:.2f} sn; kalan süreç={len(kalan)}")

    # 10) Durdurulmuş programdan sonra yeni çalıştırma temiz mi?
    r, bitti, cikti = await calistir_ve_bekle(c, 'yazdır("temiz")')
    kaydet("durdurmadan sonra yeni çalıştırma", "temiz" in cikti and "satır" not in cikti,
           f"çıktı={cikti!r}"[:160])

    # 11) Çalışırken ikinci kez Çalıştır (eski program kapanmalı)
    c.olaylari_bosalt()
    await c.cagir("calistir", {"kod": 'içe_aktar time\ntime.sleep(30)'})
    await asyncio.sleep(1)
    r, bitti, cikti = await calistir_ve_bekle(c, 'yazdır("ikinci")')
    await asyncio.sleep(1)
    kaydet("çalışırken yeniden çalıştır", "ikinci" in cikti and len(python_surecleri()) == 0,
           f"kalan süreç={len(python_surecleri())}")

    # 12) Dosya kaydet / oku (Türkçe adlı, boşluklu klasör) + CRLF
    klasor = os.path.join(SANDBOX, "Projelerim ğüş")
    os.makedirs(klasor)
    yol = os.path.join(klasor, "ödev 1.trpy")
    icerik = 'yazdır("çalışıyor")\r\nyazdır("ikinci satır")\r\n'
    r = await c.cagir("dosya_kaydet", {"yol": yol, "icerik": icerik})
    r2 = await c.cagir("dosya_oku", {"yol": yol})
    disk = open(yol, "rb").read()
    kaydet("dosya kaydet/oku", r.get("ok") and r2.get("ok") and b"\r\r\n" not in disk
           and "ikinci satır" in r2["result"].get("icerik", ""), f"diskte {len(disk)} bayt")

    # 13) Kayıtlı dosyayı çalıştır: çalışma dizini dosyanın klasörü mü, yerel modül içe aktarma
    with open(os.path.join(klasor, "yardimci.trpy"), "w", encoding="utf-8") as f:
        f.write('fonksiyon selamla(ad):\n    döndür "Selam " + ad\n')
    kod = 'içe_aktar yardimci\niçe_aktar os\nyazdır(yardimci.selamla("Ali"))\nyazdır(os.getcwd())\n' \
          'dosya = aç("cikti.txt", "w", encoding="utf-8")\ndosya.write("ok")\ndosya.close()'
    r, bitti, cikti = await calistir_ve_bekle(c, kod, dosya=yol)
    kaydet("kayıtlı dosya: yerel modül + çalışma dizini",
           "Selam Ali" in cikti and os.path.exists(os.path.join(klasor, "cikti.txt")),
           f"çıktı={cikti.strip()!r}"[:220])

    # 14) Eşzamanlı kayıtlar (otomatik kayıt + Ctrl+S)
    yol2 = os.path.join(klasor, "yarış.trpy")
    sonuc = await asyncio.gather(*[c.cagir("dosya_kaydet", {"yol": yol2, "icerik": f"# sürüm {i}\n" * 2000})
                                   for i in range(15)])
    satirlar = set(open(yol2, encoding="utf-8").read().splitlines())
    kaydet("eşzamanlı kayıt tutarlı", all(s.get("ok") for s in sonuc) and len(satirlar) == 1,
           f"farklı satır sayısı={len(satirlar)}")

    # 15) Terminal (program çalışmıyorken) kabuk komutu
    c.olaylari_bosalt()
    r = await c.cagir("terminal_komut", {"komut": "echo merhaba-terminal"})
    m, cikti = await c.olay_bekle("terminal_cikti", 10, kosul=lambda d, t: "merhaba-terminal" in t)
    kaydet("terminal: kabuk komutu", m is not None, f"{cikti.strip()!r}"[:120])

    # 16) Düzelt (AI kapalı, çalıştırma izni yok): yazım hatası düzeltilir, içe aktarma bozulmaz
    kod = 'içe_aktar math\nden os içe_aktar listdir\nyazdr(math.pi, listdir("."))'
    r = await c.cagir("duzelt", {"kod": kod, "calistirma_izni": False}, zaman=120)
    sonuc = r.get("result", {})
    yeni = sonuc.get("kod") or sonuc.get("duzeltilmis_kod") or ""
    kaydet("düzelt: yazım hatası + içe aktarma korunur",
           "yazdır(" in yeni and "math" in yeni and "listdir" in yeni,
           f"{yeni!r}"[:200])

    # 17) Tamamlama önerisi
    r = await c.cagir("tamamlama_onerileri", {"kelime": "yazd", "kod": "yazd"})
    kaydet("tamamlama 'yazd' -> yazdır", "yazdır" in json.dumps(r, ensure_ascii=False),
           str(r.get("result"))[:140])

    # 18) Hata ayıklayıcı: breakpoint'te dur, değişkeni oku, devam
    c.olaylari_bosalt()
    kod = 'toplam = 0\niçin i içinde aralık(5):\n    toplam += i\nyazdır("toplam", toplam)'
    r = await c.cagir("debug_baslat", {"kod": kod, "breakpointler": [3]})
    durdu, _ = await c.olay_bekle("debug_durdu", 15)
    if durdu is None:
        # olay adı farklı olabilir: gelen olayları listele
        kaydet("debug: breakpoint", False, f"olaylar={c.olay_say}")
    else:
        d = durdu["data"]
        kaydet("debug: breakpoint'te durdu", d.get("satir") == 3, json.dumps(d, ensure_ascii=False)[:200])
        r = await c.cagir("debug_degerlendir", {"ifade": "toplam + 100"})
        kaydet("debug: ifade değerlendir", "100" in json.dumps(r, ensure_ascii=False), str(r.get("result"))[:120])
        await c.cagir("debug_breakpoint_ayarla", {"satirlar": []})
        await c.cagir("debug_devam")
        bitti, cikti = await c.olay_bekle("calistirma_bitti", 15)
        kaydet("debug: devam -> bitti", bitti is not None and "toplam 10" in cikti, f"{cikti.strip()!r}"[:120])

    # 19) Büyük dosya performansı (editör her tuşta syntax_kontrol çağırır)
    buyuk = "\n".join(f'değer_{i} = {i} * 2\neğer değer_{i} > 10:\n    yazdır("büyük", değer_{i})'
                      for i in range(1500))
    t = time.time()
    await c.cagir("syntax_kontrol", {"kod": buyuk}, zaman=120)
    sure = time.time() - t
    kaydet("4500 satır syntax_kontrol < 2 sn", sure < 2, f"{sure:.2f} sn")

    # 20) Hatalı istekler sunucuyu düşürmemeli
    await c.ws.send("{bozuk json")
    await c.ws.send("[1,2,3]")
    r = await c.cagir("olmayan_komut")
    r2 = await c.cagir("dosya_oku", {})
    r3 = await c.cagir("ping")
    kaydet("hatalı isteklerden sonra sunucu ayakta", r3.get("ok") and not r.get("ok") and not r2.get("ok"),
           f"bilinmeyen={r.get('error')!r} eksik={r2.get('error')!r}")


async def ana():
    port = bos_port()
    token = secrets.token_urlsafe(16)
    env = dict(os.environ, TURKOD_TOKEN=token, USERPROFILE=SANDBOX, HOME=SANDBOX,
               TEMP=os.path.join(SANDBOX, "tmp"), TMP=os.path.join(SANDBOX, "tmp"),
               PYTHONIOENCODING="utf-8")
    log = open(os.path.join(SANDBOX, "backend.log"), "w", encoding="utf-8")
    sunucu = subprocess.Popen([sys.executable, "-c", SUNUCU, PROJE, str(port)],
                              env=env, stdout=log, stderr=subprocess.STDOUT, cwd=SANDBOX)
    try:
        for _ in range(100):
            try:
                ws = await websockets.connect(f"ws://127.0.0.1:{port}/ws?token={token}",
                                              max_size=None, open_timeout=2)
                break
            except Exception:
                await asyncio.sleep(0.3)
        else:
            print("Sunucu başlamadı"); return
        c = Istemci(ws)
        dinleyici = asyncio.create_task(c.dinle())
        try:
            await senaryolar(c)
        except Exception as e:
            import traceback; traceback.print_exc()
            kaydet("senaryo çöktü", False, repr(e))
        await ws.close()
        dinleyici.cancel()
    finally:
        sunucu.terminate()
        try:
            sunucu.wait(5)
        except subprocess.TimeoutExpired:
            sunucu.kill()
    gecen = sum(1 for s in SONUCLAR if s[1] == "GEÇTİ")
    print(f"\n=== {gecen}/{len(SONUCLAR)} geçti")
    return all(s[1] == "GEÇTİ" for s in SONUCLAR)


if __name__ == "__main__":
    basarili = asyncio.run(ana())
    shutil.rmtree(SANDBOX, ignore_errors=True)
    sys.exit(0 if basarili else 1)
