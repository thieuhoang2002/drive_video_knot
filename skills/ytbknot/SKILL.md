---
name: ytbknot
description: "Trích xuất và chuyển đổi video YouTube hoặc Google Drive thành tài liệu học tập kỹ thuật chuyên sâu bằng Tiếng Việt cho Antigravity (AGY). AI tự động phân tích kịch bản để chụp chính xác các khung hình kỹ thuật (code, terminal, sơ đồ), lưu bộ ảnh độc lập, bài note 2 tầng thuần Việt, không emoji, tiêu đề ngắn gọn."
user-invocable: true
argument-hint: "<youtube-or-gdrive-url> [url2] [url3] [--category <name>] [--detail brief|standard|deep] [--interval <seconds>] [--clean-ads] [--screenshots [chapters|timestamps]] [--webp-quality <90-95>] [--lossless] [--comments] [--transcript-only] [--no-save] | --check"
allowed-tools: "run_command, view_file, write_to_file, ask_question, invoke_subagent, send_message"
---

Phân tích URL YouTube hoặc Google Drive từ người dùng: <user_request>$ARGUMENTS</user_request>

## Kiểm tra môi trường

```bash
python3 --version && yt-dlp --version && ffmpeg -version 2>&1 | head -1
```

---

## Trinh sát dữ liệu

1. Xác định mức độ chi tiết (`--detail`):
   - Mặc định: `standard`.
   - Nếu người dùng yêu cầu tóm tắt nhanh: `brief`.
   - Nếu người dùng yêu cầu chi tiết nhất, từng phút giây, từng câu hỏi/thao tác: `deep`.
2. Chạy lệnh trinh sát nhanh chỉ lấy metadata và kịch bản sạch, tự động lưu vào cache cục bộ:
   ```bash
   ytbknot "[URL]" --no-save --clean-ads --detail <brief|standard|deep>
   ```
3. Đọc kết quả từ đầu ra:
   - Metadata: tiêu đề, thời lượng, chương mục, `detail_level`, `playlist_title`, `playlist_index`, `tags`.
   - `EXISTING_CATEGORIES`: Danh sách các danh mục chủ đề sẵn có tại thư mục lưu trữ hiện tại.
   - Các khối kịch bản (`Semantic Chunks`) và nội dung chi tiết.

4. **Phân loại danh mục học tập (Adaptive Taxonomy):**
   - Nếu người dùng truyền `--category <tên>`: Sử dụng danh mục được chỉ định.
   - Nếu không có tham số: AI đối chiếu nội dung bài giảng và tags với `EXISTING_CATEGORIES`.
     * Tái sử dụng danh mục có sẵn nếu cùng chủ đề (ví dụ đã có `toeic`, `system-design`...).
     * Nếu là chủ đề mới: Tự động đề xuất slug danh mục ngắn gọn (viết thường, gạch nối, ví dụ: `toeic`, `devops`, `ai-ml`, `economics`).

---

## Phân khối bài giảng & Mô hình Subagent

Để bảo toàn 100% độ bao phủ, tránh cạn kiệt context hoặc tóm tắt hời hợt, quy trình xử lý được phân bổ theo cấp độ:
- **`--detail brief`**: Chỉ phân tích tổng luận Tầng 1, lược bỏ Tầng 2 chi tiết để hoàn tất trong 2-3 phút.
- **`--detail standard`** (Mặc định):
  - Video dưới 45 phút: Xử lý liền mạch toàn bộ bài giảng trong một chu trình.
  - Video trên 45 phút: Xử lý theo từng `Semantic Chunk` (10-15 phút/khối) hoặc theo chapters.
- **`--detail deep`** (Siêu chi tiết & Điều phối Subagent):
  - **Nguyên tắc cốt lõi:** File ghi chú phải có giá trị **thay thế hoàn toàn video** — người học đọc bài viết có thể nắm trọn vẹn 100% kiến thức (tự giải được đề, gõ theo được code, hiểu rõ kiến trúc) mà không cần phải mở lại video để dò xem tác giả đang nói gì.
  - **Điều phối Subagent (Divide & Conquer)**:
    1. Agent chính (Orchestrator) gọi `ytbknot-scout` (hoặc chạy trinh sát bằng script) lấy danh sách các Semantic Chunks vi mô (1-3 phút).
    2. Nếu video dài hoặc có nhiều khối kịch bản kỹ thuật: Phân bổ các khối cho `ytbknot-writer` bóc tách độc lập từng khối.
       * **Bắt buộc truyền dữ liệu trực tiếp**: Khi dispatch `ytbknot-writer`, Agent chính phải truyền trọn vẹn văn bản transcript và mốc thời gian của chunk vào prompt để subagent không phải tra cứu lại web.
       * **Subagent không ghi file**: `ytbknot-writer` chỉ xử lý text và trả Markdown về trong tin nhắn. Agent chính là bên duy nhất tổng hợp và gọi `write_to_file`.
    3. Tác tử chính tổng hợp các phần bóc tách, gắn mốc chụp ảnh và ráp thành tài liệu hoàn chỉnh.
  - **Link mốc thời gian bấm được (Clickable Timestamp Link):** Bắt buộc gắn link mốc thời gian dẫn thẳng đến giây đó trên YouTube, định dạng: `### [[HH:MM:SS](<URL_VIDEO>&t=<GIÂY>s)] Tên phân đoạn` (hoặc `### [HH:MM:SS](<URL_VIDEO>&t=<GIÂY>s) Tên phân đoạn`). Tuyệt đối không để text tĩnh không bấm được.
  - **Khung nhận diện thể loại bài giảng:** Tự động nhận diện thể loại để áp dụng khung bóc tách tương ứng:
    1. *Bài giảng Coding và kỹ thuật thực hành:* Trích xuất mã nguồn hoặc câu lệnh đầy đủ trong code block; giải thích rõ mục đích từng cú pháp, tham số, annotation, cấu hình và phản hồi kết quả terminal hoặc DevTools.
    2. *Bài giảng Giải đề, luyện thi hoặc ngoại ngữ:* Ghi đầy đủ đề bài và toàn bộ phương án A, B, C, D; phân tích cặn kẽ tại sao đúng hoặc sai (bẫy ngữ pháp, lỗi logic, từ khóa gây nhiễu); tổng hợp bảng từ vựng, ngữ pháp cốt lõi hoặc công thức mở rộng.
    3. *Bài giảng Lý thuyết, sơ đồ hoặc kiến trúc:* Bóc tách từng luồng dữ liệu và thành phần sơ đồ; làm rõ cơ chế vận hành nội tại, điều kiện kích hoạt, công thức toán hoặc kinh tế; ghi nhận đầy đủ rủi ro, ngoại lệ và sự đánh đổi.
    4. *Hướng dẫn Công cụ và giao diện:* Liệt kê chính xác quy trình từng bước (đường dẫn click chuột, menu, phím tắt, thông số cấu hình); giải thích ý nghĩa tham số của các tùy chọn bật hoặc tắt.

---

## Trích xuất ảnh & Tổ chức thư mục

**Quy tắc chọn khung hình theo ngữ cảnh:**
- **Không chụp đầu chương**: Giây bắt đầu chương hầu hết là slide tiêu đề hoặc người nói chuyện, không chứa nội dung kỹ thuật. Phân đoạn chương chỉ dùng để chia mục lục bài viết.
- **Bài giảng thao tác màn hình (Live-coding / Terminal)**: Bắt khung hình ngay khi thao tác lệnh hoặc đoạn mã được thực thi hoàn tất.
- **Bài giảng giải đề, slide trình chiếu hoặc bảng viết (Slide-based / Whiteboard / Problem-solving)**:
  * **Bắt buộc chụp tại mốc cuối phân đoạn** của từng câu/mục (ngay trước khi giảng viên chuyển sang nội dung kế tiếp từ 2 đến 5 giây).
  * Đây là thời điểm màn hình hiển thị trọn vẹn 100% nội dung ghi chú viết tay, lời giải chi tiết, phân tích đáp án và các từ vựng mở rộng mà giảng viên đã tổng hợp (tránh chụp đầu phân đoạn khi slide còn trắng trơn).
- **Tua nhanh trực tiếp**: Luôn sử dụng danh sách mốc thời gian cụ thể để ffmpeg nhảy cóc tức thời qua HTTP Range (1-2 giây mỗi ảnh), loại bỏ hoàn toàn nguy cơ bị YouTube bóp băng thông.
- **Tối ưu định dạng WebP**: Toàn bộ ảnh chụp màn hình, sơ đồ và thumbnail được tự động chuyển đổi sang định dạng WebP (chế độ Near-Lossless chất lượng 90-95% mặc định, hoặc Lossless qua `--lossless`), giảm 80-90% dung lượng so với PNG gốc mà vẫn bảo toàn độ nét chữ và sơ đồ kỹ thuật.

**Quy trình thực thi:**
1. **Trích xuất theo kịch bản (Bắt buộc)**:
   - Trong từng khối kịch bản, AI xác định chính xác các mốc giây tối ưu theo ngữ cảnh.
   - Loại bỏ hoàn toàn các phân đoạn nói chuyện phiếm (talking head).
   - Chạy lệnh trích xuất chính thức với danh mục và mốc thời gian (dùng lại cache, không tải lại YouTube):
   ```bash
   # Video đơn lẻ:
   ytbknot "[URL]" --category "<category>" --screenshots "<ts1>,<ts2>,..." --force

   # Bài học trong thư mục có sẵn:
   ytbknot "[URL]" --target-dir "<path/to/lesson>" --screenshots "<ts1>,<ts2>,..." --force
   ```
   - Thư mục được tự động tổ chức chuyên nghiệp:
     * Video đơn lẻ: `<output-base>/<category>/<slug>/`
     * Playlist: `<output-base>/<category>/<playlist-slug>/<index>_<slug>/` kèm file tổng quan `<playlist-slug>/00_overview.md`.
2. **Nhánh ngoại lệ**: Khi video không có bất kỳ phụ đề nào, gọi công cụ `ask_question` để người dùng cung cấp tài liệu hoặc nhập mốc thời gian thủ công.

---

## Định dạng ghi chú

- **100% Tiếng Việt Kỹ thuật**.
- **Tuyệt đối không emoji/icon trang trí**.
- **Tiêu đề H2, H3 cực kỳ ngắn gọn (2-4 từ, thuần Việt, không chèn tiếng Anh trong ngoặc đơn)**.
- **Tầng 1 (Tổng luận chuyên đề):** Đọc nhanh 5 phút nắm 100% tinh hoa, quy tắc và kiến trúc cốt lõi.
- **Tầng 2 (Bóc tách chi tiết):** Đi sâu từng khối / từng câu hỏi; tiêu đề mỗi tiểu mục BẮT BUỘC chứa link timestamp bấm được dẫn thẳng đến giây đó trên YouTube (`### [[HH:MM:SS](URL?t=Xs)] Tên phân đoạn`); gắn kèm hình ảnh kỹ thuật tương ứng, phân tích bản chất và bài toán thực tế.
- Bố cục bắt buộc: Thuật ngữ -> Tổng luận chuyên đề -> Bóc tách chi tiết -> Trích dẫn then chốt -> Lệnh & Công cụ -> Đánh đổi & Rủi ro.

---

## Báo cáo kết quả

Lấy giá trị `OUTPUT_FOLDER` từ đầu ra của lệnh, lưu file ghi chú vào `<OUTPUT_FOLDER>/<slug>.md` và thông báo cho người dùng đường dẫn thư mục bài học cùng số lượng ảnh đã trích xuất.
