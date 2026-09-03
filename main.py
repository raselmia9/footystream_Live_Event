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

            update_status(f"Opening website: {url}", "green")
            await page.goto(url, timeout=60000)

            update_status("Waiting for dynamic elements to load...", "yellow")
            await page.wait_for_timeout(7000)

            html_content = await page.content()
            await browser.close()
            update_status("Browser closed successfully.", "green")

            # BeautifulSoup দিয়ে পার্স করা
            soup = BeautifulSoup(html_content, 'html.parser')

            # ওয়েবসাইট স্ট্রাকচার অনুযায়ী '/events/' যুক্ত ট্যাগ বা লিঙ্কগুলো খুঁজে বের করা
            cards = soup.find_all('a', href=lambda href: href and '/events/' in href)
            total_cards = len(cards)

            if total_cards > 0:
                update_status(f"Successfully found {total_cards} live event cards.", "green")
            else:
                update_status("HOMEPAGE_ERROR: Found 0 live event cards using default pattern.", "red")

            for index, card in enumerate(cards, start=1):
                try:
                    href = card.get('href', '')
                    details_page = href if href.startswith("http") else f"https://footystream.pk{href}" if href else url

                    full_text = card.get_text(separator="\n", strip=True)
                    lines = [line.strip() for line in full_text.split('\n') if line.strip()]

                    # এইচটিএমএল স্ট্রাকচার অনুযায়ী টেক্সট ফিল্টার করা
                    # সাধারণত এখানে প্রথম লাইন টুর্নামেন্ট/ইভেন্ট টাইটেল হয়
                    event_title = lines[1] if len(lines) > 1 else (lines[0] if lines else "Live Event")
                    
                    team1 = lines[1] if len(lines) > 1 else "Event"
                    team2 = lines[2] if len(lines) > 2 else ""

                    # লোগো সংগ্রহ করা
                    logo1, logo2 = "", ""
                    imgs = card.find_all('img')
                    if len(imgs) >= 1:
                        logo1 = imgs.get('src', '') if hasattr(imgs, 'get') else imgs.get('src', '')
                    if len(imgs) >= 2:
                        logo2 = imgs.get('src', '')

                    is_hot = "Live Now!" in full_text

                    event_item = {
                        "eventTitle": event_title,
                        "matchTime": "", 
                        "team1Logo": logo1,
                        "team2Logo": logo2,
                        "team1Title": team1,
                        "team2Title": team2,
                        "detailsPage": details_page,
                        "streamLink": "", 
                        "isHot": is_hot
                    }

                    if details_page and details_page != url:
                        events_data.append(event_item)

                except Exception as card_err:
                    update_status(f"PARSING_ERROR on card {index}: {card_err}", "red")

        # JSON ফাইলে ডেটা সেভ করা (M3U ফাইল বাদ দিয়ে)
        with open("live_event_card.json", "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=4)
        update_status("Data successfully saved to live_event_card.json", "green")

        update_status(f"Process completed successfully. Total collected events: {len(events_data)}", "green")

    except Exception as e:
        update_status(f"CRITICAL_ERROR: {e}", "red")

if __name__ == "__main__":
    asyncio.run(scrape_footystream())
