"""Browser-level checks with Playwright (headless Chromium).

T2c: rendered layout (photo, origin slot, text) has identical geometry in both conditions.
T5:  usability on a small phone screen (360x640): is the label visible without scrolling,
     and is it still visible while the participant answers the rating items?"""
import socket
import threading

import pytest
from werkzeug.serving import make_server

from conftest import enrol

pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def server(app):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = make_server("127.0.0.1", port, app)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def codes_by_condition(client, con):
    out = {}
    while len(out) < 2:
        code = enrol(client)
        cond = con.execute("SELECT condition FROM participants WHERE study_code=?", (code,)).fetchone()[0]
        out.setdefault(cond, code)
    return out


def boxes(page):
    return {sel: page.locator(sel).bounding_box() for sel in ("#profile-photo", "#origin-slot", "#profile-text")}


def test_T2c_layout_geometry_identical(server, client, con):
    codes = codes_by_condition(client, con)
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        for vp in ({"width": 1280, "height": 900}, {"width": 360, "height": 640}):
            page = b.new_page(viewport=vp)
            geo = {}
            for cond, code in codes.items():
                page.goto(f"{server}/s/{code}/profile/1")
                page.wait_for_load_state("networkidle")
                geo[cond] = boxes(page)
            for sel in geo[0]:
                g0, g1 = geo[0][sel], geo[1][sel]
                assert (g0["x"], g0["y"], g0["width"]) == (g1["x"], g1["y"], g1["width"]), sel
                assert abs(g0["height"] - g1["height"]) < 0.5 or sel == "#profile-text", sel
            page.close()
        b.close()


def test_T5_label_visibility_on_small_screen(server, client, con):
    code = codes_by_condition(client, con)[1]
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 360, "height": 640})
        page.goto(f"{server}/s/{code}/profile/1")
        page.wait_for_load_state("networkidle")
        vh = page.viewport_size["height"]
        lab = page.locator("#origin-label").bounding_box()
        first_item = page.locator("input[name=item1]").first.bounding_box()
        print(f"\n[T5] viewport=360x640 label_top={lab['y']:.0f}px label_bottom={lab['y']+lab['height']:.0f}px "
              f"first_rating_item_top={first_item['y']:.0f}px")
        assert lab["y"] + lab["height"] <= vh, "label is below the fold on first view"
        # Visibility while rating is checked by T7 (sticky origin bar, v3).
        b.close()


def test_T6_rating_tap_targets_on_small_phone(server, client, con):
    """v1 (commit 39569ff) FAILED: radios 13x13 px in 21 px cells.
    v2: each scale point is a full tappable button; must be >= 24x24 px (WCAG 2.2 SC 2.5.8),
    target 44 px height."""
    code = enrol(client)
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 360, "height": 640})
        page.goto(f"{server}/s/{code}/profile/1")
        page.wait_for_load_state("networkidle")
        sizes = page.evaluate("""() => [...document.querySelectorAll('.points .pt')]
            .map(e => { const r = e.getBoundingClientRect(); return [r.width, r.height]; })""")
        sw = page.evaluate("document.documentElement.scrollWidth")
        w = min(s[0] for s in sizes); h = min(s[1] for s in sizes)
        print(f"\n[T6] {len(sizes)} tap targets, smallest {w:.0f}x{h:.0f}px, page scrollWidth {sw}px")
        # tapping the button (not the tiny radio) selects the value
        page.locator(".points").first.locator(".pt").nth(4).click()
        checked = page.locator("input[name=item1]:checked").get_attribute("value")
        b.close()
    assert len(sizes) == 42
    assert w >= 24 and h >= 44
    assert sw <= 360, "horizontal scroll on a 360 px phone"
    assert checked == "5"


def test_T7_label_visible_while_rating_and_bar_identical(server, client, con):
    """v2 measurement: on 360x640 the label left the screen while rating items 5-6.
    v3: a sticky origin bar in the rating form; must show the label for every item (label condition)
    and have identical geometry in both conditions."""
    codes = codes_by_condition(client, con)
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        for vw, vh in ((360, 640), (390, 844), (1280, 900)):
            page = b.new_page(viewport={"width": vw, "height": vh})
            page.goto(f"{server}/s/{codes[1]}/profile/1"); page.wait_for_load_state("networkidle")
            for n in range(1, 7):
                page.locator(f".item:nth-child({n}) .points").scroll_into_view_if_needed()
                visible = page.evaluate("""(h) => [...document.querySelectorAll('.origin-label')].some(e => {
                    const r = e.getBoundingClientRect(); return r.top >= 0 && r.bottom <= h; })""", vh)
                assert visible, f"label not visible at {vw}x{vh} while rating item {n}"
            geo = {}
            for cond, code in codes.items():   # same profile (P1) in both conditions
                order = con.execute("SELECT profile_order FROM participants WHERE study_code=?",
                                    (code,)).fetchone()[0].split(",")
                page.goto(f"{server}/s/{code}/profile/{order.index('P1') + 1}"); page.wait_for_load_state("networkidle")
                geo[cond] = page.locator("#origin-slot-2").bounding_box()
            assert geo[0] == geo[1], f"sticky bar differs between conditions at {vw}x{vh}"
            page.close()
        b.close()
