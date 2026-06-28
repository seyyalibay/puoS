---
name: skillpulse
description: SkillPulse projesinin değişmez kuralları — source-agnostic fetcher mimarisi, sabit veri şeması, disk-cache altın kuralı, bilingual skill listesi ve C/ctypes frekans sayımı entegrasyon pattern'ı. İş ilanı toplama/işleme/trend/dashboard kodu yazarken oku.
---

# SkillPulse — Proje Kuralları

İş ilanlarından beceri trend analizi. UK/US (Phase 1, Adzuna API),
Türkiye/kariyer.net (Phase 2, scraping). **Deadline: 18 Haziran.**

## 1. EN KRİTİK KARAR — Source-agnostic mimari

Her veri kaynağı `fetchers/` altında AYRI bir modüldür. Sistemin geri kalanı
(`skill_extractor`, `trend_analyzer`, `dashboard`) **hiçbir kaynağı tanımaz**;
sadece şemayı bilir.

```
fetchers/adzuna.py   ─┐
fetchers/kariyer.py  ─┼─►  list[dict] (ŞEMA)  ─►  skill_extractor ─► trend_analyzer ─► dashboard
(yeni kaynak)        ─┘
```

**Kural:** Yeni kaynak eklemek = yeni fetcher modülü + şemaya uyan çıktı.
Downstream kodda HİÇBİR `if source == ...` dalı OLMAYACAK. Dashboard çoklu
kaynağı `source` alanına bakarak otomatik gösterir.

## 2. DEĞİŞMEZ VERİ ŞEMASI

Her ilan tam olarak şu altı `str` alanı içerir — eksik/fazla YOK:

```python
{
    "title": str, "company": str, "description": str,
    "location": str, "date_posted": str,  # "YYYY-MM-DD"
    "source": str,                          # "adzuna" | "kariyer"
}
```

Sözleşmenin bekçisi `fetchers/__init__.py` içindeki `validate_jobs()`.
**Her fetcher, döndürmeden ÖNCE `validate_jobs(jobs)` çağırır.** Şema bozulursa
fetcher'da patlar, ileride sessizce değil.

## 3. ALTIN KURAL — API'ye sadece bir kez git

API'ye/siteye **bir kez** git, sonucu `data/<source>.json`'a yaz, sonra hep
diskten oku. Uygulayıcı: `fetchers/cache.py` (`load_cache` / `save_cache`).

Pattern (her fetcher'da aynı):
```python
def fetch(..., force_refresh=False):
    if not force_refresh:
        cached = load_cache(SOURCE)
        if cached is not None:
            return validate_jobs(cached)
    jobs = _fetch_from_api(...)      # ağ erişimi SADECE burada
    validate_jobs(jobs)
    save_cache(SOURCE, jobs)
    return jobs
```
API'ye tekrar gitmek için açıkça `--refresh` / `force_refresh=True` gerekir.

## 4. C / ctypes ENTEGRASYON PATTERN'I (ders şartı)

Frekans sayımı **C'de** yapılır (`c_module/skill_counter.c`), Python'a `ctypes`
ile bağlanır. Köprü: `processors/skill_counter_bridge.py`.

**C tarafı** — saf, durumsuz, string→sayı fonksiyon:
```c
long count_occurrences(const char *haystack, const char *needle);
```

**Derleme:**
```bash
cd c_module && cc -O2 -shared -fPIC -o skill_counter.so skill_counter.c
```

**Python köprüsü kuralları:**
- `.so`'yu mutlak yoldan `ctypes.CDLL` ile yükle, `argtypes`/`restype` BELİRT
  (`c_char_p`, `c_char_p` → `c_long`).
- Stringleri `.encode("utf-8")` ile geçir.
- `.so` yoksa **saf-Python fallback'e düş** (`str.count`) — sistem yine çalışsın,
  `USING_C` bayrağı ile durumu raporla.
- Köprü dışında hiçbir yerde `ctypes` import edilmez; tek temas noktası burası.

Kelime-sınırı gereken riskli kısa varyantlar (`go`, `r`, `c`, `js`...) C'ye
gitmez; `skill_extractor` onları regex `\b...\b` ile sayar (C `strstr` sınır bilmez).

## 5. BİLINGUAL SKILL LİSTESİ

`skills.py` → `SKILLS: dict[canonical -> [varyantlar]]`. Her beceri İngilizce +
Türkçe + kısaltma varyantlarıyla. Canonical isim raporda görünür (genelde EN),
varyantlar metinde aranır. Türkçe karakter sorunları için hem `öğrenmesi` hem
`ogrenmesi` eklenir. Eşleştirme `text.lower()` üzerinde.

```python
"machine learning": ["machine learning", "makine öğrenmesi", "makine ogrenmesi", "ml"],
```

## 6. KLASÖR SORUMLULUKLARI

| Klasör | Sorumluluk | Kaynak bilir mi? |
|---|---|---|
| `fetchers/` | Veri toplama + şemaya çevirme + cache | EVET (tek yer) |
| `processors/` | Skill extraction + C köprüsü | HAYIR |
| `analyzers/` | Zaman bazlı trend (pandas) | HAYIR |
| `visualizers/` | Dashboard (matplotlib) | HAYIR (source'u veri olarak gösterir) |
| `c_module/` | C frekans sayacı + .so | HAYIR |
| `data/` | JSON cache + dashboard.png | — |

## 7. PHASE DİSİPLİNİ

- **Phase 1 (şimdi):** adzuna fetcher + extractor + analyzer + dashboard çalışır.
- **Phase 2:** `kariyer.py`'yi doldur — SADECE şemaya uy ve cache'le; downstream'e
  dokunma. Dashboard iki kaynağı otomatik gösterir.
- Phase 1 tam çalışmadan Phase 2'ye geçme.
