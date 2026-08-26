import asyncio
import json
import urllib.request
from playwright.async_api import async_playwright

# ১. নতুন রিমোট টেস্ট লিংক থেকে ডাটা লোড করার ফাংশন
def load_channels_from_github():
    json_url = "https://raw.githubusercontent.com/raselmia9/Crichd-Live-Event-streaming-Link-Get/refs/heads/main/Test"
    try:
        with urllib.request.urlopen(json_url) as response:
            if response.status == 200:
                data = response.read().decode("utf-8")
                return json.loads(data)
    except Exception as e:
        print(f"Error fetching JSON from GitHub: {e}")
    return []

# ২. প্রতিটি লিংকের জন্য আলাদা ব্রাউজার ট্যাব ওপেন করে m3u8 বা ট্যাগ থেকে লিংক বের করার ফাংশন
async def fetch_link_in_tab(browser, event_title, url, logo):
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
        # পেজ ভিজিট করা
        await page.goto(url, timeout=30000)
        
        # আপনার নির্দেশনা অনুযায়ী: যদি রিকোয়েস্ট থেকে সরাসরি m3u8 না পাওয়া যায়, 
        # তবে পেজের নিচের ট্যাগ থেকে লিংক খুঁজে বের করার লজিক এখানে কাজ করবে
        for _ in range(10):
            if m3u8_url:
                break
            await asyncio.sleep(1)

        # যদি রিকোয়েস্টে সরাসরি না ধরে, তবে পেজের ভেতরের নির্দিষ্ট ট্যাগ থেকে লিংক তোলার চেষ্টা
        if not m3u8_url:
            try:
                # উদাহরণস্বরূপ সবার নিচের ট্যাগ বা iframe/source ট্যাগ থেকে লিংক খোঁজা
                # আপনি চাইলে নির্দিষ্ট সিলেক্টর এখানে বসাতে পারেন
                element = await page.locator("video source, iframe, script").last.get_attribute("src")
                if element and ".m3u8" in element:
                    m3u8_url = element
            except:
                pass

    except Exception as e:
        print(f"Error for {event_title}: {e}")

    await context.close()

    if m3u8_url:
        stream_link = f"{m3u8_url}|Referer={referer_url}"
        return event_title, logo, stream_link
    return event_title, logo, None

async def main():
    events = load_channels_from_github()
    if not events:
        print("No events found in GitHub JSON file!")
        return

    target_links = []
    
    # ডেটা স্ট্রাকচার যদি ডিকশনারি বা লিস্ট হয় সে অনুযায়ী হ্যান্ডেল করা
    if isinstance(events, dict):
        events = [events] # যদি সিঙ্গেল অবজেক্ট বা অন্য ফরম্যাট হয়

    for event in events:
        event_name = event.get("event_name", event.get("name", "Live Event"))
        logo = event.get("team1_logo", event.get("logo", ""))
        url = event.get("url", "")

        if url:
            target_links.append({
                "event_name": event_name,
                "url": url,
                "logo": logo
            })

    if not target_links:
        print("No valid streaming URLs found to process!")
        return

    print(f"Total {len(target_links)} links found. Processing with parallel tabs...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        tasks = [
            fetch_link_in_tab(
                browser, 
                item["event_name"], 
                item["url"], 
                item["logo"]
            ) 
            for item in target_links
        ]

        results = await asyncio.gather(*tasks)
        await browser.close()

    # স্ট্যান্ডার্ড M3U প্লেলিস্ট ফরম্যাটে ফাইল তৈরি করা
    playlist_content = "#EXTM3U\n"
    
    success_count = 0
    for event_title, logo, stream_link in results:
        if stream_link:
            playlist_content += f'#EXTINF:-1 tvg-id="" tvg-name="{event_title}" tvg-logo="{logo}" group-title="Live Sports",{event_title}\n'
            playlist_content += f"{stream_link}\n"
            print(f"Success: {event_title}")
            success_count += 1
        else:
            print(f"Failed: {event_title} (Link not found)")

    # প্লেলিস্টটি playlist.m3u ফাইলে সেভ করা
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(playlist_content)
    
    print(f"\nPlaylist generated successfully! Total successful streams: {success_count}. Saved as 'playlist.m3u'.")

if __name__ == "__main__":
    asyncio.run(main())
