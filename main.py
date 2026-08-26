import asyncio
import json
import urllib.request
from datetime import datetime
from playwright.async_api import async_playwright

def load_remote_input_data():
    input_url = "https://raw.githubusercontent.com/raselmia9/Crichd-Live-Event-streaming-Link-Get/refs/heads/main/Test"
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
    ইনপুটের ডেট ফরম্যাট যেমন 'Aug 18, 2026 at 08:00 AM UTC' 
    সেটিকে কনভার্ট করে '2026-08-18 08:00:00' ফরম্যাটে রূপান্তর করবে।
    """
    try:
        # "at" এবং "UTC" অংশগুলো পরিষ্কার করে নেওয়া
        cleaned_str = date_str.replace(" at ", " ").replace(" UTC", "").strip()
        
        # সাধারণত ইনপুটের ফরম্যাট অনুযায়ী পার্স করা (যেমন: Aug 18, 2026 08:00 AM)
        dt = datetime.strptime(cleaned_str, "%b %d, %Y %I:%M %p")
        
        # কাঙ্ক্ষিত আউটপুট ফরম্যাটে রিটার্ন করা
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Date formatting error for '{date_str}': {e}")
        # যদি কোনো কারণে কনভার্ট করতে না পারে, তবে আগেরটাই বা ডিফল্ট মান ফিরিয়ে দেবে
        return date_str

async def fetch_m3u8_link(page_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # গতি বাড়ানোর জন্য ইমেজ ও সিএসএস ব্লক করা
        await page.route("**/*.{png,jpg,jpeg,gif,css,svg}", lambda route: route.abort())

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
            await page.goto(page_url, timeout=30000)
            for _ in range(10):
                if m3u8_url:
                    break
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Error loading page {page_url}: {e}")

        await browser.close()

        if m3u8_url:
            return f"{m3u8_url}|Referer={referer_url}"
        return None

async def main():
    items = load_remote_input_data()
    if not items:
        print("No items found or failed to load input URL!")
        return

    output_list = []

    for item in items:
        multi_streaming = item.get("multi_streaming", "")
        
        # যদি লিংক না থেকে টেক্সট থাকে, তবে সেটি স্কিপ করবে
        if not multi_streaming.startswith("http"):
            print(f"Skipping (No link): {item.get('event_name')}")
            continue

        print(f"Fetching link for: {item.get('event_name')}...")
        stream_link = await fetch_m3u8_link(multi_streaming)

        if stream_link:
            # টাইম ফরম্যাট পরিবর্তন করা
            raw_time = item.get("date_and_time", "")
            formatted_time = format_match_time(raw_time)

            formatted_item = {
                "eventTitle": item.get("event_name"),
                "matchTime": formatted_time,
                "team1Logo": item.get("team1_logo"),
                "team2Logo": item.get("team2_logo"),
                "team1Title": item.get("team1_name"),
                "team2Title": item.get("team2_name"),
                "streamLink": stream_link,
                "isHot": True
            }
            output_list.append(formatted_item)
            print(f"Success: {item.get('event_name')}")
        else:
            print(f"Failed to extract stream link for: {item.get('event_name')}")

    # ফাইনাল আউটপুট জেসন ফাইলে সেভ করা
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(output_list, f, indent=4, ensure_ascii=False)
    
    print("Output JSON generated successfully as 'output.json'!")

if __name__ == "__main__":
    asyncio.run(main())
