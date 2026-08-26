import asyncio
import json
import urllib.request
from datetime import datetime
from playwright.async_api import async_playwright

def load_remote_input_data():
    input_url = "https://raw.githubusercontent.com/raselmia9/Crichd-Live-Event-streaming-Link-Get/refs/heads/main/crichd_matches.json"
    try:
        print(f"Fetching input data from: {input_url}")
        with urllib.request.urlopen(input_url) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except Exception as e:
        print(f"Error fetching remote input data: {e}")
        return []

def format_match_time(date_str):
    """
    ইনপুটের ডেট ফরম্যাট কনভার্ট করে 'YYYY-MM-DD HH:MM:SS' ফরম্যাটে রূপান্তর করবে।
    """
    try:
        cleaned_str = date_str.replace(" at ", " ").replace(" UTC", "").strip()
        dt = datetime.strptime(cleaned_str, "%b %d, %Y %I:%M %p")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Date formatting error for '{date_str}': {e}")
        return date_str

async def fetch_m3u8_link(page_url, browser):
    context = await browser.new_context()
    page = await context.new_page()

    await page.route("**/*.{png,jpg,jpeg,gif,css,svg,woff,woff2}", lambda route: route.abort())

    m3u8_url = None
    referer_url = "https://crichd.pk/"

    def handle_request(request):
        nonlocal m3u8_url, referer_url
        if ".m3u8" in request.url:
            m3u8_url = request.url
            headers = request.headers
            referer_url = headers.get("referer", "https://crichd.pk/")

    page.on("request", handle_request)

    try:
        await page.goto(page_url, timeout=25000)
        for _ in range(8):
            if m3u8_url:
                break
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error loading page {page_url}: {e}")

    await context.close()

    if m3u8_url:
        return f"{m3u8_url}|Referer={referer_url}"
    return None

async def process_item(item, browser):
    event_name = item.get("event_name", "Unknown Event")
    multi_streaming = item.get("multi_streaming", "")
    raw_time = item.get("date_and_time", "")
    formatted_time = format_match_time(raw_time)

    # ডিফল্টভাবে ইনপুটের মূল টেক্সট বা লিংকটি সেট করে রাখা হলো (ফলব্যাক)
    stream_link = multi_streaming

    # যদি ইনপুটে http লিংক বা কাস্টম মাল্টি-লিংক ফরম্যাট থাকে
    if "http" in multi_streaming:
        print(f"Processing links for: {event_name}...")
        
        urls = []
        parts = multi_streaming.split(")")
        for part in parts:
            if ",," in part:
                url_part = part.split(",,")[1].strip()
                if url_part.startswith("http"):
                    urls.append(url_part)
            elif part.strip().startswith("http"):
                urls.append(part.strip())

        captured_link = None
        for url in urls:
            print(f"Fetching URL: {url}")
            captured = await fetch_m3u8_link(url, browser)
            if captured:
                captured_link = captured
                break  # সফলভাবে .m3u8 লিংক পেলে লুপ থামিয়ে দেবে

        if captured_link:
            stream_link = captured_link
            print(f"Success captured for: {event_name}")
        else:
            # .m3u8 লিংক না পাওয়া গেলে ইনপুটের মূল টেক্সট বা নোটিশটিই থেকে যাবে
            print(f"No .m3u8 found, keeping original text/fallback for: {event_name}")
    else:
        print(f"Plain text found, keeping text for: {event_name}")

    formatted_item = {
        "eventTitle": event_name,
        "matchTime": formatted_time,
        "team1Logo": item.get("team1_logo", ""),
        "team2Logo": item.get("team2_logo", ""),
        "team1Title": item.get("team1_name", ""),
        "team2Title": item.get("team2_name", ""),
        "streamLink": stream_link,
        "isHot": True
    }
    return formatted_item

async def main():
    items = load_remote_input_data()
    if not items:
        print("No items found or failed to load input URL!")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # কনকারেন্ট বা মাল্টি-ব্রাউজিংয়ের মাধ্যমে একসাথে সমস্ত আইটেম প্রসেস করা
        tasks = [process_item(item, browser) for item in items]
        output_list = await asyncio.gather(*tasks)

        await browser.close()

    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(output_list, f, indent=4, ensure_ascii=False)
    
    print("Output JSON successfully generated with all items!")

if __name__ == "__main__":
    asyncio.run(main())
