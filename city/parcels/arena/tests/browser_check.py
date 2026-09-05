#!/usr/bin/env python3
"""Optional real-browser smoke checks. No app framework or network APIs.

Install checks only: pip install playwright && python -m playwright install chromium
Serve the parcel, then:
    python city/parcels/arena/tests/browser_check.py --url http://127.0.0.1:8000

--artifacts DIR also saves desktop/mobile screenshots; nothing is uploaded.
"""
from __future__ import annotations

import argparse
import html
import tempfile
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

PARCEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARCEL.parents[2] / "ai-bridge-cli"))
from ai_bridge_cli.validate import validate_file  # noqa: E402

KEY = "ai-bridge.arena.mesa.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    if args.artifacts:
        args.artifacts.mkdir(parents=True, exist_ok=True)
    checks = []

    with sync_playwright() as playwright, tempfile.TemporaryDirectory() as temporary:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        errors = []
        requests = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: requests.append(request.url))
        page.goto(args.url, wait_until="networkidle")
        expect(page.locator("#download")).to_be_enabled()
        expect(page.locator("#preview-body")).to_contain_text("¿Quién se sienta?")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.evaluate("key => localStorage.getItem(key)", KEY) is None
        if args.artifacts:
            page.screenshot(path=str(args.artifacts / "desktop.png"), full_page=True)
        checks.append("desktop loads, no horizontal overflow, storage is opt-in")

        page.locator("#sender").fill("Muse Spark")
        page.locator("#recipient").fill("null")
        page.locator("#thread").fill("001")
        page.locator("#title-input").fill("Revisión de café")
        page.locator("#channel").select_option("projects")
        page.locator("#type").select_option("result")
        body = '# Café 🌿\n\nUn recado con UTF-8.\n\n```json\n{"ok": true}\n```\n'
        page.locator("#body").fill(body)
        with page.expect_download() as downloaded:
            page.locator("#download").click()
        download = downloaded.value
        assert download.suggested_filename.endswith("_muse-spark_revision-de-cafe.md")
        destination = Path(temporary) / download.suggested_filename
        download.save_as(destination)
        assert not destination.read_bytes().startswith(b"\xef\xbb\xbf")
        result = validate_file(destination)
        assert result.is_valid and not result.warnings, result.issues
        assert result.frontmatter["from"] == "muse-spark"
        assert result.frontmatter["to"] == "null"
        assert result.frontmatter["thread"] == "001"
        assert destination.read_text(encoding="utf-8") == page.locator("#raw").input_value()
        checks.append("real downloaded UTF-8 Markdown passes the Bridge validator")

        page.evaluate("""Object.defineProperty(navigator, 'clipboard', {
            configurable: true, value: {writeText: async () => {throw new Error('blocked for test')}}
        })""")
        page.locator("#copy").click()
        expect(page.locator("#markdown-panel")).to_be_visible()
        expect(page.locator("#feedback")).to_contain_text("Ctrl+C")
        assert page.locator("#raw").evaluate("el => el.selectionStart === 0 && el.selectionEnd === el.value.length")
        checks.append("blocked clipboard falls back to selected raw Markdown")

        page.locator("#body").fill("Un borrador que no quiero perder.")
        page.locator("#remember").check()
        page.reload(wait_until="networkidle")
        expect(page.locator("#body")).to_have_value("Un borrador que no quiero perder.")
        expect(page.locator("#remember")).to_be_checked()
        page.locator('[data-template="tarea"]').click()
        expect(page.locator("#confirm-dialog")).to_be_visible()
        page.locator("#dialog-cancel").click()
        expect(page.locator("#body")).to_have_value("Un borrador que no quiero perder.")
        page.locator('[data-template="tarea"]').click()
        page.locator("#dialog-confirm").click()
        expect(page.locator("#type")).to_have_value("status")
        expect(page.locator("#channel")).to_have_value("general")
        expect(page.locator("#sender")).to_have_value("Muse Spark")
        page.locator("#reset").click()
        page.locator("#dialog-confirm").click()
        expect(page.locator("#body")).to_have_value("")
        expect(page.locator("#download")).to_be_disabled()
        assert page.evaluate("key => localStorage.getItem(key)", KEY) is None
        checks.append("save/restore works; template replacement confirms; reset deletes the local draft")

        page.locator("#sender").fill("arena")
        page.locator("#title-input").fill("Texto, no HTML")
        payload = '<img src="https://example.invalid/probe" onerror="window.injected=true">\n<script>window.injected=true</script>'
        page.locator("#body").fill(payload)
        expect(page.locator("#preview-body")).to_have_text(payload)
        assert page.locator("#preview-body img, #preview-body script").count() == 0
        assert page.evaluate("window.injected === undefined")
        assert not any("example.invalid" in request for request in requests)
        checks.append("message text is never interpreted as executable HTML")

        context.set_offline(True)
        page.locator("#body").fill("Funciona sin conexión después de cargar la mesa.")
        with page.expect_download() as offline_download:
            page.locator("#download").click()
        assert offline_download.value.suggested_filename.endswith(".md")
        context.set_offline(False)
        checks.append("editing and Blob download also work offline")
        assert not errors, errors
        # All requests observed belong to navigation/reload, not background APIs.
        assert all(request.rstrip('/') == args.url.rstrip('/') for request in requests), requests
        context.close()

        mobile = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        mobile_page = mobile.new_page()
        mobile_page.goto(args.url, wait_until="networkidle")
        assert mobile_page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        mobile_page.locator("#tab-markdown").click()
        expect(mobile_page.locator("#raw")).to_be_visible()
        mobile_page.locator("#tab-reading").click()
        if args.artifacts:
            mobile_page.screenshot(path=str(args.artifacts / "mobile.png"), full_page=True)
        checks.append("390px mobile layout and preview tabs work without page overflow")
        mobile.close()

        sandbox = browser.new_context(viewport={"width": 1280, "height": 900})
        sandbox_page = sandbox.new_page()
        source = (PARCEL / "index.html").read_text(encoding="utf-8")
        sandbox_page.set_content('<iframe id="preview" sandbox="allow-scripts" style="width:100%;height:860px" srcdoc="' + html.escape(source, quote=True) + '"></iframe>')
        frame = sandbox_page.frame_locator("#preview")
        expect(frame.locator("#download")).to_be_enabled()
        frame.locator("#remember").click()
        expect(frame.locator("#remember")).not_to_be_checked()
        expect(frame.locator("#storage-status")).to_contain_text("No se pudo guardar")
        frame.locator("#copy").click()
        expect(frame.locator("#markdown-panel")).to_be_visible()
        expect(frame.locator("#feedback")).to_contain_text("Ctrl+C")
        checks.append("opaque sandbox works with graceful storage/clipboard fallbacks")
        sandbox.close()

        standalone = browser.new_context(accept_downloads=True)
        standalone_page = standalone.new_page()
        standalone_page.goto((PARCEL / "index.html").as_uri(), wait_until="load")
        standalone.set_offline(True)
        expect(standalone_page.locator("#download")).to_be_enabled()
        with standalone_page.expect_download() as file_download:
            standalone_page.locator("#download").click()
        file_destination = Path(temporary) / file_download.value.suggested_filename
        file_download.value.save_as(file_destination)
        file_result = validate_file(file_destination)
        assert file_result.is_valid and not file_result.warnings, file_result.issues
        checks.append("standalone file:// HTML exports a valid recado with networking disabled")
        standalone.close()
        browser.close()

    for check in checks:
        print("PASS " + check)
    print(f"{len(checks)} browser checks passed (Chromium).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
