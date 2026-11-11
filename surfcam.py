#!/usr/bin/env python3
# cycles through webcam streams fullscreen in mpv, with a menu to edit the list
#
# run from a terminal to get the menu, run without one (autostart) to just play
# keyboard: up/down move, a add, d delete, t time per stream, enter start, q quit
# mouse:    click a row to select it
import curses
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "streams.json")
DEFAULT_CONFIG = {
    "seconds_per_stream": 300,
    "streams": [
        {"title": "Pacific Beach", "url": "https://hdontap.com/stream/186699/pacific-beach-live-surf-webcam/"},
        {"title": "Scripps Pier Underwater", "url": "https://hdontap.com/stream/018408/scripps-pier-underwater-live-webcam/"},
        {"title": "La Jolla Shores", "url": "https://hdontap.com/stream/532541/la-jolla-shores-live-surf-cam/"},
        # yosemite cams are still images the conservancy refreshes, not video
        {"title": "Half Dome", "url": "https://pixelcaster.com/yosemite/webcams/ahwahnee2.jpg"},
        {"title": "Yosemite High Sierra", "url": "https://pixelcaster.com/yosemite/webcams/sentinel.jpg"},
        {"title": "El Capitan", "url": "https://pixelcaster.com/yosemite/webcams/turtleback.jpg"},
    ],
}
RETRY_DELAY_S = 30
CHECK_INTERVAL_S = 30 * 60
IPC_TIMEOUT_S = 5
URL_TIMEOUT_S = 15
IPC_SOCKET_PATH = "/tmp/surfcam-mpv.sock"
PLAYBACK_TIME_REQUEST = b'{"command": ["get_property", "playback-time"], "request_id": 1}\n'
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_stream_url(page_url):
    # hdontap pages hide the real stream url in the html, anything else goes straight to mpv
    if "hdontap.com" not in page_url:
        return page_url

    req = urllib.request.Request(page_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=URL_TIMEOUT_S).read().decode()
    except OSError as e:
        print(f"Failed to load {page_url}: {e}. Check network, retrying in {RETRY_DELAY_S}s")
        return None

    match = re.search(r'"streamSrc":\s*"([^"]+)"', html)
    if not match:
        print(f"No streamSrc found in {page_url}")
        return None

    url = match.group(1).replace("\\u0026", "&")
    print(f"Got URL: {url}")
    return url


def find_reply(lines):
    # mpv also pushes events on the socket, skip to our reply
    for line in lines:
        message = json.loads(line)
        if "request_id" in message:
            return message.get("data")
    return None


def get_playback_time():
    try:
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(IPC_TIMEOUT_S)
            sock.connect(IPC_SOCKET_PATH)
            sock.sendall(PLAYBACK_TIME_REQUEST)
            return find_reply(sock.makefile())
    except (OSError, ValueError) as e:
        print(f"mpv not responding on {IPC_SOCKET_PATH}: {e}")
        return None


def has_exited(process, timeout_s):
    try:
        process.wait(timeout=timeout_s)
        return True
    except subprocess.TimeoutExpired:
        return False


def play(url, title, seconds):
    is_image = url.lower().endswith(IMAGE_EXTENSIONS)
    player = subprocess.Popen([
        "mpv", "--fullscreen", "--no-osc", "--image-display-duration=inf",
        f"--osd-msg1={title}", f"--input-ipc-server={IPC_SOCKET_PATH}", url,
    ])
    end = time.monotonic() + seconds
    last_time = None
    while not has_exited(player, min(CHECK_INTERVAL_S, max(0, end - time.monotonic()))):
        if time.monotonic() >= end:
            break
        # a still image never advances, so only video can look frozen
        current_time = get_playback_time()
        if not is_image and (current_time is None or current_time == last_time):
            print("Stream frozen, restarting mpv")
            break
        last_time = current_time
    player.kill()
    player.wait()


def run(config):
    streams = config["streams"]
    # one stream would just restart itself every cycle, so leave it up
    seconds = config["seconds_per_stream"] if len(streams) > 1 else float("inf")
    while True:
        for stream in streams:
            url = get_stream_url(stream["url"])
            if url:
                play(url, stream["title"], seconds)
            else:
                time.sleep(RETRY_DELAY_S)


def prompt(screen, text):
    height, width = screen.getmaxyx()
    screen.move(height - 1, 0)
    screen.clrtoeol()
    screen.addstr(height - 1, 0, text[:width - 1])
    curses.echo()
    curses.curs_set(1)
    answer = screen.getstr(height - 1, min(len(text), width - 1)).decode().strip()
    curses.noecho()
    curses.curs_set(0)
    return answer


def menu(screen, config):
    """edits config in place, returns True to start playing"""
    curses.curs_set(0)
    curses.mousemask(curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED)
    header_rows = 3
    cursor = 0
    while True:
        streams = config["streams"]
        cursor = max(0, min(cursor, len(streams) - 1))
        width = screen.getmaxyx()[1] - 1
        screen.erase()
        screen.addstr(0, 0, "surfcam streams"[:width], curses.A_BOLD)
        screen.addstr(1, 0, "up/down move, a add, d delete, t time, enter start, q quit"[:width], curses.A_DIM)
        for i, stream in enumerate(streams):
            line = f"  {stream['title']} - {stream['url']}"[:width]
            screen.addstr(header_rows + i, 0, line, curses.A_REVERSE if i == cursor else 0)
        if not streams:
            screen.addstr(header_rows, 0, "  (no streams, press a to add one)"[:width], curses.A_DIM)
        footer = header_rows + max(len(streams), 1) + 1
        screen.addstr(footer, 0, f"  seconds on each stream: {config['seconds_per_stream']}"[:width])
        screen.refresh()

        key = screen.getch()
        if key in (curses.KEY_UP, ord("k")):
            cursor -= 1
        elif key in (curses.KEY_DOWN, ord("j")):
            cursor += 1
        elif key == ord("a"):
            title = prompt(screen, "title: ")
            url = prompt(screen, "link: ")
            if title and url:
                streams.append({"title": title, "url": url})
                cursor = len(streams) - 1
        elif key == ord("d") and streams:
            del streams[cursor]
        elif key == ord("t"):
            answer = prompt(screen, "how long do you want to be on each stream (seconds): ")
            if answer.isdigit() and int(answer) > 0:
                config["seconds_per_stream"] = int(answer)
        elif key in (curses.KEY_ENTER, 10, 13) and streams:
            return True
        elif key == ord("q"):
            return False
        elif key == curses.KEY_MOUSE:
            try:
                _, _, row, _, _ = curses.getmouse()
            except curses.error:
                continue
            if 0 <= row - header_rows < len(streams):
                cursor = row - header_rows


config = load_config()
# no terminal means autostart, so skip the menu and play what was saved
if sys.stdin.isatty():
    if not curses.wrapper(menu, config):
        sys.exit(0)
    save_config(config)
if not config["streams"]:
    sys.exit("no streams configured, run surfcam.py from a terminal to add some")
run(config)
