import asyncio
import json
from datetime import datetime, timedelta, timezone
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

def convert_utc_to_bst(utc_text):
    try:
        cleaned_text = utc_text.replace(" at ", " ").replace(" UTC", "").strip()
        dt_utc = datetime.strptime(cleaned_text, "%b %d, %Y %I:%M %p")
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        
        bst_offset = timezone(timedelta(hours=6))
        dt_bst = dt_utc.astimezone(bst_offset)
        
        return dt_bst.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return utc_text

async def scrape_single_detail(browser, card_info, index, total_links):
    page = await browser.new_page()
    link = card_info["detailsPage"]
    try:
        update_status(f"Visiting detail page [{index}/{total_links}]: {link}", "yellow")
        await page.goto(link, timeout=30000)
        await page.wait_for_timeout(1500)

        detail_html = await page.content()
        await page.close()
        
        d_soup = BeautifulSoup(detail_html, 'html.parser')

        # ১. সঠিক ইভেন্ট টাইটেল (যেমন: ATP Tour) - পেজের ওপরের হেডিং থেকে
        event_title = "Live Event"
        # ফুটিস্ট্রিমে সাধারণত টুর্নামেন্ট বা ইভেন্ট ক্যাটাগরি উপরে থাকে
        header_divs = d_soup.find_all('div', class_=lambda c: c and 'text-' in c)
        for div in header_divs:
            t = div.get_text(strip=True)
            if t and len(t) < 40 and 'UTC' not in t and 'Live' not in t and 'Stream' not in t:
                event_title = t
                break

        # ২. সঠিক ম্যাচ টাইম এবং ডেট আলাদা করা ও কনভার্ট করা
        match_time = ""
        for div in d_soup.find_all('div'):
            text = div.get_text(strip=True)
            if 'UTC' in text and ('at' in text or ',' in text):
                match_time = convert_utc_to_bst(text)
                break

        # ৩. মাল্টি ওয়াচ পেজ লিংক (multiWatchPageLink) - টেবিল থেকে শুধু Watch বাটনগুলো নেওয়া
        multi_watch_links = []
        for a_tag in d_soup.find_all('a', href=True):
            link_text = a_tag.get_text(strip=True)
            href_val = a_tag['href']
            
            # টেবিলের ভেতরের স্ট্রিম লিঙ্ক বা Watch বাটন ফিল্টার করা
            if 'Watch' in link_text or 'Link ' in link_text or '/alpha/' in href_val or '/embed/' in href_val:
                full_url = href_val if href_val.startswith("http") else f"https://footystream.pk{href_val}"
                
                if full_url not in [item['url'] for item in multi_watch_links] and 'footystream.pk/' in full_url:
                    multi_watch_links.append({
                        "channel": link_text if link_text else "Watch",
                        "url": full_url
                    })

        # প্রথম ধাপ থেকে পাওয়া তথ্যগুলো ঠিক রেখে বাকিগুলো আপডেট করা হলো
        event_item = {
            "eventTitle": event_title,
            "matchTime": match_time,
            "team1Title": card_info["team1Title"],
            "team2Title": card_info["team2Title"],
            "team1Logo": card_info["team1Logo"],
            "team2Logo": card_info["team2Logo"],
            "detailsPage": link,
            "multiWatchPageLink": multi_watch_links
        }

        update_status(f"Successfully scraped: {event_title} [{index}/{total_links}]", "green")
        return event_item

    except Exception as detail_err:
        try:
            await page.close()
        except:
            pass
        update_status(f"ERROR on detail page {link}: {detail_err}", "red")
        return None

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

            try:
                update_status("Waiting for event cards to load...", "yellow")
                await page.wait_for_selector('a[href*="/events/"]', timeout=5000)
            except:
                update_status("Selector wait timeout, proceeding with current content...", "yellow")

            homepage_html = await page.content()
            await page.close()

            soup = BeautifulSoup(homepage_html, 'html.parser')
            cards = soup.find_all('a', href=lambda href: href and '/events/' in href)
            total_cards = len(cards)

            if total_cards > 0:
                update_status(f"Successfully found {total_cards} live event cards on homepage.", "green")
            else:
                update_status("HOMEPAGE_ERROR: Found 0 live event cards.", "red")

            # প্রথম ধাপের মতো কার্ড থেকে সরাসরি টিম নাম ও লোগো সংগ্রহ করে রাখা
            cards_info_list = []
            seen_links = set()

            for card in cards:
                href = card.get('href', '')
                if href:
                    details_page = href if href.startswith("http") else f"https://footystream.pk{href}"
                    
                    if details_page not in seen_links:
                        seen_links.add(details_page)
                        
                        full_text = card.get_text(separator="\n", strip=True)
                        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                        clean_titles = [l for l in lines if not ("Live Now!" in l or "Starts in" in l or "UTC" in l or "Aug" in l or "Sep" in l or "Oct" in l or "Nov" in l or "Dec" in l or "Jan" in l or "Feb" in l or "Mar" in l or "Apr" in l or "May" in l or "Jun" in l or "Jul" in l)]

                        team1 = clean_titles[0] if len(clean_titles) > 0 else "Team 1"
                        team2 = clean_titles[1] if len(clean_titles) > 1 else "Team 2"

                        logo1, logo2 = "", ""
                        imgs = card.find_all('img')
                        if len(imgs) > 0:
                            logo1 = imgs[0].get('src', '')
                        if len(imgs) > 1:
                            logo2 = imgs[1].get('src', '')

                        cards_info_list.append({
                            "team1Title": team1,
                            "team2Title": team2,
                            "team1Logo": logo1,
                            "team2Logo": logo2,
                            "detailsPage": details_page
                        })

            total_links = len(cards_info_list)
            update_status(f"Total unique detail links to process in parallel: {total_links}", "green")

            semaphore = asyncio.Semaphore(5)

            async def bounded_scrape(card_info, idx):
                async with semaphore:
                    return await scrape_single_detail(browser, card_info, idx, total_links)

            tasks = [bounded_scrape(card_info, i) for i, card_info in enumerate(cards_info_list, start=1)]
            results = await asyncio.gather(*tasks)

            for res in results:
                if res:
                    events_data.append(res)

            await browser.close()
            update_status("Browser closed successfully.", "green")

        with open("live_event_card.json", "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=4)
        
        update_status(f"Process completed successfully. Total collected events: {len(events_data)}", "green")

    except Exception as e:
        update_status(f"CRITICAL_ERROR: {e}", "red")

if __name__ == "__main__":
    asyncio.run(scrape_footystream())
