"""
company_tiers.py — İlan kalibresi: ÜLKEYE ÖZEL üç-sinyal puanlama (Phase 2 rev. 3).

Üç sinyal her ilanı 1/2/3 tier'larından birine OYLAR; oylar ağırlıklı puana
çevrilir ve en yüksek puanı alan tier seçilir:

    1) ŞİRKET ADI  (+2 puan, Tier 1 yönünde) — tüm ülkeler için ORTAK liste.
       Büyük teknoloji/danışmanlık/finans ile öne çıkan TR şirketleri Tier 1'e
       işaret eder.
    2) MAAŞ        (+3 puan, en güçlü sinyal) — ÜLKEYE GÖRE eşik. Şemada salary
       alanı YOK; tutar başlık+açıklama metnindeki para birimi sembollerinden
       (£ / $ / ₺·TL) çıkarılır. UK & US yıllık, TR aylık yorumlanır.
         UK (GBP, yıllık):  Tier 1 £80k+   · Tier 2 £35k–80k    · Tier 3 <£35k
         US (USD, yıllık):  Tier 1 $130k+  · Tier 2 $65k–130k   · Tier 3 <$65k
         TR (TL, aylık):    Tier 1 100k+   · Tier 2 45k–100k    · Tier 3 <45k
    3) UNVAN       (+1 puan) — başlıktaki kıdem kelimeleri (EN + TR):
         Tier 1 : staff / principal / director / vp / head of
                  (+ TR: direktör, genel müdür)
         Tier 2 : senior / lead (+ TR: kıdemli)
         Tier 3 : junior / graduate / entry (+ TR: stajyer, yeni mezun, asistan)

PUANLAMA: şirket eşleşmesi +2 · maaş uyumu +3 · unvan uyumu +1. En yüksek puanlı
tier seçilir; hiçbir sinyal yoksa Tier 2 (orta) varsayılır. Maaş verisi yoksa
sınıflama doğal olarak unvan + şirket kombinasyonuna düşer.

ÜLKE TESPİTİ: ilanın 'source' alanından çıkarılır
    adzuna -> gb (UK) · jooble-us -> us · jooble-tr -> tr

API (app.py bunları kullanır):
    TIER_LABELS              : {1: "...", 2: "...", 3: "..."}
    tier_of(job: dict)       : int (1/2/3)
    classify_jobs(jobs)      : {1: [job...], 2: [...], 3: [...]}
    tier_skill_stats(jobs)   : {tier: skill_extractor.extract(...) çıktısı}
    annual_salary_gbp(text)  : float | None (geriye dönük; UK yıllık GBP)
"""
import re
import unicodedata

from processors.skill_extractor import extract

TIER_LABELS: dict[int, str] = {
    1: "Tier 1 — Kıdemli / üst düzey",
    2: "Tier 2 — Orta seviye",
    3: "Tier 3 — Giriş seviyesi",
}

# Sinyal ağırlıkları (puan)
W_COMPANY = 2  # şirket eşleşmesi -> Tier 1 yönünde
W_SALARY = 3   # maaş uyumu (en güçlü)
W_TITLE = 1    # unvan uyumu


# ---------------------------------------------------------------------------
# Ülke tespiti (ilan kaynağından)
# ---------------------------------------------------------------------------
def _country_of(job: dict) -> str:
    src = job.get("source", "") or ""
    if src == "jooble-us":
        return "us"
    if src == "jooble-tr":
        return "tr"
    return "gb"  # adzuna / bilinmeyen -> UK varsay


# ---------------------------------------------------------------------------
# 1) ŞİRKET sinyali — tüm ülkeler için ORTAK liste (+2 puan, Tier 1)
# ---------------------------------------------------------------------------
TIER1_COMPANIES: tuple[str, ...] = (
    # Büyük teknoloji / danışmanlık / finans (global)
    "Google", "Microsoft", "Apple", "Amazon", "Meta", "Netflix", "Nvidia",
    "OpenAI", "Anthropic", "Spotify", "Airbnb", "Uber", "Salesforce", "Oracle",
    "SAP", "IBM", "Accenture", "Deloitte", "McKinsey", "Goldman Sachs",
    "JP Morgan", "HSBC", "Barclays", "Vodafone", "Shell", "BP", "Unilever",
    "Tesco",
    # Türkiye
    "Türk Telekom", "Garanti", "İş Bankası", "Akbank", "Trendyol", "Getir",
    "Peak Games", "Insider", "Figopara",
)


def _norm(s: str) -> str:
    """Aksan/birleşik işaretleri kaldırıp küçük harfe çevirir (TR adlarını
    güvenle eşleştirmek için: 'İş Bankası' ~ 'is bankasi')."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


_COMPANY_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(_norm(c)) for c in TIER1_COMPANIES) + r")(?!\w)"
)


def _company_match(company: str) -> bool:
    return bool(_COMPANY_RE.search(_norm(company)))


# ---------------------------------------------------------------------------
# 2) MAAŞ sinyali — ülkeye göre para birimi + eşik (+3 puan)
# ---------------------------------------------------------------------------
# (sembol, kod, Tier1 eşiği, Tier2 eşiği, dönem)
_CURRENCY: dict[str, dict] = {
    "gb": {"sym": r"£", "code": r"gbp", "t1": 80_000, "t2": 35_000, "period": "year"},
    "us": {"sym": r"\$", "code": r"usd", "t1": 130_000, "t2": 65_000, "period": "year"},
    "tr": {"sym": r"₺", "code": r"tl|try", "t1": 100_000, "t2": 45_000, "period": "month"},
}

_DAY_RE = re.compile(r"per\s*day|day\s*rate|daily\s*rate|/\s*day", re.IGNORECASE)
_HOUR_RE = re.compile(r"per\s*hour|hourly|p/?h\b|/\s*hour", re.IGNORECASE)
# Kontrat oranlarını yıllığa çevirme çarpanları (UK/US pratiği)
_WORKDAYS_PER_YEAR = 220
_WORKHOURS_PER_YEAR = 1820  # 35 saat x 52 hafta


def _parse_amount(num: str, k_flag: bool) -> float | None:
    """'70,000' / '150.000' / '70k' / '70.5k' -> float (binlik ayraç & k ele
    alınır). Ayrıştırılamayan bozuk token'lar (örn. '4.557.60') için None."""
    try:
        if k_flag:
            return float(num.replace(",", ".")) * 1000
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", num):  # binlik ayraç (, veya .)
            return float(num.replace(".", "").replace(",", ""))
        return float(num.replace(",", "."))
    except ValueError:
        return None


def _extract_amounts(text: str, country: str) -> list[float]:
    """Metindeki para tutarlarını ülkenin DÖNEMİNE (yıl/ay) normalize ederek
    listeler. Sembol/kod sayının iki yanında da olabilir."""
    cfg = _CURRENCY[country]
    sym, code = cfg["sym"], cfg["code"]
    pat = re.compile(
        rf"(?:{sym}|\b(?:{code})\b)\s*(\d[\d.,]*\d|\d)\s*(k\b)?"
        rf"|(\d[\d.,]*\d|\d)\s*(k\b)?\s*(?:{sym}|\b(?:{code})\b)",
        re.IGNORECASE,
    )
    has_day, has_hour = bool(_DAY_RE.search(text)), bool(_HOUR_RE.search(text))
    floor = 1_000 if cfg["period"] == "month" else 10_000
    out: list[float] = []
    for m in pat.finditer(text):
        num = m.group(1) or m.group(3)
        k_flag = bool(m.group(2) or m.group(4))
        if not num:
            continue
        val = _parse_amount(num, k_flag)
        if val is None:
            continue
        if val >= floor:
            out.append(val)
        elif cfg["period"] == "year":  # küçük tutar -> kontrat oranı olabilir
            if 100 <= val <= 2_000 and has_day:
                out.append(val * _WORKDAYS_PER_YEAR)
            elif 10 <= val < 200 and has_hour:
                out.append(val * _WORKHOURS_PER_YEAR)
    return out


def _salary_tier(text: str, country: str) -> int | None:
    """Ülke eşiğine göre maaş tier'ı (1/2/3) ya da tutar bulunamazsa None.
    İlan aralık verirse ÜST uç (en büyük tutar) kullanılır."""
    cfg = _CURRENCY[country]
    amounts = _extract_amounts(text, country)
    if not amounts:
        return None
    val = max(amounts)
    if val >= cfg["t1"]:
        return 1
    if val >= cfg["t2"]:
        return 2
    return 3


def annual_salary_gbp(text: str) -> float | None:
    """Geriye dönük: metindeki £ tutarlarından yıllık GBP tahmini (None=yok)."""
    amounts = _extract_amounts(text, "gb")
    return max(amounts) if amounts else None


# ---------------------------------------------------------------------------
# 3) UNVAN sinyali — başlıktaki kıdem kelimeleri (EN + TR, +1 puan)
# ---------------------------------------------------------------------------
def _title_pattern(words: tuple[str, ...]) -> re.Pattern:
    return re.compile(r"(?<!\w)(?:" + "|".join(words) + r")(?!\w)", re.IGNORECASE)


_TIER1_TITLE = _title_pattern((
    "staff", "principal", "director", "vp", "vice president", "head of",
    "direktör", "direktoru", "direktörü",
    "genel müdür", "genel müdürü", "genel mudur",
))
_TIER2_TITLE = _title_pattern((
    "senior", "snr", r"sr\.?", "lead", "kıdemli", "kidemli",
))
_TIER3_TITLE = _title_pattern((
    "junior", r"jr\.?", "graduate", "grad", "entry[- ]?level", "entry",
    "intern", "internship", "trainee",
    "stajyer", "yeni mezun", "asistan",
))


def _title_tier(title: str) -> int | None:
    """Unvandan tier (1/2/3) ya da kıdem kelimesi yoksa None."""
    if _TIER1_TITLE.search(title):
        return 1
    if _TIER3_TITLE.search(title):
        return 3
    if _TIER2_TITLE.search(title):
        return 2
    return None


# ---------------------------------------------------------------------------
# Birleştirme — üç sinyali puana çevir, en yüksek tier'ı seç
# ---------------------------------------------------------------------------
def tier_of(job: dict) -> int:
    """Tek ilan için tier (1/2/3): şirket(+2) + maaş(+3) + unvan(+1) oylaması.
    En yüksek puanlı tier; hiç sinyal yoksa Tier 2 (orta)."""
    country = _country_of(job)
    text = f"{job.get('title', '')} {job.get('description', '')}"
    score = {1: 0, 2: 0, 3: 0}

    if _company_match(job.get("company", "")):
        score[1] += W_COMPANY

    st = _salary_tier(text, country)
    if st is not None:
        score[st] += W_SALARY

    tt = _title_tier(job.get("title", ""))
    if tt is not None:
        score[tt] += W_TITLE

    top = max(score.values())
    if top == 0:
        return 2  # hiç sinyal yok -> orta seviye varsay
    leaders = [t for t in (1, 2, 3) if score[t] == top]
    if len(leaders) == 1:
        return leaders[0]
    # Eşitlik: en güçlü/objektif sinyal olan maaş tier'ı kazanır, o da
    # eşitlikte değilse daha kıdemli (düşük numaralı) tier seçilir.
    return st if st in leaders else leaders[0]


def classify_jobs(jobs: list[dict]) -> dict[int, list[dict]]:
    """İlanları tier'lara böler: {1: [...], 2: [...], 3: [...]} (hepsi mevcut)."""
    out: dict[int, list[dict]] = {1: [], 2: [], 3: []}
    for job in jobs:
        out[tier_of(job)].append(job)
    return out


def tier_skill_stats(jobs: list[dict]) -> dict[int, dict]:
    """Her tier için ayrı skill analizi (skill_extractor.extract çıktısı)."""
    return {
        tier: extract(tier_jobs)
        for tier, tier_jobs in classify_jobs(jobs).items()
        if tier_jobs
    }
