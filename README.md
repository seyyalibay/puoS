# puoS

İş piyasası verisinden **beceri trend zekâsı**. puoS iki bağımsız sistemden oluşur:

1. **SkillPulse** — iş ilanlarından beceri trend analizi (Streamlit dashboard).
2. **Otonom Rakip Zekâsı Motoru** (`rakip_zekasi.py`) — GitHub + iş ilanı + haber
   sinyallerini birleştirip rakip hareketlerinde anomali tespit eden otonom motor.

---

## 1) SkillPulse — İş İlanı Beceri Trend Analizi

İş ilanlarını toplar, metinlerinden becerileri çıkarır, zaman içinde yükselen/düşen
trendleri hesaplar ve interaktif bir dashboard'da sunar.

- **5 ülke:** UK, ABD, Kanada, Hollanda, Türkiye
- **6 API kaynağı:** Adzuna (UK / CA / NL / US) · Jooble TR · Careerjet TR
- **~4000 gerçek iş ilanı** (diske cache'lenir — altın kural: API'ye sadece bir kez git)
- **C modülü ile 755 beceri sayımı** — frekans sayımı `c_module/skill_counter.c`
  içinde, Python'a `ctypes` köprüsüyle bağlanır (saf-Python fallback'i var)
- **Tier sistemi** — ilanları kalibreye göre sınıflar: maaş + unvan + şirket puanlama
  (Tier 1/2/3), her tier için ayrı skill analizi
- **Kariyer Eşleştirici** — kullanıcının becerilerini girince en uygun rolleri bulur
- **Gemini kariyer tavsiyesi** — her trend/rol için kısa içgörü üretir
- **Streamlit arayüzü, 4 sekme:** Trendler · Karşılaştırma · Kariyer Eşleştirici · Öneriler

### Mimari (kaynak-bağımsız)

Her veri kaynağı ayrı bir `fetchers/*.py` modülüdür ve **hepsi aynı değişmez şemayı**
döndürür. İşleme/analiz/görselleştirme katmanları kaynağı tanımaz.

```
fetchers/{adzuna,jooble,careerjet}.py ─► list[dict] (şema)
        ─► processors (skill_extractor + C köprüsü)
        ─► analyzers (trend + tier)
        ─► app.py (Streamlit) / visualizers (PNG)
```

Değişmez veri şeması:
```python
{"title": str, "company": str, "description": str,
 "location": str, "date_posted": str, "source": str}
```

```
skillpulse/
  fetchers/      # adzuna.py, jooble.py, careerjet.py, cache.py, __init__.py (şema+validasyon)
  processors/    # skill_extractor.py, skill_counter_bridge.py (ctypes köprüsü)
  analyzers/     # trend_analyzer.py (pandas), company_tiers.py (Tier 1/2/3)
  advisors/      # gemini_insights.py (gemini-flash-latest, insight cache'li)
  c_module/      # skill_counter.c (+ derlenmiş .so)
  visualizers/   # dashboard.py (matplotlib statik PNG)
  data/          # JSON cache + çıktılar (git'e gönderilmez)
  skills.py      # bilingual (EN+TR) beceri sözlüğü — 755 beceri
  main.py        # CLI orkestratör (statik PNG çıktısı)
  app.py         # Streamlit dashboard (4 sekme)
  rakip_zekasi.py # Otonom Rakip Zekâsı Motoru (aşağıda)
```

Ayrıntılı kurallar ve C/ctypes pattern'ı için **[SKILL.md](SKILL.md)**.

---

## 2) Otonom Rakip Zekâsı Motoru (`rakip_zekasi.py`)

Bir rakip şirket hakkında üç farklı sinyali toplayıp birleştiren ve anormal
hareketleri otomatik tespit eden otonom motor.

- **GitHub commit takibi** — delta fetch (yalnızca son çekimden bu yana yeni commit'ler)
- **Adzuna iş ilanı anomali tespiti** — açılan pozisyonlardaki ani değişimler
- **Haber sentiment analizi** — VADER ile şirket haberlerinin duygu skoru
- **Çift kurallı anomali tespiti** — Z-score + Moving Average (MA) surge
- **Gemini ile otomatik rapor üretimi** — tespitleri okunabilir rapora dönüştürür
- **Günlük otonom çalışma** — periyodik olarak kendi başına koşar ve rapor biriktirir

---

## Kurulum

```bash
pip install -r requirements.txt
cp .env.example .env
# .env dosyasını açıp API key'leri gir
```

> Beceri sayımını C modülü yapar. İlk kez derlemek için:
> ```bash
> cd c_module && cc -O2 -shared -fPIC -o skill_counter.so skill_counter.c && cd ..
> ```
> Derlemezsen sistem yine çalışır, saf-Python fallback'e düşer.

### Gerekli API key'leri

API key'leri **`.env`** dosyasından `python-dotenv` ile okunur — kodda hardcode key
yoktur ve `.env` git'e gönderilmez (`.gitignore`'da).

| Değişken | Nereden | Ne için |
|---|---|---|
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | https://developer.adzuna.com/ | UK/CA/NL/US ilanları + Rakip Zekâsı |
| `JOOBLE_API_KEY_TR` | https://tr.jooble.org/api/about | TR ilanları |
| `CAREERJET_API_KEY` | https://www.careerjet.com.tr/partners/ | TR ek kaynak (tam description) |
| `GEMINI_API_KEY` *(veya `GROQ_API_KEY`)* | https://aistudio.google.com/apikey · https://console.groq.com/keys | Kariyer tavsiyesi / rapor üretimi |

> Bir key tanımlı değilse ilgili kaynak/özellik devre dışı kalır, uygulama yine çalışır.
> Gemini key'i tükenirse istek otomatik olarak `GROQ_API_KEY`'e (yedek) düşer.

---

## Çalıştırma

### SkillPulse dashboard (önerilen)
```bash
streamlit run app.py
```
Tarayıcıda 4 sekmeyle açılır: **Trendler**, **Karşılaştırma**, **Kariyer Eşleştirici**,
**Öneriler**. Veri diske cache'lendiği için sonraki açılışlar API'ye gitmez; ülke,
sorgu ve gösterilecek beceri sayısı kenar çubuğundan ayarlanır.

### Rakip Zekâsı Motoru
```bash
streamlit run rakip_zekasi.py
```

### CLI — statik PNG
```bash
python main.py --refresh   # ilk çalıştırma: API'ye gider, cache'ler
python main.py             # sonraki: diskten okur (altın kural)
```
Çıktı: terminalde trendler + `data/dashboard.png`.
