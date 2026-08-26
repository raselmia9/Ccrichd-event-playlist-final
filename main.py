import asyncio
import json
import urllib.request
from playwright.async_api import async_playwright

# GitHub থেকে রিমোট JSON ডাটা লোড করা
def load_channels_from_github():
    json_url = "https://raw.githubusercontent.com/raselmia9/Crichd-Live-Event-streaming-Link-Get/refs/heads/main/Test"
    try:
        with urllib.request.urlopen(json_url) as response:
            if response.status == 200:
                data = response.read().decode("utf-8")
                return json.loads(data)
    except Exception as e:
        print(f"Error fetching JSON: {e}")
    return []

# multi_streaming স্ট্রিং থেকে সাব-লিংকগুলো আলাদা করার ফাংশন
def parse_multi_streaming(multi_str):
    links = []
    if not multi_str:
        return links
    
    parts = multi_str.split(")")
    for part in parts:
        if ",," in part:
            name_part, url_part = part.split(",,", 1)
            links.append({
                "sub_name": name_part.strip(),
                "url": url_part.strip()
            })
    return links

# প্রতিটি লিংকের জন্য আলাদা ব্রাউজার ট্যাব ওপেন করে m3u8 খুঁজে বের করার ফাংশন
async def fetch_link_in_tab(browser, event_title, sub_name, url, logo):
    full_name = f"{event_title} - {sub_name}" if sub_name else event_title
    
    context = await browser.new_context()
    page = await context.new_page()

    # পেজের গতি বাড়ানোর জন্য অপ্রয়োজনীয় ফাইল ব্লক করা
    await page.route("**/*.{png,jpg,jpeg,gif,css,svg}", lambda route: route.abort())

    m3u8_url = None
    referer_url = "https://crichdsee.st/"

    def handle_request(request):
        nonlocal m3u8_url, referer_url
        if ".m3u8" in request.url:
            m3u8_url = request.url
            headers = request.headers
            referer_url = headers.get("referer", "https://crichdsee.st/")

    page.on("request", handle_request)

    try:
        await page.goto(url, timeout=30000)
        
        # সর্বোচ্চ ১০ সেকেন্ড অপেক্ষা করা m3u8 পাওয়ার জন্য
        for _ in range(10):
            if m3u8_url:
                break
            await asyncio.sleep(1)

        # যদি নেটওয়ার্কে না পাওয়া যায়, তবে পেজের ট্যাগ থেকে খোঁজা
        if not m3u8_url:
            try:
                element = await page.locator("video source, iframe, script").last.get_attribute("src")
                if element and ".m3u8" in element:
                    m3u8_url = element
            except:
                pass

    except Exception as e:
        print(f"Error for {full_name}: {e}")

    await context.close()

    if m3u8_url:
        stream_link = f"{m3u8_url}|Referer={referer_url}"
        return full_name, logo, stream_link
    return full_name, logo, None

async def main():
    events = load_channels_from_github()
    if not events:
        print("No events found!")
        return

    target_links = []
    if isinstance(events, dict):
        events = [events]

    for event in events:
        event_name = event.get("event_name", "Live Event")
        logo = event.get("team1_logo", "")
        multi_streaming = event.get("multi_streaming", "")

        # multi_streaming ট্যাগ থেকে লিংকগুলো আলাদা করা
        sub_links = parse_multi_streaming(multi_streaming)
        for item in sub_links:
            if item["url"]:
                target_links.append({
                    "event_name": event_name,
                    "sub_name": item["sub_name"],
                    "url": item["url"],
                    "logo": logo
                })

    if not target_links:
        print("No streaming URLs found in multi_streaming!")
        return

    print(f"Total {len(target_links)} links found. Processing with parallel tabs...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        tasks = [
            fetch_link_in_tab(
                browser, 
                item["event_name"], 
                item["sub_name"], 
                item["url"], 
                item["logo"]
            ) 
            for item in target_links
        ]
        results = await asyncio.gather(*tasks)
        await browser.close()

    # M3U প্লেলিস্ট ফাইল তৈরি করা
    playlist_content = "#EXTM3U\n"
    success_count = 0
    
    for item in results:
        if item:
            full_name, logo, stream_link = item
            if stream_link:
                playlist_content += f'#EXTINF:-1 tvg-id="" tvg-name="{full_name}" tvg-logo="{logo}" group-title="Live Sports",{full_name}\n'
                playlist_content += f"{stream_link}\n"
                print(f"Success: {full_name}")
                success_count += 1
            else:
                print(f"Failed: {full_name} (Link not found)")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(playlist_content)
    
    print(f"\nPlaylist generated successfully! Total successful streams: {success_count}. Saved as 'playlist.m3u'.")

if __name__ == "__main__":
    asyncio.run(main())
