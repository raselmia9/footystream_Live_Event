import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright

def update_status(status_message):
    """স্ট্যাটাস টেক্সট ফাইলে প্রসেসের বর্তমান অবস্থা আপডেট করার ফাংশন"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    formatted_msg = f"[{timestamp}] {status_message}\n"
    print(status_message)
    # ফাইল অ্যাপেন্ড মোডে ওপেন করে প্রতি ধাপের লগ রাখা যায়, অথবা ওভাররাইট করা যায়
    with open("output_status.txt", "a", encoding="utf-8") as f:
        f.write(formatted_msg)

async def scrape_footystream():
    # প্রতিবার স্ক্রিপ্ট শুরু হওয়ার সময় স্ট্যাটাস ফাইল নতুন করে শুরু করতে চাইলে 'w' মোড ব্যবহার করতে পারেন
    with open("output_status.txt", "w", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%Sunlike')}] Process Started...\n")

    url = "https://footystream.pk/"
    events_data = []
    
    try:
        async with async_playwright() as p:
            update_status("Launching browser in headless mode...")
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            update_status(f"Opening website: {url}")
            await page.goto(url, timeout=60000)
            
            update_status("Waiting for elements to load...")
            await page.wait_for_timeout(5000)
            
            # ইভেন্ট কার্ডগুলো সিলেক্ট করা
            cards = await page.locator("a[href*='/e/']").all()
            total_cards = len(cards)
            update_status(f"Found {total_cards} live event cards.")
            
            for index, card in enumerate(cards, start=1):
                try:
                    href = await card.get_attribute("href")
                    details_page = href if href.startswith("http") else f"https://footystream.pk{href}"
                    
                    full_text = await card.inner_text()
                    
                    logo1, logo2 = "", ""
                    if await card.locator("img").count() >= 2:
                        logo1 = await card.locator("img").nth(0).get_attribute("src") or ""
                        logo2 = await card.locator("img").nth(1).get_attribute("src") or ""

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
                        "detailsPage": details_page,  # আপনার চাওয়া নতুন detailsPage key
                        "streamLink": "", 
                        "isHot": True
                    }
                    
                    events_data.append(event_item)
                except Exception as card_err:
                    update_status(f"Error parsing card {index}: {card_err}")

            await browser.close()
            update_status("Browser closed successfully.")

        # ১. live_event_card.json ফাইলে সেভ করা
        with open("live_event_card.json", "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=4)
        update_status("Data successfully saved to live_event_card.json")

        # ২. প্লেলিস্ট (.m3u) ফাইল তৈরি
        m3u_lines = ["#EXTM3U"]
        for ev in events_data:
            m3u_lines.append(f"#EXTINF:-1,{ev['eventTitle']}")
            m3u_lines.append(ev['detailsPage'])
            
        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_lines))
        update_status("Playlist successfully saved to playlist.m3u")

        update_status(f"Process completed successfully. Total collected events: {len(events_data)}")

    except Exception as e:
        update_status(f"Critical Error during execution: {e}")

if __name__ == "__main__":
    asyncio.run(scrape_footystream())
