"""Click 'Sound' in the viewer and check the audio element actually plays (Apple preview, control, replay sync)."""
import sys
import time

from playwright.sync_api import sync_playwright

base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", args=["--use-angle=d3d11", "--autoplay-policy=user-gesture-required"])
    pg = b.new_page(viewport={"width": 1600, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    state = "(() => { const a = document.getElementById('player'); return {src: a.src.slice(0, 60), t: +a.currentTime.toFixed(2), paused: a.paused, err: a.error && a.error.code}; })()"
    for url, action in [(f"{base}/viewer.html?song=global_00", None), (f"{base}/viewer.html?song=ctrl_flysong", None),
                        (f"{base}/viewer.html?song=korea_08", "#replay")]:
        pg.goto(url)
        pg.wait_for_selector("#sound")
        time.sleep(4)
        pg.click("#sound")
        if action:
            pg.click(action)
        time.sleep(3)
        s1 = pg.evaluate(state)
        time.sleep(2)
        s2 = pg.evaluate(state)
        clock = pg.evaluate("document.getElementById('clock').textContent")
        print(url.split("?")[1], action or "", s1, "->", s2["t"], "|", clock)
    print("errors:", errs[:3])
    b.close()
