import asyncio
import json
import urllib.request
from datetime import datetime, timedelta
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
    UTC সময়কে পার্স করে তার সাথে ৬ ঘণ্টা যোগ করে বাংলাদেশের লোকাল টাইম (BST) এ রূপান্তর করবে।
    """
    try:
        cleaned_str = date_str.replace(" at ", " ").replace(" UTC", "").strip()
        dt = datetime.strptime(cleaned_str, "%b %d, %Y %I:%M %p")
        
        # UTC থেকে বাংলাদেশের সময় করতে ৬ ঘণ্টা যোগ করা হলো (UTC+6)
        bd_time = dt + timedelta(hours=6)
        
        return bd_time.strftime("%Y-%m-%d %H:%M:%S")
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
        await page.goto(page_url, timeout=20000)
        for _ in range(6):
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
    
    # এখানে এখন স্বয়ংক্রিয়ভাবে বাংলাদেশ টাইম কনভার্ট হয়ে যাবে
    formatted_time = format_match_time(raw_time)

    formatted_parts = []

    if "http" in multi_streaming:
        print(f"Processing formatted links for: {event_name}...")
        
        raw_links_info = []
        parts = multi_streaming.split(")")
        for part in parts:
            if ",," in part:
                sub_parts = part.split(",,")
                label = sub_parts[0].strip()
                url = sub_parts[1].strip()
                if url.startswith("http"):
                    raw_links_info.append((label, url))
            elif part.strip().startswith("http"):
                raw_links_info.append(("Link", part.strip()))

        if raw_links_info:
            tasks = [fetch_m3u8_link(url, browser) for label, url in raw_links_info]
            results = await asyncio.gather(*tasks)

            for i, captured_m3u8 in enumerate(results):
                if captured_m3u8:
                    label = raw_links_info[i][0]
                    formatted_parts.append(f"{label},,{captured_m3u8}")

    if formatted_parts:
        stream_link = ",)".join(formatted_parts)
        print(f"Successfully generated custom format with Bangladesh Time for: {event_name}")
    else:
        stream_link = "Stream links will be activated before 1 hr."
        print(f"No .m3u8 found, using fallback text for: {event_name}")

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
        
        tasks = [process_item(item, browser) for item in items]
        output_list = await asyncio.gather(*tasks)

        await browser.close()

    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(output_list, f, indent=4, ensure_ascii=False)
    
    print("Output JSON successfully generated with Bangladesh Time!")

if __name__ == "__main__":
    asyncio.run(main())
