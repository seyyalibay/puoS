"""
skill_extractor.py — İlan metinlerinden beceri çıkarımı.

SOURCE-AGNOSTIC: Girdi sadece şemaya uyan ilan dict'leridir. Hangi
kaynaktan (adzuna/kariyer) geldiğini UMURSAMAZ.

İş akışı:
    jobs (list[dict])  ->  her ilanın description'ı küçük harfe normalize edilir
    ->  her canonical beceri için varyantları metinde aranır
    ->  frekans sayımı C modülüne (ctypes) delege edilir
    ->  ilan başına {canonical_skill: count} ve toplam sayım üretilir.

Çıktı, trend_analyzer ve dashboard'ın beklediği yapı:
    {
        "per_job":     list[dict]  # her ilan için {skill: count}
        "totals":      dict        # tüm korpusta {skill: toplam_count}
        "doc_freq":    dict        # {skill: kaç ilanda en az 1 kez geçti}
        "n_jobs":      int
    }
"""
import re
import functools

from skills import SKILLS
from processors.skill_counter_bridge import count_occurrences

# Tek/iki harfli ya da yaygın kelime olabilecek riskli varyantlar:
# bunlar için kelime-sınırı (\bvariant\b) regex'i ile sayıyoruz, yanlış
# pozitifleri (ör. "java" içinde "ava" değil ama "go" -> "google") azaltmak için.
_WORD_BOUNDARY_VARIANTS = {
    "r", "c", "go", "js", "ts", "ml", "qa", "ux", "ui", "css", "html",
    "sql", "aws", "gcp", "php", "k8s", "ci cd", "cicd", "c#", "c++",
    # Korpus taramasında alt dize sahte pozitifi verdiği ölçülenler:
    # "java"->javascript, "git"->digital, "rust"->trust, "scala"->scalable,
    # "vue"->revenue, "etl"->faaliyetleri (TR çekim ekleri)
    "java", "git", "rust", "scala", "vue", "etl",
    # Kısa/çakışan varyantlar:
    # "helm"->overwhelm/helmet, "rag"->fragment/drag, "llm"/"dbt" kısa ve riskli
    "helm", "rag", "llm", "dbt",
    # AWS/Azure/GCP kısa servis kodları (sayı/harf içinde gömülü FP'leri önle):
    # "iam"->miami, "s3"->sürüm dizgileri, "emr"->electronic medical record vb.
    "ec2", "s3", "ecs", "eks", "rds", "vpc", "iam", "emr", "aks", "gke", "gcs", "hdfs",
    # ML/metodoloji kısaltmaları: "rl"->world, "bert"->robert/albert, "gpt", "nlp"
    "nlp", "rl", "bert", "gpt", "sre", "mlops", "ddd", "cqrs",
    # Frontend/test araçları: "expo"->export, "vite"->invite, "jest"->jester
    "expo", "vite", "jest", "k6", "tdd", "bdd", "puppet",
    # Güvenlik/mimari kısaltmaları: "ssl"/"tls", "sast"/"dast", "rbac", "cdn"
    "sast", "dast", "ssl", "tls", "rbac", "cdn",
    # Kısa endüstriyel/altyapı kısaltmaları: alt-dize FP'si ölçülenler
    # "ros"->microservices/across, "mes"->messages/implementation
    "ros", "mes",
    # Ağ protokolleri: "bgp"->"background", "hls"->"challenges"
    "bgp", "hls", "v2x",
    # Endüstriyel kısaltmalar: "dcs"->"success/access", "hmi"->"submit", "vfd"->"bevfd"
    "dcs", "hmi", "vfd", "plc", "cfd",
    # Sağlık/standart kısaltmaları: "hl7", "mdr"->"murder/modern", "msa"->"embassy"
    "hl7", "mdr", "msa",
    # Finans/kalite: "pmp"->"exempt", "spc"->"aspect", "gmp"->"implement"
    "pmp", "spc", "gmp",
    # Güvenlik: "pam"->"spam/example", "nft"->"benefit"
    "pam", "nft",
    # Genel kısa: "bim"->"submit/ability", "ios"->"previous", "jwt"->"midjourney"
    "bim", "ios", "jwt",
    # İş metodoloji: "5s methodology" uzun varyantla geliyor, yalın "5s" korunmalı
    "5s",
    # Blockchain: "defi"->"define/definitely/definition"
    "defi",
    # GIS: "arcgis" uzun ama yine de sınır zorunlu
    "arcgis",
}

# Standart kelime-sınırı yetmeyen özel durumlar: negatif lookahead/lookbehind
# ile tam terim olarak eşleştirilmesi gereken varyantlar.
# Format: variant -> derlenmiş regex
_CUSTOM_PATTERNS: dict[str, re.Pattern] = {
    # "consul" -> "consulting", "consultant", "consultation" FP'si
    # Negatif lookahead: "consul" + harf gelmemeli
    "consul": re.compile(r"(?<![a-z])consul(?!t)", re.IGNORECASE),
    # "nac" -> "finance", "enhance" gibi kelimelerin içinde eşleşmesin
    "nac": re.compile(r"(?<![a-z])nac(?![a-z])", re.IGNORECASE),
    # "sil" -> "similar", "resilience" FP'si (endüstriyel "sil" canonical)
    "sil": re.compile(r"(?<![a-z])sil(?![a-z])", re.IGNORECASE),
    # "hil" -> "while", "agile" içinde eşleşmesin
    "hil": re.compile(r"(?<![a-z])hil(?![a-z])", re.IGNORECASE),
}

# İK/kurumsal boilerplate: ilan metninde geçse de beceri sayımına dahil edilmez.
# Canonical skill adlarıyla eşleşmeli (SKILLS.keys() içindeki formlar).
_STOP_CANONICALS: frozenset[str] = frozenset({
    "applicant tracking",
    "equal opportunity",
    "background check",
    "drug test",
    "cover letter",
    "resume",
    "apply now",
    "human resources",
    "hiring manager",
    "work authorization",
    "visa sponsorship",
    "benefits package",
    "health insurance",
    "paid time off",
    "remote work policy",
})


@functools.lru_cache(maxsize=None)
def _boundary_re(variant: str) -> re.Pattern:
    # À-ɏ: Latin Extended blokları (Türkçe ş,ç,ı,ö,ü,ğ dahil)
    # C'nin is_word_char() yalnızca ASCII [a-z0-9] tanıdığı için Türkçe çok-baytlı
    # karakterleri sınır sayıyor; bu regex bunları da sınır dışı tutar.
    return re.compile(
        r"(?<![a-zÀ-ɏ])" + re.escape(variant) + r"(?![a-zÀ-ɏ])"
    )


def _normalize(text: str) -> str:
    return text.lower()


def _count_variant(text: str, variant: str) -> int:
    """Bir varyantın metindeki frekansı (unicode-aware kelime sınırı)."""
    # 1. Özel negatif lookahead/lookbehind gerektiren varyantlar (Python regex)
    if variant in _CUSTOM_PATTERNS:
        return len(_CUSTOM_PATTERNS[variant].findall(text))
    # 2. C strstr ile hızlı ön-kontrol: substring yoksa regex çalıştırma.
    if count_occurrences(text, variant) == 0:
        return 0
    # 3. Unicode-aware Python regex: ASCII + Latin Extended sınır kontrolü.
    #    count_word_boundary (C, ASCII-only) yerine; Türkçe "çalışmaya" içinde
    #    "maya" gibi false positive'leri önler.
    return len(_boundary_re(variant).findall(text))


def extract_from_text(text: str) -> dict:
    """Tek bir metinden {canonical_skill: count} (0'lar dahil değil)."""
    norm = _normalize(text)
    found: dict[str, int] = {}
    for canonical, variants in SKILLS.items():
        if canonical in _STOP_CANONICALS:
            continue
        total = 0
        for v in variants:
            total += _count_variant(norm, v)
        if total > 0:
            found[canonical] = total
    return found


def extract(jobs: list[dict]) -> dict:
    """İlan listesinden korpus geneli beceri istatistikleri."""
    per_job: list[dict] = []
    totals: dict[str, int] = {}
    doc_freq: dict[str, int] = {}

    for job in jobs:
        skills_in_job = extract_from_text(job.get("description", ""))
        per_job.append(skills_in_job)
        for skill, count in skills_in_job.items():
            totals[skill] = totals.get(skill, 0) + count
            doc_freq[skill] = doc_freq.get(skill, 0) + 1  # ilanda >=1 geçti

    return {
        "per_job": per_job,
        "totals": dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True)),
        "doc_freq": dict(sorted(doc_freq.items(), key=lambda kv: kv[1], reverse=True)),
        "n_jobs": len(jobs),
    }
