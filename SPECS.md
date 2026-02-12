# VisionLink - Giyilebilir Endüstriyel Asistan Sistemi
# VisionLink - Wearable Industrial Assistant System

---

## 1. Proje Genel Bakis / Project Overview

VisionLink, endüstriyel ortamlarda calisanlar icin tasarlanmis giyilebilir bir asistan sistemidir. Raspberry Pi 4 uzerinde calisan bu sistem, iki ana alt sistemden olusur:

1. **Dokumantasyon Alt Sistemi** - Calisma oturumlarinin kayit altina alinmasi
2. **Yardimci (AI Asistan) Alt Sistemi** - Eller serbest yapay zeka destegi

---

## 2. Yontem / Methodology

### 2.1 Genel Yaklasim

Sistem iki entegre alt sistemden olusur:

#### Dokumantasyon Alt Sistemi
- Calisanin bir "calisma oturumu" acmasina olanak tanir
- Oturum altinda zaman damgali fotograf, video klip ve kisa ses notlari kaydeder
- Tum kayitlar Supabase (uzak veritabani) uzerinde saklanir
- Izlenebilirlik, egitim, ise alistirma ve denetim amacli erisim saglanir
- Istenirse yerel veritabanina da gecirilebilir

#### Yardimci Alt Sistem (Yapay Zeka Asistani)
- Gozluk araciligiyla eller serbest AI etkilesimi
- QR kod okuyarak makine/parca tanimlamasi
- Ilgili teknik bilgileri getirme ve sozlu yanit verme
- Sesli komutla onceden tanimlanmis "ajan" islevlerini calistirma:
  - Bakim raporu olusturma
  - Supervizore bildirim gonderme
  - Parca talebi olusturma

---

### 2.2 Sistem Mimarisi

```
Fiziksel Girdiler
  ├── Kamera
  ├── Mikrofon
  ├── Fiziksel Butonlar (6 adet)
  └── Operator Sesi
        │
        ▼
Kenar Hesaplama Katmani
  └── Raspberry Pi 4 (Linux + Python)
        │
        ▼
Baglanti Katmani
  └── Wi-Fi (Internet / Yerel Ag)
        │
        ▼
Bulut Katmani
  ├── Supabase (PostgreSQL + Nesne Depolama)
  │     └── Oturum verileri, medya dosyalari
  └── AI Model API (Gemini / OpenAI)
        └── Akil yurutme, SSS, rehberlik, TTS
              │
              ▼
Cikislar
  ├── Sesli geri bildirim (hoparlor / kulaklik)
  └── Yapilandirilmis calisma oturumlarinin buluta yuklenmesi
```

Raspberry Pi yerel koordinator olarak gorev yapar:
- Buton olaylarini dinler
- Medya yakalar
- Oturum durumunu takip eder
- Harici servislerle haberlesir

---

### 2.3 Donanim Tasarimi

| Bilesen | Aciklama |
|---------|----------|
| **Raspberry Pi 4 Model B** | Ana islem birimi. Kamera, mikrofon, ag baglantisi ve GPIO butonlarini yonetir |
| **Kamera Modulu** | Fotograf, kisa video cekimi ve QR kod okuma |
| **Mikrofon** | Ses notlari ve asistan etkilesimleri icin kayit |
| **Hoparlor / Kemik Iletimli Kulaklik** | Asistanin sesli yanitlari |
| **6 Fiziksel Buton (GPIO)** | 3x Dokumantasyon Modu + 3x Asistan (AI) Modu |
| **Batarya / Powerbank** | Mobil guc kaynagi |
| **3D Baskili Kasa / Montaj** | Tum bilesenleri giyilebilir formda birlestirir (gozluk, kask vb.) |

---

### 2.4 Yazilim Tasarimi

#### 2.4.1 Cihaz Calisma Zamani
- Raspberry Pi OS (Linux tabanli)
- Acilista Python tabanli kontrol yazilimi otomatik baslar
- Surekli olarak:
  - GPIO butonlarini dinler
  - Oturum durumunu takip eder
  - Medya (foto, video, ses) yakalar
  - Uygun zamanda Supabase'e yukler
  - Asistanla sesli etkilesimi yonetir

#### 2.4.2 Veri Depolama ve Supabase Entegrasyonu
- **Veritabani (PostgreSQL):** Calisma oturumu meta verileri
- **Dosya Depolama (Bucket):** Goruntu, video ve ses dosyalari

Oturum Akisi:
1. Oturum acildiginda → Supabase'te yeni satir olusturulur
2. Oturum bittiginde:
   - `end_time` bilgisi islenir
   - SD karttaki tum dosyalar Supabase'e yuklenir
   - Medya dosyalari ilgili oturumla eslestirilir

---

### 2.5 Fonksiyonel Bloklar

#### 2.5.1 Dokumantasyon Modu (Butonlar 1-3)

**Buton 1 - Oturum Baslat/Durdur:**
- Ilk basisita yeni oturum olusturur → Supabase'e bildirir
- Ikinci basista oturumu kapatir → tum verileri yukler

**Buton 2 - Fotograf / Video Cekimi:**
- Tek basis: anlik fotograf + belirli araliklarla (or. 30 sn) otomatik cekim
- Cift basis: kisa video kaydi baslatir
- Dosyalar oturum kimligiyle etiketlenir → Supabase'e yuklenir

**Buton 3 - Ses Notu:**
- Basili tutma → ses kaydi baslar
- Birakma → kayit durur
- Ses dosyasi → Supabase'e yuklenir

#### 2.5.2 Yardimci Modu (Butonlar 4-6)

**Buton 4 - AI Kamera / QR Modu:**
- Kamera QR kodu okur → ilgili parca bilgilerini bulur
- Calisanin sorusu kaydedilir
- Goruntu + ses + baglam → AI API'sine gonderilir
- Yanit sesli olarak geri verilir

**Buton 5 - AI Sesli Soru-Cevap:**
- Calisan kisa soru sorar (or. "Bu hata kodu ne anlama geliyor?")
- Soru → AI modeline gonderilir → yanit sesli doner

**Buton 6 - Ajan Modu (Komut Yurutme):**
- Calisan komut verir (or. "Son oturum icin rapor olustur ve supervizore gonder")
- AI ajani onceden tanimlanmis fonksiyonlari cagirir
- Cevabi sesli olarak onaylar

---

### 2.6 Bagimli / Bagimsiz Degiskenler

**Bagimsiz Degiskenler (kontrol edilen):**
- VisionLink kullanimi vs. geleneksel yontem
- Asistan modunun aktif olup olmamasi
- Yapilandirilmis oturum kaydinin zorunlu olup olmamasi

**Bagimli Degiskenler (etkilenen):**
- Gorevin tamamlanma suresi
- Eksik veya belgelenmemis adimlarin sayisi
- Yeni calisanin gorevleri kendi basina tamamlayabilme duzeyi
- Dogru prosedural yanit alma hizi

---

### 2.7 Test ve Dogrulama

**Test Kosullari:**
1. **Temel durum:** Cihaz olmadan manuel yontemlerle gorev tamamlama
2. **VisionLink ile:** Ayni gorev cihaz kullanilarak yapilir

**Nicel Olcutler:**
- Yapay zeka yanit gecikmesi (soru → cevap suresi)
- Oturum kayit basarisi (tum medya dogru sekilde kaydedildi mi)
- Supabase uzerindeki oturum kaydinin butunlugu

**Nitel Gozlemler:**
- Asistan, acemi calisanin kafa karisikligini azaltiyor mu?
- Ajan modu eller serbest rapor uretimini sagliyor mu?
- Dokumantasyon modu bilgi kaybini azaltiyor mu?

---

### 2.8 Is Paketleri

| Paket | Icerik |
|-------|--------|
| **Donanim Entegrasyonu** | Raspberry Pi, kamera, mikrofon, butonlar, hoparlor, batarya, 3D kasa |
| **Temel Yazilim** | Python kontrol yazilimi, GPIO olay yonetimi, oturum durumu, medya yakalama |
| **Bulut Veritabani** | Supabase tablolari, dosya yukleme sistemi, oturum bitirme mantigi |
| **Yapay Zeka Etkilesimi** | Sesli SSS, kamera/QR destekli yardim, ajan modunun fonksiyonlari |
| **Test & Degerlendirme** | Endustriyel senaryo simulasyonu, zaman olcumleri, veri butunlugu |

---

### 2.9 Fizibilite

- Tum bilesenler piyasada kolayca bulunabilir
- Acik kaynakli dokumantasyona sahip
- Dusuk maliyetli
- Moduler
- Degistirilebilir (AI modeli ic sistemle degistirilebilir)
- Farkli sektorlere uyarlanabilir
- Gelecekte genisletilebilir (or. gorme engelliler icin rehberlik)

---

## Teknik Notlar / Technical Notes

- **Platform:** Raspberry Pi 4 Model B
- **OS:** Raspberry Pi OS (Linux)
- **Dil:** Python
- **Veritabani:** Supabase (PostgreSQL + Storage)
- **AI API:** Gemini / OpenAI (henuz kesinlesmedi)
- **Iletisim:** Wi-Fi
- **GPIO Butonlari:** 6 adet fiziksel buton

---

*Bu dokuman VisionLink projesinin teknik spesifikasyonlarini icerir ve gelistirme surecinde guncellenecektir.*
