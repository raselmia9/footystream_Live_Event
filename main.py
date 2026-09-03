import asyncio
import json
from playwright.async_api import async_playwright

def update_status(status_message, dot_type="green"):
    """স্ট্যাটাস টেক্সট ফাইলে কালারফুল ডট দিয়ে লগ করার ফাংশন (টাইমস্ট্যাম্প ছাড়া)"""
    dots = {
        "green": "🟢",
        "yellow": "🟡",
        "red": "🔴"
    }
    dot = dots.get(dot_type, "🟢")
    formatted_msg = f"{dot} {status_message}\n"
    print(formatted_msg.strip(), flush=True)
    
    # প্রথমবার লেখার সময় 'w' বা পরবর্তীতে অ্যাপেন্ড করার জন্য 'a' মোড হ্যান্ডেল করা
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

            update_status(f"Opening website: {url}", "green")
            await page.goto(url, timeout=60000)

            update_status("Waiting for dynamic elements/cards to load...", "yellow")
            try:
                # পেজ সম্পূর্ণ লোড বা নেটওয়ার্ক শান্ত হওয়ার জন্য অপেক্ষা করা
                await page.wait_for_load_state("networkidle", timeout=10000)
            except:
                await page.wait_for_timeout(5000)

            # হোমপেজের কার্ড বা লিংকগুলো খুঁজে বের করার লজিক
            cards = []
            all_links = await page.locator("a").all()
            
            for link in all_links:
                href = await link.get_attribute("href")
                # স্ক্রিনশট অনুযায়ী ডিটেলস পেজের লিংকগুলোতে '/e/' থাকে
                if href and "/e/" in href:
                    cards.append(link)

            total_cards = len(cards)
            if total_cards > 0:
                update_status(f"Successfully found {total_cards} live event cards.", "green")
            else:
                update_status("HOMEPAGE_ERROR: Found 0 live event cards using default pattern.", "red")

            for index, card in enumerate(cards, start=1):
                try:
                    href = await card.get_attribute("href")
                    if not href:
                        continue
                    details_page = href if href.startswith("http") else f"https://footystream.pk{href}"

                    full_text = await card.inner_text()
                    lines = [line.strip() for line in full_text.split('\n') if line.strip()]

                    # টিম বা ইভেন্ট টাইটেল বের করা
                    team1 = lines[1] if len(lines) > 1 else (lines[0] if len(lines) > 0 else "Team 1")
                    team2 = lines[2] if len(lines) > 2 else (lines[1] if len(lines) > 1 else "Team 2")
                    event_title = f"{team1} vs {team2}" if len(lines) > 2 else (lines[0] if len(lines) > 0 else "Live Event")

                    # লোগো সংগ্রহ করা
                    logo1, logo2 = "", ""
                    imgs = card.locator("img")
                    img_count = await imgs.count()
                    if img_count >= 1:
                        logo1 = await imgs.nth(0).get_attribute("src") or ""
                    if img_count >= 2:
                        logo2 = await imgs.nth(1).get_attribute("src") or ""

                    # লাইভ স্ট্যাটাস চেক
                    is_hot = "Live Now!" in full_text

                    event_item = {
                        "eventTitle": event_title,
                        "matchTime": "", 
                        "team1Logo": logo1,
                        "team2Logo": logo2,
                        "team1Title": team1,
                        "team2Title": team2,
                        "detailsPage": details_page,  # দ্বিতীয় পেজে যাওয়ার লিংক
                        "streamLink": "", 
                        "isHot": is_hot
                    }

                    events_data.append(event_item)
                except Exception as card_err:
                    update_status(f"PARSING_ERROR on card {index}: {card_err}", "red")

            await browser.close()
            update_status("Browser closed successfully.", "green")

        # ১. live_event_card.json ফাইলে ডেটা সেভ করা
        with open("live_event_card.json", "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=4)
        update_status("Data successfully saved to live_event_card.json", "green")

        # ২. playlist.m3u ফাইল তৈরি করা
        m3u_lines = ["#EXTM3U"]
        for ev in events_data:
            m3u_lines.append(f"#EXTINF:-1,{ev['eventTitle']}")
            m3u_lines.append(ev['detailsPage'])

        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_lines))
        update_status("Playlist successfully saved to playlist.m3u", "green")

        update_status(f"Process completed successfully. Total collected events: {len(events_data)}", "green")

    except Exception as e:
        update_status(f"CRITICAL_ERROR: {e}", "red")

if __name__ == "__main__":
    asyncio.run(scrape_footystream())
