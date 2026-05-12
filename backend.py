from datetime import datetime
from typing import Optional


# ─── Sabitler ────────────────────────────────────────────────────────────────
BAKİYE_EŞİĞİ        = 75_000.0   # ₺
GECİKME_YÜKSEK_EŞİK = 30        # gün  → YÜKSEK RİSK sınırı
GECİKME_ORTA_EŞİK   = 20        # gün  → ORTA RİSK sınırı
TAHSİLAT_EŞİĞİ      = 70.0      # %


# ─── Risk Seviyeleri ─────────────────────────────────────────────────────────
class RiskSeviyesi:
    YÜKSEK = "YÜKSEK RİSK"
    ORTA   = "ORTA RİSK"
    NORMAL = "NORMAL"


# ─── Veri Modeli ─────────────────────────────────────────────────────────────
class Musteri:
    """Tek bir müşteriyi temsil eden saf veri sınıfı."""

    def __init__(
        self,
        musteri_id: str,
        ad: str,
        bakiye: float,
        gecikme: int,
        tahsilat: float,
        sektor: str,
        tarih: Optional[str] = None,
    ):
        self.id       = musteri_id
        self.ad       = ad
        self.bakiye   = bakiye
        self.gecikme  = gecikme          # gün cinsinden
        self.tahsilat = tahsilat         # 0-100 yüzde
        self.sektor   = sektor
        self.tarih    = tarih or datetime.now().strftime("%Y-%m-%d")

    def to_dict(self) -> dict:
        return {
            "id":       self.id,
            "ad":       self.ad,
            "bakiye":   self.bakiye,
            "gecikme":  self.gecikme,
            "tahsilat": self.tahsilat,
            "sektor":   self.sektor,
            "tarih":    self.tarih,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Musteri":
        return cls(
            musteri_id=d["id"],
            ad=d["ad"],
            bakiye=float(d["bakiye"]),
            gecikme=int(d["gecikme"]),
            tahsilat=float(d["tahsilat"]),
            sektor=d.get("sektor", "Belirtilmedi"),
            tarih=d.get("tarih"),
        )


# ─── Risk Motoru ─────────────────────────────────────────────────────────────
class RiskMotoru:
    """
    İş kurallarını uygulayarak risk skoru ve seviyesi hesaplar.

    Kurallar (tahta):
    ┌─────────────────────────────────────────────────────────────────┐
    │ bakiye < 75 000 AND gecikme > 30  →  YÜKSEK RİSK  (Kırmızı)   │
    │ gecikme > 20                      →  ORTA RİSK    (Sarı)       │
    │ Diğer                             →  NORMAL        (Yeşil)     │
    └─────────────────────────────────────────────────────────────────┘
    Skor 0-100 arasında; yüksek skor = düşük risk.
    """

    @staticmethod
    def hesapla(musteri: Musteri) -> dict:
        """
        Returns:
            {
                "skor"     : int,          # 0-100
                "seviye"   : str,          # RiskSeviyesi sabiti
                "aciklama" : list[str],    # uyarı mesajları
            }
        """
        skor = 100
        aciklama: list[str] = []

        # --- Bakiye kontrolü ---
        if musteri.bakiye < BAKİYE_EŞİĞİ:
            skor -= 30
            aciklama.append(
                f"⚠ Bakiye kritik eşiğin altında "
                f"({musteri.bakiye:,.0f} ₺ < {BAKİYE_EŞİĞİ:,.0f} ₺)"
            )

        # --- Gecikme kontrolü ---
        if musteri.gecikme > GECİKME_YÜKSEK_EŞİK:
            skor -= 40
            aciklama.append(
                f"⚠ Gecikme süresi kritik "
                f"({musteri.gecikme} gün > {GECİKME_YÜKSEK_EŞİK} gün)"
            )
        elif musteri.gecikme > GECİKME_ORTA_EŞİK:
            skor -= 20
            aciklama.append(
                f"⚠ Gecikme süresi yükseliyor "
                f"({musteri.gecikme} gün > {GECİKME_ORTA_EŞİK} gün)"
            )

        # --- Tahsilat oranı kontrolü ---
        if musteri.tahsilat < TAHSİLAT_EŞİĞİ:
            skor -= 20
            aciklama.append(
                f"⚠ Tahsilat oranı düşük "
                f"(%{musteri.tahsilat:.1f} < %{TAHSİLAT_EŞİĞİ:.0f})"
            )

        skor = max(0, skor)

        # --- Seviye belirleme ---
        if musteri.bakiye < BAKİYE_EŞİĞİ and musteri.gecikme > GECİKME_YÜKSEK_EŞİK:
            seviye = RiskSeviyesi.YÜKSEK
        elif musteri.gecikme > GECİKME_ORTA_EŞİK:
            seviye = RiskSeviyesi.ORTA
        else:
            seviye = RiskSeviyesi.NORMAL

        return {"skor": skor, "seviye": seviye, "aciklama": aciklama}


# ─── Müşteri Deposu (Repository) ─────────────────────────────────────────────
class MusteriDeposu:
    """
    In-memory müşteri veri deposu.
    CRUD operasyonlarını sağlar; backend/frontend ayrımının kalbi burasıdır.
    İleride bu sınıf bir dosya/DB katmanıyla değiştirilebilir.
    """

    def __init__(self):
        self._musteriler: list[Musteri] = []
        self._id_sayac = 1

    # ── Oluştur ──────────────────────────────────────────────────────────────
    def ekle(
        self,
        ad: str,
        bakiye: float,
        gecikme: int,
        tahsilat: float,
        sektor: str = "Belirtilmedi",
    ) -> Musteri:
        """Yeni müşteri oluşturur ve depoya ekler; oluşturulan nesneyi döndürür."""
        if not ad.strip():
            raise ValueError("Müşteri adı boş bırakılamaz.")
        if not (0 <= tahsilat <= 100):
            raise ValueError("Tahsilat oranı 0-100 arasında olmalıdır.")
        if bakiye < 0:
            raise ValueError("Bakiye negatif olamaz.")
        if gecikme < 0:
            raise ValueError("Gecikme süresi negatif olamaz.")

        musteri_id = f"M{self._id_sayac:03d}"
        self._id_sayac += 1

        m = Musteri(
            musteri_id=musteri_id,
            ad=ad.strip(),
            bakiye=bakiye,
            gecikme=gecikme,
            tahsilat=tahsilat,
            sektor=sektor.strip() or "Belirtilmedi",
        )
        self._musteriler.append(m)
        return m

    # ── Oku ──────────────────────────────────────────────────────────────────
    def hepsini_getir(self) -> list[Musteri]:
        """Tüm müşterilerin kopyasını döndürür."""
        return list(self._musteriler)

    def id_ile_getir(self, musteri_id: str) -> Optional[Musteri]:
        """ID'ye göre müşteri arar; bulamazsa None döndürür."""
        return next((m for m in self._musteriler if m.id == musteri_id), None)

    def ara(self, sorgu: str) -> list[Musteri]:
        """Ad veya sektörde büyük/küçük harf duyarsız arama yapar."""
        sorgu = sorgu.lower()
        return [
            m for m in self._musteriler
            if sorgu in m.ad.lower() or sorgu in m.sektor.lower()
        ]

    # ── Güncelle ─────────────────────────────────────────────────────────────
    def guncelle(self, musteri_id: str, **kwargs) -> Musteri:
        """
        Belirtilen alanları günceller.
        Geçerli alanlar: ad, bakiye, gecikme, tahsilat, sektor
        """
        m = self.id_ile_getir(musteri_id)
        if m is None:
            raise KeyError(f"Müşteri bulunamadı: {musteri_id}")

        if "ad" in kwargs and not kwargs["ad"].strip():
            raise ValueError("Müşteri adı boş bırakılamaz.")
        if "tahsilat" in kwargs and not (0 <= kwargs["tahsilat"] <= 100):
            raise ValueError("Tahsilat oranı 0-100 arasında olmalıdır.")

        for alan, deger in kwargs.items():
            if hasattr(m, alan):
                setattr(m, alan, deger)
        return m

    # ── Sil ──────────────────────────────────────────────────────────────────
    def sil(self, musteri_id: str) -> Musteri:
        """
        ID'ye göre müşteriyi depodan kaldırır.
        Başarılı olursa silinen Musteri nesnesini döndürür.
        Bulunamazsa KeyError fırlatır.
        """
        for i, m in enumerate(self._musteriler):
            if m.id == musteri_id:
                return self._musteriler.pop(i)
        raise KeyError(f"Silinecek müşteri bulunamadı: {musteri_id}")

    # ── Özet İstatistik ──────────────────────────────────────────────────────
    def ozet_istatistik(self) -> dict:
        """
        Dashboard için toplu istatistik döndürür:
          toplam, yuksek, orta, normal, ort_bakiye
        """
        liste = self._musteriler
        toplam = len(liste)

        yuksek   = 0
        orta     = 0
        normal   = 0
        bak_top  = 0.0

        for m in liste:
            sonuc = RiskMotoru.hesapla(m)
            if sonuc["seviye"] == RiskSeviyesi.YÜKSEK:
                yuksek += 1
            elif sonuc["seviye"] == RiskSeviyesi.ORTA:
                orta += 1
            else:
                normal += 1
            bak_top += m.bakiye

        return {
            "toplam":     toplam,
            "yuksek":     yuksek,
            "orta":       orta,
            "normal":     normal,
            "ort_bakiye": bak_top / max(toplam, 1),
        }


# ─── Servis Katmanı ───────────────────────────────────────────────────────────
class FinansalRiskServisi:
    """
    Frontend'in doğrudan bağlandığı tek giriş noktası.
    Depo + motor kombinasyonunu koordine eder.
    """

    def __init__(self):
        self.depo  = MusteriDeposu()
        self.motor = RiskMotoru()

    # -- Yönlendirici metodlar (frontend çağırır) -----------------------------

    def musteri_ekle(self, ad, bakiye, gecikme, tahsilat, sektor="") -> dict:
        """Müşteri ekler; {musteri, risk} sözlüğü döndürür."""
        m    = self.depo.ekle(ad, bakiye, int(gecikme), tahsilat, sektor)
        risk = self.motor.hesapla(m)
        return {"musteri": m, "risk": risk}

    def musteri_sil(self, musteri_id: str) -> Musteri:
        """Müşteriyi siler; silinen nesneyi döndürür."""
        return self.depo.sil(musteri_id)

    def musteri_listesi(self, sorgu: str = "") -> list[dict]:
        """
        Opsiyonel arama sorgusuyla müşteri listesi döndürür.
        Her öğe {musteri, risk} sözlüğüdür.
        """
        liste = self.depo.ara(sorgu) if sorgu else self.depo.hepsini_getir()
        return [
            {"musteri": m, "risk": self.motor.hesapla(m)}
            for m in liste
        ]

    def musteri_risk_detay(self, musteri_id: str) -> dict:
        """Tek müşteri için tam risk raporu döndürür."""
        m = self.depo.id_ile_getir(musteri_id)
        if m is None:
            raise KeyError(f"Müşteri bulunamadı: {musteri_id}")
        return {"musteri": m, "risk": self.motor.hesapla(m)}

    def dashboard_verisi(self) -> dict:
        """Dashboard için hazır istatistik + liste döndürür."""
        return {
            "istatistik": self.depo.ozet_istatistik(),
            "musteriler": self.musteri_listesi(),
        }

    def risk_onizle(self, bakiye: float, gecikme: int, tahsilat: float) -> dict:
        """
        Geçici Musteri nesnesi oluşturarak canlı önizleme için risk hesaplar.
        Depoya kayıt yapmaz.
        """
        gecici = Musteri(
            musteri_id="ONIZLEME",
            ad="",
            bakiye=bakiye,
            gecikme=gecikme,
            tahsilat=tahsilat,
            sektor="",
        )
        return self.motor.hesapla(gecici)
