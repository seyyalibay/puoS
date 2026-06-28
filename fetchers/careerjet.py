"""
careerjet.py — Careerjet iş ilanı API'si (Türkiye ek kaynağı).

Careerjet public API (GET, JSON):
    http://public.api.careerjet.net/search
    Affiliate hesabı: https://www.careerjet.com.tr/partners/

Jooble'dan farkı: description alanı snippet yerine tam iş ilanı metni döndürür
(genellikle 500-1500 karakter).

SÖZLEŞME:
    fetch(...) -> list[dict]   # fetchers.SCHEMA_FIELDS şemasına uyar

ALTIN KURAL:
    İlk çağrıda API'ye gidilir, sonuç data/careerjet-tr.json'a yazılır.
    Sonraki çağrılarda diskten okunur. API'ye tekrar gitmek için force_refresh=True.

Ortam değişkeni:
    CAREERJET_API_KEY   — https://www.careerjet.com.tr/partners/ adresinden alınır
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

from fetchers import load_dotenv, validate_jobs
from fetchers.cache import load_cache, save_cache, clear_cache

SOURCE = "careerjet-tr"
_API_URL = "http://public.api.careerjet.net/search"
_LOCALE  = "tr_TR"
_PAGESIZE = 99          # API max 99 (100 bazen error verir)
_FAKE_IP  = "1.1.1.1"
_FAKE_URL = "http://www.careerjet.com.tr/"
_UA       = "Mozilla/5.0 SkillPulse/1.0"

_TAG_RE   = re.compile(r"<[^>]+>")


def _api_key() -> str:
    load_dotenv()
    key = os.environ.get("CAREERJET_API_KEY", "")
    if not key:
        raise RuntimeError(
            "CAREERJET_API_KEY tanımlı değil. "
            "https://www.careerjet.com.tr/partners/ adresinden ücretsiz "
            "affiliate hesabı aç ve .env dosyasına\n"
            "  CAREERJET_API_KEY=...\nolarak ekle."
        )
    return key


def _clean(text: str) -> str:
    """HTML etiketlerini ve boşlukları temizler."""
    text = _TAG_RE.sub(" ", text or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return " ".join(text.split())


def _normalize(raw: dict) -> dict:
    """Careerjet ham ilan JSON'unu değişmez şemaya çevirir."""
    date_posted = (raw.get("date") or "")[:10]
    return {
        "title":       _clean(raw.get("title", "")),
        "company":     _clean(raw.get("company", "")),
        "description": _clean(raw.get("description", "")),
        "location":    _clean(raw.get("locations", "")),
        "date_posted": date_posted,
        "source":      SOURCE,
    }


def _fetch_from_api(keywords: str, max_jobs: int) -> list[dict]:
    key = _api_key()
    jobs: list[dict] = []
    seen: set[str] = set()
    page = 1

    while len(jobs) < max_jobs:
        params = {
            "affid":       key,
            "keywords":    keywords,
            "locale_code": _LOCALE,
            "pagesize":    str(min(_PAGESIZE, max_jobs - len(jobs))),
            "page":        str(page),
            "sort":        "relevance",
            "user_ip":     _FAKE_IP,
            "user_agent":  _UA,
            "url":         _FAKE_URL,
        }
        url = _API_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Referer": _FAKE_URL})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise RuntimeError(
                    "Careerjet API 403 döndürdü. CAREERJET_API_KEY geçersiz veya "
                    "henüz aktive edilmemiş olabilir."
                ) from e
            raise
        except (urllib.error.URLError, OSError) as e:
            # Timeout veya ağ hatası — mevcut ilanlarla devam et
            print(f"[{SOURCE}] Sayfa {page} timeout/hata, toplanan {len(jobs)} ilanla duruldu: {e}")
            break

        if payload.get("type") == "ERROR":
            raise RuntimeError(f"Careerjet API hatası: {payload}")

        raw_jobs = payload.get("jobs") or []
        n_pages  = int(payload.get("pages", 1) or 1)
        n_new = 0
        for raw in raw_jobs:
            dedup_key = raw.get("url") or f"{raw.get('title')}|{raw.get('company')}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            jobs.append(_normalize(raw))
            n_new += 1

        print(f"[{SOURCE}] {keywords!r} sayfa {page}/{n_pages}: "
              f"{len(raw_jobs)} sonuç, {n_new} yeni (toplam {len(jobs)})")

        if page >= n_pages or n_new == 0:
            break
        page += 1
        time.sleep(0.5)

    return jobs[:max_jobs]


def fetch(
    keywords: str = "data engineer",
    max_jobs: int = 1000,
    force_refresh: bool = False,
) -> list[dict]:
    """Careerjet TR ilanlarını şemaya uygun list[dict] olarak döndürür."""
    if not force_refresh:
        cached = load_cache(SOURCE, query=None)
        if cached is not None:
            return validate_jobs(cached)

    clear_cache(SOURCE)
    jobs = _fetch_from_api(keywords, max_jobs)
    validate_jobs(jobs)
    save_cache(SOURCE, jobs, query=keywords)
    return jobs
