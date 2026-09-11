"""Headless check of the web viewer: console errors + screenshot."""
import sys
import time

from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/viewer.html"
out = sys.argv[2] if len(sys.argv) > 2 else "viewer.png"
wait = float(sys.argv[3]) if len(sys.argv) > 3 else 6
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1600, "height": 900})
    logs = []
    pg.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: logs.append(f"PAGEERROR: {e}"))
    pg.goto(url)
    time.sleep(wait)
    pg.screenshot(path=out)
    for l in logs[:30]:
        print(l)
    b.close()
