import asyncio
from playwright.async_api import async_playwright

def update_status(status_message, dot_type="green"):
    dots = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
    dot = dots.get(dot_type, "🟢")
    formatted_msg = f"{dot} {status_message}\n"
    print(formatted_msg.strip(), flush=True)
    mode = "w" if "Process Started" in status_message else "a"
    with open("output_status.txt", mode, encoding="utf-8") as f:
        f.write(formatted_msg)

async def debug_footystream():
    update_status("Process Started (Debug Mode)...", "green")
    url = "https://footystream.pk/"

    try:
        async with async_playwright() as p:
            update_status("Launching browser in headless mode...", "green")
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            update_status(f"Opening website: {url}", "green")
            await page.goto(url, timeout=60000)

            update_status("Waiting for page to fully render...", "yellow")
            # একটু বেশি সময় দেওয়া যাতে জাভাস্ক্রিপ্ট পুরোপুরি লোড হতে পারে
            await page.wait_for_timeout(8000)

            # পেজের সমস্ত এংকর ট্যাগ (<a>) এবং তাদের href ও টেক্সট সংগ্রহ করা
            links = await page.locator("a").all()
            link_details = []
            
            for idx, link in enumerate(links):
                href = await link.get_attribute("href")
                text = await link.inner_text()
                if href or text.strip():
                    link_details.append(f"Link {idx+1}: Href='{href}' | Text='{text.strip().replace(chr(10), ' | ')}'")

            # একটি ডিবাগ ফাইলে সমস্ত লিংক ও স্ট্রাকচার সেভ করা
            with open("debug_links.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(link_details))
            
            update_status(f"Found {len(link_details)} links/elements. Saved to debug_links.txt", "green")

            # পুরো পেজের আউটার এইচটিএমএল ও সেভ করে নেওয়া যাতে ট্যাগগুলো দেখা যায়
            content = await page.content()
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(content)
            update_status("Full page HTML saved to debug_page.html", "green")

            await browser.close()
            update_status("Debug process completed successfully.", "green")

    except Exception as e:
    update_status(f"CRITICAL_ERROR: {e}", "red")

if __name__ == "__main__":
    asyncio.run(debug_footystream())
