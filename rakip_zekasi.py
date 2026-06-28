"""
rakip_zekasi.py — SkillPulse içindeki Rakip Zekâsı sekmesi.

otonomgit/streamlit_app.py'deki 4 sayfa burada fonksiyon olarak sarmalanır:
  render_rz_raporlar()
  render_rz_arama()
  render_rz_pozisyon()
  render_rz_radar()

src.* modülleri doğrudan otonomgit dizininden import edilir (kopyalanmaz).
"""
import os
import re
import sys
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# ── otonomgit projesini Python path'e ekle ──────────────────────────────────
_OTONOMGIT = Path("/Users/seyyitalibayindir/Desktop/otonomgit")
if str(_OTONOMGIT) not in sys.path:
    sys.path.insert(0, str(_OTONOMGIT))

REPORTS_DIR = _OTONOMGIT / "reports"

# ── Component-level CSS (global background override'lar YOK) ────────────────
_COMPONENT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
:root {
  --rz-bg2:    #0F0F0F;
  --rz-glass:  rgba(255,255,255,0.02);
  --rz-gbord:  #1F1F1F;
  --rz-cyan:   #5E6AD2;
  --rz-pink:   #E5484D;
  --rz-purple: #7C86E0;
  --rz-green:  #4CAF50;
  --rz-amber:  #F5A623;
  --rz-t1:     #FFFFFF;
  --rz-t2:     #8B8B8B;
  --rz-t3:     #4A4A4A;
}
@keyframes rz-fadeUp {
  from { opacity:0; transform:translateY(8px); }
  to   { opacity:1; transform:translateY(0); }
}
.rz-cyber-header {
  background: linear-gradient(135deg, rgba(8,13,26,0.9), rgba(139,92,246,0.06), rgba(0,245,255,0.04));
  border: 1px solid var(--rz-gbord);
  border-radius: 16px;
  padding: 28px 32px 24px;
  margin-bottom: 20px;
  position: relative;
  overflow: hidden;
  backdrop-filter: blur(24px);
  animation: rz-borderPulse 4s ease-in-out infinite, rz-fadeUp 0.4s ease;
}
.rz-cyber-scanline {
  position: absolute; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, var(--rz-cyan), transparent);
  opacity: 0.5;
  animation: rz-scanline 5s linear infinite;
}
.rz-cyber-title {
  font-family: 'Space Grotesk', sans-serif !important;
  font-size: 2.1rem; font-weight: 700; margin: 0 0 8px;
  background: linear-gradient(90deg, #00F5FF, #8B5CF6, #FF006E, #00F5FF);
  background-size: 300% auto;
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: rz-gradientFlow 5s ease infinite, rz-textGlow 3s ease-in-out infinite;
  display: inline-block;
}
.rz-cyber-header {
  background: #0F0F0F; border: 1px solid #1F1F1F; border-radius: 8px;
  padding: 18px 22px; margin-bottom: 20px; position: relative;
}
.rz-cyber-title {
  font-family: 'Inter', sans-serif; font-size: 1rem; font-weight: 600;
  color: #FFFFFF; letter-spacing: -0.01em;
}
.rz-cyber-sub {
  font-family: 'JetBrains Mono', monospace;
  color: #4A4A4A; font-size: 0.76rem; margin-top: 3px;
}
.rz-cyber-time {
  position: absolute; top: 18px; right: 20px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; color: #2A2A2A;
}
.rz-cyber-scanline { display: none; }
.rz-glass-card {
  background: #0F0F0F; border: 1px solid #1F1F1F; border-radius: 8px;
  padding: 18px 20px; margin-bottom: 8px; animation: rz-fadeUp 0.25s ease;
}
.rz-glass-card:hover { border-color: #2A2A2A; }
.rz-anomaly-alarm {
  background: #0F0F0F; border: 1px solid #1F1F1F; border-left: 2px solid #E5484D;
  border-radius: 8px; padding: 16px 20px; margin-bottom: 8px; animation: rz-fadeUp 0.25s ease;
}
.rz-anomaly-warn {
  background: #0F0F0F; border: 1px solid #1F1F1F; border-left: 2px solid #F5A623;
  border-radius: 8px; padding: 16px 20px; margin-bottom: 8px; animation: rz-fadeUp 0.25s ease;
}
.rz-anomaly-info {
  background: #0F0F0F; border: 1px solid #1F1F1F; border-left: 2px solid #5E6AD2;
  border-radius: 8px; padding: 16px 20px; margin-bottom: 8px; animation: rz-fadeUp 0.25s ease;
}
.rz-anomaly-ok {
  background: #0F0F0F; border: 1px solid #1F1F1F; border-left: 2px solid #4CAF50;
  border-radius: 8px; padding: 16px 20px; animation: rz-fadeUp 0.25s ease;
}
.rz-badge {
  display: inline-block; border-radius: 4px; padding: 2px 8px;
  font-family: 'JetBrains Mono', monospace; font-size: 0.66rem;
  font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;
}
.rz-badge-red    { background: rgba(229,72,77,0.1);   color: #E5484D;  border: 1px solid rgba(229,72,77,0.25); }
.rz-badge-yellow { background: rgba(245,166,35,0.1);  color: #F5A623;  border: 1px solid rgba(245,166,35,0.25); }
.rz-badge-purple { background: rgba(94,106,210,0.1);  color: #7C86E0;  border: 1px solid rgba(94,106,210,0.25); }
.rz-badge-green  { background: rgba(76,175,80,0.1);   color: #4CAF50;  border: 1px solid rgba(76,175,80,0.25); }
.rz-badge-cyan   { background: rgba(94,106,210,0.08); color: #5E6AD2;  border: 1px solid rgba(94,106,210,0.2); }
.rz-lbl { font-family:'Inter',sans-serif; font-size:0.69rem; text-transform:uppercase; letter-spacing:0.08em; color:#4A4A4A; font-weight:600; }
.rz-sig-name { font-family:'Inter',sans-serif; font-size:0.88rem; font-weight:600; color:#FFFFFF; }
.rz-sig-val  { font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:#8B8B8B; margin-top:4px; }
.rz-sig-desc { font-family:'Inter',sans-serif; font-size:0.78rem; color:#4A4A4A; margin-top:5px; }
</style>
"""


# ── Yardımcı: rapor ayrıştırma ──────────────────────────────────────────────

def _list_reports() -> list[Path]:
    return sorted(REPORTS_DIR.glob("*.md"), reverse=True)


def _parse_meta(text: str) -> dict:
    meta = {}
    for key, pattern in {
        "olusturulma":    r"\*\*Oluşturulma:\*\*\s*(.+)",
        "sirket_sayisi":  r"\*\*Analiz Edilen Şirket:\*\*\s*(\d+)",
        "toplam_anomali": r"\*\*Toplam Anomali:\*\*\s*(\d+)",
        "motor":          r"\*\*Motor:\*\*\s*(.+)",
    }.items():
        m = re.search(pattern, text)
        if m:
            meta[key] = m.group(1).strip()
    return meta


def _parse_summary_table(text: str) -> list[dict]:
    rows, in_table = [], False
    for line in text.splitlines():
        line = line.strip()
        if "| Şirket |" in line:
            in_table = True; continue
        if in_table:
            if line.startswith("|---") or not line.startswith("|"):
                if not line.startswith("|"): break
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 6:
                rows.append({"Şirket": cells[0], "İş İlanı": cells[1],
                             "Commit": cells[2], "Haber": cells[3],
                             "Sentiment": cells[4], "Anomali": cells[5]})
    return rows


def _parse_pipeline_table(text: str) -> list[dict]:
    rows, in_table = [], False
    for line in text.splitlines():
        line = line.strip()
        if "| Metrik |" in line:
            in_table = True; continue
        if in_table:
            if line.startswith("|---") or not line.startswith("|"):
                if not line.startswith("|"): break
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2:
                rows.append({"Metrik": cells[0], "Değer": cells[1]})
    return rows


def _severity_badge(n: int) -> str:
    if n == 0:  return "🟢"
    if n <= 2:  return "🟡"
    return "🔴"


def _severity_color(anomali_str: str) -> str:
    try:   return _severity_badge(int(anomali_str))
    except: return ""


# ── API key yükleyici ────────────────────────────────────────────────────────

def _load_api_keys():
    env_path = _OTONOMGIT / "config" / "api_keys.env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


# ── Veri çekme ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_github_activity(org: str) -> dict:
    try:
        from src.collector.rate_limiter import TokenBucketRateLimiter
        from src.collector.github_client import GitHubClient
    except ImportError as e:
        return {"error": f"Modül yüklenemedi: {e}"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token or token.startswith("ghp_xxx"):
        return {"error": "GITHUB_TOKEN tanımsız"}
    rl = TokenBucketRateLimiter("github_live", max_tokens=100, refill_rate=100,
                                refill_interval_seconds=3600)
    client = GitHubClient(token=token, rate_limiter=rl, backfill_days=7)
    try:
        repos = client.get_org_repos(org)[:5]
        if not repos:
            return {"error": f"'{org}' org'u bulunamadı veya repo yok"}
        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        total_commits, repo_details = 0, []
        for repo in repos:
            name = repo["name"]
            commits = client.get_commits(org, name, since=since)
            total_commits += len(commits)
            repo_details.append({"repo": name, "commits_7d": len(commits)})
        return {"org": org, "repos_checked": len(repos),
                "total_commits_7d": total_commits, "repo_details": repo_details}
    except Exception as e:
        return {"error": str(e)}


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_news(query: str) -> dict:
    try:
        from src.collector.rate_limiter import TokenBucketRateLimiter
        from src.collector.googlenews_rss_client import GoogleNewsRSSClient
        from src.collector.gnews_client import GNewsClient
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    except ImportError as e:
        return {"count": 0, "articles": [], "avg_sentiment": None, "error": str(e)}
    rl_rss = TokenBucketRateLimiter("rss_live", max_tokens=10, refill_rate=10,
                                    refill_interval_seconds=60)
    rl_gn  = TokenBucketRateLimiter("gnews_live", max_tokens=10, refill_rate=10,
                                    refill_interval_seconds=60, min_delay_between_requests_ms=500)
    articles = []
    try:
        rss = GoogleNewsRSSClient(rate_limiter=rl_rss)
        articles += rss.search_news(query)
    except Exception:
        pass
    gnews_key = os.environ.get("GNEWS_API_KEY", "")
    if gnews_key and not gnews_key.startswith("your_"):
        try:
            gn = GNewsClient(api_key=gnews_key, rate_limiter=rl_gn)
            articles += gn.search_news(query, max_results=10)
        except Exception:
            pass
    if not articles:
        return {"count": 0, "articles": [], "avg_sentiment": None}
    sia = SentimentIntensityAnalyzer()
    sentiments, enriched = [], []
    for a in articles[:20]:
        title = a.get("title", "") or ""
        desc  = a.get("description", "") or a.get("content", "") or ""
        text  = f"{title}. {desc}".strip()
        score = sia.polarity_scores(text)["compound"] if text else 0.0
        sentiments.append(score)
        enriched.append({
            "title":     title[:80],
            "source":    a.get("source", {}).get("name", "") if isinstance(a.get("source"), dict) else "",
            "published": a.get("publishedAt", ""),
            "sentiment": round(score, 3),
        })
    avg = round(sum(sentiments) / len(sentiments), 3) if sentiments else 0.0
    return {"count": len(enriched), "articles": enriched, "avg_sentiment": avg}


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_jobs(company_name: str) -> dict:
    try:
        from src.collector.rate_limiter import TokenBucketRateLimiter
        from src.collector.adzuna_client import AdzunaClient
    except ImportError as e:
        return {"count": 0, "error": str(e)}
    app_id  = os.environ.get("ADZUNA_APP_ID", "")
    app_key = os.environ.get("ADZUNA_APP_KEY", "")
    if not app_id or app_id.startswith("your_"):
        return {"count": 0, "note": "Adzuna API tanımsız"}
    rl = TokenBucketRateLimiter("adzuna_live", max_tokens=20, refill_rate=20,
                                refill_interval_seconds=60)
    client = AdzunaClient(app_id=app_id, app_key=app_key, rate_limiter=rl)
    try:
        jobs = client.search_jobs(f'"{company_name}"', results_per_page=50, max_pages=2)
        return {"count": len(jobs), "sample": [j.get("title", "") for j in jobs[:5]]}
    except Exception as e:
        return {"count": 0, "error": str(e)}


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_jobs_by_position(position: str) -> dict:
    try:
        from src.collector.rate_limiter import TokenBucketRateLimiter
        from src.collector.adzuna_client import AdzunaClient
    except ImportError as e:
        return {"error": str(e)}
    app_id  = os.environ.get("ADZUNA_APP_ID", "")
    app_key = os.environ.get("ADZUNA_APP_KEY", "")
    if not app_id or app_id.startswith("your_"):
        return {"error": "Adzuna API anahtarları tanımsız (config/api_keys.env)"}
    rl = TokenBucketRateLimiter("adzuna_pos", max_tokens=20, refill_rate=20,
                                refill_interval_seconds=60)
    client = AdzunaClient(app_id=app_id, app_key=app_key, rate_limiter=rl)
    try:
        jobs = client.search_jobs(position, results_per_page=50, max_pages=4)
    except Exception as e:
        return {"error": str(e)}
    if not jobs:
        return {"error": f"'{position}' için ilan bulunamadı"}
    from collections import Counter
    import statistics
    company_counts: Counter = Counter()
    company_titles: dict[str, list[str]] = {}
    for j in jobs:
        company = (j.get("company", {}) or {}).get("display_name", "") or j.get("company", "")
        if not company or company.lower() in ("unknown", ""):
            continue
        company = company.strip()
        company_counts[company] += 1
        company_titles.setdefault(company, [])
        if len(company_titles[company]) < 3:
            company_titles[company].append(j.get("title", ""))
    if not company_counts:
        return {"error": "İlanlarda şirket bilgisi bulunamadı"}
    top    = company_counts.most_common(20)
    counts = [c for _, c in top]
    mean   = statistics.mean(counts) if counts else 0
    stdev  = statistics.stdev(counts) if len(counts) > 1 else 0
    anomaly_threshold = mean + stdev
    results = []
    for company, count in top:
        results.append({
            "şirket": company, "ilan_sayisi": count,
            "anormal": count > anomaly_threshold and anomaly_threshold > 0,
            "ornek_pozisyonlar": company_titles.get(company, []),
        })
    return {"position": position, "total_jobs": len(jobs),
            "total_companies": len(company_counts),
            "mean": round(mean, 1), "anomaly_threshold": round(anomaly_threshold, 1),
            "results": results}


def _quick_anomaly_score(github: dict, news: dict, jobs: dict) -> list[dict]:
    signals = []
    commits_7d = github.get("total_commits_7d", 0)
    if not github.get("error"):
        if commits_7d > 500:
            signals.append({"sinyal": "⚡ Yüksek Commit Aktivitesi",
                            "değer": f"{commits_7d} commit / 7 gün",
                            "yorum": "Olağandışı yoğun geliştirme — büyük release veya kriz patch'i",
                            "ciddiyet": "high"})
        elif commits_7d > 200:
            signals.append({"sinyal": "📈 Artan Commit Aktivitesi",
                            "değer": f"{commits_7d} commit / 7 gün",
                            "yorum": "Normalin üzerinde geliştirme aktivitesi",
                            "ciddiyet": "medium"})
    avg_sent = news.get("avg_sentiment")
    if avg_sent is not None:
        if avg_sent < -0.1:
            signals.append({"sinyal": "📰 Negatif Haber Duyarlılığı",
                            "değer": f"avg sentiment: {avg_sent}",
                            "yorum": "Medyada olumsuz ton — itibar riski veya kriz haberleri",
                            "ciddiyet": "high" if avg_sent < -0.3 else "medium"})
        elif avg_sent > 0.3:
            signals.append({"sinyal": "📰 Güçlü Pozitif Duyarlılık",
                            "değer": f"avg sentiment: {avg_sent}",
                            "yorum": "Medyada olumlu ton — lansman, yatırım veya büyüme haberleri",
                            "ciddiyet": "low"})
    job_count = jobs.get("count", 0)
    if job_count > 150:
        signals.append({"sinyal": "💼 Yoğun İşe Alım",
                        "değer": f"{job_count} aktif ilan",
                        "yorum": "Agresif büyüme veya yüksek çalışan devir oranı sinyali",
                        "ciddiyet": "high"})
    elif job_count > 50:
        signals.append({"sinyal": "💼 Aktif İşe Alım",
                        "değer": f"{job_count} aktif ilan",
                        "yorum": "Normal büyüme aktivitesi",
                        "ciddiyet": "low"})
    return signals


# ── UI bileşenleri ───────────────────────────────────────────────────────────

def _cyber_header(title: str, subtitle: str = "", tag: str = ""):
    tag_html = (f'<span class="rz-badge rz-badge-cyan" style="margin-left:12px;vertical-align:middle;'
                f'font-size:0.7rem;">{tag}</span>') if tag else ""
    sub_html = f'<div class="rz-cyber-sub">// {subtitle}</div>' if subtitle else ""
    now_str  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.markdown(f"""
    <div class="rz-cyber-header">
      <div class="rz-cyber-scanline"></div>
      <div class="rz-cyber-time">{now_str}</div>
      <div class="rz-cyber-title">{title}{tag_html}</div>
      {sub_html}
    </div>
    """, unsafe_allow_html=True)


def _render_anomaly_signals(signals: list[dict]):
    if not signals:
        st.markdown("""
        <div class="rz-anomaly-ok">
          <div style="display:flex;align-items:center;gap:16px;">
            <div style="font-size:2.2rem;line-height:1;filter:drop-shadow(0 0 12px #00FF88);">⬤</div>
            <div>
              <div style="font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:600;color:#00FF88;">
                Sistem Normal — Anomali Sinyali Tespit Edilmedi
              </div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.76rem;color:var(--rz-t3);margin-top:5px;">
                // tüm metrikler beklenen aralıkta · izleme devam ediyor
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        return
    for s in signals:
        if s["ciddiyet"] == "high":
            card_cls   = "rz-anomaly-alarm"
            badge_html = '<span class="rz-badge rz-badge-red">ALARM</span>'
        elif s["ciddiyet"] == "medium":
            card_cls   = "rz-anomaly-warn"
            badge_html = '<span class="rz-badge rz-badge-yellow">UYARI</span>'
        else:
            card_cls   = "rz-anomaly-info"
            badge_html = '<span class="rz-badge rz-badge-purple">BİLGİ</span>'
        st.markdown(f"""
        <div class="{card_cls}">
          <div style="display:flex;align-items:flex-start;gap:14px;">
            <div style="flex:1;">
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                {badge_html}
                <span class="rz-sig-name">{s['sinyal']}</span>
              </div>
              <div class="rz-sig-val">→ {s['değer']}</div>
              <div class="rz-sig-desc">{s['yorum']}</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)


def _how_it_works():
    st.markdown("""
    <div style="background:#0F0F0F;border:1px solid #1F1F1F;border-radius:8px;padding:24px 26px;">
      <div style="font-family:Inter,sans-serif;font-size:0.72rem;font-weight:600;color:#4A4A4A;
           text-transform:uppercase;letter-spacing:0.08em;margin-bottom:16px;">Anomali Metodolojisi</div>
      <table style="width:100%;border-collapse:collapse;font-size:0.8rem;">
        <thead>
          <tr style="border-bottom:1px solid #1A1A1A;">
            <th style="text-align:left;padding:6px 10px;color:#4A4A4A;font-family:Inter,sans-serif;
                font-weight:500;font-size:0.69rem;text-transform:uppercase;letter-spacing:0.06em;">Sinyal</th>
            <th style="text-align:left;padding:6px 10px;color:#4A4A4A;font-family:Inter,sans-serif;
                font-weight:500;font-size:0.69rem;text-transform:uppercase;letter-spacing:0.06em;">Yöntem</th>
            <th style="text-align:left;padding:6px 10px;color:#4A4A4A;font-family:Inter,sans-serif;
                font-weight:500;font-size:0.69rem;text-transform:uppercase;letter-spacing:0.06em;">Eşik</th>
          </tr>
        </thead>
        <tbody>
          <tr style="border-bottom:1px solid #141414;">
            <td style="padding:9px 10px;color:#5E6AD2;font-family:JetBrains Mono,monospace;font-size:0.78rem;">İş İlanı</td>
            <td style="padding:9px 10px;color:#8B8B8B;font-family:Inter,sans-serif;">30 günlük MA + z-score</td>
            <td style="padding:9px 10px;color:#F5A623;font-family:JetBrains Mono,monospace;font-size:0.76rem;">MA7/MA30 &gt; 1.50 ve z &gt; 2.0</td>
          </tr>
          <tr style="border-bottom:1px solid #141414;">
            <td style="padding:9px 10px;color:#5E6AD2;font-family:JetBrains Mono,monospace;font-size:0.78rem;">Commit</td>
            <td style="padding:9px 10px;color:#8B8B8B;font-family:Inter,sans-serif;">IQR yöntemi</td>
            <td style="padding:9px 10px;color:#F5A623;font-family:JetBrains Mono,monospace;font-size:0.76rem;">Q3 + 1.5 × IQR üzeri</td>
          </tr>
          <tr>
            <td style="padding:9px 10px;color:#5E6AD2;font-family:JetBrains Mono,monospace;font-size:0.78rem;">Sentiment</td>
            <td style="padding:9px 10px;color:#8B8B8B;font-family:Inter,sans-serif;">60 günlük MA sapması</td>
            <td style="padding:9px 10px;color:#F5A623;font-family:JetBrains Mono,monospace;font-size:0.76rem;">|Δ| &gt; 0.15</td>
          </tr>
        </tbody>
      </table>
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# Sayfa 1 — Raporlar
# ════════════════════════════════════════════════════════════════

def render_rz_raporlar():
    import pandas as pd

    _cyber_header("Rakip Zekâsı Raporu", "otomatik analiz çıktısı", "RAPOR")
    reports = _list_reports()
    if not reports:
        st.info("reports/ klasöründe henüz rapor bulunmuyor. Pipeline'ı çalıştırın.")
        return

    report_names = [p.name.replace(".md", "") for p in reports]
    selected_name = st.selectbox("📅 Rapor seç", report_names, key="rz_report_select")
    st.caption(f"Toplam {len(reports)} rapor")

    selected_path = REPORTS_DIR / f"{selected_name}.md"
    text = selected_path.read_text(encoding="utf-8")
    meta = _parse_meta(text)
    summary_rows  = _parse_summary_table(text)
    pipeline_rows = _parse_pipeline_table(text)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📅 Oluşturulma",   meta.get("olusturulma",  "—")[:10])
    col2.metric("🏢 Şirket Sayısı", meta.get("sirket_sayisi", "—"))
    col3.metric("⚠️ Toplam Anomali", meta.get("toplam_anomali", "—"))
    _mv = meta.get("motor", "")
    col4.metric("⚙️ Motor", ("v" + _mv.split("v")[-1]) if "v" in _mv else "—")

    st.divider()
    left, right = st.columns([3, 2])

    with left:
        st.markdown('<div class="rz-lbl" style="margin-bottom:10px;">📄 Rapor İçeriği</div>',
                    unsafe_allow_html=True)
        narrative = re.sub(r"## 📊 Ham Veri Özeti.*?(?=\n##|\Z)", "", text, flags=re.DOTALL)
        narrative = re.sub(r"## ⚙️ Pipeline Bilgileri.*?(?=\n##|\Z)", "", narrative, flags=re.DOTALL)
        narrative = re.sub(r"^# .+\n", "", narrative)
        st.markdown(narrative)

    with right:
        st.markdown('<div class="rz-lbl" style="margin-bottom:10px;">📊 Şirket Özeti</div>',
                    unsafe_allow_html=True)
        if summary_rows:
            for row in summary_rows:
                row["Durum"] = _severity_color(row["Anomali"])
            df = pd.DataFrame(summary_rows)[
                ["Durum", "Şirket", "Commit", "İş İlanı", "Haber", "Sentiment", "Anomali"]
            ]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Bu raporda özet tablo bulunamadı.")

        st.markdown('<div class="rz-lbl" style="margin:16px 0 10px;">⚙️ Pipeline</div>',
                    unsafe_allow_html=True)
        if pipeline_rows:
            st.dataframe(pd.DataFrame(pipeline_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Pipeline bilgisi bulunamadı.")

        st.divider()
        st.download_button("⬇️ Markdown İndir", data=text,
                           file_name=selected_path.name, mime="text/markdown")


# ════════════════════════════════════════════════════════════════
# Sayfa 2 — Anlık Arama
# ════════════════════════════════════════════════════════════════

def render_rz_arama():
    import pandas as pd
    _load_api_keys()
    _cyber_header("Anlık Rakip Analizi",
                  "gerçek zamanlı sinyal tarama · github · haberler · ilanlar", "CANLI")

    with st.form("rz_search_form"):
        col_inp, col_org, col_btn = st.columns([3, 2, 1])
        with col_inp:
            company_name = st.text_input("Şirket Adı",
                placeholder="ör: Datadog, Twilio, Notion…", label_visibility="collapsed")
        with col_org:
            github_org_override = st.text_input("GitHub Org (opsiyonel)",
                placeholder="ör: DataDog", label_visibility="collapsed")
        with col_btn:
            submitted = st.form_submit_button("🔍 Tara", use_container_width=True)

    if not submitted or not company_name.strip():
        st.markdown("""
        <div class="rz-glass-card" style="text-align:center;padding:40px;">
          <div style="font-size:2.5rem;margin-bottom:12px;filter:drop-shadow(0 0 16px rgba(0,245,255,0.4));">⬡</div>
          <div style="font-family:'Space Grotesk',sans-serif;font-size:1rem;color:var(--rz-t2);">
            Şirket adı girerek analizi başlatın
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:var(--rz-t3);margin-top:6px;">
            // github + haber + iş ilanı verileri paralel taranır
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    company = company_name.strip()
    org     = github_org_override.strip() or re.sub(r"[^a-z0-9-]", "", company.lower())

    st.markdown(f"""
    <div class="rz-glass-card" style="padding:16px 22px;margin-bottom:20px;">
      <div style="font-family:'Space Grotesk',sans-serif;font-size:1.3rem;font-weight:700;color:var(--rz-t1);">
        🏢 {company}
      </div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.76rem;color:var(--rz-t3);margin-top:4px;">
        github_org: <span style="color:var(--rz-cyan);">{org}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_gh, col_news, col_jobs = st.columns(3)
    with col_gh:
        with st.spinner("GitHub taranıyor…"):
            github_data = _fetch_github_activity(org)
    with col_news:
        with st.spinner("Haberler çekiliyor…"):
            news_data = _fetch_news(company)
    with col_jobs:
        with st.spinner("İş ilanları çekiliyor…"):
            jobs_data = _fetch_jobs(company)

    m1, m2, m3, m4 = st.columns(4)
    commits_7d = github_data.get("total_commits_7d", 0) if not github_data.get("error") else None
    m1.metric("⚙️ Commit (7 gün)", commits_7d if commits_7d is not None else "—")
    news_count = news_data.get("count", 0)
    m2.metric("📰 Haber", news_count)
    avg_sent   = news_data.get("avg_sentiment")
    sent_str   = f"{avg_sent:+.3f}" if avg_sent is not None else "—"
    sent_delta = ("negatif" if avg_sent is not None and avg_sent < -0.05
                  else ("pozitif" if avg_sent is not None and avg_sent > 0.05 else None))
    m3.metric("😐 Sentiment", sent_str, delta=sent_delta,
              delta_color="inverse" if sent_delta == "negatif" else "normal")
    m4.metric("💼 Açık İlan", jobs_data.get("count", 0))

    st.divider()
    st.markdown('<div class="rz-lbl" style="margin-bottom:12px;">🚨 Anomali Sinyalleri</div>',
                unsafe_allow_html=True)
    _render_anomaly_signals(_quick_anomaly_score(github_data, news_data, jobs_data))
    st.divider()

    with st.expander("⚙️ GitHub Detayı", expanded=False):
        if github_data.get("error"):
            st.error(github_data["error"])
        else:
            repos = github_data.get("repo_details", [])
            if repos:
                st.dataframe(pd.DataFrame(repos), use_container_width=True, hide_index=True)
            st.caption(f"Toplam {github_data.get('repos_checked', 0)} repo tarandı (son 7 gün)")

    with st.expander(f"📰 Son Haberler ({news_count})", expanded=news_count > 0):
        if not news_data.get("articles"):
            st.info("Haber bulunamadı.")
        else:
            df_news = pd.DataFrame(news_data["articles"])[["title", "source", "sentiment"]]
            df_news.insert(0, "Ton",
                df_news["sentiment"].apply(
                    lambda s: "🔴" if s < -0.05 else ("🟢" if s > 0.05 else "⚪")))
            df_news.columns = ["Ton", "Başlık", "Kaynak", "Sentiment"]
            st.dataframe(df_news, use_container_width=True, hide_index=True)

    with st.expander("💼 Örnek İş İlanları", expanded=False):
        sample = jobs_data.get("sample", [])
        if not sample:
            st.info("İş ilanı bulunamadı veya Adzuna API tanımsız.")
        else:
            for title in sample:
                st.markdown(f"- {title}")
        if jobs_data.get("note"):
            st.caption(jobs_data["note"])


# ════════════════════════════════════════════════════════════════
# Sayfa 3 — Pozisyon Analizi
# ════════════════════════════════════════════════════════════════

def render_rz_pozisyon():
    import pandas as pd
    _load_api_keys()
    _cyber_header("Pozisyon Bazlı Şirket Analizi",
                  "sektör genelinde kimin en agresif işe aldığını tespit et", "PAZAR")

    with st.form("rz_position_form"):
        col_pos, col_btn = st.columns([5, 1])
        with col_pos:
            position_input = st.text_input("Pozisyon",
                placeholder="ör: software engineer, data scientist, product manager…",
                label_visibility="collapsed")
        with col_btn:
            pos_submitted = st.form_submit_button("🔍 Tara", use_container_width=True)

    if not pos_submitted or not position_input.strip():
        st.markdown("""
        <div class="rz-glass-card" style="text-align:center;padding:40px;">
          <div style="font-size:2rem;margin-bottom:10px;">💼</div>
          <div style="font-family:'Space Grotesk',sans-serif;color:var(--rz-t2);">
            Pozisyon adı girerek analizi başlatın
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:var(--rz-t3);margin-top:6px;">
            // adzuna'dan ilanlar çekilir · şirket bazında anomali tespiti yapılır
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    position = position_input.strip()
    st.markdown(f"""
    <div class="rz-glass-card" style="padding:14px 22px;margin-bottom:20px;">
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.76rem;color:var(--rz-t3);">
        pozisyon: <span style="color:var(--rz-cyan);font-size:1rem;font-weight:700;">{position}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner(f"Adzuna'dan '{position}' ilanları çekiliyor…"):
        pos_data = _fetch_jobs_by_position(position)

    if pos_data.get("error"):
        st.error(pos_data["error"])
        return

    results   = pos_data["results"]
    anomalies = [r for r in results if r["anormal"]]
    threshold = pos_data["anomaly_threshold"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📋 Taranan İlan",    pos_data["total_jobs"])
    m2.metric("🏢 Farklı Şirket",  pos_data["total_companies"])
    m3.metric("🚨 Anormal Şirket", len(anomalies))
    m4.metric("📊 Anomali Eşiği",  f">{threshold}")

    st.divider()

    if anomalies:
        st.markdown(f"""
        <div style="margin-bottom:16px;">
          <div style="font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:600;
               color:var(--rz-t1);margin-bottom:4px;">
            🚀 Bu Alanda Hızla Büyüyen Şirketler
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.76rem;color:var(--rz-t3);">
            // ort. {pos_data['mean']} ilan → anomali eşiği: {threshold}+ ilan
          </div>
        </div>
        """, unsafe_allow_html=True)
        for r in sorted(anomalies, key=lambda x: x["ilan_sayisi"], reverse=True):
            pozlar = " · ".join(
                f'<code style="background:rgba(0,245,255,0.08);color:#00F5FF;padding:1px 6px;'
                f'border-radius:4px;font-size:0.75rem;">{t}</code>'
                for t in r["ornek_pozisyonlar"]
            )
            st.markdown(f"""
            <div class="rz-anomaly-alarm">
              <div style="display:flex;align-items:center;gap:16px;">
                <div style="text-align:center;min-width:64px;">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:1.8rem;
                       font-weight:700;color:#FF006E;line-height:1;">{r['ilan_sayisi']}</div>
                  <div style="font-size:0.65rem;color:#475569;text-transform:uppercase;
                       letter-spacing:0.06em;">ilan</div>
                </div>
                <div style="flex:1;border-left:1px solid rgba(255,0,110,0.2);padding-left:16px;">
                  <div style="font-family:'Space Grotesk',sans-serif;font-size:1.05rem;
                       font-weight:700;color:var(--rz-t1);margin-bottom:6px;">{r['şirket']}</div>
                  <div style="font-family:'Space Grotesk',sans-serif;font-size:0.8rem;
                       color:#475569;margin-bottom:8px;">
                    Bu şirket bu alanda ağır şekilde büyüyor — agresif işe alım veya yüksek turnover sinyali
                  </div>
                  {f'<div>{pozlar}</div>' if pozlar else ''}
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="rz-anomaly-ok">
          <div style="font-family:'Space Grotesk',sans-serif;font-size:1rem;font-weight:600;color:#00FF88;">
            ✅ Anormal büyüme sinyali yok — pazar dengeli görünüyor
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.markdown('<div class="rz-lbl" style="margin-bottom:10px;">📊 En Çok İlan Açan Şirketler (Top 20)</div>',
                unsafe_allow_html=True)
    df_pos = pd.DataFrame([
        {"Durum": "🔴 Anormal" if r["anormal"] else "🟢 Normal",
         "Şirket": r["şirket"],
         "İlan Sayısı": r["ilan_sayisi"],
         "Örnek Pozisyonlar": " / ".join(r["ornek_pozisyonlar"])}
        for r in results
    ])
    st.dataframe(df_pos, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════
# Sayfa 4 — Rakip Radar (çoklu şirket radar chart)
# ════════════════════════════════════════════════════════════════

def render_rz_radar():
    import plotly.graph_objects as go

    _load_api_keys()
    _cyber_header("Rakip Radar",
                  "çoklu şirket karşılaştırması · radar analizi · büyüme tespiti", "RADAR")

    def _mock_scores(company: str) -> dict:
        rng = random.Random(hash(company) % 9999)
        return {
            "iş_ilanı":      rng.randint(20, 95),
            "commit":        rng.randint(15, 90),
            "sentiment":     rng.randint(10, 85),
            "trend":         rng.randint(25, 95),
            "anomali_skoru": rng.randint(5, 80),
        }

    st.markdown("""
    <div class="rz-glass-card" style="padding:14px 22px;margin-bottom:8px;">
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.76rem;color:var(--rz-t3);">
        // 2–5 rakip şirket gir · 5 eksenli radar chart ile karşılaştır · kim daha hızlı büyüyor?
      </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4, c5, c_btn = st.columns([2, 2, 2, 2, 2, 1])
    placeholders = ["Stripe", "Adyen", "Klarna", "Brex", "Wise"]
    raw_inputs = []
    for col, ph in zip([c1, c2, c3, c4, c5], placeholders):
        with col:
            raw_inputs.append(st.text_input("_", placeholder=ph,
                                            label_visibility="collapsed",
                                            key=f"rz_radar_co_{ph}"))
    with c_btn:
        radar_btn = st.button("⬡ Analiz", use_container_width=True, key="rz_radar_submit")

    if radar_btn:
        companies = [c.strip() for c in raw_inputs if c.strip()]
        if len(companies) >= 2:
            with st.spinner("Şirketler analiz ediliyor…"):
                scores = {co: _mock_scores(co) for co in companies}
            st.session_state["rz_radar_scores"] = scores
            st.session_state["rz_radar_companies"] = companies
        else:
            st.warning("En az 2 şirket gir.")

    scores    = st.session_state.get("rz_radar_scores")
    companies = st.session_state.get("rz_radar_companies", [])

    if not scores or len(companies) < 2:
        st.markdown("""
        <div class="rz-glass-card" style="text-align:center;padding:50px 40px;">
          <div style="font-size:3rem;margin-bottom:16px;filter:drop-shadow(0 0 24px rgba(139,92,246,0.6));">🎯</div>
          <div style="font-family:'Space Grotesk',sans-serif;font-size:1.1rem;color:var(--rz-t2);margin-bottom:8px;">
            En az 2 şirket girerek karşılaştırmayı başlatın
          </div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:var(--rz-t3);">
            // 5 eksen: iş ilanı · commit · sentiment · trend · anomali skoru
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    ranking = sorted(companies, key=lambda c: sum(scores[c].values()), reverse=True)
    winner  = ranking[0]
    total_winner = sum(scores[winner].values())

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,rgba(0,245,255,0.06),rgba(139,92,246,0.08));
         border:1px solid rgba(0,245,255,0.25);border-left:4px solid #00F5FF;
         border-radius:14px;padding:20px 28px;margin-bottom:24px;">
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;color:var(--rz-t3);
           text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;">🏆 En Hızlı Büyüyen</div>
      <div style="font-family:'Space Grotesk',sans-serif;font-size:1.6rem;font-weight:700;color:#00F5FF;">
        {winner}
      </div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.8rem;color:var(--rz-t2);margin-top:4px;">
        Toplam skor: <span style="color:#00F5FF;">{total_winner}/500</span> · Rakiplerden üstün büyüme dinamiği
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Radar chart
    categories  = ["İş İlanı", "Commit", "Sentiment", "Trend", "Anomali Skoru"]
    cat_closed  = categories + [categories[0]]
    PALETTE = [(0,245,255),(255,0,110),(139,92,246),(0,255,136),(255,184,0)]

    fig = go.Figure()
    for i, co in enumerate(companies):
        vals = [scores[co]["iş_ilanı"], scores[co]["commit"], scores[co]["sentiment"],
                scores[co]["trend"], scores[co]["anomali_skoru"]]
        vals_closed = vals + [vals[0]]
        r, g, b = PALETTE[i % len(PALETTE)]
        fig.add_trace(go.Scatterpolar(
            r=vals_closed, theta=cat_closed, fill="toself", name=co,
            line=dict(color=f"rgba({r},{g},{b},1)", width=2.5),
            fillcolor=f"rgba({r},{g},{b},0.08)",
            marker=dict(size=7, color=f"rgba({r},{g},{b},1)"),
            hovertemplate=f"<b>{co}</b><br>%{{theta}}: %{{r}}<extra></extra>",
        ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(8,13,26,0.8)",
            radialaxis=dict(visible=True, range=[0,100],
                            gridcolor="rgba(0,245,255,0.08)",
                            linecolor="rgba(0,245,255,0.1)",
                            tickfont=dict(family="JetBrains Mono", size=10, color="#475569"),
                            tickvals=[20,40,60,80,100]),
            angularaxis=dict(gridcolor="rgba(0,245,255,0.08)",
                             linecolor="rgba(0,245,255,0.15)",
                             tickfont=dict(family="Space Grotesk", size=12, color="#94A3B8")),
        ),
        paper_bgcolor="rgba(3,7,18,0)", plot_bgcolor="rgba(3,7,18,0)",
        font=dict(family="Space Grotesk", color="#94A3B8"),
        legend=dict(font=dict(family="Space Grotesk", size=13, color="#E2E8F0"),
                    bgcolor="rgba(8,13,26,0.7)", bordercolor="rgba(0,245,255,0.15)",
                    borderwidth=1),
        margin=dict(t=40, b=40, l=60, r=60), height=520,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown('<div class="rz-lbl" style="margin-bottom:14px;">📊 Detaylı Karşılaştırma</div>',
                unsafe_allow_html=True)

    axes      = ["iş_ilanı", "commit", "sentiment", "trend", "anomali_skoru"]
    ax_labels = ["💼 İş İlanı", "⚙️ Commit", "📰 Sentiment", "📈 Trend", "🚨 Anomali"]

    rows_html = ""
    for co in ranking:
        rank_i = ranking.index(co)
        medal  = ["🥇","🥈","🥉"][rank_i] if rank_i < 3 else f"#{rank_i+1}"
        total  = sum(scores[co].values())
        cells  = "".join(
            f'<td style="padding:10px 14px;font-family:\'JetBrains Mono\',monospace;'
            f'font-size:0.85rem;color:#00F5FF;text-align:center;">{scores[co][a]}</td>'
            for a in axes
        )
        bg = "rgba(0,245,255,0.04)" if rank_i == 0 else "transparent"
        rows_html += f"""
        <tr style="border-bottom:1px solid rgba(0,245,255,0.06);background:{bg};">
          <td style="padding:10px 14px;font-family:'Space Grotesk',sans-serif;
               font-weight:600;color:#E2E8F0;">{medal} {co}</td>
          {cells}
          <td style="padding:10px 14px;font-family:'JetBrains Mono',monospace;
               font-size:0.9rem;font-weight:700;color:#8B5CF6;text-align:center;">{total}</td>
        </tr>
        """
    headers_html = "".join(
        f'<th style="padding:8px 14px;color:#475569;font-family:\'Space Grotesk\',sans-serif;'
        f'font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:500;'
        f'text-align:center;">{lbl}</th>'
        for lbl in ax_labels
    )
    components.html(f"""
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <div style="background:rgba(8,13,26,0.6);border:1px solid rgba(0,245,255,0.12);
         border-radius:14px;overflow:hidden;backdrop-filter:blur(20px);">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="border-bottom:1px solid rgba(0,245,255,0.12);background:rgba(0,245,255,0.03);">
            <th style="padding:8px 14px;color:#475569;font-family:'Space Grotesk',sans-serif;
                font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;
                font-weight:500;text-align:left;">Şirket</th>
            {headers_html}
            <th style="padding:8px 14px;color:#8B5CF6;font-family:'Space Grotesk',sans-serif;
                font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;
                font-weight:500;text-align:center;">TOPLAM</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """, height=60 + len(companies) * 52)


# ════════════════════════════════════════════════════════════════
# Ana giriş noktası — app.py'den çağrılır
# ════════════════════════════════════════════════════════════════

def render_rakip_zekasi():
    """SkillPulse'daki Rakip Zekasi sekmesinin tüm içeriğini çizer."""
    st.markdown(_COMPONENT_CSS, unsafe_allow_html=True)

    # Demo banner
    st.markdown("""
<div style="background:#140e00;border:1px solid #2a1f00;border-left:3px solid #F59E0B;
     border-radius:8px;padding:12px 18px;margin-bottom:20px;
     display:flex;align-items:center;gap:12px;">
  <i class="ph ph-warning-circle" style="color:#F59E0B;font-size:20px;flex-shrink:0;"></i>
  <span style="font-family:Inter,sans-serif;font-size:0.81rem;color:#8B8B8B;line-height:1.5;">
    <strong style="color:#F59E0B;">Demo Modu</strong> — Veriler mock datadır.
    Gerçek sinyal verisi 30 günlük pipeline koşusu sonrası oluşur.
  </span>
</div>
""", unsafe_allow_html=True)

    # Metodoloji toggle
    _hcol, _bcol = st.columns([8, 1])
    with _bcol:
        if st.button("Metodoloji", use_container_width=True, key="rz_how_btn"):
            st.session_state["rz_show_how"] = not st.session_state.get("rz_show_how", False)
    if st.session_state.get("rz_show_how"):
        _how_it_works()

    st.divider()

    # Custom tab navigation
    _TABS = ["Raporlar", "Anlık Arama", "Pozisyon Analizi", "Rakip Radar"]
    active_idx = st.session_state.get("rz_active_tab", 0)

    cols = st.columns(len(_TABS))
    for i, (col, label) in enumerate(zip(cols, _TABS)):
        cls = "rz-tab-active" if i == active_idx else "rz-tab-btn"
        col.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
        with col:
            if st.button(label, key=f"rz_tab_{i}", use_container_width=True):
                st.session_state["rz_active_tab"] = i
                st.rerun()
        col.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom:8px'></div>", unsafe_allow_html=True)

    page = _TABS[active_idx]
    if page == "Raporlar":
        render_rz_raporlar()
    elif page == "Anlık Arama":
        render_rz_arama()
    elif page == "Pozisyon Analizi":
        render_rz_pozisyon()
    elif page == "Rakip Radar":
        render_rz_radar()
