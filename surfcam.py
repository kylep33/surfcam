#!/usr/bin/env python3
import subprocess
import time
import re
import urllib.request

def get_stream_url():
    req = urllib.request.Request(
        "https://hdontap.com/stream/186699/pacific-beach-live-surf-webcam/",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    html = urllib.request.urlopen(req).read().decode()
    match = re.search(r'"streamSrc":\s*"([^"]+)"', html)
    if match:
        url = match.group(1).replace("\\u0026", "&")
        print(f"Got URL: {url}")
        return url
    print("No streamSrc found in page")
    return None

while True:
    url = get_stream_url()
    if url:
        subprocess.run(["mpv", "--fullscreen", "--no-osc", url])
    else:
        print("Retrying in 30s...")
    time.sleep(30)
