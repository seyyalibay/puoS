"""
jooble.py — Jooble iş ilanı API'si için fetcher (Türkiye kaynağı).

kariyer.net scraper'ının yerine geçer (Cloudflare 403 kısıtlaması nedeniyle).

Birden çok ülkeyi destekler; ülke başına AYRI kaynak adı ve cache kullanılır:
    country="tr" -> source "jooble-tr" -> data/jooble-tr.json
    country="us" -> source "jooble-us" -> data/jooble-us.json

ÖNEMLİ — KEY ÜLKEYE BAĞLIDIR:
    Jooble her ülke sitesi için AYRI key verir (US: https://jooble.org/api/about,
    TR: https://tr.jooble.org/api/about). Yanlış ülkenin key'i 403 döndürür
    (deneyle doğrulandı, 11 Haziran 2026). Ortam değişkenleri:
        JOOBLE_API_KEY_TR, JOOBLE_API_KEY_US   (yoksa JOOBLE_API_KEY'e düşülür)
    Tanımlı değillerse proje kökündeki .env dosyasından okunur.

SÖZLEŞME:
    fetch(...) -> list[dict]   # her dict, fetchers.SCHEMA_FIELDS'e UYAR

ALTIN KURAL:
    İlk çağrıda API'ye gidilir, sonuç data/jooble-<ülke>.json'a yazılır. Sonraki
    çağrılarda diskten okunur. API'ye tekrar gitmek için force_refresh=True.

API ayrıntısı:
    POST https://{ülke}.jooble.org/api/{key}
    body: {"keywords": <sorgu>, "location": <şehir|boş>, "page": <n>}
    yanıt: {"totalCount": int, "jobs": [{title, company, snippet, location,
            updated, link, id, ...}]}
"""
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request

# macOS python.org kurulumlarında kök sertifikalar sistemde olmayabilir.
# certifi varsa onun CA paketini kullan; yoksa varsayılan context'e düş.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

from fetchers import load_dotenv, validate_jobs
from fetchers.cache import load_cache, save_cache, clear_cache

SOURCE = "jooble"  # taban ad; kaynak adı/cache dosyası için source_for() kullan


def source_for(country: str) -> str:
    """Ülke başına kaynak adı ('jooble-tr') — hem source alanı hem cache adı."""
    return f"{SOURCE}-{country or 'us'}"


def _api_base(country: str) -> str:
    """Ülke sitesinin API kökü. US ana domain'dedir, diğerleri alt domain'de."""
    host = "jooble.org" if country in ("", "us") else f"{country}.jooble.org"
    return f"https://{host}/api/"

def _api_key(country: str) -> str:
    load_dotenv()
    var = f"JOOBLE_API_KEY_{(country or 'us').upper()}"
    key = os.environ.get(var) or os.environ.get("JOOBLE_API_KEY")
    if not key:
        site = "jooble.org" if country in ("", "us") else f"{country}.jooble.org"
        raise RuntimeError(
            f"{var} tanımlı değil. https://{site}/api/about adresinden ücretsiz "
            f"key al (key ÜLKE sitesine bağlıdır) ve proje kökündeki .env "
            f"dosyasına\n  {var}=...\nolarak ekle."
        )
    return key


_TAG_RE = re.compile(r"<[^>]+>")


def _normalize(raw: dict, source: str) -> dict:
    """Jooble ham ilan JSON'unu DEĞİŞMEZ şemaya çevirir."""
    # Jooble 'updated' alanı ISO-8601 (örn. "2026-06-10T00:00:00.0000000+03:00");
    # ilk 10 hane = tarih.
    updated = raw.get("updated", "") or ""
    date_posted = updated[:10] if len(updated) >= 10 else ""
    # 'snippet' HTML parçaları içerir (<b>, &nbsp;); skill extraction düz metin ister.
    description = _TAG_RE.sub(" ", raw.get("snippet", "") or "")
    description = description.replace("&nbsp;", " ").replace("&amp;", "&").strip()
    return {
        "title": raw.get("title", "") or "",
        "company": raw.get("company", "") or "",
        "description": description,
        "location": raw.get("location", "") or "",
        "date_posted": date_posted,
        "source": source,
    }


def _dedupe_key(raw: dict) -> str:
    """id/link bazlı duplicate anahtarı. Aynı ilan ardışık sayfalarda tekrar
    çıkabilir. Şemada url alanı OLMADIĞI için dedupe normalize'dan ÖNCE,
    ham API yanıtı üzerinde yapılır — şema değişmez."""
    return (
        str(raw.get("id") or "")
        or raw.get("link")
        or f"{raw.get('title')}|{raw.get('updated')}"
    )


def _fetch_from_api(keywords: str, location: str, country: str, max_jobs: int) -> list[dict]:
    key = _api_key(country)
    base = _api_base(country)
    source = source_for(country)
    jobs: list[dict] = []
    seen: set[str] = set()
    page = 1
    while len(jobs) < max_jobs:
        body = json.dumps({"keywords": keywords, "location": location, "page": page})
        req = urllib.request.Request(
            base + key,
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise RuntimeError(
                    f"Jooble {base} key'i reddetti (403). Jooble key'leri ülke "
                    f"sitesine bağlıdır: '{country}' için key "
                    f"https://{'tr.' if country == 'tr' else ''}jooble.org/api/about "
                    "adresinden alınmalı."
                ) from e
            raise
        results = payload.get("jobs", [])
        if not results:
            break
        n_new = 0
        for raw in results:
            k = _dedupe_key(raw)
            if k in seen:
                continue
            seen.add(k)
            jobs.append(_normalize(raw, source))
            n_new += 1
        total = payload.get("totalCount", "?")
        print(f"[{source}] {keywords!r} sayfa {page}: {len(results)} sonuç, "
              f"{n_new} yeni (toplam {len(jobs)}/{total})")
        if n_new == 0:
            break  # sayfalama sona erdi, API aynı sonuçları döndürüyor
        page += 1
        time.sleep(1)  # API'ye nazik ol (rate limit)
    return jobs[:max_jobs]


def fetch(
    keywords: str = "yazılım",
    location: str = "",
    country: str = "tr",
    max_jobs: int = 1000,
    force_refresh: bool = False,
) -> list[dict]:
    """Jooble ilanlarını şemaya uygun list[dict] olarak döndürür.

    keywords: TEK arama sorgusu (örn. "yazılım"). country: Jooble ülke sitesi
    ("tr" -> tr.jooble.org; key o siteden alınmış olmalı). location: şehir
    filtresi, boş = tüm ülke. max_jobs kadar ilan hedeflenir; Jooble daha az
    döndürürse o kadar alınır. İlk kez (veya force_refresh=True) API'ye gider
    ve data/jooble-<ülke>.json'a yazar; aksi halde diskten okur.
    """
    src = source_for(country)
    if not force_refresh:
        cached = load_cache(src, query=None)
        if cached is not None:
            return validate_jobs(cached)

    # force_refresh=True veya cache yok → önce sil, sonra taze çek
    clear_cache(src)
    jobs = _fetch_from_api(keywords, location, country, max_jobs)
    validate_jobs(jobs)
    save_cache(src, jobs, query=keywords)
    return jobs
