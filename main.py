"""
main.py — SkillPulse CLI orkestratörü.

Akış (source-agnostic):
    1) fetcher(ler) ilanları toplar/diskten okur  -> list[dict] (şema)
    2) skill_extractor becerileri çıkarır
    3) trend_analyzer yükselen/düşen becerileri bulur
    4) dashboard PNG üretir

Kullanım:
    python main.py                      # adzuna, cache varsa diskten
    python main.py --refresh            # API'ye git, cache'i tazele
    python main.py --country us --what "data scientist"
    python main.py --show               # dashboard'ı ekranda da aç

C MODÜLÜ: skill sayımı c_module/skill_counter.so üzerinden (ctypes).
Derlemek için:  cd c_module && cc -O2 -shared -fPIC -o skill_counter.so skill_counter.c
"""
import argparse
import os
import sys

from fetchers import adzuna, jooble
# from fetchers import kariyer  # DEVRE DIŞI — yerini jooble aldı (Cloudflare 403)
from fetchers.cache import cache_path
from processors.skill_extractor import extract
from processors.skill_counter_bridge import USING_C
from analyzers.trend_analyzer import summary
from visualizers import dashboard


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="skillpulse", description="İş ilanı beceri trend analizi")
    p.add_argument("--country", default="gb", help="Adzuna ülke kodu: gb (UK) / us")
    p.add_argument("--what", default="developer", help="Arama sorgusu")
    p.add_argument("--max-jobs", type=int, default=1000, help="Hedeflenen ilan sayısı (Adzuna daha az döndürebilir)")
    p.add_argument("--refresh", action="store_true", help="Adzuna API'ye git, cache'i tazele")
    p.add_argument("--refresh-jooble", action="store_true", help="Jooble API'ye git (Türkiye), cache'i tazele")
    p.add_argument("--show", action="store_true", help="Dashboard'ı ekranda da aç")
    args = p.parse_args(argv)

    print(f"[skillpulse] C modülü kullanımda mı? {'EVET (.so)' if USING_C else 'HAYIR (Python fallback)'}")

    # 1) Fetch — adzuna (birincil) + jooble (cache'i varsa; API'ye GİTMEZ,
    #    onun için --refresh-jooble kullan)
    print(f"[skillpulse] Adzuna'dan ilanlar alınıyor (country={args.country}, what={args.what!r})...")
    try:
        jobs = adzuna.fetch(
            country=args.country, what=args.what, max_jobs=args.max_jobs, force_refresh=args.refresh
        )
    except RuntimeError as e:
        print(f"\n[HATA] {e}", file=sys.stderr)
        return 1
    print(f"[skillpulse] {len(jobs)} adzuna ilanı yüklendi.")

    for jc in ("us", "tr"):
        if args.refresh_jooble or os.path.exists(cache_path(jooble.source_for(jc))):
            try:
                jjobs = jooble.fetch(
                    keywords="developer" if jc == "us" else "yazılım",
                    country=jc,
                    force_refresh=args.refresh_jooble,
                )
            except RuntimeError as e:
                print(f"\n[HATA] {e}", file=sys.stderr)
                return 1
            jobs = jobs + jjobs
            print(f"[skillpulse] {len(jjobs)} jooble-{jc} ilanı eklendi (toplam {len(jobs)}).")

    # 2) Skill extraction
    stats = extract(jobs)
    print(f"\n=== En çok aranan 10 beceri (ilan sayısı) ===")
    for skill, n in list(stats["doc_freq"].items())[:10]:
        print(f"  {skill:<20} {n}")

    # 3) Trend
    trend = summary(jobs)
    print(f"\n=== Yükselen ===")
    for r in trend["rising"][:5]:
        print(f"  ↑ {r['skill']:<20} +{r['delta']*100:.1f} puan")
    print(f"=== Düşen ===")
    for r in trend["falling"][:5]:
        print(f"  ↓ {r['skill']:<20} {r['delta']*100:.1f} puan")

    # 4) Dashboard
    path = dashboard.render(jobs, show=args.show)
    print(f"\n[skillpulse] Dashboard kaydedildi: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
