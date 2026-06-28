# =============================================================================
# DEVRE DIŞI — kariyer.net Cloudflare 403 kısıtlaması nedeniyle bu fetcher'ın
# yerini fetchers/jooble.py aldı (Jooble API, Türkiye ilanları).
# Geri açmak için: tüm satırların başındaki "# " kaldırılmalı ve app.py /
# main.py'deki jooble referansları kariyer'e çevrilmelidir.
# =============================================================================
# """
# kariyer.py — kariyer.net scraping fetcher (Phase 2).
# 
# SÖZLEŞME (adzuna.py ile aynı):
#     fetch(...) -> list[dict]   # her dict, fetchers.SCHEMA_FIELDS'e UYAR (source="kariyer")
# 
# ALTIN KURAL:
#     İlk çağrıda siteye gidilir, sonuç data/kariyer.json'a yazılır. Sonraki
#     çağrılarda diskten okunur. Siteye tekrar gitmek için force_refresh=True.
# 
# Nasıl çalışır (site Nuxt tabanlı, Cloudflare arkasında):
#     - cloudscraper ile liste sayfası çekilir:
#         https://www.kariyer.net/is-ilanlari/<slug>?cp=<sayfa>
#       (sayfalama parametresi 'cp'; 'currentPage' SİTE TARAFINDAN YOK SAYILIYOR.)
#     - BeautifulSoup ile ilan kartları (a.k-ad-card) parse edilir:
#         başlık  : .k-ad-card-title
#         şirket  : [data-test=subtitle] span
#         konum   : .location
#         tarih   : .ad-date (GÖRELİ: "Bugün", "2 gün", "3 hafta"...)
#     - Açıklama listede YOK; her ilanın detay sayfasından .job-detail-content alınır.
#     - Sponsorlu kartlar atlanır (her sayfada tekrar ederler, tarihleri temsili değil).
#     - Göreli tarih, çekim gününden geriye sayılarak "YYYY-MM-DD"ye çevrilir
#       (trend analizi AYLIK olduğu için bu hassasiyet yeterli).
# 
# NAZİKLİK: her HTTP isteği arasında time.sleep(2). Bir liste sayfası ~50 ilan
# demek; 50 detay isteği ~100 sn sürer. max_jobs ile sınırla.
# """
# import re
# import time
# import unicodedata
# from datetime import date, timedelta
# 
# import cloudscraper
# from bs4 import BeautifulSoup
# 
# from fetchers import validate_jobs
# from fetchers.cache import load_cache, save_cache
# 
# SOURCE = "kariyer"
# _BASE = "https://www.kariyer.net"
# _SLEEP = 2  # saniye — her istek arası (nazik ol)
# _TIMEOUT = 30
# 
# # ---------------------------------------------------------------------------
# # CLOUDFLARE BYPASS HAZIRLIĞI — HENÜZ AKTİF DEĞİL (Phase 3 adayı)
# # Mevcut durum: cloudscraper ~70 ardışık istekten sonra 403 yiyor; cache'te
# # bu yüzden hedeflenenden az ilan var. İki aday çözüm:
# # ---------------------------------------------------------------------------
# #
# # Yöntem A — Playwright stealth:
# # # from playwright.sync_api import sync_playwright
# # # from playwright_stealth import stealth_sync
# # Gerçek tarayıcı davranışı taklit eder: gerçek Chromium çalıştırır, JS
# # challenge'larını doğal olarak çözer, navigator/webdriver parmak izlerini
# # stealth eklentisiyle gizler. Artısı: 403 oranı düşer. Eksisi: ağır bağımlılık
# # (~300MB tarayıcı), istek başına çok daha yavaş. Kurulum:
# #   pip install playwright playwright-stealth && playwright install chromium
# #
# # Yöntem B — Günlük kademeli çekim:
# # # MAX_PAGES = 3  # Günde max 3 sayfa, haftada ~150 ilan
# # Cloudflare'in istek bütçesini hiç zorlama: her çalıştırmada az sayıda sayfa
# # çek, sonucu mevcut cache'e EKLE (üzerine YAZMA — href bazlı dedupe ile
# # birleştir), cron/launchd ile günde bir tetikle. Artısı: ek bağımlılık yok,
# # en "nazik" yol. Eksisi: veri yavaş birikir; date_posted göreli olduğu için
# # her günün çekimi kendi gününe göre tarihlenir (bu aslında zaman serisini
# # zenginleştirir).
# # ---------------------------------------------------------------------------
# 
# 
# def _slugify(query: str) -> str:
#     """'yazılım' -> 'yazilim' (URL path'i ASCII slug bekliyor)."""
#     text = query.strip().lower().replace("ı", "i")
#     text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
#     return re.sub(r"[^a-z0-9]+", "-", text).strip("-")
# 
# 
# # "update 2 gün" / "Bugün" / "Dün" / "3 hafta" / "1 ay" -> gün cinsinden yaş
# _REL_UNITS = {"saat": 0, "gün": 1, "hafta": 7, "ay": 30}
# 
# 
# def _parse_relative_date(text: str, today: date) -> str:
#     """Karttaki göreli tarihi 'YYYY-MM-DD'ye çevirir; çözülemezse ''."""
#     t = text.lower().replace("update", "").strip()
#     if not t:
#         return ""
#     if "bugün" in t or "yeni" in t or "şimdi" in t:
#         return today.isoformat()
#     if "dün" in t:
#         return (today - timedelta(days=1)).isoformat()
#     m = re.search(r"(\d+)\s*(saat|gün|hafta|ay)", t)
#     if not m:
#         return ""
#     days = int(m.group(1)) * _REL_UNITS[m.group(2)]
#     return (today - timedelta(days=days)).isoformat()
# 
# 
# def _parse_card(card, today: date) -> dict | None:
#     """Liste sayfasındaki bir ilan kartı -> kısmi kayıt (description'sız)."""
#     href = card.get("href", "")
#     if not href.startswith("/is-ilani/"):
#         return None
#     title_el = card.select_one(".k-ad-card-title")
#     company_el = card.select_one("[data-test='subtitle'] span, .subtitle span")
#     location_el = card.select_one(".location")
#     date_el = card.select_one(".ad-date")
#     return {
#         "href": href,
#         "title": title_el.get_text(" ", strip=True) if title_el else "",
#         "company": company_el.get_text(" ", strip=True) if company_el else "",
#         "location": location_el.get_text(" ", strip=True) if location_el else "",
#         "date_posted": _parse_relative_date(date_el.get_text(" ", strip=True) if date_el else "", today),
#     }
# 
# 
# def _fetch_description(session: dict, href: str) -> str:
#     """İlan detay sayfasından açıklama metni (.job-detail-content).
# 
#     Cloudflare ~70 ardışık istekten sonra 403 dönmeye başlayabiliyor;
#     403'te bir kez taze oturum + uzun bekleme ile yeniden denenir.
#     session: {"scraper": cloudscraper} — tazelenebilsin diye mutable sarmalayıcı.
#     """
#     for attempt in (1, 2):
#         resp = session["scraper"].get(_BASE + href, timeout=_TIMEOUT)
#         if resp.status_code == 200:
#             soup = BeautifulSoup(resp.text, "html.parser")
#             el = soup.select_one(".job-detail-content")
#             return el.get_text(" ", strip=True) if el else ""
#         if resp.status_code == 403 and attempt == 1:
#             print("[kariyer]   403 — 30 sn bekleyip taze oturumla yeniden denenecek")
#             time.sleep(30)
#             session["scraper"] = cloudscraper.create_scraper()
#         else:
#             return ""
#     return ""
# 
# 
# def _normalize(partial: dict, description: str) -> dict:
#     """Kısmi kayıt + açıklama -> DEĞİŞMEZ şema."""
#     return {
#         "title": partial["title"],
#         "company": partial["company"],
#         "description": description,
#         "location": partial["location"],
#         "date_posted": partial["date_posted"],
#         "source": SOURCE,
#     }
# 
# 
# def _scrape(query: str, pages: int, max_jobs: int) -> list[dict]:
#     scraper = cloudscraper.create_scraper()
#     session = {"scraper": scraper}
#     slug = _slugify(query)
#     today = date.today()
# 
#     partials: list[dict] = []
#     seen: set[str] = set()
#     for page in range(1, pages + 1):
#         url = f"{_BASE}/is-ilanlari/{slug}" + (f"?cp={page}" if page > 1 else "")
#         print(f"[kariyer] liste sayfası {page}/{pages}: {url}")
#         resp = scraper.get(url, timeout=_TIMEOUT)
#         if resp.status_code != 200:
#             print(f"[kariyer] sayfa {page} -> HTTP {resp.status_code}, durduruldu.")
#             break
#         soup = BeautifulSoup(resp.text, "html.parser")
#         cards = soup.select("a.k-ad-card")
#         n_before = len(partials)
#         for card in cards:
#             if card.select_one(".sponsored-title"):
#                 continue  # sponsorlu: her sayfada tekrar eder
#             rec = _parse_card(card, today)
#             if rec and rec["href"] not in seen:
#                 seen.add(rec["href"])
#                 partials.append(rec)
#         print(f"[kariyer]   {len(partials) - n_before} yeni ilan kartı")
#         if len(partials) >= max_jobs:
#             break
#         time.sleep(_SLEEP)
# 
#     partials = partials[:max_jobs]
#     print(f"[kariyer] {len(partials)} ilan için açıklama çekilecek (~{len(partials) * _SLEEP} sn)")
# 
#     jobs: list[dict] = []
#     consecutive_empty = 0
#     for i, partial in enumerate(partials, 1):
#         time.sleep(_SLEEP)
#         desc = _fetch_description(session, partial["href"])
#         if not desc:
#             consecutive_empty += 1
#             print(f"[kariyer]   {i}/{len(partials)} açıklama boş/403, atlandı: {partial['href']}")
#             if consecutive_empty >= 5:
#                 print("[kariyer] 5 ardışık başarısız istek — site engelliyor, NAZİKÇE durduruldu.")
#                 break
#             continue
#         consecutive_empty = 0
#         jobs.append(_normalize(partial, desc))
#         if i % 10 == 0:
#             print(f"[kariyer]   {i}/{len(partials)} detay alındı")
#     return jobs
# 
# 
# def fetch(
#     query: str = "yazılım",
#     pages: int = 2,
#     max_jobs: int = 60,
#     force_refresh: bool = False,
# ) -> list[dict]:
#     """kariyer.net ilanlarını şemaya uygun list[dict] olarak döndürür.
# 
#     İlk kez (veya force_refresh=True) siteye gider ve data/kariyer.json'a yazar;
#     aksi halde diskten okur. max_jobs: detay isteği sayısını sınırlar (nazik ol).
#     """
#     if not force_refresh:
#         cached = load_cache(SOURCE)
#         if cached is not None:
#             return validate_jobs(cached)
# 
#     jobs = _scrape(query, pages, max_jobs)
#     validate_jobs(jobs)
#     save_cache(SOURCE, jobs)
#     print(f"[kariyer] {len(jobs)} ilan cache'lendi -> data/kariyer.json")
#     return jobs
