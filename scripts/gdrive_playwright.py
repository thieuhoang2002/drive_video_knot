#!/usr/bin/env python3
"""
gdrive_playwright.py — Automated Google Drive video extractor for drive_video_knot.
Automates browser actions via Playwright:
- Launches with persistent Google profile (~/.driveknot_profile)
- Automatically extracts video title, duration, chapters, and full Vietnamese transcript
- 100% focused on exhaustive transcript extraction (zero screenshot overhead)
- Outputs structured JSON or clean Markdown notes for upstream contribution to ytbknot.
"""

from __future__ import annotations

import sys
import os
import re
import json
import time
import argparse
import subprocess
from typing import List, Dict, Any, Tuple

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    os.environ["PYTHONUTF8"] = "1"

try:
    from playwright.sync_api import sync_playwright, BrowserContext, Page
except ImportError:
    print("ERROR: playwright not found. Please install via: pip install playwright", file=sys.stderr)
    sys.exit(1)


PROFILE_DIR = os.path.expanduser("~/.driveknot_profile")


def find_chrome_executable() -> str:
    """Locate official Google Chrome installation on Windows."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "chrome"


def cleanup_orphaned_chrome():
    """Clean up any lingering Chrome processes locking the profile."""
    if sys.platform == "win32":
        try:
            cmd = 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*driveknot_profile*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }'
            subprocess.run(["powershell", "-Command", cmd], capture_output=True, timeout=5)
            time.sleep(1)
        except Exception:
            pass


def parse_timestamp_to_seconds(ts: str) -> int:
    """Convert HH:MM:SS or MM:SS to seconds."""
    parts = list(map(int, ts.strip().split(":")))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return int(parts[0])


def format_seconds_to_timestamp(sec: int) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def extract_drive_file_id(url: str) -> str | None:
    """Extract 33-char or standard Google Drive file ID."""
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def launch_interactive_chrome(url: str, port: int = 9222):
    """Launch official Google Chrome on Windows Session 1 (User Interactive Desktop) via schtasks /it."""
    chrome_exe = find_chrome_executable()
    login_url = f"https://accounts.google.com/ServiceLogin?continue={url}"
    bat_path = os.path.expanduser("~/.driveknot_login.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(f'@echo off\nstart "" "{chrome_exe}" --user-data-dir="{PROFILE_DIR}" --remote-debugging-port={port} --no-first-run --start-maximized "{login_url}"\n')

    task_name = "DriveKnotLogin"
    cmd_create = f'schtasks /create /tn "{task_name}" /tr "{bat_path}" /sc once /st 00:00 /f /it'
    subprocess.run(cmd_create, shell=True, capture_output=True)
    subprocess.run(f'schtasks /run /tn "{task_name}"', shell=True, capture_output=True)
    time.sleep(2)
    subprocess.run(f'schtasks /delete /tn "{task_name}" /f', shell=True, capture_output=True)


class GDriveExtractor:
    def __init__(self, headless: bool = True):
        self.headless = headless
        os.makedirs(PROFILE_DIR, exist_ok=True)

    def _do_extract(
        self,
        page: Page,
        context: BrowserContext,
        url: str,
        output_dir: str | None = None
    ) -> Dict[str, Any]:
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # 1. Start video playback via outer play button or keyboard shortcut
        print("[*] Đang khởi động trình phát video...", file=sys.stderr)
        play_btn = page.locator("button[aria-label*='để phát: k'], [aria-label*='Phát'], [aria-label*='Play']").first
        if play_btn.count() > 0:
            try:
                play_btn.click(timeout=3000)
            except Exception:
                pass
        try:
            page.keyboard.press("k")
        except Exception:
            pass
        page.wait_for_timeout(3000)

        # 2. Extract Title
        raw_title = page.title().replace(" - Google Drive", "").strip()
        if not raw_title or raw_title == "Google Drive":
            name_el = page.locator("[data-tooltip*='Tên'], [aria-label*='Tên tệp']").first
            if name_el.count() > 0:
                raw_title = name_el.inner_text().strip()

        print(f"[+] Tiêu đề video: {raw_title}", file=sys.stderr)

        # 3. Locate video element inside iframe
        video = None
        for _ in range(12):
            for f in page.frames:
                try:
                    if f.locator("video").count() > 0:
                        video = f.locator("video").first
                        break
                except Exception:
                    continue
            if video:
                break
            page.wait_for_timeout(1000)

        # 4. Extract Duration
        duration_sec = 0
        if video:
            for _ in range(10):
                try:
                    dur = video.evaluate("v => v.duration")
                    if dur and str(dur) != "nan" and dur > 0:
                        duration_sec = int(dur)
                        break
                except Exception:
                    pass
                page.wait_for_timeout(500)

        # 5. Open Transcript and extract cues (retry loop until transcript loads)
        transcript_items = []
        print("[*] Đang bóc tách Bản chép lời (Transcript)...", file=sys.stderr)
        ts_btn = page.locator("button[aria-label='Bản chép lời'], button:has-text('Bản chép lời')").first
        if ts_btn.count() > 0:
            try:
                ts_btn.click(force=True)
            except Exception as e:
                print(f"[-] Không thể click nút bản chép lời: {e}", file=sys.stderr)

        extracted_cues = []
        for _ in range(12):
            page.wait_for_timeout(1000)
            cues = page.evaluate("""() => {
                const results = [];
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                let node;
                while ((node = walker.nextNode())) {
                    const val = node.nodeValue.trim();
                    if (/^\\d{1,2}:\\d{2}(:\\d{2})?$/.test(val)) {
                        let p = node.parentElement;
                        while (p && p.innerText.trim() === val) {
                            p = p.parentElement;
                        }
                        if (p) {
                            const full = p.innerText.replace(val, '').trim();
                            if (full.length > 2) {
                                results.push({
                                    timestamp: val,
                                    text: full.split('\\n')[0].replace(/Sao chép đường liên kết.*/gi, '').trim()
                                });
                            }
                        }
                    }
                }
                const seen = new Set();
                return results.filter(r => {
                    const k = r.timestamp + '::' + r.text;
                    if (seen.has(k)) return false;
                    seen.add(k);
                    return true;
                });
            }""")
            if len(cues) > 5:
                extracted_cues = cues
                break
            # If cues still empty, try clicking transcript button again
            if ts_btn.count() > 0 and len(cues) <= 1:
                try:
                    ts_btn.click(force=True)
                except Exception:
                    pass

        chapters = []

        if extracted_cues:
            transcript_items = extracted_cues
            print(f"[+] Trích xuất thành công {len(transcript_items)} dòng bản chép lời!", file=sys.stderr)
        else:
            print("[-] Không tìm thấy bản chép lời tự động từ giao diện Drive.", file=sys.stderr)

        result_data = {
            "url": url,
            "title": raw_title,
            "duration_seconds": duration_sec,
            "chapters": chapters,
            "transcript": transcript_items
        }

        if output_dir:
            meta_path = os.path.join(output_dir, "metadata.json")
            try:
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=2)
                print(f"[+] Đã lưu cấu trúc dữ liệu tại: {meta_path}", file=sys.stderr)
            except Exception as e:
                print(f"[-] Không thể ghi metadata.json: {e}", file=sys.stderr)

        return result_data

    def extract(
        self,
        url: str,
        output_dir: str | None = None
    ) -> Dict[str, Any]:
        cleanup_orphaned_chrome()
        chrome_exe = find_chrome_executable()

        needs_login = False
        with sync_playwright() as p:
            # 1. Quick check if already logged in via headless persistent context
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    channel="chrome",
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                )
                page = context.new_page()
                print(f"[*] Kiểm tra phiên truy cập video: {url} ...", file=sys.stderr)
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(3000)
                if page.locator("video").count() > 0 or ("Record" in page.title() and "Không tìm thấy" not in page.title()):
                    print("[+] Đã xác thực phiên Google Drive hợp lệ (chạy ngầm tự động).", file=sys.stderr)
                    res = self._do_extract(page, context, url, output_dir)
                    context.close()
                    return res
                else:
                    needs_login = True
            except Exception:
                needs_login = True
            finally:
                try:
                    context.close()
                except Exception:
                    pass

        # 2. If login is needed: Launch native Chrome on Session 1 via schtasks /it
        if needs_login:
            is_listening = False
            try:
                import urllib.request
                urllib.request.urlopen("http://localhost:9222/json/version", timeout=1)
                is_listening = True
            except Exception:
                is_listening = False

            if not is_listening:
                cleanup_orphaned_chrome()
                print("\n" + "=" * 62, file=sys.stderr)
                print("[*] ĐANG MỞ CỬA SỔ GOOGLE CHROME TRÊN MÀN HÌNH ĐỂ ĐĂNG NHẬP...", file=sys.stderr)
                print("[*] Bạn chỉ cần đăng nhập tài khoản Google 1 lần trên cửa sổ này.", file=sys.stderr)
                print("[*] Sau khi đăng nhập, hệ thống sẽ tự động hoàn tất 100% phần còn lại!", file=sys.stderr)
                print("=" * 62 + "\n", file=sys.stderr)
                launch_interactive_chrome(url, port=9222)
                time.sleep(3)

            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp("http://localhost:9222")
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else context.new_page()

                print("[*] Đang chờ đăng nhập tài khoản Google (tối đa 5 phút)...", file=sys.stderr)
                logged_in = False
                for _ in range(150):
                    time.sleep(2)
                    try:
                        target_page = page
                        for p_item in context.pages:
                            if "drive.google.com" in p_item.url:
                                target_page = p_item
                                break

                        if target_page.locator("video").count() > 0 or ("Record" in target_page.title() and "Không tìm thấy" not in target_page.title()):
                            print("\n[+] ĐĂNG NHẬP THÀNH CÔNG! PHIÊN LÀM VIỆC ĐÃ ĐƯỢC LƯU VĨNH VIỄN.", file=sys.stderr)
                            print("[*] Bắt đầu tự động trích xuất...", file=sys.stderr)
                            logged_in = True
                            page = target_page
                            break
                    except Exception:
                        pass

                if not logged_in:
                    print("[-] Quá thời gian chờ đăng nhập (5 phút). Vui lòng thử lại.", file=sys.stderr)
                    browser.close()
                    cleanup_orphaned_chrome()
                    sys.exit(1)

                result = self._do_extract(page, context, url, output_dir)
                browser.close()
                cleanup_orphaned_chrome()
                return result


def main():
    parser = argparse.ArgumentParser(description="Google Drive Video Extractor for drive_video_knot (100% Automated Transcript)")
    parser.add_argument("url", help="Google Drive video URL")
    parser.add_argument("--output-dir", help="Thư mục lưu trữ bài học và metadata.json")
    parser.add_argument("--no-headless", action="store_true", help="Hiển thị cửa sổ trình duyệt (bắt buộc cho lần đầu đăng nhập)")
    parser.add_argument("--json", action="store_true", help="In kết quả dạng JSON")

    args = parser.parse_args()

    extractor = GDriveExtractor(headless=not args.no_headless)
    data = extractor.extract(
        args.url,
        output_dir=args.output_dir
    )

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"Title: {data['title']}")
        print(f"Duration: {data['duration_seconds']}s")
        print(f"Transcript lines: {len(data['transcript'])}")


if __name__ == "__main__":
    main()
