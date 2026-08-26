import json
import urllib.request

def main():
    json_url = "https://raw.githubusercontent.com/raselmia9/Crichd-Live-Event-streaming-Link-Get/refs/heads/main/Test"
    
    try:
        with urllib.request.urlopen(json_url) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
            else:
                print("Failed to fetch JSON data.")
                return
    except Exception as e:
        print(f"Error: {e}")
        return

    if isinstance(data, dict):
        data = [data]

    # সাধারণ লিস্ট তৈরি করা (ইভেন্টের নাম এবং লিংক সহ)
    output_content = "=== Live Events & Links List ===\n\n"
    count = 0

    for item in data:
        event_name = item.get("event_name", "Live Event")
        multi_streaming = item.get("multi_streaming", "")

        output_content += f"Event: {event_name}\n"

        if multi_streaming:
            parts = multi_streaming.split(")")
            for part in parts:
                if ",," in part:
                    name_part, url_part = part.split(",,", 1)
                    sub_name = name_part.strip()
                    url = url_part.strip()
                    if url.startswith("http"):
                        output_content += f"  - {sub_name}: {url}\n"
                        count += 1
        output_content += "-" * 40 + "\n"

    # সাধারণ লিস্টটি 'links.txt' ফাইলে সেভ করা
    with open("links.txt", "w", encoding="utf-8") as f:
        f.write(output_content)

    print(f"Successfully generated simple list with {count} links. Saved as 'links.txt'.")

if __name__ == "__main__":
    main()
