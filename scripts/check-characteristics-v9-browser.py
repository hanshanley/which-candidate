"""Check the local V9 report, literal provenance, filters and frozen navigation."""

import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def check():
    handler = functools.partial(QuietHandler, directory=ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors = []
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            for javascript, width in ((True, 1280), (True, 390), (True, 320), (False, 320)):
                context = browser.new_context(
                    java_script_enabled=javascript, viewport={"width": width, "height": 900}
                )
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                response = page.goto(
                    f"http://127.0.0.1:{server.server_port}/publication/characteristics-v9/report.html",
                    wait_until="networkidle",
                )
                assert response.status == 200
                assert page.locator("#candidates tbody tr").count() == 1284
                assert page.locator("#candidates thead th").count() == 17
                assert page.locator("#candidates tbody tr td details").count() == 1284 * 15
                for version in range(1, 9):
                    assert (
                        page.locator(
                            f'nav a[href="../characteristics-v{version}/report.html"]'
                        ).count()
                        == 1
                    )
                layout = page.evaluate(
                    "({width:document.documentElement.clientWidth,"
                    "scroll:document.documentElement.scrollWidth,"
                    "controls:[...document.querySelectorAll('.filters > label,.filters input,"
                    ".filters select')].map(e=>({tag:e.tagName,right:e.getBoundingClientRect().right,"
                    "width:e.getBoundingClientRect().width}))})"
                )
                assert layout["scroll"] <= layout["width"], (javascript, width, layout)
                assert page.locator("img").count() == 2
                assert page.locator("img").evaluate_all(
                    "images => images.every(image => image.complete && image.naturalWidth > 0)"
                )
                if javascript:
                    page.locator("#search").fill("Kristi Burke")
                    visible = page.locator("#candidates tbody tr:visible")
                    assert visible.count() == 1 and "TN-01" in visible.inner_text()
                    military = visible.locator("td").nth(11).locator("details")
                    military.locator("summary").click()
                    assert military.locator("a[href*='churchvoterguides']").count() >= 1
                    page.locator("#search").fill("Caleb Walker")
                    assert visible.count() == 1 and "LA-03" in visible.inner_text()
                    assert visible.locator("a[href*='wrkf.org']").count() >= 1
                    page.locator("#search").fill("")
                    page.select_option("#party", "Democratic")
                    assert visible.count() == 449
                    page.select_option("#state", "TN")
                    assert 0 < visible.count() < 449
                    page.select_option("#sort", "gap")
                context.close()
            browser.close()
        assert not errors, errors
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    return {
        "javascript_viewport_widths": [1280, 390, 320],
        "no_javascript_viewport_widths": [320],
        "candidate_rows": 1284,
        "trait_columns_plus_candidate_and_outcome": 17,
        "literal_military_negative_and_source": "passed",
        "Walker_control_and_questionnaire_source": "passed",
        "filters_and_sort": "passed",
        "frozen_version_links_v1_through_v8": "passed",
        "decoded_figures_and_no_page_overflow": "passed",
        "page_errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
