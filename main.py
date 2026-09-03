import asyncio
import json
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

def update_status(status_message, dot_type="green"):
    dots = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
    dot = dots.get(dot_type, "🟢")
    formatted_msg = f"{dot} {status_message}\n"
    print(formatted_msg.strip(), flush=True)
    
    mode = "w" if "Process Started" in status_message else "a"
    with open("output_status.txt", mode, encoding="utf-8") as f:
        f.write(formatted_msg)

async def scrape_footystream():
    update_status("Process Started...", "green")
    url = "https://footystream.pk/"
    events_data = []

    try:
        async with async_playwright() as p:
            update_status("Launching browser in headless mode...", "green")
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            update_status(f"Opening homepage: {url}", "green")
            await page.goto(url, timeout=30000)

            # দ্রুত পেজ লোড হওয়ার জন্য ছোট অপেক্ষা
            try:
                update_status("Waiting for event cards to load...", "yellow")
                await page.wait_for_selector('a[href*="/events/"]', timeout=5000)
            except:
                update_status("Selector wait timeout, proceeding with current content...", "yellow")

            html_content = await page.content()
            await browser.close()
            update_status("Browser closed successfully.", "green")

            soup = BeautifulSoup(html_content, 'html.parser')

            # হোমপেজের সমস্ত ইভেন্ট কার্ড খুঁজে বের করা (কোনোটা বাদ না দিয়ে)
            cards = soup.find_all('a', href=lambda href: href and '/events/' in href)
            total_cards = len(cards)

            if total_cards > 0:
                update_status(f"Successfully found {total_cards} live event cards.", "green")
            else:
                update_status("HOMEPAGE_ERROR: Found 0 live event cards.", "red")

            for index, card in enumerate(cards, start=1):
                try:
                    # ১. স্ট্রিমিং পেজ বা ডিটেইল পেজের লিংক
                    href = card.get('href', '')
                    details_page = href if href.startswith("http") else f"https://footystream.pk{href}" if href else url

                    full_text = card.get_text(separator="\n", strip=True)
                    
                    # টেক্সট লাইনগুলো বের করা (কোনো কার্ড ফিল্টার করে বাদ দেওয়া হবে না)
                    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                    
                    # স্ট্যাটাস বা সময় বাদ দিয়ে টিম নাম বের করার চেষ্টা, না পেলে সাধারণ লাইন ধরে নেওয়া হবে
                    filtered_lines = [l for l in lines if not ("Live Now!" in l or "Starts in" in l or "UTC" in l)]
                    if not filtered_lines:
                        filtered_lines = lines

                    team1 = filtered_lines[0] if len(filtered_lines) > 0 else "Team 1"
                    team2 = filtered_lines[1] if len(filtered_lines) > 1 else "Team 2"

                    # ২ ও ৩. দুইটা টিমের লোগো সংগ্রহ করা
                    logo1, logo2 = "", ""
                    imgs = card.find_all('img')
                    if len(imgs) > 0:
                        logo1 = imgs[0].get('src', '')
                    if len(imgs) > 1:
                        logo2 = imgs[1].get('src', '')

                    # আপনার নির্দিষ্ট ৫টি ডাটা অবিকৃতভাবে যুক্ত করা
                    event_item = {
                        "team1Title": team1,
                        "team2Title": team2,
                        "team1Logo": logo1,
                        "team2Logo": logo2,
                        "detailsPage": details_page
                    }

                    # কোনো শর্তে কার্ড বাদ না দিয়ে সরাসরি লিস্টে যুক্ত করা হলো
                    events_data.append(event_item)

                except Exception as card_err:
                    update_status(f"PARSING_ERROR on card {index}: {card_err}", "red")

        # JSON ফাইলে সব ডেটা সেভ করা
        with open("live_event_card.json", "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=4)
        
        update_status(f"Process completed successfully. Total collected events: {len(events_data)}", "green")

    except Exception as e:
        update_status(f"CRITICAL_ERROR: {e}", "red")

if __name__ == "__main__":
    asyncio.run(scrape_footystream())
