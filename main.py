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

async def scrape_single_detail(browser, link, index, total_links):
    page = await browser.new_page()
    try:
        update_status(f"Visiting detail page [{index}/{total_links}]: {link}", "yellow")
        await page.goto(link, timeout=30000)
        await page.wait_for_timeout(1500)

        detail_html = await page.content()
        await page.close()
        
        d_soup = BeautifulSoup(detail_html, 'html.parser')

        # ১. সঠিক ইভেন্ট টাইটেল (যেমন: ATP Tour)
        event_title = "Live Event"
        # পেজের ওপরের হেডিং বা নির্দিষ্ট সেকশন থেকে ইভেন্ট টাইটেল খোঁজা
        h1_tag = d_soup.find('h1') or d_soup.find('div', class_=lambda c: c and 'text-xl' in c)
        if h1_tag:
            t = h1_tag.get_text(strip=True)
            if t and 'Live Streaming' not in t:
                event_title = t

        # ২. টিম টাইটেল ও লোগো সংগ্রহ
        team1_title, team2_title = "Team 1", "Team 2"
        logo1, logo2 = "", ""
        
        imgs = d_soup.find_all('img')
        valid_imgs = [img.get('src') for img in imgs if img.get('src') and 'logo.webp' in img.get('src')]
        if len(valid_imgs) > 0:
            logo1 = valid_imgs[0]
        if len(valid_imgs) > 1:
            logo2 = valid_imgs[1]

        # ৩. ম্যাচ টাইম কনভার্শন (YYYY-MM-DD HH:MM:SS)
        match_time = ""
        for div in d_soup.find_all('div'):
            text = div.get_text(strip=True)
            if 'UTC' in text and ('at' in text or ',' in text):
                match_time = convert_utc_to_bst(text)
                break

        # ৪. মাল্টি ওয়াচ পেজ লিংক (multiWatchPageLink) - শুধুমাত্র টেবিলের ভেতরের লিঙ্কগুলো ফিল্টার করা
        multi_watch_links = []
        
        # স্ট্রিমার বা টেবিল রো গুলোর ভেতর থেকে সঠিক লিঙ্ক বের করা
        # footystream.pk এর স্ট্রিম টেবিল সাধারণত 'Link 1', 'Link 2' এবং 'Watch' বাটন ধারণ করে
        rows = d_soup.find_all('div', class_=lambda c: c and ('grid' in c or 'flex' in c))
        
        # বিকল্প ও নিখুঁত পদ্ধতি: টেবিল বা নির্দিষ্ট সেকশন যেখানে 'Watch' বাটনগুলো থাকে
        for a_tag in d_soup.find_all('a', href=True):
            link_text = a_tag.get_text(strip=True)
            href_val = a_tag['href']
            
            # শুধুমাত্র সেই লিঙ্কগুলো নেওয়া হবে যেগুলোতে 'Watch' লেখা আছে অথবা চ্যানেল নেম (Link 1, Link 2...) আছে
            if 'Watch' in link_text or 'Link ' in link_text:
                full_url = href_val if href_val.startswith("http") else f"https://footystream.pk{href_val}"
                
                # ডুপ্লিকেট এড়াতে এবং হোম বা ফুটার লিঙ্ক বাদ দিতে চেক করা
                if full_url not in [item['url'] for item in multi_watch_links] and 'footystream.pk/' in full_url and len(href_val) > 1:
                    multi_watch_links.append({
                        "channel": link_text if link_text else "Watch",
                        "url": full_url
                    })

        event_item = {
            "eventTitle": event_title,
            "matchTime": match_time,
            "team1Title": team1_title,
            "team2Title": team2_title,
            "team1Logo": logo1,
            "team2Logo": logo2,
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

            detail_links = []
            for card in cards:
                href = card.get('href', '')
                if href:
                    full_link = href if href.startswith("http") else f"https://footystream.pk{href}"
                    if full_link not in detail_links:
                        detail_links.append(full_link)

            total_links = len(detail_links)
            update_status(f"Total unique detail links to process in parallel: {total_links}", "green")

            semaphore = asyncio.Semaphore(5)

            async def bounded_scrape(link, idx):
                async with semaphore:
                    return await scrape_single_detail(browser, link, idx, total_links)

            tasks = [bounded_scrape(link, i) for i, link in enumerate(detail_links, start=1)]
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
