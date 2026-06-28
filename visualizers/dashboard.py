"""
dashboard.py — Görselleştirme katmanı.

SOURCE-AGNOSTIC: ilan listesini alır, içindeki `source` alanlarına bakarak
KAÇ kaynak varsa hepsini otomatik gösterir. Phase 1'de tek kaynak (adzuna),
Phase 2'de kariyer eklenince DEĞİŞİKLİK GEREKMEDEN iki kaynak görünür.

3 panel üretir:
    1) En sık geçen beceriler (yatay bar)
    2) Yükselen / düşen beceriler (trend delta, diverging bar)
    3) Kaynak başına ilan dağılımı (pie) — çoklu kaynağı görünür kılar

Çıktı: data/dashboard.png (ve isteğe bağlı plt.show()).

matplotlib kullanır (data-visualization).
"""
import os

import matplotlib

matplotlib.use("Agg")  # başsız/CI ortamı için; show() çağrılırsa main değiştirir
import matplotlib.pyplot as plt

from processors.skill_extractor import extract
from analyzers.trend_analyzer import trend_scores

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _sources(jobs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for j in jobs:
        s = j.get("source", "unknown")
        counts[s] = counts.get(s, 0) + 1
    return counts


def render(jobs: list[dict], top_n: int = 15, show: bool = False) -> str:
    """Dashboard'u çizer, kaydedilen PNG yolunu döndürür."""
    stats = extract(jobs)
    trends = trend_scores(jobs)
    sources = _sources(jobs)

    fig, axes = plt.subplots(1, 3, figsize=(20, 8))
    fig.suptitle(
        f"SkillPulse — {stats['n_jobs']} ilan | kaynaklar: {', '.join(sources)}",
        fontsize=16, fontweight="bold",
    )

    # --- Panel 1: En sık beceriler ---
    ax = axes[0]
    top = list(stats["doc_freq"].items())[:top_n][::-1]
    if top:
        labels, vals = zip(*top)
        ax.barh(labels, vals, color="#2563eb")
    ax.set_title("En çok aranan beceriler (ilan sayısı)")
    ax.set_xlabel("ilan sayısı")

    # --- Panel 2: Yükselen / düşen ---
    ax = axes[1]
    if not trends.empty:
        rising = trends[trends["delta"] > 0].head(top_n // 2)
        falling = trends[trends["delta"] < 0].tail(top_n // 2)
        merged = list(falling.iloc[::-1].itertuples()) + list(rising.iloc[::-1].itertuples())
        skills = [r.skill for r in merged]
        deltas = [r.delta * 100 for r in merged]  # yüzde puana çevir
        colors = ["#dc2626" if d < 0 else "#16a34a" for d in deltas]
        ax.barh(skills, deltas, color=colors)
        ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Trend: yükselen (yeşil) / düşen (kırmızı)")
    ax.set_xlabel("yaygınlık değişimi (yüzde puan)")

    # --- Panel 3: Kaynak dağılımı ---
    ax = axes[2]
    if sources:
        ax.pie(sources.values(), labels=list(sources.keys()), autopct="%1.0f%%",
               colors=["#2563eb", "#f59e0b", "#16a34a", "#dc2626"])
    ax.set_title("Kaynak dağılımı")

    fig.tight_layout(rect=(0, 0, 1, 0.95))

    os.makedirs(_DATA_DIR, exist_ok=True)
    out_path = os.path.join(_DATA_DIR, "dashboard.png")
    fig.savefig(out_path, dpi=120)
    if show:
        plt.show()
    plt.close(fig)
    return out_path
