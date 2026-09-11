"""Render a few frames of docs/video.html (sequentially up to each target) and save screenshots."""
import sys

from playwright.sync_api import sync_playwright

base = sys.argv[1]
targets = [int(x) for x in sys.argv[2].split(",")]
out = sys.argv[3]
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(base + "/video.html")
    pg.wait_for_function("window.ready === true", timeout=120_000)
    for i in range(max(targets) + 1):
        pg.evaluate("async (i) => { renderAt(i); const c = document.getElementById('cover'); if (c && c.src && !c.complete) await c.decode().catch(()=>{}); }", i)
        if i in targets:
            pg.screenshot(path=out.replace(".png", f"_{i}.png"))
    print(errs[:5])
    b.close()
