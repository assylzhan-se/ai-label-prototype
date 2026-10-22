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
        # The participant must scroll to the rating items; is the label still on screen then?
        page.locator("input[name=item1]").first.scroll_into_view_if_needed()
        lab_after = page.locator("#origin-label").bounding_box()
        print(f"[T5] after scrolling to first rating item: label_top={lab_after['y']:.0f}px")
        assert lab_after["y"] >= 0, "label scrolled out of view while rating"
        b.close()


@pytest.mark.xfail(strict=True, reason="KNOWN ISSUE found in first implementation: 1-7 rating radios "
                   "are below the WCAG 2.2 (SC 2.5.8) 24x24 px minimum target size on a 360 px phone")
def test_T6_rating_tap_targets_on_small_phone(server, client, con):
    code = enrol(client)
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 360, "height": 640})
        page.goto(f"{server}/s/{code}/profile/1")
        page.wait_for_load_state("networkidle")
        w, h = page.evaluate("""() => { const r = document.querySelector('table.scale input[type=radio]')
                                .getBoundingClientRect(); return [r.width, r.height]; }""")
        cw = page.evaluate("() => document.querySelector('table.scale td:not(.stmt)').getBoundingClientRect().width")
        print(f"\n[T6] radio {w:.0f}x{h:.0f}px, cell width {cw:.0f}px (minimum 24x24)")
        b.close()
    assert min(w, h) >= 24 and cw >= 24
