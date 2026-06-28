"""
trend_analyzer.py — Zaman içinde beceri trendi.

SOURCE-AGNOSTIC: sadece şemaya uyan ilanlar + skill_extractor çıktısı alır.

Soru: Hangi teknolojiler YÜKSELİYOR, hangisi DÜŞÜYOR?

Yöntem:
    - İlanlar date_posted'a göre aylık dönemlere (period) bölünür.
    - Her dönem için her becerinin "yaygınlığı" = o becerinin geçtiği ilan
      sayısı / o dönemdeki toplam ilan sayısı (oran, ham sayım değil — ilan
      hacmi dönemden döneme değiştiği için normalize ediyoruz).
    - Trend skoru = ilk yarı dönemler ile son yarı dönemler arası yaygınlık
      farkı (yüzde puan). Pozitif -> yükseliyor, negatif -> düşüyor.

pandas kullanır.
"""
import pandas as pd

from processors.skill_extractor import extract_from_text


def build_dataframe(jobs: list[dict]) -> pd.DataFrame:
    """İlanları, her ilan için bulunan becerilerle uzun-format DataFrame'e çevirir.

    Kolonlar: date_posted (datetime), period (aylık), source, skill
    Her (ilan, beceri) çifti bir satır.
    """
    rows = []
    for job in jobs:
        date = pd.to_datetime(job.get("date_posted"), errors="coerce")
        skills = extract_from_text(job.get("description", ""))
        for skill in skills:
            rows.append({
                "date_posted": date,
                "source": job.get("source", "unknown"),
                "skill": skill,
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.dropna(subset=["date_posted"])
    df["period"] = df["date_posted"].dt.to_period("M").astype(str)
    return df


def skill_prevalence_by_period(jobs: list[dict]) -> pd.DataFrame:
    """period x skill matrisi: her hücre = o dönemde becerinin geçtiği ilan oranı."""
    df = build_dataframe(jobs)
    if df.empty:
        return pd.DataFrame()

    # Dönem başına toplam ilan sayısı (becerisi olmayan ilanlar dahil)
    job_dates = pd.to_datetime(
        [j.get("date_posted") for j in jobs], errors="coerce"
    )
    job_periods = pd.Series(job_dates).dropna().dt.to_period("M").astype(str)
    jobs_per_period = job_periods.value_counts()

    # Dönem x beceri: kaç ilanda geçti
    counts = (
        df.drop_duplicates(subset=["period", "skill"])  # placeholder; aşağıda düzeltilir
    )
    # Her (period, skill) için bu beceriyi içeren benzersiz ilan sayısı gerekiyor.
    # build_dataframe satırları zaten ilan-beceri çiftleri; aynı ilan tekrar etmez.
    grouped = df.groupby(["period", "skill"]).size().unstack(fill_value=0)

    # Oranı hesapla: count / o dönemdeki toplam ilan
    prevalence = grouped.div(jobs_per_period.reindex(grouped.index), axis=0).fillna(0.0)
    return prevalence.sort_index()


def trend_scores(jobs: list[dict]) -> pd.DataFrame:
    """Her beceri için yükseliyor/düşüyor skoru.

    Döner: DataFrame[skill, early, late, delta, direction]
        early     : ilk yarı dönemlerdeki ortalama yaygınlık
        late      : son yarı dönemlerdeki ortalama yaygınlık
        delta     : late - early (yüzde puan, +/-)
        direction : "rising" | "falling" | "stable"
    """
    prevalence = skill_prevalence_by_period(jobs)
    if prevalence.empty:
        return pd.DataFrame(columns=["skill", "early", "late", "delta", "direction"])

    periods = list(prevalence.index)
    mid = max(1, len(periods) // 2)
    early_periods = periods[:mid]
    late_periods = periods[mid:] or periods[-1:]

    early = prevalence.loc[early_periods].mean()
    late = prevalence.loc[late_periods].mean()
    delta = (late - early)

    out = pd.DataFrame({"early": early, "late": late, "delta": delta})
    out["direction"] = pd.cut(
        out["delta"],
        bins=[-1.0, -0.005, 0.005, 1.0],
        labels=["falling", "stable", "rising"],
    )
    out = out.sort_values("delta", ascending=False)
    out.index.name = "skill"
    return out.reset_index()


def summary(jobs: list[dict], top_n: int = 10) -> dict:
    """Dashboard/CLI için özet: en çok yükselen ve en çok düşen beceriler."""
    scores = trend_scores(jobs)
    if scores.empty:
        return {"rising": [], "falling": [], "n_jobs": len(jobs)}
    rising = scores[scores["delta"] > 0].head(top_n)
    falling = scores[scores["delta"] < 0].tail(top_n).iloc[::-1]
    return {
        "rising": rising.to_dict("records"),
        "falling": falling.to_dict("records"),
        "n_jobs": len(jobs),
    }
