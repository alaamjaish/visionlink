# VisionLink — Giyilebilir Endüstriyel Asistan Sistemi
# VisionLink — Wearable Industrial Assistant System

---

## 1. Proje Genel Bakış / Project Overview

VisionLink, endüstriyel ortamlarda çalışanlar için tasarlanmış giyilebilir bir asistan sistemidir. Raspberry Pi 4 üzerinde çalışan bu sistem iki ana alt sistemden oluşur:

1. **Dokümantasyon Alt Sistemi** — Çalışma oturumlarının kayıt altına alınması
2. **Yardımcı (Yapay Zekâ Asistanı) Alt Sistemi** — Eller serbest yapay zekâ desteği

---

## 2. Yöntem / Methodology

### 2.1 Genel Yaklaşım

Sistem birbiriyle entegre çalışan iki alt sistemden oluşur:

#### Dokümantasyon Alt Sistemi
- Çalışanın bir "çalışma oturumu" açmasına olanak tanır.
- Oturum süresince zaman damgalı fotoğraf, video klip ve kısa ses notlarını kaydeder.
- Tüm kayıtlar Supabase (uzak veritabanı) üzerinde saklanır.
- İzlenebilirlik, eğitim, işe alıştırma ve denetim amacıyla bu kayıtlara erişim sağlanır.
- Gerektiğinde yerel bir veritabanına da aktarılabilir.

#### Yardımcı Alt Sistem (Yapay Zekâ Asistanı)
- Gözlük aracılığıyla eller serbest yapay zekâ etkileşimi sunar.
- QR kod okuyarak makine veya parça tanımlaması yapar.
- İlgili teknik bilgileri getirir ve sözlü olarak yanıt verir.
- Sesli komutla önceden tanımlanmış "ajan" işlevlerini çalıştırır:
  - Bakım raporu oluşturma
  - Süpervizöre bildirim gönderme
  - Parça talebi oluşturma

---

### 2.2 Sistem Mimarisi

```
Fiziksel Girdiler
  ├── Kamera
  ├── Mikrofon
  ├── Fiziksel Butonlar (6 adet)
  └── Operatör Sesi
        │
        ▼
Kenar Hesaplama Katmanı
  └── Raspberry Pi 4 (Linux + Python)
        │
        ▼
Bağlantı Katmanı
  └── Wi-Fi (İnternet / Yerel Ağ)
        │
        ▼
Bulut Katmanı
  ├── Supabase (PostgreSQL + Nesne Depolama)
  │     └── Oturum verileri, medya dosyaları
  └── Yapay Zekâ Model API'si (Gemini / OpenAI)
        └── Akıl yürütme, SSS, rehberlik, TTS
              │
              ▼
Çıkışlar
  ├── Sesli geri bildirim (hoparlör / kulaklık)
  └── Yapılandırılmış çalışma oturumlarının buluta yüklenmesi
```

Raspberry Pi yerel koordinatör olarak görev yapar:
- Buton olaylarını dinler.
- Medyayı yakalar.
- Oturum durumunu takip eder.
- Harici servislerle haberleşir.

---

### 2.3 Donanım Tasarımı

| Bileşen | Açıklama |
|---------|----------|
| **Raspberry Pi 4 Model B** | Ana işlem birimi. Kamerayı, mikrofonu, ağ bağlantısını ve GPIO butonlarını yönetir. |
| **Kamera Modülü** | Fotoğraf çekimi, kısa video kaydı ve QR kod okuma. |
| **Mikrofon** | Ses notları ve asistan etkileşimleri için kayıt. |
| **Hoparlör / Kemik İletimli Kulaklık** | Asistanın sesli yanıtlarını iletir. |
| **6 Fiziksel Buton (GPIO)** | 3 adet Dokümantasyon Modu + 3 adet Asistan (Yapay Zekâ) Modu. |
| **Batarya / Powerbank** | Mobil güç kaynağı. |
| **3D Baskılı Kasa / Montaj** | Tüm bileşenleri giyilebilir bir formda (gözlük, kask vb.) birleştirir. |

---

### 2.4 Yazılım Tasarımı

#### 2.4.1 Cihaz Çalışma Zamanı
- Raspberry Pi OS (Linux tabanlı).
- Açılışta Python tabanlı kontrol yazılımı otomatik olarak başlar.
- Sürekli olarak:
  - GPIO butonlarını dinler.
  - Oturum durumunu takip eder.
  - Medyayı (fotoğraf, video, ses) yakalar.
  - Uygun zamanda Supabase'e yükler.
  - Asistan ile olan sesli etkileşimi yönetir.

#### 2.4.2 Veri Depolama ve Supabase Entegrasyonu
- **Veritabanı (PostgreSQL):** Çalışma oturumu üst verileri (metadata).
- **Dosya Depolama (Bucket):** Görüntü, video ve ses dosyaları.

Oturum Akışı:
1. Oturum açıldığında → Supabase'te yeni bir satır oluşturulur.
2. Oturum bittiğinde:
   - `end_time` bilgisi işlenir.
   - SD karttaki tüm dosyalar Supabase'e yüklenir.
   - Medya dosyaları ilgili oturum ile eşleştirilir.

---

### 2.5 Fonksiyonel Bloklar

#### 2.5.1 Dokümantasyon Modu (Butonlar 1-3)

**Buton 1 — Oturum Başlat / Durdur:**
- İlk basışta yeni oturum oluşturur → Supabase'e bildirir.
- İkinci basışta oturumu kapatır → tüm verileri yükler.

**Buton 2 — Fotoğraf / Video Çekimi:**
- Tek basış: anlık fotoğraf çeker ve ayrıca belirli aralıklarla (ör. 30 saniye) otomatik çekim yapar.
- Çift basış: kısa video kaydı başlatır.
- Dosyalar oturum kimliğiyle etiketlenir → Supabase'e yüklenir.

**Buton 3 — Ses Notu:**
- Basılı tutma → ses kaydı başlar.
- Bırakma → kayıt durur.
- Ses dosyası → Supabase'e yüklenir.

#### 2.5.2 Yardımcı Modu (Butonlar 4-6)

**Buton 4 — Yapay Zekâ Kamera / QR Modu:**
- Kamera QR kodu okur → ilgili parça bilgilerini getirir.
- Çalışanın sorusu kaydedilir.
- Görüntü + ses + bağlam → yapay zekâ API'sine gönderilir.
- Yanıt sesli olarak geri verilir.

**Buton 5 — Yapay Zekâ Sesli Soru-Cevap:**
- Çalışan kısa bir soru sorar (ör. "Bu hata kodu ne anlama geliyor?").
- Soru → yapay zekâ modeline gönderilir → yanıt sesli olarak döner.

**Buton 6 — Ajan Modu (Komut Yürütme):**
- Çalışan bir komut verir (ör. "Son oturum için rapor oluştur ve süpervizöre gönder").
- Yapay zekâ ajanı önceden tanımlanmış fonksiyonları çağırır.
- Yapılan işlemi sesli olarak onaylar.

---

### 2.6 Bağımlı / Bağımsız Değişkenler

**Bağımsız Değişkenler (kontrol edilen):**
- VisionLink kullanımı ile geleneksel yöntemin karşılaştırılması.
- Asistan modunun aktif olup olmaması.
- Yapılandırılmış oturum kaydının zorunlu olup olmaması.

**Bağımlı Değişkenler (etkilenen):**
- Görevin tamamlanma süresi.
- Eksik ya da belgelenmemiş adımların sayısı.
- Yeni çalışanın görevleri kendi başına tamamlayabilme düzeyi.
- Doğru prosedürel yanıtın elde edilme hızı.

---

### 2.7 Test ve Doğrulama

**Test Koşulları:**
1. **Temel durum:** Cihaz olmadan, manuel yöntemlerle görev tamamlama.
2. **VisionLink ile:** Aynı görev cihaz kullanılarak yapılır.

**Nicel Ölçütler:**
- Yapay zekâ yanıt gecikmesi (soru → cevap süresi).
- Oturum kayıt başarısı (tüm medya doğru biçimde kaydedildi mi).
- Supabase üzerindeki oturum kaydının bütünlüğü.

**Nitel Gözlemler:**
- Asistan, acemi çalışanın kafa karışıklığını azaltıyor mu?
- Ajan modu eller serbest rapor üretimini sağlıyor mu?
- Dokümantasyon modu bilgi kaybını azaltıyor mu?

---

### 2.8 İş Paketleri

| Paket | İçerik |
|-------|--------|
| **Donanım Entegrasyonu** | Raspberry Pi, kamera, mikrofon, butonlar, hoparlör, batarya, 3D kasa. |
| **Temel Yazılım** | Python kontrol yazılımı, GPIO olay yönetimi, oturum durumu, medya yakalama. |
| **Bulut Veritabanı** | Supabase tabloları, dosya yükleme sistemi, oturum bitirme mantığı. |
| **Yapay Zekâ Etkileşimi** | Sesli SSS, kamera/QR destekli yardım, ajan modunun fonksiyonları. |
| **Test ve Değerlendirme** | Endüstriyel senaryo simülasyonu, zaman ölçümleri, veri bütünlüğü. |

---

### 2.9 Fizibilite

- Tüm bileşenler piyasada kolayca bulunabilir.
- Açık kaynaklı dokümantasyona sahiptir.
- Düşük maliyetlidir.
- Modüler yapıdadır.
- Değiştirilebilir (yapay zekâ modeli yerel sistemle değiştirilebilir).
- Farklı sektörlere uyarlanabilir.
- Gelecekte genişletilebilir (ör. görme engelliler için rehberlik).

---

## Teknik Notlar / Technical Notes

- **Platform:** Raspberry Pi 4 Model B
- **İşletim Sistemi:** Raspberry Pi OS (Linux)
- **Dil:** Python
- **Veritabanı:** Supabase (PostgreSQL + Storage)
- **Yapay Zekâ API'si:** Gemini / OpenAI (henüz kesinleşmedi)
- **İletişim:** Wi-Fi
- **GPIO Butonları:** 6 adet fiziksel buton

---

*Bu doküman VisionLink projesinin teknik spesifikasyonlarını içerir ve geliştirme süreci boyunca güncellenecektir.*
