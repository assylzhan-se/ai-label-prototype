"""Capture real screenshots of the running prototype (both conditions, desktop + phone)
and measure rating-control tap-target sizes. Uses marked test sessions only."""
import os, socket, sys, threading
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
from app import create_app
from conftest import enrol
import db

OUT = os.path.join(ROOT, "docs", "screenshots")
os.makedirs(OUT, exist_ok=True)
dbp = os.path.join(OUT, "_screens.db")
if os.path.exists(dbp): os.remove(dbp)
app = create_app(db_path=dbp); c = app.test_client(); con = db.connect(dbp)
codes = {}
while len(codes) < 2:
    code = enrol(c)
    codes.setdefault(con.execute("SELECT condition FROM participants WHERE study_code=?", (code,)).fetchone()[0], code)
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = make_server("127.0.0.1", port, app); threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{port}"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    pg.goto(base + "/?test=1"); pg.screenshot(path=f"{OUT}/01_consent_mobile.png", full_page=True)
    for cond, name in ((1, "label"), (0, "nolabel")):
        pg.goto(f"{base}/s/{codes[cond]}/profile/1"); pg.wait_for_load_state("networkidle")
        pg.screenshot(path=f"{OUT}/02_profile_{name}_mobile.png")
        pg.screenshot(path=f"{OUT}/03_profile_{name}_mobile_full.png", full_page=True)
    pg.goto(f"{base}/s/{codes[1]}/post"); pg.screenshot(path=f"{OUT}/04_post_mobile.png", full_page=True)
    pg.goto(f"{base}/s/{codes[1]}/debrief"); pg.screenshot(path=f"{OUT}/05_debrief_mobile.png", full_page=True)
    # tap-target measurement on a small phone
    sp = b.new_page(viewport={"width": 360, "height": 640})
    sp.goto(f"{base}/s/{codes[1]}/profile/1"); sp.wait_for_load_state("networkidle")
    sizes = sp.evaluate("""() => [...document.querySelectorAll('table.scale input[type=radio]')]
        .map(e => {const r = e.getBoundingClientRect(); return [r.width, r.height];})""")
    cells = sp.evaluate("""() => { const r = document.querySelector('table.scale td:not(.stmt)').getBoundingClientRect(); return [r.width, r.height]; }""")
    print(f"360px phone: {len(sizes)} rating radios, radio size {sizes[0][0]:.0f}x{sizes[0][1]:.0f}px, cell {cells[0]:.0f}x{cells[1]:.0f}px")
    b.close()
srv.shutdown()
print("Saved:", sorted(f for f in os.listdir(OUT) if f.endswith(".png")))
