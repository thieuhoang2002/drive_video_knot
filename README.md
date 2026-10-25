# ytbknot

Plugin trích xuất và chuyển đổi video YouTube và Google Drive thành tài liệu học tập kỹ thuật chuyên sâu bằng Tiếng Việt cho Antigravity (AGY).

---

## 1. Giới thiệu

`ytbknot` là bộ công cụ học tập dành cho kỹ sư và người học chuyên sâu:
* **Quy trình thích ứng 2 pha:** Trinh sát nhanh metadata và transcript trong 2-3 giây, sau đó tự động phân loại video để trích xuất khung hình chuẩn xác mà không cần người dùng cấu hình phức tạp.
* **Tự động hóa toàn diện:** Lấy phụ đề, lọc phân đoạn tài trợ và quảng cáo qua SponsorBlock, chụp khung hình kỹ thuật và tổ chức bài học thành tài liệu Markdown.
* **Bộ ảnh độc lập:** Toàn bộ ảnh trích xuất từ video được lưu tách biệt tại thư mục `screenshots/` (hỗ trợ phân đoạn, chu kỳ `--interval`, phát hiện chuyển cảnh `scenes` hoặc mốc chỉ định).
* **Bài note 2 tầng chuẩn mực:**
  * **Tầng 1 (Tổng luận chuyên đề):** Đọc nhanh 5 phút để nắm trọn 100% tinh hoa, công thức và quy tắc cốt lõi.
  * **Tầng 2 (Bóc tách chi tiết):** Phân tích từng phân đoạn demo hoặc câu hỏi, đối chiếu đề bài, phương án, họ từ mở rộng và khung hình tương ứng.
* **Tiêu chuẩn trình bày:** 100% Tiếng Việt Kỹ thuật, không dùng bất kỳ emoji trang trí nào, tiêu đề ngắn gọn thuần Việt (2-4 từ, không ngoặc đơn tiếng Anh).
* **Lọc ảnh kỹ thuật theo ngữ cảnh:** AI tự động phân loại bài giảng: với live-coding bắt ảnh khi lệnh hoàn tất; với bài giảng giải đề/slide bắt ảnh tại mốc cuối phân đoạn (trước khi chuyển câu 2-5 giây) để lưu trọn vẹn 100% bút phê, ghi chú và lời giải chi tiết của giảng viên; loại bỏ hoàn toàn ảnh chân dung (talking head).

---

## 2. Cài đặt & Yêu cầu hệ thống

### Công cụ phụ thuộc:
* **Python 3.10+**
* **yt-dlp**
* **playwright** (Hỗ trợ trích xuất video Google Drive)
* **ffmpeg**
* **Node.js** (để yt-dlp giải mã JavaScript runtime của YouTube)

```bash
# Kiểm tra môi trường
python3 --version
yt-dlp --version
ffmpeg -version
node --version
```

### Vị trí plugin trong Antigravity:
```text
~/.gemini/config/plugins/ytbknot/
├── plugin.json
├── README.md
├── rules/
│   └── AGENTS.md
├── scripts/
│   ├── gdrive_playwright.py
│   └── ytbknot.py
└── skills/
    └── ytbknot/
        ├── SKILL.md
        └── references/
            └── learning-template.md
```

Lệnh thực thi CLI được gắn sẵn vào PATH: `ytbknot` (tại `~/.local/bin/ytbknot`).

---

## 3. Hướng dẫn sử dụng

### Sử dụng qua Slash Command trong Antigravity:
```text
/ytbknot https://www.youtube.com/watch?v=...
```

Khi được gọi, kỹ năng sẽ tự động thực thi theo quy trình 2 pha:
1. **Pha 1 (Trinh sát):** Tải nhanh metadata và transcript sạch (lưu cache, không chụp ảnh).
2. **Pha 2 (Trích xuất hành động thực tế):**
   * AI phân tích kịch bản để tìm mốc thời gian thao tác kỹ thuật cụ thể (terminal, code IDE, sơ đồ kiến trúc), tuyệt đối không chụp tại mốc đầu chương (tránh ảnh chân dung hoặc slide bìa).
   * Nếu có chương: AI chọn 1-2 mốc hành động then chốt nằm sâu trong thân từng chương.
   * Nếu không có chương: AI chọn 5-10 mốc thời gian kỹ thuật quan trọng nhất dọc bài giảng.
   * Nếu ngoại lệ (không có phụ đề hoặc thời lượng > 2 giờ): Mở hộp thoại hỏi ý định người dùng.

### Trích xuất Video từ Google Drive:

Hỗ trợ trọn vẹn các video lưu trữ trên Google Drive (bao gồm cả link công khai lẫn video khóa học nội bộ ở chế độ **"Chỉ xem, tắt tính năng tải về"**).

#### 1. Sử dụng qua Slash Command trong Antigravity:
```text
/ytbknot https://drive.google.com/file/d/.../view
```
* Tác tử AI (Antigravity) sẽ tự động kích hoạt engine Playwright chạy ngầm.
* **Xác thực 1 lần duy nhất:** Nếu video nằm trong tổ chức hoặc yêu cầu đăng nhập tài khoản Google có quyền xem, trình duyệt sẽ tự động mở lên 1 lần duy nhất để bạn đăng nhập. Phiên làm việc được lưu vĩnh viễn tại `~/.driveknot_profile` (hoàn toàn độc lập, không ảnh hưởng Chrome chính).
* AI tự động mở "Bản chép lời" (Transcript), bóc tách phụ đề tiếng Việt, tự động chọn các mốc thao tác/slide quan trọng để chụp ảnh sắc nét trực tiếp từ thẻ video qua Chrome DevTools Protocol (CDP) và xuất bài note 2 tầng hoàn chỉnh.

#### 2. Sử dụng qua Terminal CLI:
* **Tự động hóa hoàn toàn từ A-Z (Tự bóc transcript + Tự chọn mốc chụp ảnh kỹ thuật thông minh):**
  ```bash
  python scripts/gdrive_playwright.py "https://drive.google.com/file/d/.../view" --output-dir "facebook-ads/buoi-1"
  ```
  *(Engine tự động quét Chương và từ khóa thao tác màn hình để tự chọn 6-10 khung hình kỹ thuật đắt giá nhất mà bạn không cần phải nhập mốc thời gian thủ công).*

* **Trích xuất chỉ định mốc thời gian thủ công (Tùy chọn nâng cao):**
  ```bash
  python scripts/gdrive_playwright.py "https://drive.google.com/file/d/.../view" --screenshots "15:41,23:16,55:36,1:08:08" --output-dir "facebook-ads/buoi-1"
  ```

* **Xuất dữ liệu có cấu trúc dạng JSON:**
  ```bash
  python scripts/gdrive_playwright.py "https://drive.google.com/file/d/.../view" --json
  ```

---

### Các tùy chọn qua Terminal CLI (YouTube):

* **Trinh sát nhanh (chỉ lấy kịch bản và cache, không tạo thư mục):**
  ```bash
  ytbknot "https://www.youtube.com/watch?v=..." --no-save --clean-ads
  ```

* **Trích xuất theo các mốc thời gian chỉ định (tua nhanh trực tiếp, không nghẽn mạng):**
  ```bash
  ytbknot "https://www.youtube.com/watch?v=..." --screenshots "1:15,4:30,9:45" --force
  ```

* **Trích xuất theo danh mục chuyên đề:**
  ```bash
  ytbknot "https://www.youtube.com/watch?v=..." --category "toeic" --screenshots "1:15,4:30,9:45" --force
  ```

* **Chỉ định thư mục gốc lưu trữ bài học (mặc định là thư mục hiện tại `.`):**
  ```bash
  ytbknot "https://www.youtube.com/watch?v=..." --output-base ~/Lectures --category "system-design"
  ```

* **Chụp ảnh theo chu kỳ thời gian:**
  ```bash
  ytbknot "https://www.youtube.com/watch?v=..." --interval 60 --clean-ads
  ```

* **Chọn mức độ chi tiết bài ghi chú (`--detail`):**
  * `brief`: Tóm lược nhanh Tầng 1 (đọc trong 2-3 phút, chỉ 2-4 ảnh cốt lõi).
  * `standard`: Cấu trúc 2 tầng chuẩn mực kỹ thuật (mặc định).
  * `deep`: Phân tích vi mô siêu chi tiết từng phút giây (1-3 phút/khối hoặc từng câu hỏi/thao tác); tự động nhận diện 4 thể loại bài giảng (Live-coding, Luyện thi/Ngoại ngữ, Lý thuyết/Sơ đồ, Hướng dẫn công cụ); nội dung ghi chú thay thế hoàn toàn video.
  ```bash
  ytbknot "https://www.youtube.com/watch?v=..." --detail deep --clean-ads
  ```

* **Lấy thêm bình luận thảo luận từ cộng đồng:**
  ```bash
  ytbknot "https://www.youtube.com/watch?v=..." --comments
  ```

* **Lập chỉ mục toàn bộ Playlist hoặc Kênh YouTube (Curriculum Tracker):**
  Quét toàn bộ danh sách trong 2-4 giây, tạo Master Dashboard `00_INDEX.md` định dạng Todo List và dựng sẵn cây thư mục học tập cho từng bài:
  ```bash
  ytbknot "https://www.youtube.com/playlist?list=..." --index --category "system-design"
  ```

---

## 4. Cấu trúc kết quả đầu ra

Hệ thống phân cấp thư mục tự thích ứng (tối đa 2 tầng) giúp dễ dàng quản lý đa lĩnh vực và trọn bộ khóa học (Playlist):

### Video đơn lẻ có phân loại danh mục:
```text
toeic/
└── giai-chi-tiet-de-thi-part-5/
    ├── screenshots/                 # Bộ ảnh chụp màn hình kỹ thuật chuẩn WebP (Near-Lossless 90-95%)
    │   ├── 001_07m34s.webp
    │   └── ...
    ├── thumbnail.webp               # Ảnh bìa chuẩn WebP siêu nhẹ
    └── giai-chi-tiet-de-thi-part-5.md # Ghi chú 2 tầng chuẩn kỹ thuật
```

### Danh sách phát (Playlist / Series khóa học):
```text
system-design/
└── microservices-tu-co-ban-den-nang-cao/
    ├── 00_INDEX.md                  # Master Dashboard theo dõi tiến độ (Todo List, % hoàn thành)
    ├── 00_overview.md               # Mục lục tổng quan khóa học & tiến độ
    ├── 01_kien-truc-tong-quan/
    │   ├── screenshots/
    │   │   └── 001_...webp
    │   ├── thumbnail.webp
    │   └── 01_kien-truc-tong-quan.md # Bài note hoàn chỉnh (đã học xong -> tick [x])
    └── 02_message-queue-kafka/
        ├── README.md                # Lệnh chạy trích xuất tạo sẵn cho bài kế tiếp
        └── ...
```
