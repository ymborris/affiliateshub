#!/usr/bin/env python3
"""
OfferPilot — launch-calendar crawler (GitHub Action worker).

Parses PUBLIC launch calendar pages into ../offers.json.
Best-effort: if scraping yields too little (site redesign, network issue),
the previous offers.json is kept and the run still succeeds — the site's
core features never depend on this feed.

Add more sources as (name, url, parser) triples in SOURCES.
"""
import json, re, sys, html, datetime, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (compatible; OfferPilotBot/1.0)"}
OUT = "offers.json"

NICHES = {
 "mmo":      ["make money","income","commission","affiliate","passive","side hustle","traffic","plr","profit","oto","funnel","list building"],
 "software": ["software","app","automation","tool","plugin"," ai","ai ","video creator","builder","cloud","saas","hosting","bot"],
 "health":   ["supplement","health","remedy","vitamin","joint","hearing","blood sugar","prostate","detox","tea","nerve"],
 "weightloss":["weight","fat","keto","slim","metabolism","diet","fitness","belly"],
 "dating":   ["dating","relationship","soulmate","attraction","romance"],
 "finance":  ["crypto","bitcoin","trading","forex","investment","gold ira","credit"],
 "selfhelp": ["manifestation","mindset","meditation","abundance","subconscious","numerology","moon reading"],
 "survival": ["survival","prepper","emp","blackout"],
 "pets":     ["dog","puppy","cat","pet"],
 "education":["course","masterclass","certification","training","ebook"],
}
def guess_niche(text):
    t = " " + text.lower() + " "
    best, score = "other", 0
    for k, words in NICHES.items():
        s = sum(1 for w in words if re.search(r"\b" + re.escape(w.strip()) + r"\b", t))
        if s > score: best, score = k, s
    return best

def guess_network(url, text, brand=""):
    t = (brand + " " + url + " " + text).lower()
    if "warrior" in t: return "WarriorPlus"
    if "jvzoo" in t or "jvz" in t: return "JVZoo"
    if "clickbank" in t: return "ClickBank"
    if "digistore" in t: return "Digistore24"
    return brand or ""

def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")

ITEM_RE = re.compile(r"class=['\"]item\s[^'\"]*['\"]>(.*?)(?=class=['\"]item\s|<footer|$)", re.I | re.S)
A_RE    = re.compile(r"<a href=['\"]([^'\"]+)['\"]\s+rel=['\"]bookmark['\"]>(.*?)</a>", re.I | re.S)
BRAND1  = re.compile(r"title=['\"]([^'\"]+)['\"][^>]*class=['\"][^'\"]*brand", re.I)
BRAND2  = re.compile(r"class=['\"][^'\"]*brand[^'\"]*['\"][^>]*title=['\"]([^'\"]+)", re.I)
NAME_RE = re.compile(r"itemprop=['\"]name['\"]\s+content=['\"]([^'\"]+)", re.I)
DATE_RE = re.compile(r"itemprop=['\"]releaseDate['\"]\s+content=['\"]([^'\"]+)", re.I)
DET_RE  = re.compile(r"item_details[^>]*>\s*(?:&nbsp;)?\s*([^<]+)", re.I)
PRICE_RE= re.compile(r"\$([\d,.]+)")
COMM_RE = re.compile(r"at\s*([\d.]+)\s*%")

def scrape_muncheye(url):
    page = get(url)
    found = []
    for m in ITEM_RE.finditer(page):
        b = m.group(1)
        a = A_RE.search(b)
        if not a:
            continue
        link = a.group(1)
        atitle = html.unescape(re.sub(r"<[^>]+>", " ", a.group(2)))
        atitle = re.sub(r"\s+", " ", atitle).strip()
        if len(atitle) < 3:
            continue
        bm = BRAND1.search(b) or BRAND2.search(b)
        brand = bm.group(1).strip() if bm else ""
        nm = NAME_RE.search(b)
        rd = DATE_RE.search(b)
        det = DET_RE.search(b)
        if not rd and not det:
            continue  # not a real launch entry
        details = html.unescape(det.group(1)).strip() if det else ""
        price, comm = 0, 0
        pm, cm = PRICE_RE.search(details), COMM_RE.search(details)
        if pm:
            try: price = float(pm.group(1).replace(",", ""))
            except ValueError: price = 0
        if cm:
            try: comm = float(cm.group(1))
            except ValueError: comm = 0
        name = nm.group(1).strip() if nm and len(nm.group(1).strip()) > 1 else atitle
        if link.startswith("/"):
            link = "https://muncheye.com" + link
        found.append({
            "name": name[:80],
            "url": link,
            "network": guess_network(link, atitle, brand),
            "niche": guess_niche(atitle + " " + name + " " + link),
            "launch": rd.group(1) if rd else "",
            "details": details,
            "price": price,
            "commPct": comm,
            "source": "MunchEye",
        })
    return found

SOURCES = [
    ("MunchEye", "https://muncheye.com/", scrape_muncheye),
    ("MunchEye p2", "https://muncheye.com/page/2", scrape_muncheye),
]

def scrape():
    offers, seen = [], set()
    for name, url, parser in SOURCES:
        try:
            rows = parser(url)
        except Exception as e:
            print(f"[skip] {name}: {e}", file=sys.stderr); continue
        for of in rows:
            key = of["name"].lower().strip()
            if not key or key in seen: continue
            seen.add(key); offers.append(of)
            if len(offers) >= 60: return offers
    return offers

def main():
    offers = scrape()
    if len(offers) < 3:
        print(f"Only {len(offers)} launches scraped — keeping previous offers.json"); return
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {"generated": now.isoformat(timespec="seconds").replace("+00:00", "Z"), "offers": offers}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"Wrote {OUT} with {len(offers)} launches")

if __name__ == "__main__":
    main()
