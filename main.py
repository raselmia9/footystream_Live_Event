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

            soup = BeautifulSoup(html_content, 'html.parser')

            # সঠিক পাথ অনুযায়ী কার্ডগুলো খোঁজা
            cards = soup.find_all('a', href=lambda href: href and '/events/' in href)
            total_cards = len(cards)

            if total_cards > 0:
                update_status(f"Successfully found {total_cards} live event cards.", "green")
            else:
                update_status("HOMEPAGE_ERROR: Found 0 live event cards.", "red")

            for index, card in enumerate(cards, start=1):
                try:
                    href = card.get('href', '')
                    details_page = href if href.startswith("http") else f"https://footystream.pk{href}" if href else url

                    full_text = card.get_text(separator="\n", strip=True)
                    
                    # সুনির্দিষ্টভাবে টিম বা ইভেন্টের নামগুলো বের করার জন্য ভেতরের কন্টেইনার খোঁজা
                    titles = []
                    # HTML স্ট্রাকচার অনুযায়ী টেক্সট কন্টেইনার ফিল্টার করা
                    title_container = card.find('div', class_=lambda c: c and 'flex-col' in c)
                    if title_container:
                        t_divs = title_container.find_all('div', class_=lambda c: c and 'items-center' in c)
                        for t in t_divs:
                            t_text = t.get_text(strip=True)
                            if t_text:
                                titles.append(t_text)

                    # যদি কন্টেইনার থেকে না পাওয়া যায়, তবে লাইন বাই লাইন ফিল্টার করা (স্ট্যাটাস বাদ দিয়ে)
                    if not titles:
                        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                        titles = [l for l in lines if not ("Live Now!" in l or "Starts in" in l)]

                    team1 = titles[0] if len(titles) > 0 else "Team 1"
                    team2 = titles[1] if len(titles) > 1 else ""
                    
                    if team2:
                        event_title = f"{team1} vs {team2}"
                    else:
                        event_title = team1

                    # লোগো নিরাপদভাবে সংগ্রহ করা
                    logo1, logo2 = "", ""
                    imgs = card.find_all('img')
                    if len(imgs) > 0:
                        logo1 = imgs[0].get('src', '')
                    if len(imgs) > 1:
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

        # JSON ফাইলে ডেটা সেভ করা
        with open("live_event_card.json", "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=4)
        update_status(f"Data successfully saved to live_event_card.json. Total collected: {len(events_data)}", "green")

        update_status(f"Process completed successfully.", "green")

    except Exception as e:
        update_status(f"CRITICAL_ERROR: {e}", "red")

if __name__ == "__main__":
    asyncio.run(scrape_footystream())
