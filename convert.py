from pathlib import Path
from playwright.sync_api import sync_playwright

html = Path(r"C:\Users\0025BL744\Desktop\watsonx\infrastructure-incident-triage-assistant-3-page-pitch.html")

with sync_playwright() as p:
    browser = p.chromium.launch()

    page = browser.new_page()

    page.goto(
        f"file:///{html.resolve().as_posix()}",
        wait_until="networkidle"
    )

    page.pdf(
        path="report.pdf",
        format="A4",
        scale=2,
        print_background=True,
        margin={
            "top": "0",
            "bottom": "0",
            "left": "0",
            "right": "0"
        }
    )

    browser.close()

print("✅ PDF created successfully!")
print("Saved to:", html.with_suffix(".pdf"))