# Crawler Bố Cáo Điện Tử (bocaodientu.dkkd.gov.vn)

Dự án này là một công cụ cào dữ liệu (web crawler) viết bằng Python, dùng để lấy danh sách các bố cáo "Đăng ký thay đổi" của doanh nghiệp và lưu tự động vào cơ sở dữ liệu PostgreSQL. Dự án cũng đi kèm với các công cụ trực quan hóa dữ liệu hiện đại.

## 1. Kiến trúc Hệ thống (Docker Compose)
Dự án bao gồm 6 container (services) chính:
- **db (`dkkd_postgres`)**: Cơ sở dữ liệu PostgreSQL lưu trữ bảng `announcements`.
- **crawler_app (`dkkd_crawler`)**: Ứng dụng cào dữ liệu viết bằng Python (sử dụng Playwright Async), tự động giả lập trình duyệt, vượt qua ReCAPTCHA bằng 2captcha.
- **viewer_app (`dkkd_viewer`)**: Ứng dụng Web viết bằng Python (Flask), hiển thị dữ liệu cào được dạng bảng hiện đại (port 3000) và cung cấp các API tải PDF.
- **browser (`dkkd_browser`)**: Container chạy Chromium (`lscr.io/linuxserver/chromium`) độc lập để cào dữ liệu.
- **browser_proxy (`dkkd_browser_proxy`)**: Dịch vụ `socat` để expose cổng Debugging (CDP) an toàn.
- **adminer (`dkkd_adminer`)**: Công cụ quản trị CSDL qua giao diện Web (port 8888).

## 2. Cấu trúc Thư mục
```text
bocaodientu/
├── docker-compose.yml       # Cấu hình triển khai 4 dịch vụ
├── README.md                # Tài liệu hướng dẫn và thông tin dự án
├── crawler/                 # Dịch vụ Crawler App (Python + Playwright)
│   ├── Dockerfile           
│   ├── requirements.txt     
│   ├── database.py          # Kết nối và thao tác với Database bằng SQLAlchemy
│   └── main_playwright.py   # Script crawl dữ liệu chính (xử lý Captcha, tải PDF)
├── viewer/                  # Dịch vụ Viewer App (Python + Flask)
│   ├── Dockerfile           
│   ├── requirements.txt     
│   ├── app.py               # Backend Flask (Route API, Render giao diện)
│   ├── pdf_downloader.py    # Logic hỗ trợ tải file PDF về từ backend API
│   └── templates/           
│       └── index.html       # Giao diện hiển thị danh sách công ty cào được
```

## 3. Cách Chạy (Run)
Mở terminal và di chuyển vào thư mục dự án, chạy lệnh:
```bash
docker compose up -d --build
```

## 4. Cách Truy Cập Dữ Liệu
1. **Giao diện Khách hàng (Viewer UI):** Truy cập `http://localhost:3000`.
   - Giao diện hiển thị tối đa 500 bản ghi mới nhất tích hợp hệ thống **Tab phân loại động** (Đăng ký mới, Đăng ký thay đổi, Giải thể, v.v...) lọc bằng Javascript.
   - **Phân trang (Pagination)**: Dữ liệu được tính toán và chia nhỏ 20 dòng/trang.
   - **Nút Về đầu trang (Floating)**: Tự động xuất hiện ở góc phải khi người dùng cuộn xuống trang, hỗ trợ trượt lên đầu trang nhanh chóng.
   - **Tối ưu tốc độ tải trang**: Font chữ hiện đại "Outfit" (định dạng nén .woff2) được lưu trữ và tải trực tiếp từ máy chủ cục bộ (local host) thay vì qua Google Fonts, giúp UI phản hồi tức thời không độ trễ.
2. **Giao diện Quản trị Database (Adminer):** Truy cập `http://localhost:8888`
   - **System:** PostgreSQL
   - **Server:** `db`
   - **User / Password:** `crawler_user` / `your_password`
   - **DB:** `dkkd_data`

## 5. Thiết Kế Kỹ Thuật (Lưu Ý)
- Trang web nguồn dùng **ASP.NET WebForms**, crawler sử dụng **Playwright (Async)** chạy chế độ headless nhằm dễ dàng vượt qua các cơ chế kiểm tra bot và điều hướng phân trang.
- Chế độ **Mở khóa Captcha**: Hệ thống tiêm Token tự động giải bằng API của dịch vụ thứ 3 (2captcha) thông qua JavaScript tiêm vào trang để bấm nút "Tải về".
- Cơ chế **Tải PDF qua Playwright Remote CDP**: 
  - Khác với phương pháp cũ bị lỗi file 0 byte (do dùng lẫn lộn lệnh CDP `Browser.setDownloadBehavior` và Playwright stream dẫn tới xung đột), hệ thống hiện tại **tuyệt đối không can thiệp bằng lệnh CDP `Browser.setDownloadBehavior`**.
  - Thay vào đó, crawler khởi tạo context với `accept_downloads=True`, kết hợp sử dụng hàm `page.expect_download()` và gọi hàm `download.save_as(file_path)` chuẩn của Playwright. Playwright sẽ tự động stream nội dung file PDF qua websocket CDP và ghi thẳng file xuống local (ở container Python), giúp dữ liệu được truyền tải an toàn.
  - Nhờ cơ chế này, quá trình ghi file thực hiện bởi ứng dụng backend đang chạy nên loại bỏ triệt để các rắc rối về cấp quyền (Permission Denied/chown 777) so với việc ép container Chromium độc lập tự ghi file.
- Để vào tab "Đăng ký thay đổi", script gọi click vào đối tượng `ctl00$C$RptProdGroups$ctl02$LnkActiveAnnType` trên giao diện web.
- **Mã số doanh nghiệp** đã được bóc tách từ các thẻ lồng bên trong bảng dữ liệu.
- Cơ chế **Vòng lặp tự động (Auto-Loop)**: Script cào dữ liệu được bọc trong vòng lặp vô hạn `while True` và sử dụng `asyncio.sleep(180)` để tự động lặp lại quy trình cào mỗi 3 phút một lần.
- Có cơ chế **Retry Connection** trong code kết nối CSDL để tránh Crash crawler khi PostgreSQL chưa khởi động kịp trong Docker.

## 6. Khắc phục lỗi thường gặp (Troubleshooting)
- **Lỗi `socket hang up` khi tải PDF**: Lỗi này xảy ra khi Backend (Playwright) mất kết nối hoặc không thể kết nối tới trình duyệt Chromium qua cổng CDP (9222).
  - **Nguyên nhân cốt lõi**: Container `lscr.io/linuxserver/chromium` sử dụng biến môi trường `CHROME_CLI` để nhận các tham số dòng lệnh (không phải `CLI_ARGS`). Nếu dùng sai tên biến, Chromium sẽ khởi động mà không mở cổng debug 9222, dẫn tới việc proxy `socat` liên tục từ chối kết nối và ngắt socket.
  - **Cách khắc phục**: Đảm bảo trong `docker-compose.yml` service `browser` sử dụng chính xác biến môi trường `CHROME_CLI=--remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 --no-sandbox --disable-dev-shm-usage`.

- **Lỗi "Không thể giải mã Captcha (2Captcha API trả về rỗng)"**:
  - **Nguyên nhân**: Dịch vụ 2Captcha đôi khi phản hồi rất chậm khi tải hệ thống, vượt qua mức chờ mặc định của code (ví dụ 30 lần thử x 3s = 90 giây). Khi hết thời gian, script sẽ trả về rỗng khiến tiến trình bị lỗi.
  - **Cách khắc phục**: Cần nâng `max_retries` trong vòng lặp chờ giải Captcha lên cao hơn (ví dụ 60 lần ~ 180s) để đảm bảo luôn bắt được token khi API bị chậm.

- **Lỗi "File bị 0 byte hoặc không tải được" (Bất chấp đã cấp quyền 777)**:
  - **Nguyên nhân cốt lõi**: Sự xung đột giữa 2 cơ chế tải file. Code cũ đã cấu hình `Browser.setDownloadBehavior` qua CDP để ép trình duyệt lưu trực tiếp vào thư mục chia sẻ, nhưng ĐỒNG THỜI lại gọi hàm `page.expect_download()` và `download.save_as()` của Playwright. Khi dùng chung cả hai, trình duyệt tự lưu file thành công, nhưng Playwright bị "hẫng" luồng dữ liệu (stream) do cơ chế quản lý nội bộ bị qua mặt. Kết quả là lệnh `download.save_as()` của Playwright cố đọc luồng rỗng và ghi đè một file 0 byte lên đúng vị trí file thật vừa được tải.
  - **Cách khắc phục**: Phải gỡ bỏ hoàn toàn lệnh CDP `Browser.setDownloadBehavior` và `Page.setDownloadBehavior` tự chế. Chỉ cần khai báo `accept_downloads=True` lúc tạo context, gọi `page.expect_download()` và sử dụng duy nhất hàm `download.save_as()` mặc định của Playwright. Playwright sẽ tự động stream nội dung file qua websocket CDP và lưu xuống server an toàn, không bị xung đột thành 0 byte.

- **Lỗi không hiển thị dữ liệu ở một số Tab (dù DB có dữ liệu)**:
  - **Nguyên nhân**: Truy vấn SQL ở backend cũ chỉ lấy `LIMIT 100`. Nếu crawler chạy liên tục ở trang mặc định (Đăng ký mới), 100 bản ghi này sẽ bị chiếm dụng toàn bộ bởi "Đăng ký mới". Ngoài ra, chuỗi văn bản lấy từ DB đôi khi sai lệch với tên Tab (VD: Tab tên "ĐĂNG KÝ THAY ĐỔI" nhưng DB lưu là "Thay đổi nội dung ĐKDN").
  - **Cách khắc phục**: Tăng `LIMIT` lên 500 trong `app.py`. Sửa file `index.html` của Viewer để map đúng các từ khóa ("Thay đổi nội dung", "Chuyển đổi loại hình", v.v...) vào Tab tương ứng.

- **Lỗi "Executable doesn't exist at /ms-playwright/..." khi khởi động Container Crawler**:
  - **Nguyên nhân**: Trong `requirements.txt` không khóa phiên bản `playwright` nên pip tự động tải phiên bản mới nhất (vd: 1.48+ hoặc 1.63), trong khi `Dockerfile` sử dụng base image cũ (vd: `v1.43.0-jammy`). Sự chênh lệch phiên bản này khiến module Python không tìm thấy các file nhị phân của trình duyệt ở đường dẫn nó mong muốn. (Ngoài ra, cố nâng base image lên bản mới có thể dính lỗi GPG apt update do server Ubuntu cũ).
  - **Cách khắc phục**: Phải đồng bộ cứng phiên bản bằng cách ghi rõ `playwright==1.43.0` vào `requirements.txt` để khớp chính xác với `FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy` trong `Dockerfile`.

