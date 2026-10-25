#!/usr/bin/env python3
"""
gdrive_playwright.py — Automated Google Drive video extractor for drive_video_knot.
Automates browser actions via Playwright:
- Launches with persistent Google profile (~/.driveknot_profile)
- Automatically logs in once if required (shows browser window on first run)
- Extracts video title, duration, chapters, and full Vietnamese transcript
- Automatically analyzes kịch bản / chapters để tự chọn 6-10 mốc thời gian kỹ thuật then chốt
- Captures high-resolution keyframe screenshots directly from <video> via CDP
- Outputs structured JSON or clean Markdown notes for upstream contribution to ytbknot.
"""

from __future__ import annotations

import sys
import os
import re
import json
import time
import argparse
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


def format_seconds_to_filename(sec: int) -> str:
    """Format seconds into 05m30s string."""
    m = sec // 60
    s = sec % 60
    return f"{m:02d}m{s:02d}s"


def extract_drive_file_id(url: str) -> str | None:
    """Extract 33-char or standard Google Drive file ID."""
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def auto_select_keyframe_timestamps(
    transcript: List[Dict[str, str]],
    chapters: List[Dict[str, Any]],
    duration_sec: int,
    target_count: int = 8
) -> List[str]:
    """
    Tự động xác định các mốc thời gian kỹ thuật quan trọng nhất (không cần người dùng nhập tay).
    Tuân thủ quy tắc ytbknot:
    1. Không chụp đầu chương (tránh slide bìa, mặt người nói).
    2. Ưu tiên các phân đoạn có từ khóa thao tác màn hình, sơ đồ, bảng biểu, công cụ.
    3. Trải đều dọc theo thân bài giảng, cách nhau tối thiểu 2-4 phút.
    """
    selected_seconds: List[int] = []

    # Chiến lược 1: Nếu video có Chương (Chapters) trên Google Drive
    if chapters and len(chapters) >= 2:
        for i in range(len(chapters)):
            ch_start = chapters[i]["seconds"]
            ch_end = chapters[i + 1]["seconds"] if i + 1 < len(chapters) else duration_sec
            ch_len = ch_end - ch_start

            # Bỏ qua chương mở đầu quá ngắn (< 60s) hoặc phần giới thiệu
            if ch_start < 90 and i == 0:
                continue

            # Bắt tại 70% - 85% thân chương (thời điểm màn hình hiển thị trọn vẹn giải pháp / code / bảng)
            if ch_len > 30:
                target_sec = ch_start + int(ch_len * 0.75)
                selected_seconds.append(target_sec)

        if selected_seconds:
            return [format_seconds_to_timestamp(s) for s in selected_seconds[:target_count]]

    # Chiến lược 2: Phân tích ngữ nghĩa kịch bản (Visual trigger keywords)
    visual_keywords = [
        "màn hình", "nhìn vào", "bảng", "sơ đồ", "giao diện", "bước 1", "bước 2", "bước 3",
        "ví dụ", "cài đặt", "bấm vào", "tài khoản", "fanpage", "bm", "tạo", "hình", "slide",
        "chi phí", "tính tiền", "cột bên phải", "cấu hình", "thao tác", "nhấp", "chọn"
    ]

    scored_cues: List[Tuple[int, int, str]] = []
    for item in transcript:
        ts = item.get("timestamp", "0:00")
        sec = parse_timestamp_to_seconds(ts)
        text = item.get("text", "").lower()
        score = sum(1 for kw in visual_keywords if kw in text)
        if score > 0:
            scored_cues.append((sec, score, ts))

    # Lọc các mốc cách nhau tối thiểu 180s (3 phút), tránh 2 phút đầu và 2 phút cuối
    last_sec = -300
    for sec, score, ts in scored_cues:
        if 120 < sec < (duration_sec - 120) and (sec - last_sec) >= 180:
            selected_seconds.append(sec)
            last_sec = sec
        if len(selected_seconds) >= target_count:
            break

    # Chiến lược 3: Fallback trải đều theo thời lượng nếu không có keyword
    if len(selected_seconds) < 4 and duration_sec > 300:
        selected_seconds = []
        step = duration_sec / (target_count + 1)
        for i in range(target_count):
            selected_seconds.append(int((i + 1) * step))

    return [format_seconds_to_timestamp(s) for s in selected_seconds]


class GDriveExtractor:
    def __init__(self, headless: bool = True):
        self.headless = headless
        os.makedirs(PROFILE_DIR, exist_ok=True)

    def _open_context(self, p, headless: bool) -> BrowserContext:
        return p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=headless,
            viewport={"width": 1280, "height": 720},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )

    def extract(
        self,
        url: str,
        screenshot_timestamps: List[str] | None = None,
        auto_screenshots: bool = True,
        output_dir: str | None = None
    ) -> Dict[str, Any]:
        with sync_playwright() as p:
            # First attempt: headless
            context = self._open_context(p, headless=self.headless)
            page = context.new_page()

            print(f"[*] Đang truy cập: {url} ...", file=sys.stderr)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            # Check if login required
            title = page.title()
            if "Không tìm thấy trang" in title or "accounts.google.com" in page.url or "Đăng nhập" in title:
                print("\n[!] Video yêu cầu đăng nhập tài khoản Google có quyền xem.", file=sys.stderr)
                print("[!] Đang mở cửa sổ trình duyệt để bạn đăng nhập Google 1 lần duy nhất...", file=sys.stderr)
                context.close()
                
                # Launch headful for user login
                context = self._open_context(p, headless=False)
                page = context.new_page()
                page.goto(url, timeout=60000)
                
                print("[*] Vui lòng đăng nhập Google trên cửa sổ vừa hiện lên.", file=sys.stderr)
                print("[*] Hệ thống sẽ tự động phát hiện khi video tải thành công...", file=sys.stderr)
                
                for _ in range(120):
                    time.sleep(2)
                    if page.locator("video").count() > 0 or "Record" in page.title() or "Google Drive" in page.title():
                        if "Không tìm thấy trang" not in page.title() and "accounts.google.com" not in page.url:
                            print("[+] Đăng nhập thành công! Thông tin đăng nhập đã được lưu vĩnh viễn.", file=sys.stderr)
                            break

            # Now on the video page
            page.wait_for_selector("video", timeout=30000)
            video = page.locator("video").first

            # Extract Title
            raw_title = page.title().replace(" - Google Drive", "").strip()
            if not raw_title or raw_title == "Google Drive":
                name_el = page.locator("[data-tooltip*='Tên'], [aria-label*='Tên tệp']").first
                if name_el.count() > 0:
                    raw_title = name_el.inner_text().strip()

            print(f"[+] Tiêu đề video: {raw_title}", file=sys.stderr)

            # Get video duration in seconds
            try:
                duration_sec = int(video.evaluate("v => Math.floor(v.duration || 0)"))
            except Exception:
                duration_sec = 0

            # Step: Extract Chapters ("Chương") if available
            chapters = []
            chapter_btn = page.locator("button:has-text('Chương'), [aria-label*='Chương'], [aria-label*='Chapters']").first
            if chapter_btn.count() > 0:
                try:
                    chapter_btn.click()
                    page.wait_for_timeout(1000)
                    ch_items = page.evaluate("""
                        () => {
                            const res = [];
                            document.querySelectorAll('[role=\"menuitem\"], [role=\"listitem\"]').forEach(el => {
                                const text = el.innerText || '';
                                const m = text.match(/(\\d{1,2}:\\d{2}(:\\d{2})?)/);
                                if (m) {
                                    res.push({ timestamp: m[1], title: text.replace(m[1], '').trim() });
                                }
                            });
                            return res;
                        }
                    """)
                    for ch in ch_items:
                        ch["seconds"] = parse_timestamp_to_seconds(ch["timestamp"])
                        chapters.append(ch)
                    if chapters:
                        print(f"[+] Tìm thấy {len(chapters)} chương mục sẵn có từ Drive!", file=sys.stderr)
                except Exception:
                    pass

            # Step: Open transcript ("Bản chép lời")
            transcript_items = []
            print("[*] Đang bóc tách Bản chép lời (Transcript)...", file=sys.stderr)
            transcript_btn = page.locator("button:has-text('Bản chép lời'), [aria-label*='Bản chép lời'], [aria-label*='Transcript']").first
            
            if transcript_btn.count() > 0:
                try:
                    transcript_btn.click()
                    page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"[-] Không thể click nút bản chép lời: {e}", file=sys.stderr)

            # Extract transcript text and timestamps from DOM
            extracted_cues = page.evaluate("""
                () => {
                    const results = [];
                    const tsEls = Array.from(document.querySelectorAll('div, span, p')).filter(e => /^\\d{1,2}:\\d{2}(:\\d{2})?$/.test(e.innerText.trim()));
                    tsEls.forEach(el => {
                        const ts = el.innerText.trim();
                        const item = el.closest('[role=\"listitem\"]') || el.parentElement;
                        let text = item ? item.innerText.replace(ts, '').trim() : '';
                        text = text.replace(/Sao chép đường liên kết.*/gi, '').trim();
                        if (text && text.length > 2) {
                            results.push({ timestamp: ts, text: text });
                        }
                    });
                    const seen = new Set();
                    return results.filter(r => {
                        const k = r.timestamp + '::' + r.text;
                        if (seen.has(k)) return false;
                        seen.add(k);
                        return true;
                    });
                }
            """)

            if extracted_cues:
                transcript_items = extracted_cues
                print(f"[+] Trích xuất thành công {len(transcript_items)} dòng bản chép lời!", file=sys.stderr)
            else:
                print("[-] Không tìm thấy bản chép lời tự động từ giao diện Drive.", file=sys.stderr)

            # Step: Resolve Screenshot Timestamps (Automatic or Manual)
            final_shots = screenshot_timestamps
            if not final_shots and auto_screenshots and output_dir:
                print("[*] Đang tự động phân tích kịch bản để chọn khung hình kỹ thuật...", file=sys.stderr)
                final_shots = auto_select_keyframe_timestamps(
                    transcript_items, chapters, duration_sec, target_count=8
                )
                print(f"[+] Tự động chọn {len(final_shots)} mốc thời gian tối ưu: {', '.join(final_shots)}", file=sys.stderr)

            # Step: Capture Screenshots
            captured_screenshots = []
            if final_shots and output_dir:
                shots_dir = os.path.join(output_dir, "screenshots")
                os.makedirs(shots_dir, exist_ok=True)
                print(f"[*] Bắt đầu chụp {len(final_shots)} khung hình kỹ thuật tự động...", file=sys.stderr)

                for idx, ts in enumerate(final_shots, start=1):
                    sec = parse_timestamp_to_seconds(ts)
                    time_label = format_seconds_to_filename(sec)
                    img_name = f"{idx:03d}_{time_label}.png"
                    img_path = os.path.join(shots_dir, img_name)

                    try:
                        video.evaluate(f"v => {{ v.currentTime = {sec}; }}")
                        page.wait_for_timeout(1500)
                        video.screenshot(path=img_path)
                        captured_screenshots.append({
                            "timestamp": ts,
                            "seconds": sec,
                            "filename": img_name,
                            "path": img_path
                        })
                        print(f"    [OK] Đã chụp tự động {img_name} tại mốc {ts}", file=sys.stderr)
                    except Exception as err:
                        print(f"    [ERR] Lỗi khi chụp tại {ts}: {err}", file=sys.stderr)

            context.close()

            return {
                "url": url,
                "title": raw_title,
                "duration_seconds": duration_sec,
                "chapters": chapters,
                "transcript": transcript_items,
                "screenshots": captured_screenshots
            }


def main():
    parser = argparse.ArgumentParser(description="Google Drive Video Extractor for drive_video_knot (100% Automated)")
    parser.add_argument("url", help="Google Drive video URL")
    parser.add_argument("--screenshots", help="Mốc thời gian chỉ định (tùy chọn, mặc định tự động chọn thông minh)")
    parser.add_argument("--no-screenshots", action="store_true", help="Không chụp ảnh màn hình")
    parser.add_argument("--output-dir", help="Thư mục lưu trữ ảnh chụp và bài học")
    parser.add_argument("--no-headless", action="store_true", help="Hiển thị cửa sổ trình duyệt")
    parser.add_argument("--json", action="store_true", help="In kết quả dạng JSON")

    args = parser.parse_args()

    shots = [s.strip() for s in args.screenshots.split(",")] if args.screenshots else None
    extractor = GDriveExtractor(headless=not args.no_headless)
    
    auto_shots = not args.no_screenshots
    data = extractor.extract(
        args.url,
        screenshot_timestamps=shots,
        auto_screenshots=auto_shots,
        output_dir=args.output_dir
    )

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"Title: {data['title']}")
        print(f"Transcript lines: {len(data['transcript'])}")
        print(f"Screenshots captured: {len(data['screenshots'])}")


if __name__ == "__main__":
    main()
