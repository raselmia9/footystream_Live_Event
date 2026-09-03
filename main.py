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

            # সময় বাঁচানোর জন্য অতিরিক্ত ৭ সেকেন্ড না রেখে ডাইনামিক এলিমেন্ট লোডের জন্য স্মার্ট ওয়েট ব্যবহার করা হলো
            try:
                update_status("Waiting for event cards to load...", "yellow")
                await page.wait_for_selector('a[href*="/events/"]', timeout=5000)
            except:
                update_status("Selector wait timeout, proceeding with current content...", "yellow")

            html_content = await page.content()
            await browser.close()
            update_status("Browser closed successfully.", "green")

            soup = BeautifulSoup(html_content, 'html.parser')

            # কোনো কার্ড যাতে মিস না হয়, তার জন্য সুনির্দিষ্টভাবে সমস্ত ইভেন্ট কার্ড খুঁজে বের করা
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
                    
                    # ২ ও ৩. দুইটা টিমের টাইটেল বের করা
                    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                    clean_titles = [l for l in lines if not ("Live Now!" in l or "Starts in" in l or "UTC" in l or "Aug" in l or "Sep" in l or "Oct" in l or "Nov" in l or "Dec" in l or "Jan" in l or "Feb" in l or "Mar" in l or "Apr" in l or "May" in l or "Jun" in l or "Jul" in l)]

                    team1 = clean_titles[0] if len(clean_titles) > 0 else "Team 1"
                    team2 = clean_titles[1] if len(clean_titles) > 1 else "Team 2"

                    # ৪ ও ৫. দুইটা টিমের লোগো সংগ্রহ করা
                    logo1, logo2 = "", ""
                    imgs = card.find_all('img')
                    if len(imgs) > 0:
                        logo1 = imgs[0].get('src', '')
                    if len(imgs) > 1:
                        logo2 = imgs[1].get('src', '')

                    # আপনার নির্দেশনা অনুযায়ী শুধুমাত্র নির্দিষ্ট ৫টি ডাটা রাখা হয়েছে
                    event_item = {
                        "team1Title": team1,
                        "team2Title": team2,
                        "team1Logo": logo1,
                        "team2Logo": logo2,
                        "detailsPage": details_page
                    }

                    if details_page and details_page != url:
                        events_data.append(event_item)

                except Exception as card_err:
                    update_status(f"PARSING_ERROR on card {index}: {card_err}", "red")

        # JSON ফাইলে ডেটা সেভ করা
        with open("live_event_card.json", "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=4)
        
        update_status(f"Process completed successfully. Total collected events: {len(events_data)}", "green")

    except Exception as e:
        update_status(f"CRITICAL_ERROR: {e}", "red")

if __name__ == "__main__":
    asyncio.run(scrape_footystream())
