"""
adzuna.py — Adzuna iş ilanı API'si için fetcher (Phase 1).

API key: https://developer.adzuna.com/  (ücretsiz, app_id + app_key)
Ortam değişkenleri ile verilir:
    ADZUNA_APP_ID
    ADZUNA_APP_KEY

SÖZLEŞME:
    fetch(...) -> list[dict]   # her dict, fetchers.SCHEMA_FIELDS'e UYAR

ALTIN KURAL:
    İlk çağrıda API'ye gidilir, sonuç data/adzuna.json'a yazılır. Sonraki
    çağrılarda diskten okunur. API'ye tekrar gitmek için force_refresh=True.

API ayrıntısı:
    GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
    params: app_id, app_key, results_per_page, what (sorgu), max_days_old
    country: "gb" (UK) veya "us" (US) — Phase 1 hedefi.
"""
import os
import ssl
import time
import urllib.parse
import urllib.request
import json

# macOS python.org kurulumlarında kök sertifikalar sistemde olmayabilir.
# certifi varsa onun CA paketini kullan; yoksa varsayılan context'e düş.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

from fetchers import load_dotenv, validate_jobs
from fetchers.cache import load_cache, save_cache, clear_cache

SOURCE = "adzuna"   # GB (backward compat alias)
_BASE = "https://api.adzuna.com/v1/api/jobs"


def source_for(country: str) -> str:
    """Ülkeye göre cache kaynak adı döndürür (adzuna, adzuna-ca, …)."""
    return SOURCE if country == "gb" else f"adzuna-{country}"


def _api_creds(country: str = "gb") -> tuple[str, str]:
    load_dotenv()
    if country == "ca":
        return "93f82ed3", "41ecf80049eff40791240a1216e90366"
    if country == "nl":
        return "c17a302c", "3c5408f292137aa5ba6280dbe5526437"
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise RuntimeError(
            "ADZUNA_APP_ID / ADZUNA_APP_KEY tanımlı değil. "
            "https://developer.adzuna.com/ adresinden ücretsiz key al ve proje "
            "kökündeki .env dosyasına\n"
            "  ADZUNA_APP_ID=...\n  ADZUNA_APP_KEY=...\n"
            "olarak ekle (veya export et)."
        )
    return app_id, app_key


def _normalize(raw: dict, country: str) -> dict:
    """Adzuna ham ilan JSON'unu DEĞİŞMEZ şemaya çevirir."""
    created = raw.get("created", "") or ""
    date_posted = created[:10] if len(created) >= 10 else ""
    company = ""
    if isinstance(raw.get("company"), dict):
        company = raw["company"].get("display_name", "") or ""
    location = ""
    if isinstance(raw.get("location"), dict):
        location = raw["location"].get("display_name", "") or ""
    return {
        "title": raw.get("title", "") or "",
        "company": company,
        "description": raw.get("description", "") or "",
        "location": location,
        "date_posted": date_posted,
        "source": source_for(country),
    }


def _dedupe_key(raw: dict) -> str:
    """URL bazlı duplicate anahtarı. Aynı ilan ardışık sayfalarda tekrar
    çıkabilir (sayfalar arasında sıralama kayabilir); redirect_url ilan başına
    tekildir. Şemada url alanı OLMADIĞI için dedupe normalize'dan ÖNCE,
    ham API yanıtı üzerinde yapılır — şema değişmez."""
    return (
        raw.get("redirect_url")
        or str(raw.get("id") or "")
        or f"{raw.get('title')}|{raw.get('created')}"
    )


def _fetch_from_api(
    country: str,
    what: str,
    max_jobs: int,
    results_per_page: int,
    max_days_old: int,
) -> list[dict]:
    app_id, app_key = _api_creds(country)
    jobs: list[dict] = []
    seen: set[str] = set()
    pages = -(-max_jobs // results_per_page)  # ceil
    for page in range(1, pages + 1):
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": results_per_page,
            "what": what,
            "max_days_old": max_days_old,
            "content-type": "application/json",
        }
        url = f"{_BASE}/{country}/search/{page}?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=30, context=_SSL_CTX) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        results = payload.get("results", [])
        if not results:
            break
        n_new = 0
        for raw in results:
            key = _dedupe_key(raw)
            if key in seen:
                continue
            seen.add(key)
            jobs.append(_normalize(raw, country))
            n_new += 1
        print(f"[adzuna] {what!r} sayfa {page}/{pages}: {len(results)} sonuç, "
              f"{n_new} yeni (toplam {len(jobs)})")
        if len(results) < results_per_page:
            break  # son sayfa — Adzuna'da bu sorgu için daha fazla ilan yok
        if len(jobs) >= max_jobs:
            break
        time.sleep(1)  # API'ye nazik ol (rate limit)
    return jobs[:max_jobs]


def fetch(
    country: str = "gb",
    what: str = "developer",
    max_jobs: int = 1000,
    results_per_page: int = 50,
    max_days_old: int = 60,
    force_refresh: bool = False,
) -> list[dict]:
    """Adzuna ilanlarını şemaya uygun list[dict] olarak döndürür.

    what: TEK arama sorgusu (örn. "developer"). max_jobs kadar ilan hedeflenir
    (varsayılan 1000 = 20 sayfa x 50); Adzuna daha az döndürürse o kadar alınır.
    İlk kez (veya force_refresh=True) API'ye gider ve data/adzuna.json'a yazar;
    aksi halde diskten okur.
    """
    src = source_for(country)
    if not force_refresh:
        cached = load_cache(src, query=None)
        if cached is not None:
            return validate_jobs(cached)

    clear_cache(src)
    jobs = _fetch_from_api(country, what, max_jobs, results_per_page, max_days_old)
    validate_jobs(jobs)
    save_cache(src, jobs, query=what)
    return jobs
