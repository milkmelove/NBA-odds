"""Snapshot DraftKings lines, props and injuries (NBA + NFL + NCAA men's/women's basketball) from ESPN feeds.
Writes odds.json.gz (raw ESPN items) + meta.json to ./out"""
import json, gzip, time, os, sys, urllib.request, datetime as dt

UA = {"User-Agent": "Mozilla/5.0 (odds-snapshot)"}
def get(url, tries=3):
    err = ""
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception as e:
            err = str(e); time.sleep(2 * (i + 1))
    print("FAIL", url, err, file=sys.stderr)
    return None

# key -> (sport path, league path, extra query, use dates?)
LEAGUES = {"nba": ("basketball", "nba", "", True),
           "mens-college-basketball": ("basketball", "mens-college-basketball", "&groups=50&limit=400", True),
           "womens-college-basketball": ("basketball", "womens-college-basketball", "&groups=50&limit=400", True),
           "nfl": ("football", "nfl", "", False)}  # NFL: scoreboard default = current week
now = dt.datetime.now(dt.timezone.utc)
et = now - dt.timedelta(hours=5)
dates = sorted({et.strftime("%Y%m%d"), (et + dt.timedelta(days=1)).strftime("%Y%m%d")})
out = {"pulled_utc": now.isoformat(), "games": []}
stats = {}
for lg, (sport, path, extra, use_dates) in LEAGUES.items():
    stats[lg] = {"games": 0, "with_lines": 0, "props": 0}
    for d in (dates if use_dates else [None]):
        q = f"?dates={d}{extra}" if d else "?limit=100"
        sb = get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{path}/scoreboard{q}")
        if not sb: continue
        for ev in sb.get("events", []):
            comp = ev["competitions"][0]
            g = {"league": lg, "id": ev["id"], "date": ev["date"], "name": ev["name"],
                 "status": ev["status"]["type"]["name"],
                 "teams": [(c["homeAway"], c["team"]["abbreviation"]) for c in comp["competitors"]],
                 "odds": comp.get("odds"), "core_odds": None, "props": []}
            if g["status"] in ("STATUS_SCHEDULED", "STATUS_IN_PROGRESS", "STATUS_HALFTIME"):
                root = f"https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{path}/events/{ev['id']}/competitions/{ev['id']}/odds"
                co = get(root, tries=1)
                if co and co.get("items"): g["core_odds"] = co["items"]
                base = root + "/100/propBets"
                page = 1
                while True:
                    r = get(f"{base}?limit=200&page={page}", tries=1 if lg in ("mens-college-basketball","womens-college-basketball") else 3)
                    if not r: break
                    g["props"] += r.get("items", [])
                    if page >= r.get("pageCount", 1): break
                    page += 1
            out["games"].append(g)
            stats[lg]["games"] += 1
            stats[lg]["with_lines"] += bool(g["odds"] or g["core_odds"])
            stats[lg]["props"] += len(g["props"])
out["injuries"] = get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries")
os.makedirs("out", exist_ok=True)
with gzip.open("out/odds.json.gz", "wt") as f: json.dump(out, f)
meta = {"pulled_utc": out["pulled_utc"], "games": len(out["games"]), "by_league": stats,
        "props": sum(len(g["props"]) for g in out["games"])}
json.dump(meta, open("out/meta.json", "w"))
print(json.dumps(meta, indent=1))
