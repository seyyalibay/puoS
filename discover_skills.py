#!/usr/bin/env python3
"""
discover_skills.py — Cache'deki ilanlardan bağlam-temelli beceri keşfi.

Yöntem:
  "experience with X", "knowledge of X" vb. bağlam kalıplarından aday
  terimler çeker; endüstriyel/jenerik kelimeleri filtreler; skills.py ile
  karşılaştırır; yeni yazılım becerilerini ekler.

Kullanım:
    python3 discover_skills.py               # analiz + yeni ekle (silmez)
    python3 discover_skills.py --dry-run     # sadece raporla
    python3 discover_skills.py --force-remove# sıfır-görünüm becerileri sil
    python3 discover_skills.py --min-df 5    # eşik (varsayılan: 10)

ÖNEMLİ: Sıfır görünümlü beceriler otomatik SİLİNMEZ.
  Mevcut corpus (imalat ilanları + kültür metni ağırlıklı) bu kararı
  verecek kalitede değil. --force-remove ile açık onay gerekir.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from skills import SKILLS, SKILL_CATEGORIES
from processors.skill_extractor import extract

# ── CLI ────────────────────────────────────────────────────────────────────────
DRY_RUN      = "--dry-run"      in sys.argv
FORCE_REMOVE = "--force-remove" in sys.argv
MIN_DF = 10
for i, arg in enumerate(sys.argv):
    if arg == "--min-df" and i + 1 < len(sys.argv):
        MIN_DF = int(sys.argv[i + 1])

SKILLS_FILE  = Path(__file__).parent / "skills.py"
CACHE_FILES  = [
    Path(__file__).parent / "data" / "adzuna.json",
    Path(__file__).parent / "data" / "jooble-us.json",
    Path(__file__).parent / "data" / "jooble-tr.json",
]
NEW_CATEGORY = "Keşfedilen Beceriler 🆕"

# Corpus kalitesi için minimum eşik: bilinen skill'lerin en az %30'u görünmeli
QUALITY_THRESHOLD = 0.30

# ── Bağlam kalıpları ───────────────────────────────────────────────────────────
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
]

# ── Filtreleme sözlükleri ──────────────────────────────────────────────────────
_TRAILING_NOISE = {
    "experience", "skills", "skill", "tools", "tool", "systems", "system",
    "technologies", "technology", "concepts", "concept", "principles",
    "practices", "practice", "frameworks", "framework", "environments",
    "environment", "methodologies", "methodology", "platforms", "platform",
}

_GENERIC: set[str] = {
    "the", "and", "or", "for", "with", "in", "of", "to", "a", "an",
    "be", "our", "your", "their", "team", "company", "role", "good",
    "great", "strong", "excellent", "high", "full", "key", "core",
    "modern", "large", "fast", "complex", "various", "multiple",
    "different", "relevant", "related", "required", "preferred",
    "additional", "similar", "equivalent", "following", "current",
    "latest", "new", "best", "other", "some", "one", "two", "three",
    "design", "development", "testing", "support", "management",
    "delivery", "operations", "production", "performance", "quality",
    "security", "data", "cloud", "software", "hardware", "network",
    "system", "platform", "service", "solution", "product", "project",
    "process", "model", "application", "infrastructure", "architecture",
    "at least", "minimum", "proven", "demonstrable", "solid", "broad",
    "deep", "extensive", "industry", "sector", "public", "private",
    "client", "customer", "user", "business", "leading", "cutting",
}

# Endüstriyel / imalat terimleri — yazılım listesine alınmaz
_INDUSTRIAL: set[str] = {
    "plc", "plcs", "scada", "hmi", "dcs", "bms", "ems", "vfd",
    "catia", "catia v5", "solidworks", "autocad", "siemens", "fanuc",
    "ab", "allen bradley", "rockwell", "schneider", "mitsubishi",
    "ladder logic", "ladder diagram", "function block", "structured text",
    "robotics", "automation", "building automation", "hvac", "electrical",
    "mechanical", "civil", "structural", "instrumentation", "commissioning",
    "manufacturing", "fabrication", "assembly", "welding", "machining",
    "pneumatics", "hydraulics", "pid control", "pid", "rtu", "opc ua",
    "wincc", "tia portal", "step 7", "codesys",
}

_TECH_HINT = re.compile(
    r"\d"
    r"|[.+#/]"
    r"|(?:js|ts|sql|db|ml|ai|api|sdk|cli|ops|sec)$",
    re.I,
)

_TECH_WHITELIST = {
    "react", "angular", "vue", "svelte", "nextjs", "nuxt", "remix", "astro",
    "django", "flask", "fastapi", "nestjs", "express", "fastify", "hono",
    "spring", "quarkus", "micronaut", "rails", "sinatra", "phoenix",
    "pytorch", "tensorflow", "keras", "jax", "flax", "transformers",
    "langchain", "llamaindex", "openai", "anthropic", "huggingface",
    "sklearn", "pandas", "numpy", "polars", "dask", "ray", "modin",
    "kafka", "flink", "spark", "hadoop", "hive", "presto", "trino",
    "airflow", "prefect", "dagster", "temporal", "camunda", "conductor",
    "dbt", "airbyte", "fivetran", "stitch", "nifi", "debezium",
    "snowflake", "databricks", "redshift", "bigquery", "synapse",
    "clickhouse", "druid", "pinot", "starrocks",
    "terraform", "pulumi", "ansible", "puppet", "chef", "saltstack",
    "docker", "kubernetes", "helm", "argocd", "flux", "argo",
    "prometheus", "grafana", "datadog", "splunk", "newrelic", "dynatrace",
    "jaeger", "zipkin", "opentelemetry", "loki",
    "postgres", "postgresql", "mysql", "sqlite", "mariadb",
    "mongodb", "cassandra", "redis", "memcached", "dynamodb",
    "neo4j", "arangodb", "tigergraph", "pinecone", "weaviate",
    "chroma", "qdrant", "pgvector", "milvus", "vespa",
    "git", "github", "gitlab", "bitbucket",
    "nginx", "apache", "caddy", "traefik", "envoy", "istio", "linkerd",
    "pytest", "jest", "mocha", "jasmine", "junit", "testng",
    "selenium", "playwright", "cypress", "appium", "k6",
    "pydantic", "sqlalchemy", "alembic", "celery", "dramatiq",
    "rabbitmq", "nats", "activemq", "zeromq", "mosquitto",
    "supabase", "firebase", "convex", "pocketbase", "appwrite",
    "vercel", "netlify", "railway", "render", "fly.io",
    "graphql", "grpc", "protobuf", "thrift", "avro",
    "rust", "golang", "kotlin", "swift", "scala", "elixir", "haskell",
    "groovy", "perl", "lua", "clojure", "erlang", "ocaml", "nim",
    "htmx", "alpinejs", "qwik", "solidjs",
    "turborepo", "nx", "pnpm", "bun", "deno",
    "tauri", "electron", "capacitor", "ionic", "expo",
    "vault", "consul", "nomad", "waypoint",
    "wandb", "mlflow", "bentoml", "seldon", "kubeflow",
    "onnx", "triton", "torchserve", "ray serve",
    "elasticsearch", "opensearch",
    "powershell", "nushell", "fish",
    "polars", "narwhals", "ibis",
    "modal", "replicate", "together",
    "neon", "turso", "planetscale", "cockroachdb",
    "mistral", "llama", "cohere", "gemini",
    "windmill", "n8n", "zapier", "make",
    "htmx", "hyperscript",
}


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


def _is_software_tech(term: str) -> bool:
    t = term.lower()
    if t in _INDUSTRIAL:
        return False
    if t in _TECH_WHITELIST:
        return True
    if _TECH_HINT.search(t):
        return True
    parts = t.split()
    if len(parts) == 1:
        return len(t) >= 4 and t not in _GENERIC
    if len(parts) <= 3:
        return (
            all(len(p) >= 3 for p in parts)
            and any(p not in _GENERIC for p in parts)
            and not any(p in _INDUSTRIAL for p in parts)
        )
    return False


# ── Veri ve çıkarma ────────────────────────────────────────────────────────────

def load_jobs() -> list[dict]:
    jobs: list[dict] = []
    for path in CACHE_FILES:
        if not path.exists():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("jobs", raw) if isinstance(raw, dict) else raw
        jobs.extend(items)
    return jobs


def build_variant_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canon, variants in SKILLS.items():
        lookup[canon.lower()] = canon
        for v in variants:
            lookup[v.lower()] = canon
    return lookup


def extract_candidates(jobs: list[dict]) -> dict[str, int]:
    doc_count: Counter = Counter()
    for job in jobs:
        desc = (job.get("description") or "") + " " + (job.get("title") or "")
        seen: set[str] = set()
        for pat in CONTEXT_PATTERNS:
            for m in pat.finditer(desc):
                cand = _clean(m.group(1))
                if cand and cand not in seen:
                    seen.add(cand)
        doc_count.update(seen)
    return dict(doc_count)


def auto_category(term: str) -> str:
    t = term.lower()
    if any(x in t for x in ["aws ", "amazon ", "ec2", "sqs", "sns", "kinesis", "sagemaker"]):
        return "AWS Servisleri ☁️"
    if "azure" in t:
        return "Azure Servisleri ☁️"
    if any(x in t for x in ["gcp", "google cloud", "bigquery", "vertex", "gke", "firebase"]):
        return "GCP Servisleri ☁️"
    if any(x in t for x in ["sql", "postgres", "mysql", "mongo", "redis", "cassandra",
                              "dynamo", "neo4j", " db", "database", "influx",
                              "pinecone", "weaviate", "vector", "clickhouse"]):
        return "Veritabanları 🗄️"
    if any(x in t for x in ["spark", "kafka", "airflow", "flink", "dbt", "snowflake",
                              "databricks", "fivetran", "airbyte", "etl", "pipeline",
                              "dagster", "prefect", "temporal"]):
        return "Veri Mühendisliği 🔧"
    if any(x in t for x in ["pytest", "jest", "mocha", "junit", "cypress", "selenium",
                              "playwright", "testing", "quality"]):
        return "Test & Kalite ✅"
    if any(x in t for x in ["terraform", "ansible", "helm", "argocd", "docker",
                              "kubernetes", "k8s", "jenkins", "github action",
                              "prometheus", "grafana", "datadog"]):
        return "DevOps & Platform 🔧"
    if any(x in t for x in ["pytorch", "tensorflow", "keras", "jax", "langchain",
                              "openai", "huggingface", "llm", "gpt", "embedding",
                              "rag", "nlp", "vision", "mistral", "llama", "gemini"]):
        return "ML / AI 🤖"
    if any(x in t for x in ["react", "angular", "vue", "svelte", "next", "nuxt",
                              "html", "css", "tailwind", "flutter", "swift", "kotlin",
                              "ios", "android", "htmx", "astro"]):
        return "Frontend & Mobil 🎨"
    if any(x in t for x in ["fastapi", "django", "flask", "express", "nest",
                              "spring", "graphql", "grpc", "rest", "api",
                              "rabbitmq", "celery", "microservice"]):
        return "Backend & API ⚙️"
    if any(x in t for x in ["security", "crypto", "auth", "ssl", "tls",
                              "owasp", "pentest", "vault", "iam", "rbac"]):
        return "Güvenlik 🔒"
    if any(x in t for x in ["tableau", "power bi", "looker", "grafana",
                              "kibana", "metabase", "superset", "plotly"]):
        return "Veri Görselleştirme 📊"
    return NEW_CATEGORY


# ── skills.py düzenleme ────────────────────────────────────────────────────────

def remove_from_skills_py(canonicals: list[str]) -> tuple[int, list[str]]:
    src = SKILLS_FILE.read_text(encoding="utf-8")
    removed, skipped = 0, []
    for canon in canonicals:
        search = re.search(
            r'\n\s+"' + re.escape(canon) + r'":\s*\[.*?\],[ \t]*(#[^\n]*)?\n',
            src, re.DOTALL
        )
        if search:
            comment = (search.group(1) or "").lower()
            if any(kw in comment for kw in ["fp", "yalın", "jenerik", "karışır", "riski"]):
                skipped.append(f"{canon} (FP notu var)")
                continue
        pattern = re.compile(
            r'\n(\s+"' + re.escape(canon) + r'":\s*\[.*?\],[ \t]*(?:#[^\n]*)?)(?=\n)',
            re.DOTALL,
        )
        new_src, count = pattern.subn("", src)
        if count:
            src = new_src
            removed += 1
        else:
            skipped.append(f"{canon} (regex eşleşmedi)")
    if not DRY_RUN:
        SKILLS_FILE.write_text(src, encoding="utf-8")
    return removed, skipped


def add_to_skills_py(by_category: dict[str, list[str]]) -> int:
    src = SKILLS_FILE.read_text(encoding="utf-8")
    added = 0
    if f'"{NEW_CATEGORY}"' in src:
        m = re.search(
            r'("' + re.escape(NEW_CATEGORY) + r'":\s*\{)(.*?)(\n\s+\},)',
            src, re.DOTALL
        )
        if m:
            existing = m.group(2)
            new_entries = "".join(
                f'\n        "{term}": ["{term}"],'
                for terms in by_category.values()
                for term in sorted(terms)
                if f'"{term}"' not in existing
            )
            added = new_entries.count('": ["')
            if new_entries:
                src = src[:m.start()] + m.group(1) + m.group(2) + new_entries + m.group(3) + src[m.end():]
    else:
        block = f'\n    # {"=" * 69}\n    "{NEW_CATEGORY}": {{\n'
        for cat_hint, terms in sorted(by_category.items()):
            if terms:
                block += f"        # {cat_hint}\n"
                for term in sorted(terms):
                    block += f'        "{term}": ["{term}"],\n'
                    added += 1
        block += "    },\n"
        insert = src.rfind("\n}\n\n\n# --- Düzleştirme")
        if insert == -1:
            insert = src.rfind("\n}\n")
        src = src[:insert] + "\n" + block + src[insert:]
    if not DRY_RUN:
        SKILLS_FILE.write_text(src, encoding="utf-8")
    return added


# ── Ana akış ──────────────────────────────────────────────────────────────────

def main() -> None:
    W = 72
    SEP = "─" * W
    print("=" * W)
    print("  SkillPulse — Beceri Keşif Analizi")
    if DRY_RUN:       print("  [DRY-RUN]      Dosyalar değiştirilmeyecek.")
    if FORCE_REMOVE:  print("  [FORCE-REMOVE] Sıfır-görünüm beceriler silinecek!")
    print(f"  MIN_DF = {MIN_DF} | Mevcut skill = {len(SKILLS)}")
    print("=" * W)

    jobs = load_jobs()
    if not jobs:
        sys.exit("Hiç cache verisi bulunamadı.")
    print(f"\n📂 {len(jobs)} ilan yüklendi")

    # Extractor ile mevcut skill eşleşmesi
    print("⚙️  Extractor ile beceriler karşılaştırılıyor...")
    stats    = extract(jobs)
    doc_freq = stats["doc_freq"]

    confirmed: list[tuple[str, int]] = []
    rare:      list[tuple[str, int]] = []
    zero_list: list[str]             = []
    for canon in sorted(SKILLS):
        n = doc_freq.get(canon, 0)
        if n >= MIN_DF:
            confirmed.append((canon, n))
        elif n > 0:
            rare.append((canon, n))
        else:
            zero_list.append(canon)

    # Corpus kalite skoru
    found_any = len(confirmed) + len(rare)   # en az 1 kez geçen
    quality   = found_any / len(SKILLS)
    quality_ok = quality >= QUALITY_THRESHOLD

    # Bağlam çıkarma
    print("🔍 Bağlam kalıplarından yeni terimler çekiliyor...")
    all_candidates = extract_candidates(jobs)
    variant_lookup = build_variant_lookup()

    discoveries: dict[str, int] = {}
    for term, df in all_candidates.items():
        if df < MIN_DF or term in variant_lookup:
            continue
        if not _is_software_tech(term):
            continue
        discoveries[term] = df

    disc_by_cat: dict[str, list[str]] = {}
    for term in sorted(discoveries, key=discoveries.get, reverse=True):
        disc_by_cat.setdefault(auto_category(term), []).append(term)
    total_disc = sum(len(v) for v in disc_by_cat.values())

    # ── Rapor ──────────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print(f"📊  CORPUS KALİTE RAPORU")
    print(SEP)
    print(f"  Toplam ilan          : {len(jobs)}")
    print(f"  En az 1 eşleşen skill: {found_any}/{len(SKILLS)} (%{quality*100:.0f})")
    if quality_ok:
        print(f"  Corpus kalitesi      : ✅ YETERLİ (%{QUALITY_THRESHOLD*100:.0f}+ eşik)")
    else:
        print(f"  Corpus kalitesi      : ⚠️  YETERSİZ (%{quality*100:.0f} < %{QUALITY_THRESHOLD*100:.0f} eşik)")
        print(f"  → İlanlar büyük ölçüde yazılım odaklı değil veya açıklamalar kısaltılmış.")
        print(f"  → Sıfır görünümlü beceriler ({len(zero_list)}) GERÇEKTEn kullanılmıyor")
        print(f"    olmayabilir; silmek için --force-remove gerekir.")

    print(f"\n{SEP}")
    print(f"✅  ONAYLANAN  ({len(confirmed)} beceri — {MIN_DF}+ ilanda)")
    print(SEP)
    for canon, n in sorted(confirmed, key=lambda x: -x[1])[:30]:
        bar = "█" * min(36, n // 5)
        print(f"  {canon:<32} {n:>6} ilan  {bar}")
    if len(confirmed) > 30:
        print(f"  ... ve {len(confirmed)-30} beceri daha")

    print(f"\n{SEP}")
    print(f"🟡  NADİR  ({len(rare)} beceri — 1–{MIN_DF-1} ilan, korunuyor)")
    print(SEP)
    for canon, n in sorted(rare, key=lambda x: -x[1]):
        print(f"  {canon:<40} {n} ilan")

    print(f"\n{SEP}")
    keep_str = "" if FORCE_REMOVE else "  [--force-remove olmadan SİLİNMEZ]"
    print(f"⚠️   SIFIR GÖRÜNÜM  ({len(zero_list)} beceri — 0 ilan){keep_str}")
    print(SEP)
    cols = 3
    padded = zero_list + [""] * (-len(zero_list) % cols)
    for i in range(0, len(padded), cols):
        row = padded[i:i+cols]
        print("  " + "   ".join(f"{c:<24}" for c in row if c))

    print(f"\n{SEP}")
    print(f"🆕  KEŞFEDİLEN  ({total_disc} yeni yazılım terimi — bağlam kalıpları, {MIN_DF}+ ilan)")
    print(SEP)
    if not discoveries:
        print("  Yeni teknik terim bulunamadı.")
        print("  Not: Bu corpus'ta bağlam kalıpları çok az tetiklendi.")
        print("  Daha kaliteli veri için 'developer' sorgusuyla API'yi tazele.")
    for cat in sorted(disc_by_cat):
        terms = disc_by_cat[cat]
        print(f"\n  [{cat}]  ({len(terms)} terim)")
        for term in terms[:15]:
            print(f"    {term:<38} {discoveries[term]:>6} ilan")
        if len(terms) > 15:
            print(f"    ... ve {len(terms)-15} terim daha")

    # ── Güncelleme ──────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("✏️   skills.py güncelleniyor...")
    print(SEP)

    # Yeni keşifler ekle
    if disc_by_cat:
        added = add_to_skills_py(disc_by_cat)
        verb  = "(dry-run)" if DRY_RUN else "eklendi → skills.py"
        print(f"  🆕 {added} yeni terim {verb}")
    else:
        print("  Eklenecek yeni terim yok.")

    # Sıfır görünüm — sadece --force-remove ile
    if FORCE_REMOVE and zero_list:
        if not quality_ok:
            print(f"\n  ⚠️  UYARI: Corpus kalitesi yetersiz (%{quality*100:.0f}).")
            print(f"      {len(zero_list)} beceri silinmek üzere — yanlış pozitif riski yüksek!")
        removed, skipped = remove_from_skills_py(zero_list)
        verb = "(dry-run)" if DRY_RUN else "kaldırıldı → skills.py"
        print(f"  🗑  {removed} sıfır-görünüm beceri {verb}")
        if skipped:
            print(f"  ⚠️  {len(skipped)} korunan:")
            for s in skipped[:10]:
                print(f"      {s}")
    elif zero_list and not FORCE_REMOVE:
        print(f"  🔒 {len(zero_list)} sıfır-görünüm beceri KORUNDU.")
        print(f"     Silmek için: python3 discover_skills.py --force-remove")

    # ── Özet ────────────────────────────────────────────────────────────────
    removed_count = 0
    if FORCE_REMOVE and not DRY_RUN and zero_list:
        removed_count = len(zero_list)

    print(f"\n{'='*W}")
    print("  ÖZET")
    print(f"  📊 Corpus kalitesi   : %{quality*100:.0f} ({'✅' if quality_ok else '⚠️'})")
    print(f"  ✅ Onaylanan         : {len(confirmed)}")
    print(f"  🟡 Nadir (korunan)  : {len(rare)}")
    print(f"  ⚠️  Sıfır görünüm    : {len(zero_list)}" +
          (" (kaldırıldı)" if FORCE_REMOVE and not DRY_RUN else " (korundu)"))
    print(f"  🆕 Keşfedilen       : {total_disc}" +
          (" (dry-run)" if DRY_RUN else " (eklendi)" if total_disc > 0 else ""))
    print(f"{'='*W}")
    if not DRY_RUN and (total_disc > 0 or (FORCE_REMOVE and zero_list)):
        print("\nℹ️  skills.py güncellendi. Streamlit'i yeniden başlat: streamlit run app.py")


if __name__ == "__main__":
    main()
