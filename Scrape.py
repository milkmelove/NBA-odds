"""Snapshot NBA DraftKings lines, player props and injuries from ESPN's public feeds.
Writes odds.json.gz (raw ESPN items, nothing dropped) + meta.json to ./out"""
import json, gzip, time, os, sys, urllib.request, datetime as dt

UA = {"User-Agent": "Mozilla/5.0 (nba-odds-snapshot)"}
def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception as e:
            err = str(e); time.sleep(2 * (i + 1))
    print("FAIL", url, err, file=sys.stderr)
    return None

now = dt.datetime.now(dt.timezone.utc)
et = now - dt.timedelta(hours=5)  # ET (close enough for choosing dates)
dates = sorted({et.strftime("%Y%m%d"), (et + dt.timedelta(days=1)).strftime("%Y%m%d")})
out = {"pulled_utc": now.isoformat(), "games": []}
for d in dates:
    sb = get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d}")
    if not sb: continue
    for ev in sb.get("events", []):
        comp = ev["competitions"][0]
        g = {"id": ev["id"], "date": ev["date"], "name": ev["name"],
             "status": ev["status"]["type"]["name"],
             "teams": [(c["homeAway"], c["team"]["abbreviation"]) for c in comp["competitors"]],
             "odds": comp.get("odds"), "props": []}
        if g["status"] == "STATUS_SCHEDULED" or g["status"] == "STATUS_IN_PROGRESS":
            base = f"https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{ev['id']}/competitions/{ev['id']}/odds/100/propBets"
            page = 1
            while True:
                r = get(f"{base}?limit=200&page={page}")
                if not r: break
                g["props"] += r.get("items", [])
                if page >= r.get("pageCount", 1): break
                page += 1
        out["games"].append(g)
out["injuries"] = get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries")
os.makedirs("out", exist_ok=True)
with gzip.open("out/odds.json.gz", "wt") as f: json.dump(out, f)
json.dump({"pulled_utc": out["pulled_utc"], "games": len(out["games"]),
           "props": sum(len(g["props"]) for g in out["games"])}, open("out/meta.json", "w"))
print(open("out/meta.json").read())
