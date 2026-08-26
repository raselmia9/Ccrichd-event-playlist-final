import asyncio
import json
import urllib.request
from playwright.async_api import async_playwright

# GitHub থেকে রিমোট JSON ডাটা লোড করার ফাংশন (বিল্ট-ইন লাইব্রেরি দিয়ে)
def load_channels_from_github():
    json_url = "https://raw.githubusercontent.com/raselmia9/Crichd-Live-Event-streaming-Link-Get/refs/heads/main/crichd_matches.json"
    try:
        with urllib.request.urlopen(json_url) as response:
            if response.status == 200:
                data = response.read().decode("utf-8")
                return json.loads(data)
    except Exception as e:
        print(f"Error fetching JSON from GitHub: {e}")
    return []

# মাল্টি-স্ট্রিমিং স্ট্রিং পার্স করে আলাদা নাম এবং ইউআরএল বের করার ফাংশন
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

# প্রতিটি লিংকের জন্য আলাদা ব্রাউজার কন্টেক্সট এবং ট্যাব ওপেন করে m3u8 খুঁজে বের করার ফাংশন
async def fetch_link_in_tab(browser, event_title, sub_name, url, logo):
    full_name = f"{event_title} - {sub_name}"
    
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
        
        for _ in range(10):
            if m3u8_url:
                break
            await asyncio.sleep(1)

    except Exception as e:
        print(f"Error for {full_name}: {e}")

    await context.close()

    if m3u8_url:
        stream_link = f"{m3u8_url}|Referer={referer_url}"
        return full_name, logo, stream_link
    return full_name, logo, None

async def main():
    # যেহেতু এটি সাধারণ ফাংশন, তাই সরাসরি কল করা হয়েছে
    events = load_channels_from_github()
    if not events:
        print("No events found in GitHub JSON file!")
        return

    target_links = []
    for event in events:
        event_name = event.get("event_name", "Live Event")
        logo = event.get("team1_logo", "")
        multi_streaming = event.get("multi_streaming", "")

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
        print("No valid streaming links found to process!")
        return

    print(f"Total {len(target_links)} links found. Launching browser for parallel tab processing...")

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

    playlist_content = "#EXTM3U\n"
    
    success_count = 0
    for full_name, logo, stream_link in results:
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
