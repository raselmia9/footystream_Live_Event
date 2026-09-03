import asyncio
import json
from bs4 import BeautifulSoup
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
            # পেজ পুরোপুরি রেন্ডার হওয়ার জন্য পর্যাপ্ত সময় দেওয়া
            await page.wait_for_timeout(7000)

            # পেজের রেন্ডার হওয়া পুরো HTML কোড সংগ্রহ করা
            html_content = await page.content()
            await browser.close()
            update_status("Browser closed successfully.", "green")

            # BeautifulSoup দিয়ে HTML পার্স করা (খুব নমনীয় এবং শক্তিশালী পদ্ধতি)
            soup = BeautifulSoup(html_content, 'html.parser')

            # যেসব লিংকের ভেতরে '/e/' আছে, সেগুলো খুঁজে বের করা
            cards = soup.find_all('a', href=lambda href: href and '/e/' in href)
            total_cards = len(cards)

            if total_cards > 0:
                update_status(f"Successfully found {total_cards} live event cards using BeautifulSoup.", "green")
            else:
                update_status("HOMEPAGE_ERROR: Found 0 live event cards. Checking alternative tags...", "yellow")
                # বিকল্প হিসেবে অন্য কোনো ট্যাগ বা ডিভ চেক করা যেতে পারে
                cards = soup.find_all('div', class_=lambda c: c and 'card' in c)
                total_cards = len(cards)
                update_status(f"Alternative search found {total_cards} cards.", "green" if total_cards > 0 else "red")

            for index, card in enumerate(cards, start=1):
                try:
                    # যদি কার্ডটি সরাসরি 'a' ট্যাগ না হয়ে ভেতরের কোনো এলিমেন্ট হয়
                    href = card.get('href') if card.name == 'a' else ''
                    if not href:
                        a_tag = card.find('a', href=True)
                        if a_tag:
                            href = a_tag.get('href', '')
                    
                    details_page = href if href.startswith("http") else f"https://footystream.pk{href}" if href else url

                    full_text = card.get_text(separator="\n", strip=True)
                    lines = [line.strip() for line in full_text.split('\n') if line.strip()]

                    # টিম বা ইভেন্ট টাইটেল বের করা
                    team1 = lines[0] if len(lines) > 0 else "Team 1"
                    team2 = lines[1] if len(lines) > 1 else "Team 2"
                    event_title = f"{team1} vs {team2}" if len(lines) > 1 else team1

                    # লোগো সংগ্রহ করা
                    logo1, logo2 = "", ""
                    imgs = card.find_all('img')
                    if len(imgs) >= 1:
                        logo1 = imgs[0].get('src', '')
                    if len(imgs) >= 2:
                        logo2 = imgs[1].get('src', '')

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

        # ১. live_event_card.json ফাইলে ডেটা সেভ করা (M3U ফাইল বাদ দেওয়া হয়েছে)
        with open("live_event_card.json", "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=4)
        update_status("Data successfully saved to live_event_card.json", "green")

        update_status(f"Process completed successfully. Total collected events: {len(events_data)}", "green")

    except Exception as e:
        update_status(f"CRITICAL_ERROR: {e}", "red")

if __name__ == "__main__":
    asyncio.run(scrape_footystream())
