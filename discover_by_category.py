#!/usr/bin/env python3
"""
discover_by_category.py — Domain başına skill discovery + skills.py güncelleme.

fetch_discovery_corpus.py tarafından çekilen data/discovery/*.json dosyalarını
okur; her domain için top-30 yeni skill çıkarır; Türkçe varyant ekler ve
skills.py'yi günceller.

Kullanım:
    python3 discover_by_category.py               # analiz + güncelle
    python3 discover_by_category.py --dry-run     # sadece raporla
    python3 discover_by_category.py --min-df 5    # eşik (varsayılan: 5)
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from skills import SKILLS

try:
    from advisors.gemini_insights import gemini_available
    try:
        import google.generativeai as genai
        _HAS_GEMINI = gemini_available()
    except ImportError:
        _HAS_GEMINI = False
except ImportError:
    _HAS_GEMINI = False

# ── CLI ────────────────────────────────────────────────────────────────────────
DRY_RUN = "--dry-run" in sys.argv
MIN_DF  = 5
for i, arg in enumerate(sys.argv):
    if arg == "--min-df" and i + 1 < len(sys.argv):
        MIN_DF = int(sys.argv[i + 1])

DISCOVERY_DIR = Path(__file__).parent / "data" / "discovery"
SKILLS_FILE   = Path(__file__).parent / "skills.py"
TOP_N         = 30   # domain başına en fazla kaç skill eklensin

# ── Bağlam kalıpları (discover_skills.py ile aynı) ────────────────────────────
_END = r"(?=\s*[,.\n;()\[\]]|\s+and\s|\s+or\s|\Z)"
CONTEXT_PATTERNS: list[re.Pattern] = [
    re.compile(r"experience (?:with|in|of|using)\s+([A-Za-z][A-Za-z0-9 ./+#\-]{1,35}?)" + _END, re.I),
    re.compile(r"knowledge of\s+([A-Za-z][A-Za-z0-9 ./+#\-]{1,35}?)" + _END, re.I),
    re.compile(r"proficien(?:t|cy) (?:with|in)\s+([A-Za-z][A-Za-z0-9 ./+#\-]{1,35}?)" + _END, re.I),
    re.compile(r"familiarity with\s+([A-Za-z][A-Za-z0-9 ./+#\-]{1,35}?)" + _END, re.I),
    re.compile(r"expertise (?:with|in)\s+([A-Za-z][A-Za-z0-9 ./+#\-]{1,35}?)" + _END, re.I),
    re.compile(r"working with\s+([A-Za-z][A-Za-z0-9 ./+#\-]{1,35}?)" + _END, re.I),
    re.compile(r"hands[- ]on\s+(?:experience\s+with\s+)?([A-Za-z][A-Za-z0-9 ./+#\-]{1,35}?)" + _END, re.I),
    re.compile(r"skilled in\s+([A-Za-z][A-Za-z0-9 ./+#\-]{1,35}?)" + _END, re.I),
    re.compile(r"using\s+([A-Za-z][A-Za-z0-9 ./+#\-]{1,25}?)\s+(?:to\b|for\b)", re.I),
    re.compile(r"strong\s+(?:background|skills?) (?:in|with)\s+([A-Za-z][A-Za-z0-9 ./+#\-]{1,35}?)" + _END, re.I),
    re.compile(r"certification(?:s)? (?:in|with|for)\s+([A-Za-z][A-Za-z0-9 ./+#\-]{1,35}?)" + _END, re.I),
    # Basit isim + version kalıbı (Python 3, Java 17, .NET 8 vb.)
    re.compile(r"\b([A-Z][a-zA-Z0-9+#.\-]{2,20})\s+\d+(?:\.\d+)*\b"),
    # Bullet point sonrası teknik terim
    re.compile(r"(?:•|▪|→|\*|\-)\s*([A-Z][a-zA-Z0-9+#.\-]{2,30})\b"),
]

# ── Jenerik / gürültü kelimeleri ──────────────────────────────────────────────
_GENERIC: set[str] = {
    "the", "and", "or", "for", "with", "in", "of", "to", "a", "an",
    "be", "our", "your", "team", "company", "role", "good", "great",
    "strong", "excellent", "high", "full", "key", "core", "modern",
    "large", "fast", "complex", "various", "multiple", "different",
    "relevant", "related", "required", "preferred", "additional",
    "current", "latest", "new", "best", "other", "some", "one", "two",
    "design", "development", "testing", "support", "management",
    "delivery", "operations", "production", "performance", "quality",
    "service", "solution", "product", "project", "process", "model",
    "application", "infrastructure", "architecture", "proven", "solid",
    "broad", "deep", "extensive", "industry", "sector", "leading",
    "growing", "cutting", "edge", "rapidly", "highly", "senior",
    "junior", "mid", "level", "experienced", "skilled",
}
_TRAILING_NOISE = {
    "experience", "skills", "skill", "tools", "tool", "systems", "system",
    "technologies", "technology", "concepts", "principles", "practices",
    "practice", "frameworks", "framework", "environments", "environment",
    "methodologies", "methodology", "platforms", "platform",
}
_TECH_HINT = re.compile(r"\d|[.+#/]|(?:js|ts|sql|db|ml|ai|api|sdk|cli|ops)$", re.I)


def _clean(raw: str) -> str | None:
    t = raw.strip().lower()
    parts = t.split()
    while parts and parts[-1] in _TRAILING_NOISE:
        parts = parts[:-1]
    if not parts:
        return None
    t = " ".join(parts)
    if len(t) < 2 or len(t) > 40:
        return None
    if t in _GENERIC or all(p in _GENERIC for p in t.split()):
        return None
    if re.fullmatch(r"[\d\W]+", t):
        return None
    return t


def _is_tech(term: str) -> bool:
    t = term.lower()
    if _TECH_HINT.search(t):
        return True
    parts = t.split()
    if len(parts) == 1:
        return len(t) >= 3 and t not in _GENERIC
    return all(len(p) >= 2 for p in parts) and any(p not in _GENERIC for p in parts)


# ── Türkçe varyant sözlüğü ────────────────────────────────────────────────────
# Yaygın teknik terimlerin Türkçe karşılıkları. Burada olmayanlar için
# İngilizce terimin kendisi kullanılır.
_TR_MAP: dict[str, list[str]] = {
    # Yazılım genel
    "machine learning": ["makine öğrenmesi", "makine ogrenmesi"],
    "deep learning": ["derin öğrenme", "derin ogrenme"],
    "data science": ["veri bilimi"],
    "data analysis": ["veri analizi"],
    "data engineering": ["veri mühendisliği"],
    "data pipeline": ["veri ardışığı"],
    "artificial intelligence": ["yapay zeka", "yapay zeka mühendisliği"],
    "natural language processing": ["doğal dil işleme"],
    "computer vision": ["bilgisayarlı görü"],
    "reinforcement learning": ["pekiştirmeli öğrenme"],
    "business intelligence": ["iş zekası"],
    "version control": ["sürüm kontrolü"],
    "cybersecurity": ["siber güvenlik"],
    "cloud computing": ["bulut bilişim"],
    "agile": ["çevik geliştirme"],
    "scrum": ["scrum"],
    # Endüstriyel
    "automation": ["otomasyon"],
    "industrial automation": ["endüstriyel otomasyon"],
    "control systems": ["kontrol sistemleri"],
    "robotics": ["robotik"],
    "mechatronics": ["mekatronik"],
    # Mekanik
    "cad": ["bilgisayar destekli tasarım"],
    "finite element analysis": ["sonlu elemanlar analizi"],
    "heat transfer": ["ısı transferi"],
    "fluid dynamics": ["akışkanlar mekaniği"],
    # Elektrik
    "power electronics": ["güç elektroniği"],
    "signal processing": ["sinyal işleme"],
    "embedded systems": ["gömülü sistemler"],
    "firmware": ["donanım yazılımı", "firmware"],
    # Finans
    "quantitative analysis": ["nicel analiz"],
    "risk management": ["risk yönetimi"],
    "financial modeling": ["finansal modelleme"],
    "algorithmic trading": ["algoritmik trading"],
    # Sağlık
    "bioinformatics": ["biyoinformatik"],
    "medical imaging": ["tıbbi görüntüleme"],
    "health informatics": ["sağlık bilişimi"],
    # Kimya
    "process engineering": ["proses mühendisliği"],
    "chemical engineering": ["kimya mühendisliği"],
    # İnşaat
    "structural analysis": ["yapısal analiz"],
    "bim": ["yapı bilgi modellemesi"],
}


def _tr_variants(term: str) -> list[str]:
    """Terim için Türkçe varyant listesi döndürür. Bulunamazsa boş liste."""
    return _TR_MAP.get(term.lower(), [])


# ── Gemini ile toplu Türkçe çevirisi ─────────────────────────────────────────

def _gemini_translate_batch(terms: list[str]) -> dict[str, str]:
    """Gemini ile bir grup terimi Türkçeye çevirir. Başarısız olursa {} döner."""
    if not _HAS_GEMINI or not terms:
        return {}
    import os
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
        model = genai.GenerativeModel("gemini-2.0-flash")
        term_list = "\n".join(f"- {t}" for t in terms[:50])
        prompt = (
            "Aşağıdaki teknik terimlerin Türkçe karşılıklarını ver.\n"
            "Her satır için: İNGİLİZCE | TÜRKÇE formatını kullan.\n"
            "Türkçe karşılığı yoksa veya İngilizce kullanılıyorsa boş bırak.\n\n"
            + term_list
        )
        resp = model.generate_content(prompt)
        result: dict[str, str] = {}
        for line in (resp.text or "").splitlines():
            if "|" in line:
                parts = line.split("|", 1)
                eng = parts[0].strip("- ").strip().lower()
                tr  = parts[1].strip()
                if eng and tr:
                    result[eng] = tr
        return result
    except Exception:
        return {}


# ── Discovery per category ────────────────────────────────────────────────────

def extract_candidates(jobs: list[dict]) -> Counter:
    counts: Counter = Counter()
    for job in jobs:
        desc = (job.get("description") or "") + " " + (job.get("title") or "")
        seen: set[str] = set()
        for pat in CONTEXT_PATTERNS:
            for m in pat.finditer(desc):
                cand = _clean(m.group(1))
                if cand and cand not in seen:
                    seen.add(cand)
        counts.update(seen)
    return counts


def discover_for_category(
    cat: str, jobs: list[dict], variant_lookup: dict[str, str]
) -> list[tuple[str, int]]:
    """Kategori için yeni skill'leri keşfeder. Döner: [(term, doc_count), ...]"""
    candidates = extract_candidates(jobs)
    results = []
    for term, df in candidates.items():
        if df < MIN_DF:
            continue
        if term in variant_lookup:
            continue
        if not _is_tech(term):
            continue
        results.append((term, df))
    return sorted(results, key=lambda x: -x[1])[:TOP_N]


# ── skills.py yazma ────────────────────────────────────────────────────────────

# Kategori adları (domain → skills.py kategori etiketi)
CATEGORY_LABELS: dict[str, str] = {
    "software":    "Yazılım & Geliştirme 💻",
    "data":        "Veri & Analitik 📊",
    "industrial":  "Endüstriyel & Otomasyon 🏭",
    "mechanical":  "Mekanik & İmalat ⚙️",
    "electrical":  "Elektrik & Elektronik ⚡",
    "construction":"İnşaat & Yapı 🏗️",
    "chemical":    "Kimya & Proses 🧪",
    "finance":     "Finans & İş 💼",
    "health":      "Sağlık & Biyomedikal 🏥",
    "network":     "Ağ & Altyapı 🌐",
}


def build_category_block(
    cat: str,
    discoveries: list[tuple[str, int]],
    gemini_tr: dict[str, str],
) -> str:
    """Bir kategori için skills.py blok metni üretir."""
    label = CATEGORY_LABELS.get(cat, f"{cat.title()} 🆕")
    block  = f'    # {"=" * 69}\n'
    block += f'    "{label}": {{\n'
    for term, df in discoveries:
        # Türkçe varyant: built-in map → Gemini → boş
        tr_builtin = _tr_variants(term)
        tr_gemini  = gemini_tr.get(term.lower(), "")
        variants   = [term]  # canonical her zaman dahil
        for v in tr_builtin:
            if v not in variants:
                variants.append(v)
        if tr_gemini and tr_gemini.lower() not in variants:
            variants.append(tr_gemini.lower())
        variants_str = ", ".join(f'"{v}"' for v in variants)
        block += f'        "{term}": [{variants_str}],  # {df} ilan\n'
    block += "    },\n"
    return block


def add_categories_to_skills_py(blocks: dict[str, str]) -> int:
    """Yeni kategori bloklarını skills.py'ye ekler.
    Mevcut kategori etiketleri atlanır. Döner: eklenen terim sayısı."""
    src   = SKILLS_FILE.read_text(encoding="utf-8")
    added = 0
    for cat, block in blocks.items():
        label = CATEGORY_LABELS.get(cat, "")
        if f'"{label}"' in src:
            # Kategori zaten var: içine ekle
            m = re.search(
                r'("' + re.escape(label) + r'":\s*\{)(.*?)(\n\s+\},)',
                src, re.DOTALL
            )
            if m:
                existing = m.group(2)
                new_lines = ""
                for line in block.splitlines():
                    if '": [' in line:
                        term = line.strip().split('"')[1]
                        if f'"{term}"' not in existing:
                            new_lines += "\n" + line
                            added += 1
                if new_lines:
                    replacement = m.group(1) + m.group(2) + new_lines + m.group(3)
                    src = src[:m.start()] + replacement + src[m.end():]
        else:
            # Yeni kategori: SKILL_CATEGORIES kapanışından önce ekle
            insert = src.rfind("\n}\n\n\n# --- Düzleştirme")
            if insert == -1:
                insert = src.rfind("\n}\n")
            src = src[:insert] + "\n" + block + src[insert:]
            added += block.count('": [')

    if not DRY_RUN:
        SKILLS_FILE.write_text(src, encoding="utf-8")
    return added


# ── Ana akış ──────────────────────────────────────────────────────────────────

def main() -> None:
    W = 72
    SEP = "─" * W
    print("=" * W)
    print("  SkillPulse — Domain Bazında Beceri Keşfi")
    if DRY_RUN: print("  [DRY-RUN] Dosyalar değiştirilmeyecek.")
    print(f"  MIN_DF = {MIN_DF} | TOP_N = {TOP_N} | Gemini = {'✅' if _HAS_GEMINI else '❌'}")
    print("=" * W)

    # Variant lookup
    variant_lookup: dict[str, str] = {}
    for canon, variants in SKILLS.items():
        variant_lookup[canon.lower()] = canon
        for v in variants:
            variant_lookup[v.lower()] = canon

    # Discovery dosyalarını tara
    cat_files = sorted(DISCOVERY_DIR.glob("*.json"))
    if not cat_files:
        sys.exit(
            "data/discovery/ klasöründe dosya yok!\n"
            "Önce çalıştır: python3 fetch_discovery_corpus.py"
        )

    all_discoveries: dict[str, list[tuple[str, int]]] = {}
    total_jobs = 0

    for cat_file in cat_files:
        cat = cat_file.stem
        raw = json.loads(cat_file.read_text(encoding="utf-8"))
        jobs = raw.get("jobs", raw) if isinstance(raw, dict) else raw
        total_jobs += len(jobs)

        print(f"\n{SEP}")
        label = CATEGORY_LABELS.get(cat, cat)
        print(f"🔍 {label}  ({len(jobs)} ilan)")
        print(SEP)

        discoveries = discover_for_category(cat, jobs, variant_lookup)
        all_discoveries[cat] = discoveries

        if discoveries:
            for term, df in discoveries[:15]:
                print(f"  🆕 {term:<38} {df:>5} ilan")
            if len(discoveries) > 15:
                print(f"  ... ve {len(discoveries)-15} terim daha")
        else:
            print("  Yeni teknik terim bulunamadı.")

    # Gemini ile Türkçe çevirisi
    all_new_terms: list[str] = [
        term
        for discoveries in all_discoveries.values()
        for term, _ in discoveries
        if not _tr_variants(term)
    ]
    gemini_tr: dict[str, str] = {}
    if _HAS_GEMINI and all_new_terms:
        print(f"\n{SEP}")
        print(f"🌐 Gemini ile {len(all_new_terms)} terim Türkçeye çevriliyor...")
        print(SEP)
        gemini_tr = _gemini_translate_batch(all_new_terms)
        print(f"  {len(gemini_tr)} çeviri alındı.")

    # Blokları oluştur
    category_blocks: dict[str, str] = {}
    for cat, discoveries in all_discoveries.items():
        if discoveries:
            category_blocks[cat] = build_category_block(cat, discoveries, gemini_tr)

    # skills.py güncelleme
    print(f"\n{SEP}")
    print("✏️  skills.py güncelleniyor...")
    print(SEP)

    if category_blocks:
        added = add_categories_to_skills_py(category_blocks)
        verb  = "(dry-run)" if DRY_RUN else "eklendi → skills.py"
        print(f"  🆕 {added} yeni terim {verb}")
    else:
        print("  Eklenecek yeni terim yok.")

    # Rapor
    print(f"\n{'='*W}")
    print("  ÖZET")
    print(f"  📂 İşlenen ilan         : {total_jobs}")
    print(f"  📁 Kategori sayısı      : {len(all_discoveries)}")
    grand_total = sum(len(v) for v in all_discoveries.values())
    print(f"  🆕 Toplam keşfedilen    : {grand_total}")
    for cat, discoveries in sorted(all_discoveries.items()):
        label = CATEGORY_LABELS.get(cat, cat)
        print(f"     {label:<35} {len(discoveries)} terim")
    print(f"{'='*W}")
    if not DRY_RUN and grand_total > 0:
        print("\nℹ️  skills.py güncellendi. Streamlit'i yeniden başlat: streamlit run app.py")
        print(f"   python3 -c \"from skills import SKILLS; print(len(SKILLS), 'beceri')\"")


if __name__ == "__main__":
    main()
