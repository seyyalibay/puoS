# SkillPulse

İş ilanlarından **beceri trend analizi**. Hangi teknolojiler yükseliyor, hangisi
düşüyor? Phase 1: UK/US piyasası (Adzuna API). Phase 2: Türkiye (kariyer.net),
şirket kalibresi analizi ve Gemini destekli içgörüler.

## Ne yapar?

1. İş ilanlarını toplar (kaynak-bağımsız fetcher'lar: Adzuna API + kariyer.net
   scraper) ve diske cache'ler.
2. İlan metinlerinden becerileri çıkarır (bilingual EN+TR sözlük, C ile frekans sayımı).
3. Zaman içinde yükselen/düşen becerileri hesaplar.
4. İlanları kalibreye göre sınıflar — önce maaş (ilan metnindeki £ tutarı,
   yıllığa çevrilir: Tier 1 £70k+, Tier 2 £35–70k, Tier 3 <£35k), maaş yoksa
   unvan (Staff/Principal/Director/VP/Head of/Lead → 1, Senior/Mid → 2,
   Junior/Graduate/Entry/Associate → 3) — ve tier başına ayrı skill analizi yapar.
5. İnteraktif Streamlit dashboard'u (3 sekme: Trendler / Karşılaştırma / Öneriler)
   ve statik PNG üretir; Öneriler sekmesi her trend için Gemini Flash ile
   kısa içgörü yazar.

## Mimari (özet)

Kaynak-bağımsız: her veri kaynağı ayrı bir `fetchers/*.py` modülü ve **hepsi aynı
değişmez şemayı** döndürür. İşleme/analiz/görselleştirme katmanları kaynağı bilmez.

```
fetchers/{adzuna,kariyer}.py ─► list[dict] (şema) ─► processors ─► analyzers ─► visualizers
```

Veri şeması (değişmez):
```python
{"title": str, "company": str, "description": str,
 "location": str, "date_posted": str, "source": str}
```

Ayrıntılı kurallar ve C/ctypes pattern'ı için **[SKILL.md](SKILL.md)**.

```
skillpulse/
  fetchers/      # adzuna.py, kariyer.py (cloudscraper+bs4), cache.py, __init__.py (şema+validasyon)
  processors/    # skill_extractor.py, skill_counter_bridge.py (ctypes köprüsü)
  analyzers/     # trend_analyzer.py (pandas), company_tiers.py (maaş+unvan bazlı Tier 1/2/3)
  advisors/      # gemini_insights.py (gemini-flash-latest, insight cache'li)
  c_module/      # skill_counter.c (+ derlenmiş .so)
  visualizers/   # dashboard.py (matplotlib)
  data/          # JSON cache (adzuna/kariyer/insights) + dashboard.png
  skills.py      # bilingual beceri sözlüğü (77 beceri, 176 varyant)
  main.py        # CLI orkestratör
  app.py         # Streamlit dashboard (3 sekme)
```

## Kurulum

1. **Bağımlılıklar:**
   ```bash
   pip install -r requirements.txt
   ```

2. **C modülünü derle** (ders şartı — frekans sayımı C'de):
   ```bash
   cd c_module
   cc -O2 -shared -fPIC -o skill_counter.so skill_counter.c
   cd ..
   ```
   > Derlemezsen sistem yine çalışır; saf-Python fallback'e düşer. C kullanımda
   > olup olmadığını `main.py` çıktısının ilk satırı söyler.

3. **API key'leri ayarla (`.env`):** Şablonu kopyala ve kendi key'lerinle doldur.
   Key'ler `.env`'den `python-dotenv` ile okunur; kodda hardcode key yoktur ve
   `.env` git'e gönderilmez (`.gitignore`'da).
   ```bash
   cp .env.example .env
   # ardından .env'yi bir editörle açıp değerleri gir
   ```
   `.env` içindeki değişkenler:

   | Değişken | Nereden | Zorunlu mu? |
   |---|---|---|
   | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | https://developer.adzuna.com/ | UK ilanları için |
   | `JOOBLE_API_KEY_US`, `JOOBLE_API_KEY_TR` | https://jooble.org/api/about | US/TR ilanları için (her ülke ayrı key) |
   | `CAREERJET_API_KEY` | https://www.careerjet.com.tr/partners/ | Opsiyonel ek kaynak |
   | `GEMINI_API_KEY` (+ `_2`..`_6`) | https://aistudio.google.com/apikey | Öneriler sekmesi için |
   | `GROQ_API_KEY`, `GROQ_MODEL` | https://console.groq.com/keys | Gemini key'leri tükenirse yedek |

   > Bir key tanımlı değilse o kaynak/özellik devre dışı kalır ama uygulama
   > çalışmaya devam eder (ör. Gemini yoksa Öneriler sekmesi uyarı gösterir).

## Çalıştırma

### İnteraktif dashboard (önerilen) — Streamlit
```bash
streamlit run app.py
```
Tarayıcıda açılır; 3 sekme:
- **📈 Trendler** — en çok aranan beceriler (arama kutusuyla filtrelenir),
  yükselen/düşen trendler, aylık yaygınlık zaman serisi (plotly, interaktif).
- **⚖️ Karşılaştırma** — aynı beceriler kaynak başına (adzuna vs kariyer) ve
  şirket kalibresi başına (Tier 1/2/3) yan yana.
- **💡 Öneriler** — her güçlü trend için Gemini Flash'tan 1-2 cümlelik
  içgörü ("Azure yükseliyor çünkü..."). Sonuçlar `data/insights.json`'a
  cache'lenir; aynı trend için API'ye tekrar gidilmez.

Veri diske cache'lendiği için sonraki açılışlar API'ye gitmez (altın kural).
Ülke, sorgu ve gösterilecek beceri sayısı kenar çubuğundan ayarlanır.

### kariyer.net verisini toplamak / tazelemek
```bash
python main.py --refresh-kariyer
```
cloudscraper + BeautifulSoup ile liste ve detay sayfalarını gezer (her istek
arası 2 sn, sponsorlu ilanlar atlanır, art arda 403 yerse kendini durdurur)
ve `data/kariyer.json`'a yazar. Dashboard iki kaynağı otomatik birleştirir.

### CLI — statik PNG
```bash
# İlk çalıştırma: API'ye gider, data/adzuna.json'a cache'ler
python main.py --refresh

# Sonraki çalıştırmalar: diskten okur, API'ye GİTMEZ (altın kural)
python main.py

# US piyasası, veri bilimci ilanları, dashboard'ı ekranda da aç
python main.py --country us --what "data scientist" --show
```
Çıktı: terminalde en çok aranan + yükselen/düşen beceriler, ayrıca
`data/dashboard.png`.

## Phase planı

- **Phase 1 (tamam):** Adzuna fetcher + skill extractor + trend analyzer + PNG dashboard.
- **Phase 2 (tamam):** Streamlit UI (3 sekme) · `fetchers/kariyer.py`
  (cloudscraper + BeautifulSoup) · `analyzers/company_tiers.py` (Tier 1/2/3) ·
  `advisors/gemini_insights.py` (gemini-flash-latest). Şema değişmedi, downstream
  kod kaynakları hâlâ tanımıyor.

**Deadline: 18 Haziran.**
