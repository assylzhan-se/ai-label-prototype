"""Measure whether the label is on screen while each rating statement is brought into view
(minimal scroll, as a participant scrolling down would see it). Test session only."""
import os, socket, sys, threading
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
from app import create_app
from conftest import enrol
import db
dbp = os.path.join(ROOT, "data", "_visibility.db")
if os.path.exists(dbp): os.remove(dbp)
app = create_app(db_path=dbp); c = app.test_client(); con = db.connect(dbp)
while True:
    code = enrol(c)
    if con.execute("SELECT condition FROM participants WHERE study_code=?", (code,)).fetchone()[0] == 1: break
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = make_server("127.0.0.1", port, app); threading.Thread(target=srv.serve_forever, daemon=True).start()
print("viewport,item,visible_label_top_px,label_visible")
with sync_playwright() as p:
    b = p.chromium.launch()
    for w, h in ((360, 640), (390, 844), (1280, 900)):
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.goto(f"http://127.0.0.1:{port}/s/{code}/profile/1"); pg.wait_for_load_state("networkidle")
        for n in range(1, 7):
            pg.locator(f".item:nth-child({n}) .points").scroll_into_view_if_needed()
            boxes = [pg.locator(sel).bounding_box() for sel in ("#origin-label", "#origin-label-2")]
            vis = [bb for bb in boxes if bb and bb["y"] >= 0 and bb["y"] + bb["height"] <= h]
            top = min(bb["y"] for bb in vis) if vis else float("nan")
            print(f"{w}x{h},{n},{top:.0f},{int(bool(vis))}")
        pg.close()
    b.close()
srv.shutdown(); os.remove(dbp)
