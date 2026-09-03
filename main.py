import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright

def update_status(status_message):
    """স্ট্যাটাস টেক্সট ফাইলে প্রসেসের বর্তমান অবস্থা ও এরর লগ করার ফাংশন"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    formatted_msg = f"[{timestamp}] {status_message}\n"
    print(status_message)
    with open("output_status.txt", "a", encoding="utf-8") as f:
        f.write(formatted_msg)

async def scrape_footystream():
    # প্রতিবার রান শুরু হওয়ার সময় স্ট্যাটাস ফাইল রিসেট করা
    with open("output_status.txt", "w", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Process Started...\n")

    url = "https://footystream.pk/"
    events_data = []
    
    try:
        async with async_playwright() as p:
            update_status("Launching browser in headless mode...")
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            update_status(f"Opening website: {url}")
            try:
                # পেজ লোড করার জন্য নির্দিষ্ট টাইমআউট এবং নেটওয়ার্ক স্ট্যাটাস চেক
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            except Exception as e:
                update_status(f"HOMEPAGE_ERROR: Failed to load URL {url}. Details: {e}")
                return

            update_status("Waiting for dynamic elements/cards to load...")
            try:
                # হোমপেজের কার্ডগুলো আসার জন্য একটু বেশি সময় বা নির্দিষ্ট সিলেক্টরের জন্য অপেক্ষা করা
                await page.wait_for_timeout(7000)
            except Exception as e:
                update_status(f"HOMEPAGE_ERROR: Timeout while waiting for elements. Details: {e}")

            # হোমপেজে কার্ড বা লিংক খুঁজে বের করার জন্য একাধিক পসিবল সিলেক্টর ট্রাই করা
            # যেহেতু সাইটে a[href*='/e/'] বা অন্য কোনো ক্লাস থাকতে পারে
            cards = []
            selectors_to_try = ["a[href*='/e/']", ".match-card", "a.card", "div.live-card"]
            
            for sel in selectors_to_try:
                found_elements = await page.locator(sel).all()
                if len(found_elements) > 0:
                    cards = found_elements
                    update_status(f"SUCCESS: Found {len(cards)} cards using selector: {sel}")
                    break
            
            if len(cards) == 0:
                update_status("HOMEPAGE_ERROR: Found 0 live event cards using all default selectors. Page structure might have changed.")
                # ডিবাগিংয়ের জন্য পেজের সোর্স বা টাইটেল চেক করতে পারি
                page_title = await page.title()
                update_status(f"DEBUG_INFO: Current Page Title was: '{page_title}'")

            for index, card in enumerate(cards, start=1):
                try:
                    href = await card.get_attribute("href")
                    if not href:
                        continue
                    details_page = href if href.startswith("http") else f"https://footystream.pk{href}"
                    
                    full_text = await card.inner_text()
                    
                    logo1, logo2 = "", ""
                    img_locators = card.locator("img")
                    img_count = await img_locators.count()
                    if img_count >= 2:
                        logo1 = await img_locators.nth(0).get_attribute("src") or ""
                        logo2 = await img_locators.nth(1).get_attribute("src") or ""

                    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                    team1 = lines[0] if len(lines) > 0 else "Team 1"
                    team2 = lines[1] if len(lines) > 1 else "Team 2"
                    event_title = f"{team1} vs {team2}"

                    event_item = {
                        "eventTitle": event_title,
                        "matchTime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "team1Logo": logo1,
                        "team2Logo": logo2,
                        "team1Title": team1,
                        "team2Title": team2,
                        "detailsPage": details_page,
                        "streamLink": "", 
                        "isHot": True
                    }
                    
                    events_data.append(event_item)
                except Exception as card_err:
                    update_status(f"PARSING_ERROR: Failed to parse card index {index}. Details: {card_err}")

            await browser.close()
            update_status("Browser closed successfully.")

        # ফাইল সেভিং পার্ট
        with open("live_event_card.json", "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=4)
        update_status("Data successfully saved to live_event_card.json")

        m3u_lines = ["#EXTM3U"]
        for ev in events_data:
            m3u_lines.append(f"#EXTINF:-1,{ev['eventTitle']}")
            m3u_lines.append(ev['detailsPage'])
            
        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_lines))
        update_status("Playlist successfully saved to playlist.m3u")

        update_status(f"Process completed successfully. Total collected events: {len(events_data)}")

    except Exception as critical_err:
        update_status(f"CRITICAL_ERROR: An unexpected error occurred during execution. Details: {critical_err}")

if __name__ == "__main__":
    asyncio.run(scrape_footystream())
