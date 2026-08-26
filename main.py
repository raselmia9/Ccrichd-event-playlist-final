import asyncio
import json
import os
from playwright.async_api import async_playwright
import requests

INPUT_JSON_URL = "https://raw.githubusercontent.com/raselmia9/Crichd-Live-Event/refs/heads/main/crichd_matches.json"

async def extract_m3u8_from_url(context, page_url):
    page = await context.new_page()
    await page.route("**/*.{png,jpg,jpeg,gif,css,svg,woff,woff2}", lambda route: route.abort())

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
        await page.goto(page_url, timeout=25000)
        for _ in range(10):
            if m3u8_url:
                break
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error loading {page_url}: {e}")

    await page.close()
    if m3u8_url:
        return f"{m3u8_url}|Referer={referer_url}"
    return None

async def process_match(context, match):
    event_title = match.get("event_name", "Live Sports")
    match_time = match.get("date_and_time", "2026-01-01 00:00:00")
    team1_logo = match.get("team1_logo", "")
    team2_logo = match.get("team2_logo", "")
    team1_title = match.get("team1_name", "Team 1")
    team2_title = match.get("team2_name", "Team 2")
    multi_streaming_str = match.get("multi_streaming", "")

    # যদি আগে থেকেই মেসেজ দেওয়া থাকে যে লিংক পরে আসবে, তবে ব্রাউজারে না গিয়ে সরাসরি সেটি বসিয়ে দেওয়া
    if "Stream links will be activated" in multi_streaming_str:
        stream_link_formatted = multi_streaming_str
    else:
        stream_parts = []
        links_raw = multi_streaming_str.split(")")
        extraction_tasks = []
        link_labels = []

        for item in links_raw:
            if ",," in item:
                parts = item.split(",,")
                label = parts[0].replace("(", "").strip()
                url = parts[1].replace("(", "").strip()
                
                if url.startswith("http"):
                    link_labels.append(label)
                    extraction_tasks.append(extract_m3u8_from_url(context, url))

        if extraction_tasks:
            m3u8_results = await asyncio.gather(*extraction_tasks)
            for label, m3u8_link in zip(link_labels, m3u8_results):
                if m3u8_link:
                    stream_parts.append(f"{label},,{m3u8_link}")

        if stream_parts:
            stream_link_formatted = ",) ".join(stream_parts)
        else:
            stream_link_formatted = "Stream links will be activated before 1 hr of starting time."

    return {
        "eventTitle": event_title,
        "matchTime": match_time,
        "team1Logo": team1_logo,
        "team2Logo": team2_logo,
        "team1Title": team1_title,
        "team2Title": team2_title,
        "streamLink": stream_link_formatted,
        "isHot": True
    }

async def main():
    print("ইনপুট JSON ফাইল লোড করা হচ্ছে...")
    try:
        response = requests.get(INPUT_JSON_URL)
        matches_data = response.json()
    except Exception as e:
        print(f"JSON লোড করতে সমস্যা হয়েছে: {e}")
        return

    if not matches_data:
        print("কোনো ম্যাচ ডাটা পাওয়া যায়নি!")
        return

    print(f"মোট {len(matches_data)} টি ম্যাচ প্রসেস করা হচ্ছে...")

    final_output = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        match_tasks = [process_match(context, match) for match in matches_data]
        final_output = await asyncio.gather(*match_tasks)

        await browser.close()

    output_filename = "Live Event.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)

    print(f"সফলভাবে '{output_filename}' ফাইল তৈরি করা হয়েছে!")

if __name__ == "__main__":
    asyncio.run(main())
