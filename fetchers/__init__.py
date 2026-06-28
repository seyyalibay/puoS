"""
fetchers — Source-agnostic veri toplama katmanı.

EN KRİTİK MİMARİ KARAR:
Her veri kaynağı (Adzuna, kariyer.net, ...) ayrı bir fetcher modülüdür.
TÜM fetcher'lar AYNI şemayı döndürmek ZORUNDADIR. Sistemin geri kalanı
(skill_extractor, trend_analyzer, dashboard) hiçbir kaynağı TANIMAZ;
sadece aşağıdaki şemayı bilir.

DEĞİŞMEZ VERİ ŞEMASI (bir iş ilanı = bir dict):
    {
        "title":       str,   # ilan başlığı
        "company":     str,   # şirket adı
        "description": str,   # ilan metni (skill extraction bunun üzerinde çalışır)
        "location":    str,   # şehir/bölge
        "date_posted": str,   # "YYYY-MM-DD"
        "source":      str,   # "adzuna" | "jooble-us" | "jooble-tr"
    }

Her fetcher modülü `fetch(...) -> list[dict]` arayüzünü sağlar ve sonucu
data/ klasörüne JSON olarak cache'ler (ALTIN KURAL: API'ye sadece bir kez git).
"""

import os

# Şema sözleşmesi — tek doğruluk kaynağı. Yeni fetcher yazarken buna uy.
SCHEMA_FIELDS = ("title", "company", "description", "location", "date_posted", "source")

# fetchers/ -> proje kökü -> .env
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def load_dotenv() -> None:
    """Proje kökündeki .env dosyasını os.environ'a yükler (mevcutları EZMEZ).

    API key isteyen her fetcher, key'i okumadan önce bunu çağırır — böylece
    key'ler export edilmeden .env'den çalışır. Yükleme python-dotenv ile yapılır.
    """
    from dotenv import load_dotenv as _load_dotenv

    # override=False -> dışarıdan export edilmiş değişkenleri EZMEZ.
    _load_dotenv(dotenv_path=_ENV_PATH, override=False)


def validate_job(job: dict) -> dict:
    """Bir iş ilanı dict'inin şemaya uyduğunu doğrular.

    Fetcher'lar döndürmeden ÖNCE bunu çağırmalı. Bu, source-agnostic
    sözleşmenin tek bekçisidir — şema bozulursa burada patlar, ileride değil.
    """
    missing = [f for f in SCHEMA_FIELDS if f not in job]
    if missing:
        raise ValueError(f"Job eksik alan(lar) içeriyor: {missing} | job={job!r}")
    extra = [k for k in job if k not in SCHEMA_FIELDS]
    if extra:
        raise ValueError(f"Job şemada olmayan alan(lar) içeriyor: {extra}")
    for f in SCHEMA_FIELDS:
        if not isinstance(job[f], str):
            raise TypeError(f"Alan '{f}' str olmalı, {type(job[f]).__name__} geldi.")
    return job


def validate_jobs(jobs: list[dict]) -> list[dict]:
    """Bir liste ilanı toplu doğrular ve aynı listeyi döndürür."""
    for job in jobs:
        validate_job(job)
    return jobs
