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
    detail_links = []
    events_data = []

    try:
        async with async_playwright() as p:
            update_status("Launching browser in headless mode...", "green")
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # --- ধাপ ১: প্রথম পেজ থেকে শুধুমাত্র কার্ডের ইউআরএলগুলো সংগ্রহ করা ---
            update_status(f"Opening homepage: {url}", "green")
            await page.goto(url, timeout=60000)

            update_status("Waiting for homepage elements to load...", "yellow")
            await page.wait_for_timeout(5000)

            homepage_html = await page.content()
            soup = BeautifulSoup(homepage_html, 'html.parser')

            cards = soup.find_all('a', href=lambda href: href and '/events/' in href)
            
            for card in cards:
                href = card.get('href', '')
                if href:
                    full_link = href if href.startswith("http") else f"https://footystream.pk{href}"
                    if full_link not in detail_links:
                        detail_links.append(full_link)

            update_status(f"Total unique detail links collected from homepage: {len(detail_links)}", "green")

            # --- ধাপ ২: প্রতিটি ইভেন্টের দ্বিতীয় পেজে (Detail Page) প্রবেশ করে ডেটা সংগ্রহ ---
            for index, link in enumerate(detail_links, start=1):
                try:
                    update_status(f"Visiting detail page [{index}/{len(detail_links)}]: {link}", "yellow")
                    await page.goto(link, timeout=45000)
                    await page.wait_for_timeout(3000) # পেজ লোড হওয়ার সময় দেওয়া

                    detail_html = await page.content()
                    d_soup = BeautifulSoup(detail_html, 'html.parser')

                    # স্ক্রিনশট অনুযায়ী ডেটা এক্সট্রাক্ট করা
                    # ১. ইভেন্ট টাইটেল বা টিম টাইটেল
                    team_titles = []
                    # পেজের ভেতরের হেডিং বা টিম নেম খোঁজা
                    for t_div in d_soup.find_all('div', class_=lambda c: c and ('text-' in c or 'font-' in c)):
                        t_text = t_div.get_text(strip=True)
                        if t_text and len(t_text) < 50 and t_text not in team_titles:
                            team_titles.append(t_text)

                    team1 = team_titles[0] if len(team_titles) > 0 else "Team 1"
                    team2 = team_titles[1] if len(team_titles) > 1 else "Team 2"
                    event_title = f"{team1} vs {team2}" if len(team_titles) > 1 else team1

                    # ২. ম্যাচ টাইম (যেমন স্ক্রিনশটে থাকা ডেট/টাইম)
                    match_time = ""
                    time_div = d_soup.find(lambda tag: tag.name == 'div' and ('UTC' in tag.text or '2026-' in tag.text))
                    if time_div:
                        match_time = time_div.get_text(strip=True)

                    # ৩. লোগো সংগ্রহ
                    logo1, logo2 = "", ""
                    imgs = d_soup.find_all('img')
                    valid_imgs = [img.get('src') for img in imgs if img.get('src') and 'logo.webp' in img.get('src')]
                    if len(valid_imgs) > 0:
                        logo1 = valid_imgs[0]
                    if len(valid_imgs) > 1:
                        logo2 = valid_imgs[1]

                    # ৪. স্ট্রিম লিঙ্ক বা ওয়াচ লিঙ্ক সংগ্রহ
                    stream_links = []
                    # স্ক্রিনশটের টেবিল থেকে 'Watch' বা লিঙ্কগুলো ট্র্যাক করা
                    for a_tag in d_soup.find_all('a', href=True):
                        if 'stream' in a_tag['href'] or 'watch' in a_tag['href'] or 'embed' in a_tag['href']:
                            stream_links.append(a_tag['href'])

                    event_item = {
                        "eventTitle": event_title,
                        "matchTime": match_time,
                        "team1Logo": logo1,
                        "team2Logo": logo2,
                        "team1Title": team1,
                        "team2Title": team2,
                        "detailsPage": link,
                        "streamLinks": stream_links, # একাধিক স্ট্রিম লিঙ্ক রাখার জন্য লিস্ট
                        "isHot": True
                    }

                    events_data.append(event_item)
                    update_status(f"Successfully scraped: {event_title}", "green")

                except Exception as detail_err:
                    # নির্দিষ্ট কোনো পেজে এরর হলে তা লগ করবে কিন্তু কোড থামবে না
                    update_status(f"ERROR on detail page {link}: {detail_err}", "red")

            await browser.close()
            update_status("Browser closed successfully.", "green")

        # চূড়ান্ত ডেটা JSON ফাইলে সেভ করা
        with open("live_event_card.json", "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=4)
        
        update_status(f"Process completed successfully. Total saved events: {len(events_data)}", "green")

    except Exception as e:
        update_status(f"CRITICAL_ERROR: {e}", "red")

if __name__ == "__main__":
    asyncio.run(scrape_footystream())
