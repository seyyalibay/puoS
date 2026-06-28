"""
app.py — SkillPulse Streamlit dashboard (Phase 2).

Çalıştırma:
    streamlit run app.py

main.py ile AYNI source-agnostic pipeline'ı kullanır (fetcher -> extractor ->
analyzer). Fark: çıktı statik PNG değil, tarayıcıda interaktif dashboard.

3 sekme:
    📈 Trendler      — en çok aranan + yükselen/düşen beceriler, arama kutusu
    ⚖️ Karşılaştırma — seçili ülke içinde: tier dağılımı, top 10, yükselen/düşen
    💡 Öneriler      — Gemini Flash ile trend başına kısa insight

ALTIN KURAL korunur: varsayılan olarak diskten (data/<source>.json) okur.
Kenar çubuğundaki "API'den tazele" butonuna basılmadıkça API'ye GİTMEZ.
"""
import os
import re
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

from fetchers import adzuna, jooble, load_dotenv
# from fetchers import kariyer  # DEVRE DIŞI — yerini jooble aldı (Cloudflare 403)
from fetchers import careerjet
from fetchers.cache import cache_path, load_fetched_at, load_cached_query

# .env'i hemen yükle: cache-hit yolunda fetcher'lar load_dotenv çağırmadığı için
# GEMINI_API_KEY (ve diğer key'ler) açılışta os.environ'a girsin.
load_dotenv()
from processors.skill_extractor import extract, extract_from_text
from skills import SKILLS, SKILL_CATEGORIES
from processors.skill_counter_bridge import USING_C
from analyzers.trend_analyzer import trend_scores, skill_prevalence_by_period

# Adım 3 (tier) ve Adım 4 (Gemini) modülleri henüz yoksa sekmeler "yakında" der;
# modüller eklendiğinde BURADA DEĞİŞİKLİK GEREKMEDEN devreye girerler.
try:
    from analyzers.company_tiers import classify_jobs, TIER_LABELS, tier_of
    HAS_TIERS = True
except ImportError:
    HAS_TIERS = False

try:
    from advisors.gemini_insights import (
        generate_insights, generate_career_advice, generate_role_commentary,
        translate_query, gemini_available,
    )
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

st.set_page_config(page_title="SkillPulse", page_icon="📈", layout="wide")

from design import (
    apply_global_css, apply_chart_theme,
    metric_card, section_header, page_header,
    badge, tag, empty_state, match_card, insight_card,
    SIDEBAR_BRAND, sidebar_source_list, ICONS, BAR_COLOR,
    BAR_RISE_COLOR, BAR_FALL_COLOR, LINE_COLORS,
)
apply_global_css()

# Rakip Zekâsı modülünü top-level'da import et (tab bloğunda olunca her rerunda çalışır)
from rakip_zekasi import render_rakip_zekasi

PLOT = {"height": 420, "margin": dict(l=0, r=0, t=30, b=0)}


# ---------------------------------------------------------------------------
# Veri yükleme (source-agnostic): mevcut TÜM kaynakların cache'lerini birleştir.
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_all_cached() -> list[dict]:
    jobs: list[dict] = []
    if os.path.exists(cache_path(adzuna.SOURCE)):
        jobs.extend(adzuna.fetch(country="gb"))
    if os.path.exists(cache_path(adzuna.source_for("ca"))):
        jobs.extend(adzuna.fetch(country="ca"))
    if os.path.exists(cache_path(adzuna.source_for("nl"))):
        jobs.extend(adzuna.fetch(country="nl"))
    for c in ("us", "tr"):
        if os.path.exists(cache_path(jooble.source_for(c))):
            jobs.extend(jooble.fetch(country=c))
    if os.path.exists(cache_path(careerjet.SOURCE)):
        jobs.extend(careerjet.fetch())
    return jobs


# hash_funcs=id: load_all_cached her zaman aynı liste nesnesini döndürür,
# id() ile hash kontrolü 4800 dict'i tek tek hash'lemekten ~10x hızlı.
@st.cache_data(show_spinner=False, hash_funcs={list: id})
def corpus_stats(jobs: list[dict]) -> dict:
    return extract(jobs)


@st.cache_data(show_spinner=False, hash_funcs={list: id})
def cached_trends(jobs: list[dict]) -> pd.DataFrame:
    return trend_scores(jobs)


@st.cache_data(show_spinner=False, hash_funcs={list: id})
def cached_prevalence(jobs: list[dict]) -> pd.DataFrame:
    return skill_prevalence_by_period(jobs)


def doc_freq_share(jobs: list[dict]) -> pd.Series:
    """Becerinin geçtiği ilan ORANI (kaynaklar/tier'lar farklı boyutta olduğu için)."""
    if not jobs:
        return pd.Series(dtype=float)
    freq = corpus_stats(jobs)["doc_freq"]
    return pd.Series(freq, dtype=float) / len(jobs)


MAX_JOBS = 1000  # 20 sayfa x 50 ilan; Adzuna daha az döndürürse o kadar alınır

# Ülke -> veri kaynağı eşlemesi.
# TR iki kaynağa sahip: Jooble TR + Careerjet TR (COUNTRY_SOURCES_TR_ALL ile erişilir).
COUNTRY_LABELS = {"gb": "UK", "ca": "Kanada", "nl": "Hollanda", "us": "US", "tr": "Türkiye"}
COUNTRY_SOURCES = {
    "gb": adzuna.SOURCE,
    "ca": adzuna.source_for("ca"),
    "nl": adzuna.source_for("nl"),
    "us": jooble.source_for("us"),
    "tr": jooble.source_for("tr"),   # birincil (backward compat)
}
# TR'nin tüm source adları — filtreleme ve sayım için kullanılır.
TR_SOURCES: frozenset[str] = frozenset({jooble.source_for("tr"), careerjet.SOURCE})

DEFAULT_QUERY = {"gb": "developer", "ca": "developer", "nl": "developer", "us": "developer", "tr": "yazılım"}

# "Tüm Ülkeler" modu: ülke renk kodlu göster.
ALL = "all"
COUNTRY_OPTIONS = {ALL: "🌍 Tüm Ülkeler", **COUNTRY_LABELS}
# Sabit renk kodu
COUNTRY_COLORS = {"UK": "#2563eb", "Kanada": "#dc2626", "Hollanda": "#f97316", "US": "#7c3aed", "Türkiye": "#16a34a"}


def jobs_by_country(jobs: list[dict]) -> dict[str, list[dict]]:
    """{ülke etiketi: o ülkenin ilanları} — yalnızca verisi olan ülkeler."""
    out = {
        lbl: [j for j in jobs if j.get("source") == COUNTRY_SOURCES[code]]
        for code, lbl in COUNTRY_LABELS.items()
    }
    return {lbl: cj for lbl, cj in out.items() if cj}


# Pazar dili: UK/US İngilizce, TR Türkçe. Otomatik çeviri açıkken sorgu her
# ülkenin diline çevrilir (Türkçe "yazılım" -> UK/US için "software" vb.).
COUNTRY_LANG = {"gb": "en", "ca": "en", "nl": "nl", "us": "en", "tr": "tr"}


def market_query(text: str, code: str, translate: bool) -> tuple[str, list[str]]:
    """Sorguyu ülkenin diline/tech bağlamına çevirir (translate=True ve Gemini
    varsa). Döner: (arama_terimi, ilişkili_roller). arama_terimi aramada
    kullanılacak EN ALAKALI tek tech terim; ilişkili_roller ise (genel meslekler
    için) bilgi amaçlı gösterilecek tech rol listesidir. Çeviri kapalıysa/patlarsa
    metin aynen, rol listesi boş döner."""
    if not translate or not (HAS_GEMINI and gemini_available()):
        return text, []
    lang = COUNTRY_LANG[code]
    try:
        d = translate_query(text)
        term = d.get(lang, text) or text
        roles = [r for r in d.get(f"roles_{lang}", []) if r]
        # Tek terim (= meslek zaten tech) ise gösterilecek ek rol yok.
        return term, (roles if len(roles) > 1 else [])
    except Exception:
        return text, []


# Career matcher input'unda kısa token → tam form genişletme tablosu.
# skill_extractor.py'nin varyant listesiyle uyumlu tam formlar kullanılır.
_SHORT_TOKENS: dict[str, str] = {
    "c":   "c language",
    "r":   "r language",
    "go":  "golang",
    "js":  "javascript",
    "ts":  "typescript",
    "py":  "python",
    "k8s": "kubernetes",
    "tf":  "terraform",
    "ml":  "machine learning",
}


def _expand_shorts(raw: str) -> str:
    """Career matcher girişindeki kısa token'ları extractor'ın tanıdığı tam forma çevirir.
    Ayırıcıları koruyarak token-by-token değiştirir; skill_extractor.py'ye dokunmaz."""
    parts = re.split(r"([,\n;]+)", raw)
    return "".join(_SHORT_TOKENS.get(p.strip().lower(), p) for p in parts)


def recognize_skills(raw: str) -> tuple[set[str], list[str]]:
    """Virgül/yeni satır/noktalı virgülle ayrılmış beceri girdisini token'lara böler;
    her token'ı AYRI AYRI tanımaya çalışır. Döner:
        (tanınan_canonical_set, tanınmayan_token_list)
    Böylece "Python, Foobar" -> ({"python"}, ["Foobar"]) gibi kısmi tanıma raporlanır."""
    recognized: set[str] = set()
    unknown: list[str] = []
    seen: set[str] = set()
    for chunk in re.split(r"[,\n;]+", raw):
        token = chunk.strip()
        if not token:
            continue
        found = set(extract_from_text(token).keys())
        if found:
            recognized |= found
        else:
            low = token.lower()
            if low not in seen:
                seen.add(low)
                unknown.append(token)
    return recognized, unknown


def freshness_label(code: str) -> str:
    """Bir ülke kaynağının cache'i için "Son güncelleme: X gün önce" etiketi.
    Zaman damgası yoksa (eski şema cache) veya cache yoksa açıklayıcı metin döner."""
    ts = load_fetched_at(COUNTRY_SOURCES[code])
    if not ts:
        return "🕓 Son güncelleme: bilinmiyor"
    try:
        when = datetime.fromisoformat(ts)
        delta = datetime.now(timezone.utc) - when
        secs = delta.total_seconds()
        if secs < 3600:
            human = f"{max(1, int(secs // 60))} dk önce"
        elif secs < 86400:
            human = f"{int(secs // 3600)} saat önce"
        else:
            human = f"{int(secs // 86400)} gün önce"
        return f"🕓 Son güncelleme: {human}"
    except ValueError:
        return "🕓 Son güncelleme: bilinmiyor"


def _source_label(src: str) -> str:
    for code, lbl in COUNTRY_LABELS.items():
        if COUNTRY_SOURCES[code] == src:
            return lbl
    return src or "?"


_TITLE_STOP_WORDS: frozenset[str] = frozenset({
    # İngilizce genel unvan kelimeleri
    "engineer", "developer", "manager", "analyst", "specialist", "consultant",
    "lead", "senior", "junior", "staff", "principal", "architect",
    "designer", "coordinator", "director",
    # Türkçe genel unvan kelimeleri
    "mühendisi", "müdür", "uzman", "geliştirici", "analist",
    "yöneticisi", "direktör", "koordinatör", "kıdemli", "baş", "sorumlu",
})


def _role_keywords(role: str) -> list[str]:
    """Sorgudaki stop word'leri çıkarıp spesifik anahtar kelimeleri döndürür."""
    return [w for w in role.lower().split() if w not in _TITLE_STOP_WORDS]


def compute_role_skill_scores(user_skills: set, jobs: list[dict], target_role: str) -> dict:
    """Hedef role göre kullanıcı becerilerinin yaygınlığını hesaplar.

    Döner: {"scores": [...], "top_missing": [...], "n_role_jobs": int}
    scores: [{"skill", "pct", "count"}] — kullanıcının her becerisi için yaygınlık %
    top_missing: roldeki en çok aranan, kullanıcıda olmayan beceriler
    """
    keywords = _role_keywords(target_role)
    if keywords:
        # Spesifik kelimelerden en az biri title'da geçmeli (OR)
        role_jobs = [
            j for j in jobs
            if any(kw in (j.get("title") or "").lower() for kw in keywords)
        ]
    else:
        # Tüm kelimeler stop word'se orijinal sorguyla tam eşleşme dene
        role_jobs = [j for j in jobs if target_role.lower() in (j.get("title") or "").lower()]
    if not role_jobs:
        return {"scores": [], "top_missing": [], "n_role_jobs": 0}
    role_stats = extract(role_jobs)
    n = len(role_jobs)
    scores = [
        {"skill": s, "pct": role_stats["doc_freq"].get(s, 0) / n * 100,
         "count": role_stats["doc_freq"].get(s, 0)}
        for s in user_skills
    ]
    scores.sort(key=lambda x: x["pct"], reverse=True)
    top_missing = [
        s for s in role_stats["doc_freq"] if s not in user_skills
    ][:8]
    return {"scores": scores, "top_missing": top_missing, "n_role_jobs": n}


def _stars(pct: float) -> tuple[str, str]:
    """Yaygınlık yüzdesine göre (yıldız, etiket) döndürür."""
    if pct >= 80:
        return "⭐⭐⭐⭐⭐", "kritik"
    if pct >= 60:
        return "⭐⭐⭐⭐☆", "çok değerli"
    if pct >= 40:
        return "⭐⭐⭐☆☆", "değerli"
    if pct >= 20:
        return "⭐⭐☆☆☆", "yardımcı"
    return "⭐☆☆☆☆", "az rastlanan"


def compute_career_match(user: set, jobs: list[dict], per_job: list[dict], target_code: str) -> dict:
    """Kullanıcı becerilerini ilanlarla eşleştirir.

    - match (skill coverage): ilanın istediği becerilerin kaçına sahipsin (|U∩J|/|J|)
    - your_hit: senin becerilerinin kaçı ilanda geçiyor (|U∩J|/|U|)
    Çıktı: en iyi eşleşmeler, skill gap (en çok eksik beceriler) ve ülke analizi.
    Tek beceriden az talep eden ilanlar (gürültü) elenir.
    """
    pairs = list(zip(jobs, per_job))
    tpairs = pairs if target_code == ALL else [
        (j, p) for j, p in pairs if j.get("source") == COUNTRY_SOURCES[target_code]
    ]

    matches: list[dict] = []
    gap: dict[str, int] = {}
    for j, p in tpairs:
        js = set(p.keys())
        if len(js) < 2:
            continue
        inter = user & js
        for s in js - user:
            gap[s] = gap.get(s, 0) + 1
        if not inter:
            continue
        matches.append({
            "title": j.get("title", "") or "(başlıksız)",
            "company": j.get("company", "") or "—",
            "country": _source_label(j.get("source", "")),
            "tier": tier_of(j) if HAS_TIERS else None,
            "coverage": len(inter) / len(js),
            "your_hit": len(inter) / len(user) if user else 0.0,
            "matched": sorted(inter),
            "missing": sorted(js - user),
        })
    matches.sort(key=lambda m: (m["coverage"], len(m["matched"])), reverse=True)
    top_gap = sorted(gap.items(), key=lambda kv: kv[1], reverse=True)[:5]

    # Ülke analizi: TÜM ülkeler üzerinden (hedef filtresinden bağımsız) uygunluk.
    country_match: dict[str, dict] = {}
    for code, lbl in COUNTRY_LABELS.items():
        src = COUNTRY_SOURCES[code]
        covs = [
            len(user & set(p.keys())) / len(set(p.keys()))
            for j, p in pairs
            if j.get("source") == src and len(p) >= 2
        ]
        if covs:
            country_match[lbl] = {
                "qualify": round(sum(c >= 0.5 for c in covs) / len(covs) * 100, 1),
                "mean": round(sum(covs) / len(covs) * 100, 1),
                "n": len(covs),
            }
    return {"matches": matches, "top_gap": top_gap, "country_match": country_match}


def _badges(items: list, bg: str, fg: str, icon: str) -> str:
    return "".join(
        f"<span style='background:{bg};color:{fg};padding:4px 10px;border-radius:10px;"
        f"display:inline-block;margin:3px 4px 3px 0;font-size:0.9em'>{icon} {i}</span>"
        for i in items
    )


def render_career_advice(advice: dict) -> None:
    """Detaylı Gemini kariyer tavsiyesini kart/timeline/badge'lerle çizer."""
    # 1) Profil özeti
    with st.container(border=True):
        st.markdown("#### 📋 Profil özeti")
        st.write(advice["profil_ozeti"] or "—")

    # 2) Güçlü / geliştirilecek yönler — yeşil/kırmızı badge'ler
    g1, g2 = st.columns(2)
    with g1:
        with st.container(border=True):
            st.markdown("#### 💪 Güçlü yönler")
            st.markdown(
                _badges(advice["guclu_yonler"], "#dcfce7", "#166534", "✓") or "—",
                unsafe_allow_html=True,
            )
    with g2:
        with st.container(border=True):
            st.markdown("#### 🔧 Geliştirilecek yönler")
            st.markdown(
                _badges(advice["gelistirilecek"], "#fee2e2", "#991b1b", "!") or "—",
                unsafe_allow_html=True,
            )

    # 3) Roller — kart başına uyum %, neden, eksik beceriler, maaş
    if advice["roller"]:
        st.markdown("#### 🎯 Sana en uygun roller")
        for col, r in zip(st.columns(len(advice["roller"])), advice["roller"]):
            with col:
                with st.container(border=True):
                    st.markdown(f"**{r['unvan']}**")
                    if r["uyum"]:
                        st.markdown(
                            f"<span style='background:#2563eb;color:white;padding:2px 10px;"
                            f"border-radius:10px;font-weight:600'>Uyum {r['uyum']}</span>",
                            unsafe_allow_html=True,
                        )
                    if r["neden"]:
                        st.caption(r["neden"])
                    if r["eksik"]:
                        st.markdown("Eksik: " + " ".join(f"`{e}`" for e in r["eksik"]))
                    if r["maas_potansiyeli"]:
                        st.markdown(f"💰 {r['maas_potansiyeli']}")

    # 4) Yol haritası — timeline 3ay → 6ay → 12ay
    st.markdown("#### 🗺️ Öğrenme yol haritası")
    steps = [
        ("3 AY", "#2563eb", advice["yol_haritasi"]["3_ay"]),
        ("6 AY", "#7c3aed", advice["yol_haritasi"]["6_ay"]),
        ("12 AY", "#16a34a", advice["yol_haritasi"]["12_ay"]),
    ]
    tcols = st.columns([5, 1, 5, 1, 5])
    for i, (label, color, step) in enumerate(steps):
        with tcols[i * 2]:
            st.markdown(
                f"<div style='border-top:4px solid {color};background:#f8fafc;border-radius:8px;"
                f"padding:10px;min-height:150px'>"
                f"<span style='background:{color};color:white;padding:2px 10px;border-radius:10px;"
                f"font-weight:700;font-size:0.85em'>⬤ {label}</span>"
                f"<div style='font-weight:700;margin-top:8px;font-size:1.05em'>{step['beceri'] or '—'}</div>"
                f"<div style='font-size:0.85em;color:#334155;margin-top:4px'>{step['neden']}</div>"
                f"<div style='font-size:0.8em;color:#64748b;margin-top:6px'>📚 {step['nasil']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    for j in (1, 3):
        tcols[j].markdown(
            "<div style='text-align:center;font-size:2em;color:#cbd5e1;padding-top:55px'>→</div>",
            unsafe_allow_html=True,
        )

    # 5) Maaş potansiyeli — ülke bazlı metrik kartlar
    st.markdown("#### 💰 Maaş potansiyeli")
    mz = advice["maas_ozeti"]
    for col, (k, lbl) in zip(st.columns(3), [("UK", "🇬🇧 UK"), ("US", "🇺🇸 US"), ("TR", "🇹🇷 TR")]):
        col.metric(lbl, mz.get(k) or "—")

    # 6) Pazar analizi
    st.markdown("#### 🌍 Pazar analizi")
    pa = advice["pazar_analizi"]
    with st.container(border=True):
        if pa["en_iyi_pazar"]:
            st.markdown(f"**En iyi pazar:** {pa['en_iyi_pazar']}")
        if pa["neden"]:
            st.write(pa["neden"])
        if pa["rekabet"]:
            st.info(f"📊 Rekabet: {pa['rekabet']}")

    # 7) Hedef şirketler — renkli etiketler
    if advice["hedef_sirketler"]:
        st.markdown("#### 🏢 Hedef şirketler")
        palette = ["#2563eb", "#7c3aed", "#16a34a", "#dc2626", "#f59e0b"]
        for i, c in enumerate(advice["hedef_sirketler"]):
            color = palette[i % len(palette)]
            st.markdown(
                f"<span style='background:{color};color:white;padding:4px 12px;border-radius:12px;"
                f"font-weight:600;margin-right:8px'>{c['sirket']}</span>"
                f"<span style='color:#334155'>{c['neden']}</span>",
                unsafe_allow_html=True,
            )


def refresh_adzuna(country: str, what: str) -> int:
    """API'ye gider, cache'i tazeler ve Streamlit cache'ini temizler.
    Çekilen ilan sayısını döndürür."""
    jobs = adzuna.fetch(country=country, what=what, max_jobs=MAX_JOBS, force_refresh=True)
    st.cache_data.clear()
    return len(jobs)


def refresh_jooble(country: str, keywords: str) -> int:
    """Jooble API'ye gider (ülke sitesi), cache'i tazeler ve Streamlit
    cache'ini temizler. Çekilen ilan sayısını döndürür."""
    jobs = jooble.fetch(keywords=keywords, country=country, max_jobs=MAX_JOBS, force_refresh=True)
    st.cache_data.clear()
    return len(jobs)


# Türkçe teknik terim → (öneri mesajı, alternatif sorgular listesi)
_TR_QUERY_MAP: dict[str, tuple[str, list[str]]] = {
    "veri mühendisi":    ("'Data Engineer' veya 'Veri Analisti'",
                          ["data engineer", "veri analisti", "data analyst"]),
    "veri analisti":     ("'Data Analyst' veya 'Veri Bilimci'",
                          ["data analyst", "veri bilimci", "data scientist"]),
    "veri bilimci":      ("'Data Scientist' veya 'Machine Learning'",
                          ["data scientist", "machine learning engineer"]),
    "yazılım mühendisi": ("'Software Engineer' veya 'Backend Developer'",
                          ["software engineer", "backend developer", "yazılım geliştirici"]),
    "yapay zeka":        ("'AI Engineer' veya 'Machine Learning'",
                          ["ai engineer", "machine learning", "deep learning"]),
    "makine öğrenmesi":  ("'Machine Learning Engineer'",
                          ["machine learning engineer", "mlops engineer"]),
    "bulut mühendisi":   ("'Cloud Engineer' veya 'DevOps'",
                          ["cloud engineer", "devops engineer", "azure engineer"]),
    "güvenlik mühendisi":("'Security Engineer' veya 'Cybersecurity'",
                          ["security engineer", "cybersecurity engineer"]),
    "ağ mühendisi":      ("'Network Engineer'",
                          ["network engineer", "network administrator"]),
    "elektrik mühendisi":("'Electrical Engineer'",
                          ["electrical engineer", "electronics engineer"]),
}


def _tr_suggestion(query: str) -> tuple[str, list[str]] | None:
    """TR sorgusuna öneri + alternatif sorgu listesi döndürür; eşleşme yoksa None."""
    return _TR_QUERY_MAP.get(query.strip().lower())


def refresh_tr_combined(queries_jooble: list[str], queries_cjet: list[str]) -> tuple[int, int]:
    """TR için Jooble TR + Careerjet TR'yi birleşik olarak çeker.
    Her iki kaynak için birden fazla sorgu desteklenir (_TR_QUERY_MAP ile).
    Hedef: toplam 1000 ilan (Jooble ≤500, Careerjet ≤500, akıllı dağılım).
    Dedup: title.lower()+company.lower() üzerinden.
    Her kaynak kendi cache dosyasına ayrı kaydedilir.
    (n_jooble, n_cjet) döndürür."""
    from fetchers.cache import save_cache, clear_cache
    from fetchers import validate_jobs as _validate

    _MAX_EACH = 500
    _TARGET   = 1000

    # --- Jooble TR (çoklu sorgu) ---
    clear_cache(jooble.source_for("tr"))
    seen: set[str] = set()
    jooble_jobs: list[dict] = []
    per_q = max(100, _MAX_EACH // len(queries_jooble))
    for q in queries_jooble:
        if len(jooble_jobs) >= _MAX_EACH:
            break
        try:
            batch = jooble._fetch_from_api(q, "", "tr", min(per_q, _MAX_EACH - len(jooble_jobs)))
        except RuntimeError:
            continue
        for j in batch:
            key = f"{j.get('title','').lower()}|{j.get('company','').lower()}"
            if key not in seen:
                seen.add(key)
                jooble_jobs.append(j)
    _validate(jooble_jobs)
    save_cache(jooble.source_for("tr"), jooble_jobs, query=" / ".join(queries_jooble))

    # --- Careerjet TR (çoklu sorgu, kalan bütçe) ---
    cjet_budget = min(_MAX_EACH, _TARGET - len(jooble_jobs))
    clear_cache(careerjet.SOURCE)
    cjet_jobs: list[dict] = []
    if cjet_budget > 0:
        per_q_c = max(100, cjet_budget // len(queries_cjet))
        for q in queries_cjet:
            if len(cjet_jobs) >= cjet_budget:
                break
            try:
                batch = careerjet._fetch_from_api(q, min(per_q_c, cjet_budget - len(cjet_jobs)))
            except RuntimeError:
                continue
            for j in batch:
                key = f"{j.get('title','').lower()}|{j.get('company','').lower()}"
                if key not in seen:
                    seen.add(key)
                    cjet_jobs.append(j)
    _validate(cjet_jobs)
    save_cache(careerjet.SOURCE, cjet_jobs, query=" / ".join(queries_cjet))

    st.cache_data.clear()
    return len(jooble_jobs), len(cjet_jobs)


def refresh_jooble_multi(country: str, queries: list[str]) -> int:
    """Birden fazla sorgu için Jooble'dan ilan çeker, birleştirir, cache'e yazar.
    Dedup: title + company kombinasyonu üzerinden. Toplam ilan sayısını döndürür."""
    import json as _json
    from fetchers.cache import save_cache, clear_cache, cache_path
    from fetchers import validate_jobs as _validate

    src = jooble.source_for(country)
    per_query = max(200, MAX_JOBS // len(queries))
    seen: set[str] = set()
    all_jobs: list[dict] = []

    clear_cache(src)
    for q in queries:
        try:
            jobs = jooble._fetch_from_api(q, "", country, per_query)
        except RuntimeError:
            raise
        for j in jobs:
            key = f"{j.get('title','').lower()}|{j.get('company','').lower()}"
            if key not in seen:
                seen.add(key)
                all_jobs.append(j)

    _validate(all_jobs)
    combined_query = " / ".join(queries)
    save_cache(src, all_jobs, query=combined_query)
    st.cache_data.clear()
    return len(all_jobs)


# ---------------------------------------------------------------------------
# Veriyi tek seferde yükle — sidebar ve ana içerik aynı nesneyi kullanır.
# ---------------------------------------------------------------------------
jobs = load_all_cached()

# ---------------------------------------------------------------------------
# Kenar çubuğu — kontroller
# ---------------------------------------------------------------------------
st.sidebar.markdown(SIDEBAR_BRAND, unsafe_allow_html=True)
_c_status = "C modülü aktif" if USING_C else "Python fallback"
st.sidebar.markdown(
    f'<div style="padding:0 16px 8px;font-family:Inter,sans-serif;font-size:0.72rem;'
    f'color:#4A4A4A">{_c_status}</div>',
    unsafe_allow_html=True,
)
st.sidebar.divider()

st.sidebar.markdown('<div class="sp-sb-section">Veri kaynağı</div>', unsafe_allow_html=True)
country = st.sidebar.selectbox("Ülke", list(COUNTRY_OPTIONS), format_func=COUNTRY_OPTIONS.get)

if country == ALL:
    # Tüm ülkeler: tek arama sorgusu üç kaynağa birden uygulanır.
    what = st.sidebar.text_input(
        "Arama sorgusu", value="developer", key="query_all"
    )
    auto_tr = False
    if HAS_GEMINI and gemini_available():
        auto_tr = st.sidebar.checkbox(
            "🌐 Sorguyu pazar diline çevir", value=True,
            help="Türkçe yazarsan UK/US için İngilizce'ye, İngilizce yazarsan TR için Türkçe'ye çevrilir (Gemini).",
        )
    st.sidebar.caption(f"Beş API'den (UK·CA·NL·US·TR) en fazla {MAX_JOBS}'er ilan çekilir.")
    if st.sidebar.button("🔄 Tüm ülkeleri tazele", width="stretch"):
        _FETCH_CFG = [
            ("gb", "🇬🇧 UK (Adzuna)",    1000, 25),
            ("ca", "🇨🇦 CA (Adzuna)",    1000, 25),
            ("nl", "🇳🇱 NL (Adzuna)",    1000, 25),
            ("us", "🇺🇸 US (Jooble)",    1000, 25),
            ("tr", "🇹🇷 TR (Jooble+CJ)",  500, 30),
        ]
        prog  = st.sidebar.progress(0.0)
        label = st.sidebar.empty()
        for i, (code, name, est_jobs, est_secs) in enumerate(_FETCH_CFG):
            q, roles = market_query(what, code, auto_tr)
            label.markdown(f"🔄 **{name}** çekiliyor... ({est_jobs} ilan, ~{est_secs} sn)")
            prog.progress(i / len(_FETCH_CFG))
            try:
                if code in ("gb", "ca", "nl"):
                    n = refresh_adzuna(code, q)
                else:
                    n = refresh_jooble(code, q)
                extra = f" — '{q}'" if q != what else ""
                st.sidebar.success(f"✅ {name}: {n} ilan{extra}")
                if roles:
                    st.sidebar.caption(f"🔗 İlişkili tech roller: {', '.join(roles)}")
            except RuntimeError as e:
                st.sidebar.error(f"{name}: {e}")
            prog.progress((i + 1) / len(_FETCH_CFG))
        label.markdown("✅ **Tüm kaynaklar tamamlandı!**")
        st.sidebar.caption(f"⏱ Tahmini toplam süre: ~{sum(s for *_, s in _FETCH_CFG)} sn")
        st.rerun()

    counts = {lbl: sum(1 for j in jobs if j.get("source") == COUNTRY_SOURCES[code])
              for code, lbl in COUNTRY_LABELS.items()}
    total = sum(counts.values())
    st.sidebar.markdown(
        f"**📋 Toplam: {total} ilan** "
        f"(UK: {counts['UK']} | 🇨🇦 {counts['Kanada']} | 🇳🇱 {counts['Hollanda']} | US: {counts['US']} | TR: {counts['Türkiye']})"
    )
    for code, lbl in COUNTRY_LABELS.items():
        st.sidebar.caption(f"{lbl} · {freshness_label(code)}")
else:
    api_name = "Adzuna" if country in ("gb", "ca", "nl") else "Jooble"
    what = st.sidebar.text_input(
        "Arama sorgusu", value=DEFAULT_QUERY[country], key=f"query_{country}"
    )

    # TR öneri sistemi: Türkçe teknik terim girilince İngilizce alternatifler öner
    _tr_hint = _tr_suggestion(what) if country == "tr" else None
    if _tr_hint:
        _hint_msg, _alt_queries = _tr_hint
        st.sidebar.info(
            f"💡 TR pazarında bu rol genellikle İngilizce aranır. "
            f"{_hint_msg} ile deneyin."
        )

    auto_tr = False
    if HAS_GEMINI and gemini_available():
        auto_tr = st.sidebar.checkbox(
            "🌐 Sorguyu pazar diline çevir", value=True,
            help=("UK/US İngilizce, TR Türkçe pazar. Sorgun bu ülkenin diline "
                  "çevrilir (Gemini)."),
        )
    st.sidebar.caption(f"{api_name} API'den en fazla {MAX_JOBS} ilan çekilir (daha az döndürebilir).")

    _lbl_flag = {"gb": "🇬🇧 UK", "ca": "🇨🇦 CA", "nl": "🇳🇱 NL", "us": "🇺🇸 US", "tr": "🇹🇷 TR"}[country]
    _est_jobs = 500 if country == "tr" else 1000
    _est_secs = 15  if country == "tr" else 25

    if country == "tr":
        # TR: Jooble + Careerjet birleşik tazele
        _cjet_q = st.sidebar.text_input(
            "Careerjet sorgusu", value=what, key="cjet_query_tr",
            help="Careerjet için ayrı sorgu. Jooble sorgusu yukarıdaki 'Arama sorgusu' alanından alınır.",
        )
        if st.sidebar.button("🔄 TR Tümünü Tazele (Jooble + Careerjet)", width="stretch"):
            q_jooble, roles = market_query(what, "tr", auto_tr)
            # _TR_QUERY_MAP'ta eşleşme varsa alternatif sorgular da eklenir
            _hint = _tr_suggestion(what)
            _jooble_queries = ([q_jooble] + _hint[1]) if _hint else [q_jooble]
            _cjet_queries   = ([_cjet_q]  + _hint[1]) if _hint else [_cjet_q]
            prog = st.sidebar.progress(0.0, text="🔄 TR Jooble + Careerjet çekiliyor... (~30 sn)")
            try:
                n_j, n_c = refresh_tr_combined(_jooble_queries, _cjet_queries)
                prog.progress(1.0, text="✅ TR tamamlandı!")
                st.sidebar.success(
                    f"✅ TR toplam: {n_j + n_c} ilan\n"
                    f"Jooble: {n_j} | Careerjet: {n_c}"
                )
                if roles:
                    st.sidebar.caption(f"🔗 İlişkili tech roller: {', '.join(roles)}")
            except RuntimeError as e:
                prog.progress(1.0, text="❌ Hata oluştu")
                st.sidebar.error(str(e))
            else:
                st.rerun()
        # TR için alternatif sorgularla Jooble tazele
        if _tr_hint:
            _hint_msg, _alt_queries = _tr_hint
            if st.sidebar.button("🔄 Jooble alternatif sorgularla tazele", width="stretch",
                                 help=f"Şu sorgular birleştirilerek çekilir: {', '.join(_alt_queries)}"):
                prog = st.sidebar.progress(0.0, text="🔄 TR Jooble birleşik sorgular çekiliyor...")
                try:
                    n_fetched = refresh_jooble_multi("tr", _alt_queries)
                    prog.progress(1.0, text="✅ TR Jooble tamamlandı!")
                    st.sidebar.success(
                        f"✅ {n_fetched} ilan birleştirildi.\n"
                        f"Sorgular: {', '.join(_alt_queries)}"
                    )
                except RuntimeError as e:
                    prog.progress(1.0, text="❌ Hata oluştu")
                    st.sidebar.error(str(e))
                else:
                    st.rerun()
    else:
        if st.sidebar.button("🔄 API'den tazele", width="stretch"):
            q, roles = market_query(what, country, auto_tr)
            prog = st.sidebar.progress(0.0, text=f"🔄 {_lbl_flag} ilanları çekiliyor... ({_est_jobs} ilan, ~{_est_secs} sn)")
            try:
                n_fetched = refresh_adzuna(country, q) if country in ("gb", "ca", "nl") else refresh_jooble(country, q)
                prog.progress(1.0, text=f"✅ {_lbl_flag} tamamlandı!")
                extra = f" (sorgu: '{q}')" if q != what else ""
                st.sidebar.success(f"✅ {n_fetched} ilan bulundu.{extra}")
                if roles:
                    st.sidebar.caption(f"🔗 İlişkili tech roller: {', '.join(roles)}")
            except RuntimeError as e:
                prog.progress(1.0, text="❌ Hata oluştu")
                st.sidebar.error(str(e))
            else:
                st.rerun()

    if country == "tr":
        _n_jooble = sum(1 for j in jobs if j.get("source") == jooble.source_for("tr"))
        _n_cjet   = sum(1 for j in jobs if j.get("source") == careerjet.SOURCE)
        _n_tr     = _n_jooble + _n_cjet
        if _n_tr:
            st.sidebar.markdown(
                f"**🇹🇷 TR: {_n_tr} ilan** "
                f"(Jooble: {_n_jooble} | Careerjet: {_n_cjet})"
            )
            st.sidebar.caption(freshness_label(country))
    else:
        n_country = sum(1 for j in jobs if j.get("source") == COUNTRY_SOURCES[country])
        if n_country:
            st.sidebar.markdown(f"**📋 {n_country} ilan bulundu**")
            st.sidebar.caption(freshness_label(country))

st.sidebar.divider()

# Veri kaynakları listesi — her kaynak için cache durumunu gösterir.
_SOURCE_LABELS = {
    COUNTRY_SOURCES["gb"]: "Adzuna UK",
    COUNTRY_SOURCES["ca"]: "Adzuna CA",
    COUNTRY_SOURCES["nl"]: "Adzuna NL",
    COUNTRY_SOURCES["us"]: "Jooble US",
    COUNTRY_SOURCES["tr"]: "Jooble TR",
    careerjet.SOURCE:      "Careerjet TR",
}
_src_status = {lbl: os.path.exists(cache_path(src)) for src, lbl in _SOURCE_LABELS.items()}
st.sidebar.markdown(sidebar_source_list(_src_status), unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.caption(f"Taranan beceri: {len(SKILLS)} canonical")
top_n = st.sidebar.slider("Gösterilecek beceri sayısı", 5, 30, 15)


# ---------------------------------------------------------------------------
# Ana içerik
# ---------------------------------------------------------------------------
st.markdown(
    page_header("SkillPulse", "İş ilanlarından gerçek zamanlı beceri trendi"),
    unsafe_allow_html=True,
)

if not jobs:
    st.info(
        "Henüz veri yok. Kenar çubuğundan **🔄 API'den tazele** ile Adzuna (UK) "
        "veya Jooble'dan (Türkiye) ilan çek. (Önce `ADZUNA_APP_ID`/`ADZUNA_APP_KEY` "
        "ya da `JOOBLE_API_KEY` tanımladığından emin ol.)"
    )
    st.stop()

# Seçili ülkeye göre aktif ilan seti: Trendler/Öneriler sekmeleri bu subset
# üzerinden çalışır. Kariyer Eşleştirici kendi target_code filtresiyle tüm
# jobs'ı kullandığından ayrı tutulur.
if country == ALL:
    active_jobs = jobs
elif country == "tr":
    # TR iki kaynaktan beslenir: Jooble TR + Careerjet TR
    active_jobs = [j for j in jobs if j.get("source") in TR_SOURCES]
else:
    active_jobs = [j for j in jobs if j.get("source") == COUNTRY_SOURCES[country]]

with st.spinner("Analiz ediliyor..."):
    stats = corpus_stats(active_jobs)
    sources = pd.Series([j.get("source", "unknown") for j in active_jobs]).value_counts()
    trends = cached_trends(active_jobs)

tab_trend, tab_compare, tab_match, tab_advice, tab_rakip = st.tabs(
    ["Trendler", "Karşılaştırma", "Kariyer Eşleştirici", "Öneriler", "Rakip Zekâsı"]
)


# ===========================================================================
# SEKME 1 — TRENDLER
# ===========================================================================
with tab_trend:
    c1, c2, c3 = st.columns(3)
    with c1:
        if country == ALL:
            _parts = [
                f"UK: {int(sources.get(COUNTRY_SOURCES['gb'], 0))}",
                f"CA: {int(sources.get(COUNTRY_SOURCES['ca'], 0))}",
                f"NL: {int(sources.get(COUNTRY_SOURCES['nl'], 0))}",
                f"US: {int(sources.get(COUNTRY_SOURCES['us'], 0))}",
                f"TR: {int(sources.get(COUNTRY_SOURCES['tr'], 0))}",
            ]
            _sub = "  ·  ".join(_parts)
        else:
            _flag = {"gb": "UK", "ca": "CA", "nl": "NL", "us": "US", "tr": "TR"}[country]
            _sub = f"{_flag}: {int(sources.get(COUNTRY_SOURCES[country], 0))} ilan"
        st.markdown(metric_card("Toplam ilan", f"{stats['n_jobs']:,}", _sub), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("Tespit edilen beceri", len(stats["doc_freq"])), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Kaynak sayısı", len(sources)), unsafe_allow_html=True)

    st.divider()

    # --- Arama kutusu: beceri filtrele ---
    query = st.text_input(
        "Beceri ara",
        placeholder="örn. python, aws, react...",
        help="Aşağıdaki grafik ve tablolar bu filtreye göre daralır.",
    ).strip().lower()

    freq = pd.Series(stats["doc_freq"], name="ilan sayısı")
    if query:
        freq = freq[freq.index.str.contains(query, regex=False)]
        if freq.empty:
            st.warning(f"'{query}' ile eşleşen beceri yok. ({len(SKILLS)} canonical beceri aranıyor.)")

    if not freq.empty:
        st.caption(
            "Sonuçlar iş ilanı metinlerinde geçen tüm becerileri kapsar — "
            "birincil beceriler yanı sıra bağlamsal/tamamlayıcı beceriler de dahildir."
        )
        top = freq.head(top_n).sort_values()
        fig = px.bar(
            x=top.values, y=top.index, orientation="h",
            labels={"x": "ilan sayısı", "y": ""},
            title=f"En çok aranan beceriler (top {len(top)})",
            color_discrete_sequence=[BAR_COLOR],
        )
        apply_chart_theme(fig)
        st.plotly_chart(fig, width="stretch")

    st.divider()

    # --- Trend: yükselen / düşen ---
    st.markdown(section_header("Trend — yükselen / düşen", "trend-up"), unsafe_allow_html=True)
    if trends.empty:
        st.warning("Trend hesabı için yeterli tarihli veri yok.")
    else:
        tdf = trends.copy()
        if query:
            tdf = tdf[tdf["skill"].str.contains(query, regex=False)]
        tdf["delta_puan"] = (tdf["delta"] * 100).round(1)
        rising = tdf[tdf["delta"] > 0].head(top_n // 2)
        falling = tdf[tdf["delta"] < 0].tail(top_n // 2)

        combo = pd.concat([falling, rising]).sort_values("delta_puan")
        if not combo.empty:
            fig = px.bar(
                combo, x="delta_puan", y="skill", orientation="h",
                color=combo["delta_puan"] > 0,
                color_discrete_map={True: BAR_RISE_COLOR, False: BAR_FALL_COLOR},
                labels={"delta_puan": "Δ yüzde puan (son dönem - ilk dönem)", "skill": ""},
                title="Yaygınlık değişimi",
            )
            apply_chart_theme(fig, show_legend=False)
            st.plotly_chart(fig, width="stretch")

        tcol1, tcol2 = st.columns(2)
        with tcol1:
            st.markdown("**Yükselen**")
            st.dataframe(
                rising[["skill", "delta_puan"]].rename(columns={"skill": "beceri", "delta_puan": "Δ yüzde puan"}),
                hide_index=True, width="stretch",
            )
        with tcol2:
            st.markdown("**Düşen**")
            st.dataframe(
                falling[["skill", "delta_puan"]].rename(columns={"skill": "beceri", "delta_puan": "Δ yüzde puan"}),
                hide_index=True, width="stretch",
            )

    st.divider()

    # --- Zaman içinde yaygınlık ---
    st.markdown(section_header("Zaman içinde yaygınlık (aylık)", "chart-line"), unsafe_allow_html=True)
    prevalence = cached_prevalence(active_jobs)
    if prevalence.empty:
        st.warning("Zaman serisi için yeterli veri yok.")
    else:
        default = [s for s in list(stats["doc_freq"].keys())[:6] if s in prevalence.columns]
        chosen = st.multiselect("Beceri seç", options=list(prevalence.columns), default=default)
        if chosen:
            long = (prevalence[chosen] * 100).reset_index().melt(
                id_vars="period", var_name="beceri", value_name="yaygınlık (%)"
            )
            fig = px.line(
                long, x="period", y="yaygınlık (%)", color="beceri", markers=True,
                labels={"period": "dönem"},
            )
            apply_chart_theme(fig)
            st.plotly_chart(fig, width="stretch")
            st.caption("Y ekseni: o dönemdeki ilanların yüzde kaçında beceri geçti.")


# ===========================================================================
# SEKME 2 — KARŞILAŞTIRMA (kaynak bazında + şirket kalibresi)
# ===========================================================================
with tab_compare:
  if country == ALL:
    # === TÜM ÜLKELER — UK · US · TR yan yana, ülke renk kodlu ===============
    st.subheader("Tüm ülkeler — karşılaştırma (UK · US · TR)")
    st.caption("Renk kodu: 🔵 UK · 🔴 US · 🟢 TR")
    bycountry = jobs_by_country(jobs)
    if not bycountry:
        st.info("Hiç veri yok. Tek bir ülke seçip **🔄 API'den tazele** ile veri çek.")
    else:
        # --- 1) Tier dağılımı (ülke bazında) ---
        st.markdown("### İlan kalibresine göre (Tier 1 / 2 / 3 — ülke bazında)")
        if not HAS_TIERS:
            st.info("🚧 Kalibre sınıflandırması henüz yok.")
        else:
            trows = []
            for lbl, cj in bycountry.items():
                d = classify_jobs(cj)
                n = len(cj)
                for tier, label in TIER_LABELS.items():
                    trows.append({
                        "ülke": lbl, "tier": label, "ilan": len(d[tier]),
                        "oran (%)": round(len(d[tier]) / n * 100, 1),
                    })
            fig = px.bar(
                pd.DataFrame(trows), x="tier", y="oran (%)", color="ülke",
                barmode="group", color_discrete_map=COUNTRY_COLORS,
                title="Tier dağılımı (ülke içi oran)", hover_data=["ilan"],
            )
            apply_chart_theme(fig)
            st.plotly_chart(fig, width="stretch")
            st.warning(
                "⚠️ Tier analizi UK için güvenilir (%52 maaş sinyali). "
                "US ve TR'de Jooble veri kısıtlaması nedeniyle "
                "ilanların çoğu sinyal içermiyor, sonuçlar gösterge niteliğindedir."
            )

        st.divider()

        # --- 2) En çok aranan beceriler (skill × ülke, gruplu) ---
        st.markdown("### En çok aranan beceriler (ülke bazında)")
        all_options = sorted(stats["doc_freq"].keys())
        all_default = list(stats["doc_freq"].keys())[: min(10, top_n)]
        chosen_all = st.multiselect(
            "Karşılaştırılacak beceriler", options=all_options,
            default=all_default, key="all_skills",
        )
        shares = {lbl: doc_freq_share(cj) for lbl, cj in bycountry.items()}
        if chosen_all:
            rows = [
                {"beceri": s, "ülke": lbl, "yaygınlık (%)": shares[lbl].get(s, 0.0) * 100}
                for lbl in bycountry
                for s in chosen_all
            ]
            fig = px.bar(
                pd.DataFrame(rows), x="beceri", y="yaygınlık (%)", color="ülke",
                barmode="group", color_discrete_map=COUNTRY_COLORS,
                title="Becerinin geçtiği ilan oranı (ülke başına)",
            )
            apply_chart_theme(fig)
            st.plotly_chart(fig, width="stretch")

        st.divider()

        # --- 3) Trend (ülke bazında, aynı renk kodu) ---
        st.markdown("### Trend — yükselen ↑ / düşen ↓ (ülke bazında)")
        trend_rows = []
        for lbl, cj in bycountry.items():
            ct = cached_trends(cj)
            if ct.empty:
                continue
            ct = ct.copy()
            ct["delta_puan"] = (ct["delta"] * 100).round(1)
            movers = pd.concat([
                ct[ct["delta"] > 0].head(top_n // 2),
                ct[ct["delta"] < 0].tail(top_n // 2),
            ])
            for _, r in movers.iterrows():
                trend_rows.append({"beceri": r["skill"], "ülke": lbl, "delta_puan": r["delta_puan"]})
        if trend_rows:
            fig = px.bar(
                pd.DataFrame(trend_rows).sort_values("delta_puan"),
                x="delta_puan", y="beceri", color="ülke", orientation="h",
                barmode="group", color_discrete_map=COUNTRY_COLORS,
                labels={"delta_puan": "Δ yüzde puan (son dönem - ilk dönem)", "beceri": ""},
                title="Yaygınlık değişimi (ülke başına)",
            )
            apply_chart_theme(fig)
            st.plotly_chart(fig, width="stretch")
        else:
            st.warning("Trend hesabı için yeterli tarihli veri yok.")
  else:
    country_label = COUNTRY_LABELS[country]
    cjobs = [j for j in jobs if j.get("source") == COUNTRY_SOURCES[country]]

    st.markdown(section_header(f"Ülke içi karşılaştırma — {country_label}", "scales"), unsafe_allow_html=True)

    if not cjobs:
        st.info(
            f"**{country_label}** için veri yok. Kenar çubuğundan "
            f"**🔄 API'den tazele** ile {'Adzuna' if country == 'gb' else 'Jooble'}'dan "
            "ilan çek."
        )
    else:
        cstats = corpus_stats(cjobs)

        # --- 1) Tier 1 / 2 / 3 beceri dağılımı ---
        st.markdown("### İlan kalibresine göre (Tier 1 / 2 / 3 — şirket + maaş + unvan)")
        if not HAS_TIERS:
            st.info("🚧 Kalibre sınıflandırması Phase 2 Adım 3'te ekleniyor.")
        else:
            tiered = classify_jobs(cjobs)  # {tier: list[job]}
            mc = st.columns(len(TIER_LABELS))
            for i, (tier, label) in enumerate(TIER_LABELS.items()):
                mc[i].metric(label, f"{len(tiered.get(tier, []))} ilan")

            by_tier = {
                TIER_LABELS[t]: doc_freq_share(tjobs)
                for t, tjobs in tiered.items() if tjobs
            }
            compare_options = sorted(cstats["doc_freq"].keys())
            default_skills = list(cstats["doc_freq"].keys())[: min(10, top_n)]
            chosen_cmp = st.multiselect(
                "Karşılaştırılacak beceriler", options=compare_options, default=default_skills
            )
            if chosen_cmp and by_tier:
                rows = [
                    {"beceri": s, "tier": label, "yaygınlık (%)": share.get(s, 0.0) * 100}
                    for label, share in by_tier.items()
                    for s in chosen_cmp
                ]
                fig = px.bar(
                    pd.DataFrame(rows), x="beceri", y="yaygınlık (%)", color="tier",
                    barmode="group",
                    color_discrete_sequence=LINE_COLORS[:3],
                    title="Becerinin geçtiği ilan oranı, kalibre başına",
                )
                apply_chart_theme(fig)
                st.plotly_chart(fig, width="stretch")
                st.caption(
                    "Üç sinyal puanlanır (şirket +2 → Tier 1 · maaş +3 · unvan +1); "
                    "en yüksek puanlı tier seçilir. Maaş eşiği ÜLKEYE göre değişir — "
                    "UK: £80k/£35k yıllık · US: $130k/$65k yıllık · TR: 100k/45k TL aylık. "
                    "Unvan: Staff/Principal/Director/VP/Head of/direktör/genel müdür → 1, "
                    "Senior/Lead/kıdemli → 2, Junior/Graduate/Entry/stajyer → 3."
                )

            if country in ("us", "tr"):
                st.warning(
                    "⚠️ Tier analizi UK için güvenilir (%52 maaş sinyali). "
                    "US ve TR'de Jooble veri kısıtlaması nedeniyle "
                    "ilanların çoğu sinyal içermiyor, sonuçlar gösterge niteliğindedir."
                )

            # Tier başına ayrı top-10 tablosu
            tcols = st.columns(len(by_tier) or 1)
            for col, (label, share) in zip(tcols, by_tier.items()):
                with col:
                    st.markdown(f"**{label} — top 10**")
                    top10 = (share.sort_values(ascending=False).head(10) * 100).round(1)
                    st.dataframe(
                        top10.rename("yaygınlık (%)").rename_axis("beceri").reset_index(),
                        hide_index=True, width="stretch",
                    )

        st.divider()

        # --- 2) En çok aranan beceriler (top 10) ---
        st.markdown("### En çok aranan beceriler (top 10)")
        cfreq = pd.Series(cstats["doc_freq"], name="ilan sayısı").head(10)
        if cfreq.empty:
            st.warning("Bu ülkenin ilanlarında tespit edilen beceri yok.")
        else:
            ctop = cfreq.sort_values()
            fig = px.bar(
                x=ctop.values, y=ctop.index, orientation="h",
                labels={"x": "ilan sayısı", "y": ""},
                title=f"{country_label} — en çok aranan beceriler",
                color_discrete_sequence=[BAR_COLOR],
            )
            apply_chart_theme(fig)
            st.plotly_chart(fig, width="stretch")

        st.divider()

        # --- 3) Trend: yükselen vs düşen ---
        st.markdown("### Trend — yükselen ↑ / düşen ↓")
        ctrends = cached_trends(cjobs)
        if ctrends.empty:
            st.warning("Trend hesabı için yeterli tarihli veri yok.")
        else:
            ctdf = ctrends.copy()
            ctdf["delta_puan"] = (ctdf["delta"] * 100).round(1)
            c_rising = ctdf[ctdf["delta"] > 0].head(top_n // 2)
            c_falling = ctdf[ctdf["delta"] < 0].tail(top_n // 2)

            combo = pd.concat([c_falling, c_rising]).sort_values("delta_puan")
            if not combo.empty:
                fig = px.bar(
                    combo, x="delta_puan", y="skill", orientation="h",
                    color=combo["delta_puan"] > 0,
                    color_discrete_map={True: BAR_RISE_COLOR, False: BAR_FALL_COLOR},
                    labels={"delta_puan": "Δ yüzde puan (son dönem - ilk dönem)", "skill": ""},
                    title=f"{country_label} — yaygınlık değişimi",
                )
                apply_chart_theme(fig, show_legend=False)
                st.plotly_chart(fig, width="stretch")

            ccol1, ccol2 = st.columns(2)
            with ccol1:
                st.markdown("**Yükselen**")
                st.dataframe(
                    c_rising[["skill", "delta_puan"]].rename(columns={"skill": "beceri", "delta_puan": "Δ yüzde puan"}),
                    hide_index=True, width="stretch",
                )
            with ccol2:
                st.markdown("**Düşen**")
                st.dataframe(
                    c_falling[["skill", "delta_puan"]].rename(columns={"skill": "beceri", "delta_puan": "Δ yüzde puan"}),
                    hide_index=True, width="stretch",
                )


# ===========================================================================
# SEKME 3 — KARİYER EŞLEŞTİRİCİ
# ===========================================================================
with tab_match:
    st.markdown(section_header("Kariyer Eşleştirici", "crosshair"), unsafe_allow_html=True)
    st.caption(
        "Becerilerini gir; hangi ilanlara uyduğunu, eksiklerini ve "
        "kişiselleştirilmiş kariyer tavsiyeni gör."
    )

    TARGETS = {"Tümü": ALL, "UK": "gb", "US": "us", "Türkiye": "tr"}
    mc1, mc2 = st.columns([3, 1])
    with mc1:
        raw_skills = st.text_area(
            "Becerilerinizi girin (virgülle ayırın)",
            value=st.session_state.get("match_raw", ""),
            placeholder="Python, SQL, TensorFlow, Docker",
            height=80,
        )
    with mc2:
        target_label = st.selectbox("Hedef ülke", list(TARGETS), key="match_target")

    target_role = st.text_input(
        "🎯 Hedef mesleğiniz (isteğe bağlı)",
        value=st.session_state.get("match_role", ""),
        placeholder="örn. Data Engineer, Backend Developer, PLC Engineer",
    ).strip()

    # --- 📋 Desteklenen becerileri kategori kategori göster (filtreli) ---
    with st.expander(f"Desteklenen becerileri gör ({len(SKILLS)} beceri, {len(SKILL_CATEGORIES)} kategori)"):
        flt = st.text_input(
            "Listede ara", key="skill_browser_filter",
            placeholder="ör. aws, kafka, react...",
        ).strip().lower()
        any_shown = False
        for cat, cat_skills in SKILL_CATEGORIES.items():
            names = sorted(cat_skills)
            if flt:
                names = [n for n in names if flt in n or any(flt in v for v in cat_skills[n])]
            if not names:
                continue
            any_shown = True
            st.markdown(f"**{cat}** ({len(names)})")
            st.caption(" · ".join(names))
        if flt and not any_shown:
            st.info(f"'{flt}' ile eşleşen beceri yok.")

    if st.button("🎯 Eşleştir", type="primary"):
        expanded = _expand_shorts(raw_skills)
        recognized, unknown = recognize_skills(expanded)
        st.session_state["match_raw"] = raw_skills
        st.session_state["match_role"] = target_role
        st.session_state["match_user"] = recognized
        st.session_state["match_unknown"] = unknown
        st.session_state["match_target_label"] = target_label
        st.session_state.pop("career_advice", None)
        st.session_state.pop("role_comment", None)
        st.session_state["match_result"] = (
            compute_career_match(recognized, jobs, stats["per_job"], TARGETS[target_label])
            if recognized else None
        )
        if recognized and target_role:
            st.session_state["role_scores"] = compute_role_skill_scores(recognized, jobs, target_role)
        else:
            st.session_state.pop("role_scores", None)

    user_skills = st.session_state.get("match_user", set())
    unknown_skills = st.session_state.get("match_unknown", [])
    result = st.session_state.get("match_result")

    if "match_result" not in st.session_state:
        st.info("Becerilerini girip **🎯 Eşleştir**'e bas.")
    elif not user_skills:
        # Hiçbiri tanınmadı -> kırmızı hata
        st.error(
            "❌ Girdiğiniz becerilerden hiçbiri listemizde bulunamadı"
            + (f": {', '.join(unknown_skills)}." if unknown_skills else ".")
            + " Desteklenen becerileri görmek için yukarıdaki **📋 Desteklenen "
            "becerileri gör** bölümünü açın. Örnek: Python, SQL, AWS, React."
        )
    elif result:
        # Bir kısmı tanınmadıysa -> sarı uyarı (analiz yine de devam eder)
        if unknown_skills:
            st.warning(
                "⚠️ Şu beceriler listemizde bulunamadı: "
                f"**{', '.join(unknown_skills)}**. Desteklenen becerileri görmek için "
                "yukarıdaki **📋 Desteklenen becerileri gör** bölümüne tıklayın. "
                "Tanınan becerilerle analiz aşağıda sürüyor."
            )
        st.success("Tanınan beceriler: " + ", ".join(sorted(user_skills)))

        # --- 1) En çok eşleşen 10 ilan ---
        st.markdown("### 🔝 En çok eşleşen 10 ilan")
        top10 = result["matches"][:10]
        if not top10:
            st.info("Bu becerilerle eşleşen ilan bulunamadı. Hedef ülkeyi değiştirmeyi dene.")
        else:
            for m in top10:
                st.markdown(
                    match_card(
                        title=m["title"],
                        company=m["company"],
                        country=m["country"],
                        pct=m["coverage"] * 100,
                        matched=m["matched"],
                        missing=m["missing"],
                    ),
                    unsafe_allow_html=True,
                )

        st.divider()

        # --- 2) Skill gap özeti ---
        st.markdown("### 📉 Skill gap — bu profille en çok eksik kalan beceriler")
        if result["top_gap"]:
            gap_df = pd.DataFrame(
                [{"beceri": s, "kapı açacağı ilan": n} for s, n in result["top_gap"]]
            )
            gcol1, gcol2 = st.columns([1, 1])
            with gcol1:
                st.dataframe(gap_df, hide_index=True, width="stretch")
            with gcol2:
                fig = px.bar(
                    gap_df.sort_values("kapı açacağı ilan"),
                    x="kapı açacağı ilan", y="beceri", orientation="h",
                    color_discrete_sequence=[BAR_RISE_COLOR],
                )
                apply_chart_theme(fig, height=220)
                st.plotly_chart(fig, width="stretch")
            st.caption("Bu becerileri öğrenirsen, karşılarındaki kadar ek ilana uygun hale gelirsin.")
        else:
            st.info("Eksik beceri yok — bu hedef için güçlü bir profil!")

        # --- 3) Hedef meslek analizi ---
        role_scores_data = st.session_state.get("role_scores")
        saved_role = st.session_state.get("match_role", "")
        if role_scores_data and saved_role:
            st.divider()
            n_role = role_scores_data["n_role_jobs"]
            if n_role == 0:
                st.warning(f"**{saved_role}** ile eşleşen ilan bulunamadı. Başlık yazımını kontrol et.")
            else:
                st.markdown(f"### 🎯 {saved_role} — beceri analizi ({n_role} ilan)")
                scores = role_scores_data["scores"]
                top_missing = role_scores_data["top_missing"]

                for row in scores:
                    stars, label = _stars(row["pct"])
                    st.markdown(
                        f"**{row['skill']}** &nbsp; → &nbsp; %{row['pct']:.0f} &nbsp; "
                        f"{stars} &nbsp; *({label})*",
                        unsafe_allow_html=False,
                    )

                if top_missing:
                    st.caption(
                        "Bu roldeki en çok aranan eksik beceriler: "
                        + ", ".join(f"`{s}`" for s in top_missing[:6])
                    )

                if HAS_GEMINI and gemini_available():
                    if st.button("💬 Role özgü Gemini yorumu al", key="role_comment_btn"):
                        with st.spinner("Gemini düşünüyor..."):
                            try:
                                st.session_state["role_comment"] = generate_role_commentary(
                                    saved_role, scores, top_missing
                                )
                            except Exception as e:
                                st.error(f"Gemini hatası: {e}")
                    comment = st.session_state.get("role_comment")
                    if comment:
                        with st.container(border=True):
                            st.markdown(f"**🤖 {saved_role} için Gemini yorumu**")
                            st.write(comment)

        st.divider()

        # --- 4) Gemini kariyer tavsiyesi (kartlar) ---
        st.markdown("### 🤖 Gemini kariyer tavsiyesi")
        if not HAS_GEMINI:
            st.info("🚧 Gemini modülü bulunamadı.")
        elif not gemini_available():
            st.warning("`GEMINI_API_KEY` tanımlı değil (.env'de olmalı).")
        else:
            if st.button("✨ Kişiselleştirilmiş tavsiye üret", key="career_btn"):
                seen_co: list[str] = []
                for m in result["matches"]:
                    if m["company"] and m["company"] != "—" and m["company"] not in seen_co:
                        seen_co.append(m["company"])
                    if len(seen_co) >= 8:
                        break
                profile = {
                    "skills": sorted(user_skills),
                    "target": st.session_state.get("match_target_label", "Tümü"),
                    "missing": [{"skill": s, "jobs": n} for s, n in result["top_gap"]],
                    "sample_titles": [m["title"] for m in result["matches"][:5]],
                    "companies": seen_co,
                }
                with st.spinner("Gemini düşünüyor..."):
                    try:
                        st.session_state["career_advice"] = generate_career_advice(profile)
                    except Exception as e:
                        st.error(f"Gemini hatası: {e}")

            advice = st.session_state.get("career_advice")
            if advice:
                render_career_advice(advice)
                st.caption("Sonuç cache'lendi; aynı profil tekrar sorgulanırsa API'ye gidilmez.")


# ===========================================================================
# SEKME 4 — ÖNERİLER (Gemini Flash)
# ===========================================================================
with tab_advice:
    st.markdown(section_header("Trend yorumları (Gemini Flash)", "lightning"), unsafe_allow_html=True)
    if not HAS_GEMINI:
        st.info("🚧 Gemini entegrasyonu Phase 2 Adım 4'te ekleniyor.")
    elif not gemini_available():
        st.warning(
            "`GEMINI_API_KEY` ortam değişkeni tanımlı değil. "
            "https://aistudio.google.com/apikey adresinden ücretsiz key al ve "
            "`export GEMINI_API_KEY=...` ile tanımlayıp Streamlit'i yeniden başlat."
        )
    elif trends.empty:
        st.warning("Trend verisi olmadan öneri üretilemez.")
    else:
        st.caption(
            "Her yükselen/düşen beceri için Gemini Flash kısa bir insight üretir. "
            "Sonuç session içinde cache'lenir; her tıklamada API'ye gidilmez."
        )
        n_insights = st.slider("Kaç trend yorumlansın?", 3, 10, 5)
        if st.button("✨ Insight üret", type="primary"):
            with st.spinner("Gemini düşünüyor..."):
                try:
                    st.session_state["insights"] = generate_insights(trends, top_n=n_insights)
                except Exception as e:
                    st.error(f"Gemini hatası: {e}")

        for item in st.session_state.get("insights", []):
            st.markdown(
                insight_card(item["skill"], item["delta"], item["insight"]),
                unsafe_allow_html=True,
            )


# ===========================================================================
# SEKME 5 — RAKİP ZEKÂSI (otonomgit'in tüm sayfaları)
# ===========================================================================
with tab_rakip:
    render_rakip_zekasi()


st.divider()
st.caption(
    "SkillPulse · source-agnostic mimari · frekans sayımı C/ctypes ile · "
    f"kaynaklar: {', '.join(sources.index)}"
)
