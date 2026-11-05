"""
Automated 1080p Portfolio Demo Video & Screenshot Generator for GitHub Repository Explainer.
Uses Playwright to smoothly navigate through the live app at http://localhost:5173,
saving:
  - portfolio-demo/github-repo-explainer-demo.webm (1080p video for portfolio & README preview)
  - portfolio-demo/1-overview.png
  - portfolio-demo/2-mermaid-diagram.png
  - portfolio-demo/3-file-explanations.png
  - portfolio-demo/4-onboarding-guide.png
"""

import os
import shutil
import time
from playwright.sync_api import sync_playwright

FRONTEND_URL = os.getenv("DEMO_URL", "http://localhost:5173")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio-demo")


def smooth_scroll(page, target_y: int, steps: int = 25, pause: float = 0.03):
    """Smoothly scroll the window to target_y for a polished video recording."""
    current_y = page.evaluate("() => window.scrollY")
    delta = (target_y - current_y) / steps
    for i in range(1, steps + 1):
        page.evaluate(f"() => window.scrollTo(0, {int(current_y + delta * i)})")
        time.sleep(pause)


def record_portfolio_demo():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"[1/5] Launching 1920x1080 Chromium recorder targeting {FRONTEND_URL} ...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=OUTPUT_DIR,
            record_video_size={"width": 1920, "height": 1080},
            color_scheme="dark",
        )
        page = context.new_page()

        # 1. Open app & showcase hero + history sidebar
        print("[2/5] Opening GitHub Repository Explainer dashboard...")
        page.goto(FRONTEND_URL, wait_until="networkidle")
        time.sleep(2.5)

        # Save Screenshot 1: Architecture Overview
        page.screenshot(path=os.path.join(OUTPUT_DIR, "1-overview.png"))

        # 2. Showcase Tab 1: Architecture Overview + Inline Mermaid Preview
        print("[3/5] Showcasing Architecture Overview & Mermaid Diagram...")
        smooth_scroll(page, 420, steps=25, pause=0.03)
        time.sleep(2.0)
        smooth_scroll(page, 780, steps=25, pause=0.03)
        time.sleep(2.0)
        smooth_scroll(page, 0, steps=20, pause=0.025)
        time.sleep(1.0)

        # 3. Showcase Tab 2: Interactive Mermaid Diagram
        diagram_tab = page.get_by_role("button", name="Mermaid Diagram")
        if diagram_tab.count() > 0:
            diagram_tab.click()
            time.sleep(2.0)
            page.screenshot(path=os.path.join(OUTPUT_DIR, "2-mermaid-diagram.png"))

            # Toggle Layout (Left -> Right vs Top -> Down)
            layout_btn = page.locator("button[title*='Switch Layout Direction']")
            if layout_btn.count() > 0:
                layout_btn.click()
                time.sleep(1.8)
                layout_btn.click()
                time.sleep(1.5)

            # Zoom in
            zoom_in_btn = page.locator("button[title*='Zoom In']")
            if zoom_in_btn.count() > 0:
                zoom_in_btn.click()
                time.sleep(1.0)

            reset_zoom_btn = page.locator("button[title='Reset Zoom']")
            if reset_zoom_btn.count() > 0:
                reset_zoom_btn.click()
                time.sleep(1.0)

            # Toggle Fullscreen view
            fs_btn = page.locator("button[title*='Fullscreen']")
            if fs_btn.count() > 0:
                fs_btn.click()
                time.sleep(2.0)
                exit_fs_btn = page.locator("button[title*='Exit Fullscreen']")
                if exit_fs_btn.count() > 0:
                    exit_fs_btn.click()
                    time.sleep(1.0)

        # 4. Showcase Tab 3: Grounded Per-File Explanations + Live Search Filter
        print("[4/5] Showcasing Grounded Per-File Explanations & Live Filter...")
        files_tab = page.locator("button", has_text="File Explanations")
        if files_tab.count() > 0:
            files_tab.click()
            time.sleep(2.0)
            page.screenshot(path=os.path.join(OUTPUT_DIR, "3-file-explanations.png"))
            smooth_scroll(page, 650, steps=25, pause=0.03)
            time.sleep(1.8)
            smooth_scroll(page, 0, steps=20, pause=0.025)
            time.sleep(1.0)

            search_input = page.locator("input[placeholder*='Filter files']")
            if search_input.count() > 0:
                search_input.click()
                for ch in "src":
                    search_input.type(ch, delay=120)
                time.sleep(1.8)
                search_input.fill("")
                time.sleep(1.0)

        # 5. Showcase Tab 4: "Start Here" Contributor Onboarding Guide
        print("[5/5] Showcasing 'Start Here' Contributor Onboarding Guide...")
        onboarding_tab = page.get_by_role("button", name="Start Here Guide")
        if onboarding_tab.count() > 0:
            onboarding_tab.click()
            time.sleep(2.0)
            page.screenshot(path=os.path.join(OUTPUT_DIR, "4-onboarding-guide.png"))
            smooth_scroll(page, 550, steps=25, pause=0.03)
            time.sleep(2.0)
            smooth_scroll(page, 0, steps=20, pause=0.025)
            time.sleep(1.2)

        video_path = page.video.path()
        context.close()
        browser.close()

        final_webm = os.path.join(OUTPUT_DIR, "github-repo-explainer-demo.webm")
        if os.path.exists(video_path):
            if os.path.exists(final_webm):
                os.remove(final_webm)
            shutil.move(video_path, final_webm)
            print("\n" + "=" * 70)
            print("PORTFOLIO DEMO VIDEO & SCREENSHOTS SAVED!")
            print(f"  Video:       {final_webm}")
            print(f"  Screenshots: {OUTPUT_DIR}\\1-overview.png ... 4-onboarding-guide.png")
            print("=" * 70)


if __name__ == "__main__":
    record_portfolio_demo()
