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
    """
    একক একটি পেজ থেকে মাল্টি-ব্রাউজিং বা নতুন কনটেক্সট ব্যবহার করে .m3u8 লিংক ক্যাপচার করবে।
    """
    context = await browser.new_context()
    page = await context.new_page()

    # গতি বাড়ানোর জন্য ইমেজ, সিএসএস ও ফন্ট ব্লক করা
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
        await page.goto(page_url, timeout=30000)
        for _ in range(10):
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
    """
    প্রতিটি আইটেম প্রসেস করবে: লিংক থাকলে ব্রাউজারে ফেচ করবে, টেক্সট থাকলে সরাসরি বসিয়ে দেবে।
    """
    event_name = item.get("event_name", "Unknown Event")
    multi_streaming = item.get("multi_streaming", "")
    raw_time = item.get("date_and_time", "")
    formatted_time = format_match_time(raw_time)

    stream_link = multi_streaming  # ডিফল্টভাবে ইনপুটের টেক্সট বা ভ্যালু ধরা হলো

    # যদি এটি একটি ভ্যালিড লিংক হয়, তবে মাল্টি-ব্রাউজিং বা ব্রাউজার দিয়ে .m3u8 লিংক ক্যাপচার করবে
    if multi_streaming.startswith("http"):
        print(f"Fetching stream link for: {event_name}...")
        captured_link = await fetch_m3u8_link(multi_streaming, browser)
        if captured_link:
            stream_link = captured_link
            print(f"Success captured: {event_name}")
        else:
            print(f"Failed to capture, keeping fallback text for: {event_name}")
    else:
        print(f"No link (Plain text found), keeping text for: {event_name}")

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
        # একটিমাত্র ব্রাউজার ইনস্ট্যান্স ওপেন করা হবে, যার ভেতরে মাল্টি-ট্যাব বা কনটেক্সট রান করবে
        browser = await p.chromium.launch(headless=True)
        
        # একসাথে সবগুলোর জন্য টাস্ক তৈরি করা (Concurrent/Parallel Processing)
        tasks = [process_item(item, browser) for item in items]
        
        # একসাথে সমস্ত আইটেম প্রসেস সম্পন্ন করা
        output_list = await asyncio.gather(*tasks)

        await browser.close()

    # ফাইনাল আউটপুট জেসন ফাইলে সেভ করা (কোনো আইটেম বাদ না দিয়ে সব সেভ হবে)
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(output_list, f, indent=4, ensure_ascii=False)
    
    print("Output JSON generated successfully with all items as 'output.json'!")

if __name__ == "__main__":
    asyncio.run(main())
