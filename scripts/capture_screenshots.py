"""Browser E2E verification and screenshots of the FastAPI-backed FleetOps simulator."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.getenv("FLEETOPS_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = Path("artifacts/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    assert page.request.post(f"{BASE}/api/reset").ok
    assert page.goto(BASE, wait_until="domcontentloaded").ok
    page.wait_for_function('document.querySelectorAll("#fleet-grid > div").length === 4')
    page.screenshot(path=str(OUT / "01-dashboard.png"), full_page=True, animations="disabled")
    page.locator("#nav-faults").click()
    page.locator("#fault-cards-grid > div").first.wait_for()
    page.screenshot(path=str(OUT / "02-fault-injector.png"), full_page=True, animations="disabled")
    page.locator("#nav-terminal").click()
    page.locator("#terminal-input").fill("top")
    page.locator("#terminal-input").press("Enter")
    page.get_by_text("[SIMULATED DIAGNOSTIC]").wait_for()
    page.screenshot(path=str(OUT / "03-terminal.png"), full_page=True, animations="disabled")
    page.locator("#nav-health").click()
    page.locator("#run-script-btn").click()
    page.locator("#script-output-container pre").wait_for()
    page.screenshot(path=str(OUT / "04-health-check.png"), full_page=True, animations="disabled")
    page.locator("#nav-faults").click()
    page.locator("#fault-cards-grid button").first.click()
    page.locator("#modal-node-select").select_option("node-hetzner-01")
    page.locator("#modal-fault-type").select_option("disk")
    page.get_by_role("button", name="Execute Failure").click()
    page.wait_for_function('document.querySelector("#global-incident-count").textContent.trim() === "1"')
    page.screenshot(path=str(OUT / "05-active-fault.png"), full_page=True, animations="disabled")
    page.locator("#nav-tickets").click()
    page.locator("#tickets-list-container").get_by_text("NVMe Sector Reallocation Failure").first.wait_for()
    page.screenshot(path=str(OUT / "06-incident-ticket.png"), full_page=True, animations="disabled")
    state = page.request.get(f"{BASE}/api/state").json()
    assert len(state["nodes"]) == 4 and len(state["incidents"]) == 1
    assert state["incidents"][0]["status"] == "Open"
    assert state["nodes"][0]["status"] == "CRITICAL"
    assert page.request.post(f"{BASE}/api/incidents/{state['incidents'][0]['id']}/resolve").ok
    assert page.request.get(f"{BASE}/api/health-check").json()["healthy"] is True
    assert not errors, f"Browser JS errors: {errors}"
    print("PASS: browser UI, incident creation and recovery, 6 screenshots, no JS errors")
    browser.close()
