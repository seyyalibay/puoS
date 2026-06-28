"""
Disk cache yardımcıları — ALTIN KURAL'ın uygulayıcısı.

API'ye / siteye SADECE bir kez git. Sonucu data/<source>.json olarak yaz.
Sonraki çalıştırmalarda diskten oku. Tüm fetcher'lar bu iki fonksiyonu kullanır.

DOSYA ŞEMASI:
    {"query": "<arama sorgusu>", "fetched_at": "<ISO-8601 UTC>", "jobs": [...]}

    Sorgu değişince cache geçersiz sayılır ve sıfırdan çekilir — eski sorguya
    ait ilanlar yeni analize KARIŞMAZ. load_cache() query parametresiyle
    çağrılırsa mismatch durumunda None döner (yeniden çekmeyi tetikler).
"""
import json
import os
from datetime import datetime, timezone

# fetchers/ -> proje kökü -> data/
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def cache_path(source: str) -> str:
    return os.path.join(_DATA_DIR, f"{source}.json")


def _read_raw(source: str):
    """Cache dosyasını ham okur, yoksa None."""
    path = cache_path(source)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_cache(source: str, query: str | None = None) -> list[dict] | None:
    """Cache varsa ilanları döndürür, yoksa None.

    query verilirse cache'deki sorguyla karşılaştırır; farklıysa None döner
    (fetcher yeniden çekmeyi tetikler). query=None ise sorgu kontrolü yapılmaz.
    Eski şema (düz liste) dosyalar da okunur ama query kontrolü atlanır.
    """
    raw = _read_raw(source)
    if raw is None:
        return None
    if isinstance(raw, list):  # eski şema — sorgu bilgisi yok, geçersiz say
        return None
    # Yeni şema: {"query": ..., "fetched_at": ..., "jobs": [...]}
    if query is not None:
        cached_query = (raw.get("query") or "").strip().lower()
        if cached_query != query.strip().lower():
            return None  # sorgu değişmiş → cache geçersiz
    return raw.get("jobs", [])


def load_fetched_at(source: str) -> str | None:
    """Cache'in en son yazıldığı ISO-8601 UTC zaman damgası, yoksa None."""
    raw = _read_raw(source)
    if isinstance(raw, dict):
        return raw.get("fetched_at")
    return None


def load_cached_query(source: str) -> str | None:
    """Cache'in hangi sorguyla çekildiğini döndürür, bilinmiyorsa None."""
    raw = _read_raw(source)
    if isinstance(raw, dict):
        return raw.get("query")
    return None


def clear_cache(source: str) -> None:
    """Cache dosyasını siler. Yoksa sessizce geçer."""
    path = cache_path(source)
    if os.path.exists(path):
        os.remove(path)


def save_cache(source: str, jobs: list[dict], query: str = "") -> str:
    """İlanları data/<source>.json olarak (query + fetched_at ile) yazar."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    path = cache_path(source)
    payload = {
        "query": query,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "jobs": jobs,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path
