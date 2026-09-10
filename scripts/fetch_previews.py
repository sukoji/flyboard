"""Find each chart song on the iTunes Search API and download its official 30 s preview.

Audio stays local (audio/ is gitignored); only track metadata is written to results/tracks.csv.
"""
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BAD = re.compile(r"instrumental|karaoke|カラオケ|off vocal|inst\.|remix|live|acoustic|cover|8-bit|music box|tv size|sped up",
                 re.I)


def norm(s):
    s = unicodedata.normalize("NFKC", str(s)).lower()
    return re.sub(r"[\s\W_]+", "", s)


def search(term, country):
    q = urllib.parse.urlencode({"term": term, "country": country, "media": "music", "entity": "song", "limit": 25})
    with urllib.request.urlopen(f"https://itunes.apple.com/search?{q}", timeout=20) as r:
        return json.load(r)["results"]


def pick(results, artist, title):
    a, t = norm(artist), norm(title)
    best, best_score = None, 0
    for r in results:
        if not r.get("previewUrl"):
            continue
        ra, rt = norm(r.get("artistName", "")), norm(r.get("trackName", ""))
        score = 0
        score += 4 if t == rt else 3 if (t in rt or rt in t) else 0
        score += 3 if (a in ra or ra in a) else 0
        if BAD.search(r.get("trackName", "")) and not BAD.search(title):
            score -= 5
        if score > best_score:
            best, best_score = r, score
    return best if best_score >= 6 else None


def main(charts=("global", "japan", "korea")):
    rows = []
    path = ROOT / "results" / "tracks.csv"
    done = pd.read_csv(path).set_index("id") if path.exists() else pd.DataFrame()
    for chart in charts:
        songs = pd.read_csv(ROOT / "charts" / f"{chart}.csv")
        (ROOT / "audio" / chart).mkdir(parents=True, exist_ok=True)
        for i, s in songs.iterrows():
            sid = f"{chart}_{i:02d}"
            if sid in done.index and done.loc[sid, "found"] and done.loc[sid, "title"] == s.title \
                    and (ROOT / str(done.loc[sid, "audio"])).exists():
                rows.append({"id": sid, **done.loc[sid].to_dict()})
                continue
            hit = None
            for country in dict.fromkeys([s.country, "US", "JP", "KR"]):
                try:
                    hit = pick(search(f"{s.artist} {s.title}", country), s.artist, s.title)
                except Exception as e:  # rate limit / network: back off once
                    print("  retry:", e)
                    time.sleep(20)
                    hit = pick(search(f"{s.artist} {s.title}", country), s.artist, s.title)
                time.sleep(3)
                if hit:
                    break
            if not hit:
                print(f"MISS  {sid} {s.artist} - {s.title}")
                rows.append({"id": sid, "chart": chart, **s.to_dict(), "found": False})
                continue
            dst = ROOT / "audio" / chart / f"{i:02d}.m4a"
            if not dst.exists():
                urllib.request.urlretrieve(hit["previewUrl"], dst)
            print(f"ok    {sid} {s.artist} - {s.title}  ->  {hit['artistName']} - {hit['trackName']} ({country})")
            rows.append({"id": sid, "chart": chart, **s.to_dict(), "found": True,
                         "itunes_artist": hit["artistName"], "itunes_track": hit["trackName"],
                         "itunes_url": hit.get("trackViewUrl", ""), "audio": str(dst.relative_to(ROOT))})
    (ROOT / "results").mkdir(exist_ok=True)
    path = ROOT / "results" / "tracks.csv"
    new = pd.DataFrame(rows)
    if path.exists():  # keep rows of charts not fetched this run
        old = pd.read_csv(path)
        new = pd.concat([old[~old.chart.isin(charts)], new]).sort_values("id")
    new.to_csv(path, index=False, encoding="utf-8")


if __name__ == "__main__":
    main(tuple(sys.argv[1:]) or ("global", "japan", "korea"))
