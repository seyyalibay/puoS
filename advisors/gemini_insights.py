"""
gemini_insights.py — Trend başına kısa LLM içgörüsü (Phase 2).

Sağlayıcı: BİRİNCİL Gemini (gemini-2.5-flash), YEDEK Groq (llama-3.3-70b).
        Tüm çağrılar _run() üzerinden gider; Gemini key'leri sırayla denenir,
        hepsi başarısız olursa Groq devreye girer.
        NOT: gemini-flash-latest (→3.5-flash) sürekli 504/kota verdiği için
        gemini-2.5-flash'a geçildi (stabil, ~1-2 sn).
Key   : GEMINI_API_KEY / GEMINI_API_KEY_2.. (rotasyon) + GROQ_API_KEY (yedek)

Tasarım kararları:
    - TEK API çağrısı: tüm trendler tek prompt'ta gönderilir, JSON listesi
      istenir. Trend başına ayrı çağrı hem yavaş hem kota israfı olurdu.
    - ALTIN KURAL'ın LLM hali: üretilen insight'lar data/insights.json'a
      cache'lenir; aynı (skill, delta) için API'ye TEKRAR GİDİLMEZ.
    - response_mime_type="application/json" ile model JSON'a zorlanır;
      yine de bozuk dönerse tek tek ayıklamayı dener.

API (app.py bunları kullanır):
    gemini_available() -> bool
    generate_insights(trends: pd.DataFrame, top_n: int = 5) -> list[dict]
        # her eleman: {"skill": str, "delta": float, "insight": str}
"""
import hashlib
import json
import os
import re

import pandas as pd

# gemini-flash-latest şu an gemini-3.5-flash'a gidiyor ve sürekli 504/kota veriyor.
# gemini-2.5-flash stabil ve hızlı (test: 1-2 sn, JSON modu çalışıyor).
GEMINI_MODEL = "gemini-2.5-flash"

# Tek bir generate_content çağrısının toplam süre sınırı (saniye). Bu olmadan
# SDK, 429 (kota) gibi durumlarda otomatik yeniden-deneme/backoff yaptığından
# spinner dakikalarca "düşünüyor..." diye asılı kalabiliyordu.
_REQUEST_TIMEOUT = 30

# Yedekli API key'leri sırayla okunur. Birincisi (GEMINI_API_KEY) kota dolarsa
# istek otomatik olarak GEMINI_API_KEY_2 / _3 ... ile TEKRAR denenir. Böylece
# bir key'in dakikalık kotası dolunca kullanıcı beklemeden diğeriyle devam eder.
# .env'e GEMINI_API_KEY_N ekledikçe burada DEĞİŞİKLİK GEREKMEZ; otomatik bulunur.
def _api_keys() -> list[str]:
    """Tanımlı tüm Gemini key'lerini sırayla, tekrarsız döndürür (boşları atar).

    Önce GEMINI_API_KEY, ardından GEMINI_API_KEY_2, _3, ... şeklinde sayıca artan
    tüm değişkenleri tarar (ilk boşlukta durur)."""
    keys: list[str] = []
    primary = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if primary:
        keys.append(primary)
    n = 2
    while True:
        v = (os.environ.get(f"GEMINI_API_KEY_{n}") or "").strip()
        if not v:
            break
        if v not in keys:
            keys.append(v)
        n += 1
    return keys


def _is_quota_error(e: Exception) -> bool:
    name, msg = type(e).__name__, str(e).lower()
    return name == "ResourceExhausted" or "429" in str(e) or "quota" in msg or "rate limit" in msg


# ── Groq yedek sağlayıcısı ───────────────────────────────────────────────────
# Gemini'nin TÜM key'leri başarısız olursa (504/kota/expired) analizi Groq üretir.
# OpenAI-uyumlu endpoint olduğu için tek bir HTTP çağrısı yeterli.
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class _GenResult:
    """generate_content çıktısını taklit eder: çağrı yerleri sadece .text okur."""
    def __init__(self, text: str):
        self.text = text


def _groq_available() -> bool:
    return bool((os.environ.get("GROQ_API_KEY") or "").strip())


def _call_groq(generation_config: dict, prompt: str) -> _GenResult:
    """Groq (llama-3.3-70b) ile tek istek; Gemini ile aynı arabirimi döndürür."""
    import requests

    body = {
        "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": generation_config.get("temperature", 0.4),
    }
    # Gemini JSON modunun Groq karşılığı
    if generation_config.get("response_mime_type") == "application/json":
        body["response_format"] = {"type": "json_object"}
    resp = requests.post(
        _GROQ_URL,
        headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY'].strip()}",
                 "Content-Type": "application/json"},
        json=body,
        timeout=_REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return _GenResult(resp.json()["choices"][0]["message"]["content"])


def _run(generation_config: dict, prompt):
    """Tüm AI çağrılarının tek girişi. BİRİNCİL sağlayıcı GEMINI'dir.

    Önce Gemini key'leri sırayla denenir (kota/expired/504 olursa diğerine geçer);
    hepsi başarısız olursa YEDEK olarak Groq devreye girer. Hiçbiri çalışmazsa
    anlaşılır bir mesaj fırlatır. Her çağrı timeout ile sınırlıdır.
    """
    errors: list[Exception] = []

    # 1) BİRİNCİL: Gemini key rotasyonu
    keys = _api_keys()
    if keys:
        import google.generativeai as genai
        for key in keys:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(GEMINI_MODEL, generation_config=generation_config)
            try:
                return model.generate_content(prompt, request_options={"timeout": _REQUEST_TIMEOUT})
            except Exception as e:
                errors.append(e)
                continue

    # 2) YEDEK: Groq (Gemini'nin tümü başarısız olursa)
    if _groq_available():
        try:
            return _call_groq(generation_config, prompt)
        except Exception as ge:
            errors.append(ge)

    if not errors:
        raise RuntimeError("Ne GEMINI_API_KEY ne GROQ_API_KEY tanımlı değil.")
    if all(_is_quota_error(e) for e in errors):
        raise RuntimeError(
            "Tüm sağlayıcılar kota sınırına takıldı. ~1 dakika bekleyip tekrar dene."
        ) from errors[-1]
    detay = "; ".join(f"{type(e).__name__}" for e in errors)
    raise RuntimeError(
        f"Hiçbir AI sağlayıcısı yanıt vermedi ({detay}). "
        "Key'lerin geçerli/aktif olduğunu kontrol et."
    ) from errors[-1]

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
_CACHE_PATH = os.path.join(_DATA_DIR, "insights.json")
_CAREER_CACHE_PATH = os.path.join(_DATA_DIR, "career_cache.json")
_QUERY_CACHE_PATH = os.path.join(_DATA_DIR, "query_translations.json")

_PROMPT = """Sen bir teknoloji işgücü piyasası analistisin. Aşağıda iş ilanlarından
çıkarılmış beceri trendleri var. delta = becerinin geçtiği ilan oranındaki değişim
(yüzde puan; ilk dönemler vs son dönemler). Pozitif = yükseliyor, negatif = düşüyor.

Her beceri için TÜRKÇE, 1-2 cümlelik, somut bir içgörü yaz. Format:
"X yükseliyor/düşüyor çünkü ..." gibi; sektör bilgine dayan, uydurma istatistik verme.
Kariyer planlayan bir geliştiriciye ne anlama geldiğini söyle.

Trendler:
{trends_json}

SADECE şu şemada bir JSON listesi döndür:
[{{"skill": "...", "insight": "..."}}, ...]
"""


def gemini_available() -> bool:
    # Gemini key'i VEYA Groq yedeği varsa AI özellikleri aktiftir.
    return bool(_api_keys()) or _groq_available()


def _parse_json(text: str):
    """Gemini yanıtından JSON ayrıştır.
    Model bazen ```json ... ``` bloğu veya fazladan metin döndürür; bunları temizler."""
    t = text.strip()
    # ```json ... ``` veya ``` ... ``` bloğunu soy
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t.rstrip())
        t = t.strip()
    # İlk [ veya { karakterinden başlat (öncesinde açıklama metni varsa at).
    # ÖNEMLİ: metinde HANGİSİ ÖNCE geliyorsa onu kök al. Aksi halde bir nesnenin
    # ({...}) içindeki ilk dizi (örn. "roller": [...]) yanlışlıkla kök sanılır ve
    # nesnenin geri kalanı (profil_ozeti, maas_ozeti...) kaybolur.
    candidates = []
    for sc, ec in [("[", "]"), ("{", "}")]:
        i = t.find(sc)
        if i != -1:
            candidates.append((i, sc, ec))
    candidates.sort()  # metinde en erken görünen parantez kök olur
    for _idx, start_char, end_char in candidates:
        idx = t.find(start_char)
        if idx != -1:
            # Eşleşen kapanış parantezini bul
            depth, in_str, escape = 0, False, False
            for i, ch in enumerate(t[idx:], idx):
                if escape:
                    escape = False
                    continue
                if ch == "\\" and in_str:
                    escape = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if not in_str:
                    if ch == start_char:
                        depth += 1
                    elif ch == end_char:
                        depth -= 1
                        if depth == 0:
                            return json.loads(t[idx:i + 1])
            break
    return json.loads(t)


def _cache_key(skill: str, delta: float) -> str:
    return f"{skill}|{round(delta * 100, 1):+.1f}"


def _load_cache() -> dict:
    if os.path.exists(_CACHE_PATH):
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _pick_trends(trends: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """En güçlü sinyalli top_n trend: |delta| büyükten küçüğe, stable hariç."""
    moving = trends[trends["direction"] != "stable"].copy()
    if moving.empty:
        moving = trends.copy()
    moving["abs_delta"] = moving["delta"].abs()
    return moving.sort_values("abs_delta", ascending=False).head(top_n)


def _call_gemini(items: list[dict]) -> dict[str, str]:
    """Tek çağrıda tüm beceriler için {skill: insight} döndürür."""
    prompt = _PROMPT.format(trends_json=json.dumps(items, ensure_ascii=False, indent=2))
    resp = _run({"response_mime_type": "application/json", "temperature": 0.4}, prompt)
    parsed = _parse_json(resp.text)
    if isinstance(parsed, dict):  # model bazen {"insights": [...]} sarar
        for v in parsed.values():
            if isinstance(v, list):
                parsed = v
                break
    return {
        str(row.get("skill", "")).lower(): str(row.get("insight", "")).strip()
        for row in parsed
        if isinstance(row, dict) and row.get("insight")
    }


def generate_insights(trends: pd.DataFrame, top_n: int = 5) -> list[dict]:
    """trend_scores() çıktısından top_n trend için insight listesi üretir.

    Disk cache'i (data/insights.json) önceliklidir; yalnızca cache'te olmayan
    beceriler için Gemini'ye TEK istek atılır.
    """
    if not gemini_available():
        raise RuntimeError("GEMINI_API_KEY ortam değişkeni tanımlı değil.")

    chosen = _pick_trends(trends, top_n)
    cache = _load_cache()

    results: list[dict] = []
    missing: list[dict] = []
    for _, row in chosen.iterrows():
        key = _cache_key(row["skill"], row["delta"])
        if key in cache:
            results.append({"skill": row["skill"], "delta": row["delta"], "insight": cache[key]})
        else:
            missing.append({
                "skill": row["skill"],
                "delta_yuzde_puan": round(row["delta"] * 100, 1),
                "yon": "yükseliyor" if row["delta"] > 0 else "düşüyor",
            })

    if missing:
        insights = _call_gemini(missing)
        for item in missing:
            skill = item["skill"]
            text = insights.get(skill.lower())
            if not text:
                continue
            delta = float(chosen.loc[chosen["skill"] == skill, "delta"].iloc[0])
            cache[_cache_key(skill, delta)] = text
            results.append({"skill": skill, "delta": delta, "insight": text})
        _save_cache(cache)

    # Görüntü sırası: |delta| büyükten küçüğe
    results.sort(key=lambda r: abs(r["delta"]), reverse=True)
    return results


# ===========================================================================
# KARİYER EŞLEŞTİRİCİ — profil bazlı tek seferlik kariyer tavsiyesi
# ===========================================================================
# Cache format sürümü — şema değişince ESKİ cache geçersiz kalsın diye anahtara katılır.
_CAREER_FMT = "v2"

_CAREER_PROMPT = """Sen deneyimli bir teknoloji kariyer danışmanısın. Bir geliştiricinin
beceri profilini ve iş ilanı verisine dayalı analizi değerlendir.

Beceriler: {skills}
Hedef pazar: {target}
İlan talebine göre en çok eksik kalan beceriler (kaç ilana kapı açacağı):
{missing}
Ülke bazında uygunluk oranı (ilanların yüzde kaçında beceriler yeterli):
{country_match}
En iyi eşleşen örnek ilan başlıkları:
{titles}
Veride öne çıkan şirketler:
{companies}

SADECE aşağıdaki şemada, TÜRKÇE, AYRINTILI bir JSON döndür. Uydurma istatistik verme;
sayıları yukarıdaki analizden al, maaş aralıklarını güncel sektör bilgine dayandır:
{{
  "profil_ozeti": "güçlü yönler + mevcut pozisyon analizi (2-3 cümle)",
  "roller": [
    {{"unvan": "rol adı", "uyum": "%78", "neden": "neden uygun (1 cümle)",
      "eksik": ["eksik beceri 1", "eksik beceri 2"],
      "maas_potansiyeli": "UK: £65-80k, US: $110-130k"}}
  ],
  "yol_haritasi": {{
    "3_ay": {{"beceri": "...", "neden": "...", "nasil": "somut kaynak/yöntem"}},
    "6_ay": {{"beceri": "...", "neden": "...", "nasil": "..."}},
    "12_ay": {{"beceri": "...", "neden": "...", "nasil": "..."}}
  }},
  "maas_ozeti": {{"UK": "£60-85k", "US": "$110-140k", "TR": "110-160k₺"}},
  "pazar_analizi": {{"en_iyi_pazar": "UK | US | TR", "neden": "veriye dayalı gerekçe",
                     "rekabet": "rakiplere göre durum/kritik eksik"}},
  "hedef_sirketler": [{{"sirket": "şirket adı", "neden": "stack/konum/tier gerekçesi"}}],
  "guclu_yonler": ["kısa madde", "kısa madde"],
  "gelistirilecek": ["kısa madde", "kısa madde"]
}}
Kurallar: roller TAM 3 tane; yol_haritasi 3/6/12 ay üç adım; hedef_sirketler 3-5;
en uygun role göre uyum yüzdesi ver; maas_ozeti profilin genel potansiyeli (ülke bazlı)."""


def _career_key(profile: dict) -> str:
    """Aynı profil (beceriler + hedef pazar + format sürümü) için kararlı anahtar."""
    payload = json.dumps(
        {"skills": sorted(profile.get("skills", [])),
         "target": profile.get("target", ""), "fmt": _CAREER_FMT},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _load_career_cache() -> dict:
    if os.path.exists(_CAREER_CACHE_PATH):
        with open(_CAREER_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_career_cache(cache: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_CAREER_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _s(v) -> str:
    return str(v if v is not None else "").strip()


def _norm_step(d) -> dict:
    d = d if isinstance(d, dict) else {}
    return {"beceri": _s(d.get("beceri")), "neden": _s(d.get("neden")), "nasil": _s(d.get("nasil"))}


def _normalize_career(data: dict) -> dict:
    """Gemini çıktısını eksiksiz/savunmacı şekilde yeni detaylı şemaya oturtur."""
    roller = []
    for r in data.get("roller", []) or []:
        if not isinstance(r, dict) or not _s(r.get("unvan")):
            continue
        roller.append({
            "unvan": _s(r.get("unvan")),
            "uyum": _s(r.get("uyum")),
            "neden": _s(r.get("neden")),
            "eksik": [_s(x) for x in (r.get("eksik") or []) if _s(x)],
            "maas_potansiyeli": _s(r.get("maas_potansiyeli")),
        })
    sirketler = []
    for c in data.get("hedef_sirketler", []) or []:
        if isinstance(c, dict) and _s(c.get("sirket")):
            sirketler.append({"sirket": _s(c.get("sirket")), "neden": _s(c.get("neden"))})
    yh = data.get("yol_haritasi", {}) or {}
    pa = data.get("pazar_analizi", {}) or {}
    maas = data.get("maas_ozeti", {}) or {}
    return {
        "profil_ozeti": _s(data.get("profil_ozeti")),
        "roller": roller[:3],
        "yol_haritasi": {k: _norm_step(yh.get(k)) for k in ("3_ay", "6_ay", "12_ay")},
        "maas_ozeti": {k: _s(maas.get(k)) for k in ("UK", "US", "TR")},
        "pazar_analizi": {
            "en_iyi_pazar": _s(pa.get("en_iyi_pazar")),
            "neden": _s(pa.get("neden")),
            "rekabet": _s(pa.get("rekabet")),
        },
        "hedef_sirketler": sirketler[:5],
        "guclu_yonler": [_s(x) for x in (data.get("guclu_yonler") or []) if _s(x)],
        "gelistirilecek": [_s(x) for x in (data.get("gelistirilecek") or []) if _s(x)],
    }


def _call_gemini_career(profile: dict) -> dict:
    missing = "\n".join(
        f"- {m['skill']} ({m['jobs']} ilan)" for m in profile.get("missing", [])
    ) or "- (yok)"
    country_match = "\n".join(
        f"- {k}: %{v}" for k, v in profile.get("country_match", {}).items()
    ) or "- (veri yok)"
    titles = "\n".join(f"- {t}" for t in profile.get("sample_titles", [])) or "- (yok)"
    companies = "\n".join(f"- {c}" for c in profile.get("companies", [])) or "- (yok)"
    prompt = _CAREER_PROMPT.format(
        skills=", ".join(profile.get("skills", [])) or "(girilmedi)",
        target=profile.get("target", "Tümü"),
        missing=missing, country_match=country_match, titles=titles, companies=companies,
    )
    data = _parse_json(
        _run({"response_mime_type": "application/json", "temperature": 0.5}, prompt).text
    )
    if isinstance(data, list) and data:  # model bazen listeye sarar
        data = data[0]
    return _normalize_career(data)


def generate_career_advice(profile: dict) -> dict:
    """Profil (beceriler + analiz) için Gemini kariyer tavsiyesi üretir.

    Disk cache'i (data/career_cache.json) önceliklidir: AYNI profil (beceriler +
    hedef pazar) tekrar sorgulanırsa API'ye GİTMEZ.
    """
    if not gemini_available():
        raise RuntimeError("GEMINI_API_KEY ortam değişkeni tanımlı değil.")
    key = _career_key(profile)
    cache = _load_career_cache()
    if key in cache:
        return cache[key]
    result = _call_gemini_career(profile)
    cache[key] = result
    _save_career_cache(cache)
    return result


# ===========================================================================
# ROLE ÖZGÜ BECERİ YORUMU
# ===========================================================================
_ROLE_COMMENT_FMT = "v1"
_ROLE_COMMENT_CACHE_PATH = os.path.join(_DATA_DIR, "role_comment_cache.json")

_ROLE_COMMENT_PROMPT = """Sen bir teknoloji kariyer danışmanısın.

Hedef rol: {role}
Kullanıcının becerileri ve bu roldeki ilanlar içindeki yaygınlık oranı:
{skill_scores}
Bu roldeki en çok aranan, kullanıcıda OLMAYAN beceriler:
{top_missing}

TÜRKÇE, 3-5 cümle, somut ve kişiselleştirilmiş bir yorum yaz:
1. Mevcut becerilerin bu rol için değeri
2. Role özgü öncelikli geliştirme alanları
3. Genel konumlandırma değerlendirmesi

SADECE düz metin döndür, JSON değil."""


def _role_comment_key(role: str, skills_with_pct: list[dict]) -> str:
    payload = json.dumps(
        {"role": role.lower(), "scores": sorted((s["skill"], round(s["pct"])) for s in skills_with_pct),
         "fmt": _ROLE_COMMENT_FMT},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def generate_role_commentary(role: str, skill_scores: list[dict], top_missing: list[str]) -> str:
    """Hedef role göre kullanıcının beceri profilini yorumlar.

    skill_scores: [{"skill": str, "pct": float}, ...] (kullanıcının becerileri + yaygınlık)
    top_missing: bu roldeki en çok aranan, kullanıcıda olmayan beceriler listesi
    Disk cache'i önceliklidir.
    """
    if not gemini_available():
        raise RuntimeError("GEMINI_API_KEY ortam değişkeni tanımlı değil.")

    cache = {}
    if os.path.exists(_ROLE_COMMENT_CACHE_PATH):
        with open(_ROLE_COMMENT_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
    key = _role_comment_key(role, skill_scores)
    if key in cache:
        return cache[key]

    scores_txt = "\n".join(f"- {s['skill']}: %{s['pct']:.0f}" for s in skill_scores)
    missing_txt = "\n".join(f"- {m}" for m in top_missing[:5]) or "- (yok)"
    prompt = _ROLE_COMMENT_PROMPT.format(
        role=role, skill_scores=scores_txt, top_missing=missing_txt
    )
    text = _run({"temperature": 0.4}, prompt).text.strip()
    cache[key] = text
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_ROLE_COMMENT_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    return text


# ===========================================================================
# SORGU ÇEVİRİSİ — arama sorgusunu pazara göre dile çevir (EN ↔ TR)
# ===========================================================================
def _clean_roles(value, primary: str) -> list:
    """Gemini'den gelen rol listesini temizler: string'e çevir, boşları/tekrarları
    at, en başa birincil terimi koy. Hep en az [primary] döner."""
    out = []
    if isinstance(value, list):
        for v in value:
            s = str(v).strip()
            if s:
                out.append(s)
    elif isinstance(value, str):
        out = [s.strip() for s in value.split(",") if s.strip()]
    # birincil terim her zaman ilk sırada ve listede tekil olsun
    seen, ordered = set(), []
    for term in [primary, *out]:
        low = term.lower()
        if term and low not in seen:
            seen.add(low)
            ordered.append(term)
    return ordered or [primary]


def translate_query(text: str) -> dict:
    """İş arama sorgusunu tech iş piyasası bağlamında çevirir. Döner:
    {"en", "tr", "roles_en", "roles_tr"} — en/tr aramada kullanılacak BİRİNCİL
    (en alakalı) tech terim; roles_* ise ilişkili tech rollerinin listesi (ilk
    eleman birincil terimle aynıdır, gerisi bilgi amaçlı UI'da gösterilir).

    Diske (data/query_translations.json) cache'lenir; aynı sorgu tekrar gelirse
    API'ye GİTMEZ. Eski (roles_* içermeyen) cache kayıtları ilk kullanımda otomatik
    yeniden çevrilir. Gemini yoksa/çağrı patlarsa girilen metin aynen döner
    (güvenli geri düşüş — arama yine de çalışır).
    """
    raw = (text or "").strip()
    if not raw:
        return {"en": "", "tr": "", "roles_en": [], "roles_tr": []}
    if not gemini_available():
        return {"en": raw, "tr": raw, "roles_en": [raw], "roles_tr": [raw]}

    norm = raw.lower()
    cache = {}
    if os.path.exists(_QUERY_CACHE_PATH):
        with open(_QUERY_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
    # Yeni şema rol listesi de içerir; eski kayıt eksikse yeniden çevirelim.
    cached = cache.get(norm)
    if cached and "roles_en" in cached and "roles_tr" in cached:
        return cached

    try:
        prompt = (
            "Sen bir iş piyasası arama asistanısın. Verilen sorgu için, iş ilanı "
            "sitelerinde aramaya yarayacak kısa ve doğru terimler üret.\n\n"
            "KRİTİK KURAL — SEKTÖR BAĞLAMI:\n"
            "Mühendislik terimleri MUTLAKA fiziksel/endüstriyel bağlamda çevrilmeli, "
            "yazılım bağlamında DEĞİL. Örnekler:\n"
            "  'otomasyon mühendisi' → 'industrial automation engineer' (YANLIŞ: 'software automation engineer')\n"
            "  'kontrol mühendisi'   → 'control systems engineer'        (YANLIŞ: 'qa engineer')\n"
            "  'üretim mühendisi'    → 'manufacturing engineer'           (YANLIŞ: 'production software engineer')\n"
            "  'mekatronik mühendisi'→ 'mechatronics engineer'\n"
            "  'elektrik mühendisi'  → 'electrical engineer'\n"
            "  'makine mühendisi'    → 'mechanical engineer'\n"
            "  'inşaat mühendisi'    → 'civil engineer'\n"
            "  'kimya mühendisi'     → 'chemical engineer'\n\n"
            "DİĞER KURALLAR:\n"
            "- Sorgu zaten bir tech rol/teknoloji ise (developer, veri bilimci, "
            "react, devops...) doğrudan yaygın iş-başlığına çevir.\n"
            "- Sorgu tech-DIŞI bir meslek ise (aşçı, doktor, avukat, çiftçi...) "
            "literal çevirme; ilişkili sektör/tech rollerini ver. Örnekler: "
            "aşçı → ['food tech'], doktor → ['health tech', 'medtech'], "
            "avukat → ['legal tech'], çiftçi → ['agritech'].\n"
            "'en'/'tr' alanı ARAMADA kullanılacak EN ALAKALI tek terim; "
            "'roles_en'/'roles_tr' ilişkili terimler listesi (her biri 1-3 kelime).\n"
            'SADECE şu JSON: {"en": "...", "tr": "...", '
            '"roles_en": ["...", "..."], "roles_tr": ["...", "..."]}\n'
            f"Sorgu: {raw}"
        )
        data = _parse_json(
            _run({"response_mime_type": "application/json", "temperature": 0.0}, prompt).text
        )
        roles_en = _clean_roles(data.get("roles_en"), str(data.get("en", raw)).strip() or raw)
        roles_tr = _clean_roles(data.get("roles_tr"), str(data.get("tr", raw)).strip() or raw)
        result = {
            "en": roles_en[0],
            "tr": roles_tr[0],
            "roles_en": roles_en,
            "roles_tr": roles_tr,
        }
    except Exception:
        # çeviri başarısızsa aramayı engelleme
        return {"en": raw, "tr": raw, "roles_en": [raw], "roles_tr": [raw]}

    cache[norm] = result
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_QUERY_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    return result
