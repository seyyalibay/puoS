#!/usr/bin/env python3
"""
fetch_discovery_corpus.py — Keşif corpus'u için kategori bazında ilan çeker.

Her kategori için Adzuna UK API'den 200'er ilan çeker ve
data/discovery/<kategori>.json olarak kaydeder.

Kullanım:
    python3 fetch_discovery_corpus.py              # tümünü çek
    python3 fetch_discovery_corpus.py --only software data  # sadece bu kategoriler
    python3 fetch_discovery_corpus.py --force-refresh       # cache'i yenile
    python3 fetch_discovery_corpus.py --list                # kategorileri listele
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

from fetchers import load_dotenv

# ── Dizin ─────────────────────────────────────────────────────────────────────
DISCOVERY_DIR = Path(__file__).parent / "data" / "discovery"
DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)

JOBS_PER_QUERY  = 200   # sorgu başına ilan sayısı
RESULTS_PER_PAGE = 50   # Adzuna sayfa boyutu
COUNTRY          = "gb" # Adzuna UK (en kaliteli İngilizce ilanlar)

# ── Tüm discovery kategorileri ve sorguları ────────────────────────────────────
CATEGORIES: dict[str, list[str]] = {
    "software": [
        "software engineer", "backend developer", "frontend developer",
        "full stack developer", "mobile developer", "ios developer",
        "android developer", "devops engineer", "platform engineer", "sre",
        "cloud engineer", "cloud architect", "solutions architect",
        "security engineer", "cybersecurity analyst",
        "game developer", "embedded software engineer",
    ],
    "data": [
        "data engineer", "data scientist", "data analyst",
        "machine learning engineer", "ai engineer", "mlops engineer",
        "data architect", "database administrator",
        "business intelligence analyst", "bi developer",
        "analytics engineer", "quantitative analyst",
        "nlp engineer", "computer vision engineer",
        "research scientist", "applied scientist",
        "product analyst", "growth analyst", "marketing analyst",
        "financial data analyst", "risk analyst",
        "data governance analyst", "data quality engineer",
        "etl developer", "data pipeline engineer",
        "reporting analyst", "tableau developer",
        "power bi developer", "looker developer",
        "statistical analyst", "econometrician",
        "real time data engineer", "streaming engineer",
        "data infrastructure engineer", "lakehouse engineer",
    ],
    "industrial": [
        "industrial automation engineer", "control systems engineer",
        "plc scada engineer", "manufacturing automation engineer",
        "instrumentation engineer", "industrial iot engineer",
        "robotics engineer", "mechatronics engineer",
        "process automation engineer", "mes engineer",
        "rpa developer", "plc programmer", "scada developer",
    ],
    "mechanical": [
        "mechanical engineer", "design engineer",
        "cad engineer", "product designer",
        "quality engineer", "hvac engineer", "thermal engineer",
        "materials engineer", "tooling engineer",
    ],
    "electrical": [
        "electrical engineer", "electronics engineer",
        "embedded systems engineer", "firmware engineer",
        "pcb designer", "power electronics engineer",
        "telecommunications engineer", "rf engineer",
        "fpga engineer", "hardware engineer",
        "signal processing engineer",
    ],
    "construction": [
        "civil engineer", "structural engineer",
        "bim engineer", "project engineer",
        "infrastructure engineer",
    ],
    "chemical": [
        "chemical engineer", "process engineer",
        "oil gas engineer", "pharmaceutical engineer",
        "materials scientist",
    ],
    "finance": [
        "financial analyst", "investment analyst",
        "quantitative analyst", "algorithmic trader",
        "risk analyst", "actuary", "credit analyst",
        "product manager", "business analyst", "scrum master",
        "project manager", "program manager",
    ],
    "health": [
        "biomedical engineer", "clinical data manager",
        "health informatics", "medical device engineer",
        "bioinformatics engineer",
    ],
    "network": [
        "network engineer", "systems administrator",
        "it infrastructure engineer", "storage engineer",
        "database engineer", "systems engineer",
    ],
}

# ── CLI ────────────────────────────────────────────────────────────────────────
FORCE_REFRESH = "--force-refresh" in sys.argv
DO_LIST       = "--list" in sys.argv
ONLY_CATS: list[str] = []
SKIP_CATS: list[str] = []
if "--only" in sys.argv:
    idx = sys.argv.index("--only")
    ONLY_CATS = [a for a in sys.argv[idx+1:] if not a.startswith("--")]
if "--skip-categories" in sys.argv:
    idx = sys.argv.index("--skip-categories")
    raw = sys.argv[idx+1] if idx+1 < len(sys.argv) else ""
    SKIP_CATS = [s.strip() for s in raw.replace(",", " ").split() if s.strip()]


# ── Adzuna API yardımcıları ────────────────────────────────────────────────────

def _api_creds() -> tuple[str, str]:
    load_dotenv()
    app_id  = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        sys.exit(
            "ADZUNA_APP_ID / ADZUNA_APP_KEY eksik!\n"
            "https://developer.adzuna.com/ adresinden ücretsiz key alıp .env'e ekle."
        )
    return app_id, app_key


def _normalize(raw: dict, query: str) -> dict:
    created = (raw.get("created") or "")[:10]
    company = ""
    if isinstance(raw.get("company"), dict):
        company = raw["company"].get("display_name", "") or ""
    location = ""
    if isinstance(raw.get("location"), dict):
        location = raw["location"].get("display_name", "") or ""
    return {
        "title":       raw.get("title", "") or "",
        "company":     company,
        "description": raw.get("description", "") or "",
        "location":    location,
        "date_posted": created,
        "source":      f"discovery:{query}",
    }


def fetch_query(query: str, app_id: str, app_key: str, max_jobs: int = JOBS_PER_QUERY) -> list[dict]:
    """Tek sorgu için Adzuna'dan ilanları çeker."""
    jobs: list[dict] = []
    seen: set[str] = set()
    pages = -(-max_jobs // RESULTS_PER_PAGE)
    for page in range(1, pages + 1):
        params = {
            "app_id": app_id, "app_key": app_key,
            "results_per_page": RESULTS_PER_PAGE,
            "what": query, "max_days_old": 60,
            "content-type": "application/json",
        }
        url = (f"https://api.adzuna.com/v1/api/jobs/{COUNTRY}/search/{page}?"
               + urllib.parse.urlencode(params))
        try:
            with urllib.request.urlopen(url, timeout=30, context=_SSL_CTX) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"    ⚠️  API hatası (sayfa {page}): {e}")
            break
        results = payload.get("results", [])
        if not results:
            break
        for raw in results:
            key = (raw.get("redirect_url") or str(raw.get("id") or "")
                   or f"{raw.get('title')}|{raw.get('created')}")
            if key not in seen:
                seen.add(key)
                jobs.append(_normalize(raw, query))
        if len(results) < RESULTS_PER_PAGE or len(jobs) >= max_jobs:
            break
        time.sleep(0.5)  # nazik rate limiting
    return jobs[:max_jobs]


def load_category_cache(cat: str) -> list[dict] | None:
    path = DISCOVERY_DIR / f"{cat}.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return raw.get("jobs", [])
    return raw


def save_category_cache(cat: str, jobs: list[dict]) -> None:
    path = DISCOVERY_DIR / f"{cat}.json"
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "category":   cat,
        "n_jobs":     len(jobs),
        "jobs":       jobs,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Ana akış ──────────────────────────────────────────────────────────────────

def main() -> None:
    W = 70
    print("=" * W)
    print("  SkillPulse — Discovery Corpus Oluşturucu")
    print(f"  Adzuna UK · {JOBS_PER_QUERY} ilan/sorgu · {COUNTRY.upper()}")
    if FORCE_REFRESH: print("  [FORCE-REFRESH] Tüm cache'ler yenilenecek.")
    print("=" * W)

    if DO_LIST:
        for cat, queries in CATEGORIES.items():
            cached = load_category_cache(cat)
            status = f"✅ {len(cached)} ilan" if cached else "⬜ yok"
            print(f"  {cat:<15} {len(queries):>2} sorgu  {status}")
        return

    cats = [c for c in CATEGORIES if (not ONLY_CATS or c in ONLY_CATS) and c not in SKIP_CATS]
    if not cats:
        sys.exit(f"Geçersiz kategori. Mevcut: {', '.join(CATEGORIES)}")

    # Mevcut cache durumu
    total_cached = sum(
        len(load_category_cache(c) or []) for c in cats if not FORCE_REFRESH
    )
    print(f"\n📂 {len(cats)} kategori işlenecek.")
    if total_cached:
        print(f"   Cache'de zaten {total_cached} ilan var (--force-refresh ile yenile).")

    app_id, app_key = _api_creds()
    grand_total = 0

    for ci, cat in enumerate(cats, 1):
        queries = CATEGORIES[cat]
        print(f"\n{'─'*W}")
        print(f"[{ci}/{len(cats)}] 📁 {cat.upper()}  ({len(queries)} sorgu)")
        print(f"{'─'*W}")

        # Cache kontrolü
        if not FORCE_REFRESH:
            cached = load_category_cache(cat)
            if cached:
                print(f"  ✅ Zaten cached: {len(cached)} ilan — atlanıyor.")
                grand_total += len(cached)
                continue

        cat_jobs: list[dict] = []
        seen_ids: set[str] = set()

        for qi, query in enumerate(queries, 1):
            print(f"  [{qi:2}/{len(queries)}] 🔍 {query!r}  ", end="", flush=True)
            fetched = fetch_query(query, app_id, app_key)
            # Duplicate kontrolü (başlık + şirket bazlı)
            new_jobs = []
            for j in fetched:
                uid = f"{j['title']}|{j['company']}|{j['date_posted']}"
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    new_jobs.append(j)
            cat_jobs.extend(new_jobs)
            print(f"→ {len(fetched)} çekildi, {len(new_jobs)} yeni (toplam {len(cat_jobs)})")
            time.sleep(0.5)

        save_category_cache(cat, cat_jobs)
        grand_total += len(cat_jobs)
        print(f"\n  💾 Kaydedildi: data/discovery/{cat}.json  ({len(cat_jobs)} ilan)")

    print(f"\n{'='*W}")
    print(f"  TAMAMLANDI — Toplam {grand_total} ilan")
    print(f"  Sonraki adım: python3 discover_by_category.py")
    print(f"{'='*W}")


if __name__ == "__main__":
    main()
