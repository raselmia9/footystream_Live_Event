import asyncio
import os
import re
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
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

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

async def capture_stream_link(browser, watch_url, channel_name):
    page = await browser.new_page()
    captured_stream = ""
    
    def handle_request(request):
        nonlocal captured_stream
        if captured_stream:
            return
        url = request.url
        if ".m3u8" in url or "playlist.m3u8" in url or "manifest" in url:
            headers = request.headers
            referer = headers.get("referer", "")
            
            if referer:
                captured_stream = f"{channel_name},,{url}|Referer={referer}"
            else:
                captured_stream = f"{channel_name},,{url}"

    page.on("request", handle_request)

    try:
        await page.goto(watch_url, timeout=30000)
        try:
            await page.wait_for_timeout(2000)
            await page.click("body", timeout=3000)
        except:
            pass

        for _ in range(12):
            if captured_stream:
                break
            await page.wait_for_timeout(1000)
            
    except Exception as e:
        pass
    finally:
        try:
            await page.close()
        except:
            pass
            
    return captured_stream

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

        # ইভেন্ট টাইটেল
        event_title = "Live Event"
        event_div = d_soup.find('div', class_=lambda c: c and 'text-white font-semibold text-sm' in c)
        if event_div:
            t = event_div.get_text(strip=True)
            if t:
                event_title = t

        # ম্যাচ টাইম কনভার্শন
        match_time = ""
        time_container = d_soup.find('div', class_=lambda c: c and 'text-xs' in c)
        if time_container:
            time_text = time_container.get_text(strip=True)
            if 'UTC' in time_text:
                match_time = convert_utc_to_bst(time_text)

        if not match_time:
            for div in d_soup.find_all('div'):
                text = div.get_text(strip=True)
                if 'UTC' in text and ('at' in text or ',' in text):
                    match_time = convert_utc_to_bst(text)
                    break

        # মাল্টি ওয়াচ পেজ লিংক সংগ্রহ
        multi_watch_links = []
        table = d_soup.find('table')
        if table:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 2:
                    channel_name = cols[1].get_text(strip=True)
                    a_tag = row.find('a', href=True)
                    if a_tag and channel_name:
                        href_val = a_tag['href']
                        full_url = href_val if href_val.startswith("http") else f"https://footystream.pk{href_val}"
                        multi_watch_links.append({
                            "channel": channel_name,
                            "url": full_url
                        })

        if not multi_watch_links:
            for a_tag in d_soup.find_all('a', href=True):
                href_val = a_tag['href']
                if '/alpha/' in href_val or '/embed/' in href_val:
                    full_url = href_val if href_val.startswith("http") else f"https://footystream.pk{href_val}"
                    if full_url not in [item['url'] for item in multi_watch_links]:
                        multi_watch_links.append({
                            "channel": "Link 1",
                            "url": full_url
                        })

        # স্ট্রিম লিংক ক্যাপচার করা
        stream_link_parts = []
        if multi_watch_links:
            stream_tasks = [capture_stream_link(browser, mw["url"], mw["channel"]) for mw in multi_watch_links]
            stream_results = await asyncio.gather(*stream_tasks)
            
            for res in stream_results:
                if res:
                    stream_link_parts.append(res)

        json_stream_parts = []
        
        # গিটহাব রেপোজিটরি ইনফো সংগ্রহ
        github_repo = os.environ.get("GITHUB_REPOSITORY", "raselmia9/footystream_Live_Event")
        github_branch = os.environ.get("GITHUB_REF_NAME", "main")

        if stream_link_parts:
            # ফোল্ডার তৈরির সময় সাধারণ স্পেস রাখা হবে যাতে লোকাল ফোল্ডারে সমস্যা না হয়
            t1 = sanitize_filename(card_info["team1Title"])
            t2 = sanitize_filename(card_info["team2Title"])
            folder_name = f"{t1}_vs_{t2}"
            event_dir = os.path.join("all_event", folder_name)
            os.makedirs(event_dir, exist_ok=True)

            for part in stream_link_parts:
                parts_split = part.split(",,", 1)
                if len(parts_split) == 2:
                    ch_name = sanitize_filename(parts_split[0])
                    raw_stream_info = parts_split[1]
                    
                    stream_url = raw_stream_info
                    referer_val = ""
                    if "|Referer=" in raw_stream_info:
                        stream_url, referer_val = raw_stream_info.split("|Referer=", 1)

                    file_path = os.path.join(event_dir, f"{ch_name}.m3u8")
                    
                    # ফোল্ডারের ভেতরের .m3u8 ফাইলের কন্টেন্ট
                    m3u8_content = "#EXTM3U\n"
                    m3u8_content += "#EXT-X-VERSION:3\n"
                    m3u8_content += f"#EXT-X-STREAM-INF:BANDWIDTH=2000000,PROGRAM-ID=1,RESOLUTION=1280x720,FRAME-RATE=25.000\n"
                    if referer_val:
                        m3u8_content += f"{stream_url}|Referer={referer_val}\n"
                    else:
                        m3u8_content += f"{stream_url}\n"

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(m3u8_content)

                    # জেসন ফাইলের জন্য ফোল্ডার ও ফাইলের নাম এনকোড করা যাতে স্পেসের জায়গায় %20 বসে
                    encoded_folder_name = quote(folder_name)
                    encoded_ch_name = quote(f"{ch_name}.m3u8")
                    
                    raw_link = f"https://raw.githubusercontent.com/{github_repo}/{github_branch}/all_event/{encoded_folder_name}/{encoded_ch_name}"
                    
                    # রেফারার যেভাবে আগে যুক্ত হতো ঠিক সেভাবেই থাকবে
                    if referer_val:
                        json_stream_parts.append(f"{parts_split[0]},,{raw_link}|Referer={referer_val}")
                    else:
                        json_stream_parts.append(f"{parts_split[0]},,{raw_link}")

        final_stream_link = ",)".join(json_stream_parts) if json_stream_parts else ""

        event_item = {
            "eventTitle": event_title,
            "matchTime": match_time,
            "team1Title": card_info["team1Title"],
            "team2Title": card_info["team2Title"],
            "team1Logo": card_info["team1Logo"],
            "team2Logo": card_info["team2Logo"],
            "isHot": True,
            "streamLink": final_stream_link,
            "detailsPage": link,
            "multiWatchPageLink": multi_watch_links
        }

        update_status(f"Successfully processed: {event_title} [{index}/{total_links}]", "green")
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

            semaphore = asyncio.Semaphore(3)

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
