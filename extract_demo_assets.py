"""
Captures 4 crisp 1080p PNG screenshots and builds an auto-playing animated walkthrough GIF (demo.gif)
directly from the live app at http://localhost:5173 so README.md renders on GitHub and in IDE Preview!
"""

import os
import time
from PIL import Image
from playwright.sync_api import sync_playwright

FRONTEND_URL = os.getenv("DEMO_URL", "http://localhost:5173")
DEMO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio-demo")


def capture_screenshots_and_gif():
    os.makedirs(DEMO_DIR, exist_ok=True)
    frames = []

    def snap_frame(page, extra_save_name=None):
        temp_path = os.path.join(DEMO_DIR, f"_gif_frame_{len(frames):02d}.png")
        page.screenshot(path=temp_path)
        frames.append(temp_path)
        if extra_save_name:
            out_path = os.path.join(DEMO_DIR, extra_save_name)
            page.screenshot(path=out_path)
            print(f"Saved screenshot: {out_path}")

    print(f"[1/3] Capturing 1080p screenshots & GIF frames from {FRONTEND_URL} ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, color_scheme="dark")
        page.goto(FRONTEND_URL, wait_until="networkidle")
        time.sleep(2.0)

        # 1. Architecture Overview
        snap_frame(page, "1-overview.png")
        page.evaluate("() => window.scrollTo(0, 420)")
        time.sleep(0.5)
        snap_frame(page)
        page.evaluate("() => window.scrollTo(0, 0)")
        time.sleep(0.4)

        # 2. Mermaid Diagram
        diagram_tab = page.get_by_role("button", name="Mermaid Diagram")
        if diagram_tab.count() > 0:
            diagram_tab.click()
            time.sleep(1.5)
            snap_frame(page, "2-mermaid-diagram.png")

            # Toggle layout direction for a second frame
            layout_btn = page.locator("button[title*='Switch Layout Direction']")
            if layout_btn.count() > 0:
                layout_btn.click()
                time.sleep(1.2)
                snap_frame(page)
                layout_btn.click()
                time.sleep(1.0)

        # 3. File Explanations
        files_tab = page.locator("button", has_text="File Explanations")
        if files_tab.count() > 0:
            files_tab.click()
            time.sleep(1.2)
            snap_frame(page, "3-file-explanations.png")
            page.evaluate("() => window.scrollTo(0, 520)")
            time.sleep(0.5)
            snap_frame(page)
            page.evaluate("() => window.scrollTo(0, 0)")
            time.sleep(0.4)

        # 4. Onboarding Guide
        onboarding_tab = page.get_by_role("button", name="Start Here Guide")
        if onboarding_tab.count() > 0:
            onboarding_tab.click()
            time.sleep(1.2)
            snap_frame(page, "4-onboarding-guide.png")
            page.evaluate("() => window.scrollTo(0, 420)")
            time.sleep(0.5)
            snap_frame(page)

        browser.close()

    print("[2/3] Building animated walkthrough portfolio-demo/demo.gif ...")
    imgs = [Image.open(fp).resize((1280, 720), Image.Resampling.LANCZOS) for fp in frames]
    gif_path = os.path.join(DEMO_DIR, "demo.gif")
    imgs[0].save(
        gif_path,
        save_all=True,
        append_images=imgs[1:],
        duration=1100,
        loop=0,
        optimize=True,
    )
    print(f"Saved animated GIF: {gif_path}")

    for fp in frames:
        if os.path.exists(fp):
            os.remove(fp)
    print("[3/3] Done!")


if __name__ == "__main__":
    capture_screenshots_and_gif()
