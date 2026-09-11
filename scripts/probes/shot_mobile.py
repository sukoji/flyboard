"""Mobile screenshots (iPhone-sized viewport, touch) of a page: viewport shot + full-page shot + overflow check."""
import sys
import time

from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
wait = float(sys.argv[3]) if len(sys.argv) > 3 else 6
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    time.sleep(wait)
    pg.screenshot(path=out.replace(".png", "_view.png"))
    pg.screenshot(path=out.replace(".png", "_full.png"), full_page=True)
    print("scrollWidth", pg.evaluate("document.documentElement.scrollWidth"), "clientWidth",
          pg.evaluate("document.documentElement.clientWidth"), "height", pg.evaluate("document.documentElement.scrollHeight"))
    wide = pg.evaluate("""[...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1)
                          .slice(0, 8).map(e => e.tagName + '.' + (e.className || '') + ' ' + Math.round(e.getBoundingClientRect().right))""")
    print("overflowing:", wide)
    print("errors:", errs[:3])
    b.close()
