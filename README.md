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
- Cơ chế **Tải PDF qua Trình duyệt Native (Shared Volume)**: 
  - Khác với phương pháp cũ bị lỗi file 0 byte do cố gắng dùng cơ chế stream qua websocket CDP (`page.expect_download()` và `download.save_as()`) vốn bị lỗi từ chối kết nối hoặc hạn chế bảo mật trên các bản Chromium mới, hệ thống hiện tại **bắt buộc sử dụng lệnh CDP `Page.setDownloadBehavior`**.
  - Script sẽ gửi lệnh `setDownloadBehavior` để ép Chromium tải file trực tiếp xuống ổ cứng ở đường dẫn nội bộ `/config/Downloads` (được mount với thư mục shared volume `./downloads`). 
  - Sau đó, ứng dụng backend Python sẽ liên tục giám sát (polling) thư mục dùng chung này, chờ cho đến khi tệp phụ `.crdownload` biến mất, xác nhận tiến trình tải nguyên bản từ Chromium đã hoàn tất 100%, rồi mới tiếp tục xử lý đổi tên. Cách này giải quyết dứt điểm rủi ro hẫng luồng dữ liệu 0 byte.
- Để vào tab "Đăng ký thay đổi", script gọi click vào đối tượng `ctl00$C$RptProdGroups$ctl02$LnkActiveAnnType` trên giao diện web.
- **Mã số doanh nghiệp** đã được bóc tách từ các thẻ lồng bên trong bảng dữ liệu.
- Cơ chế **Vòng lặp tự động (Auto-Loop)**: Script cào dữ liệu được bọc trong vòng lặp vô hạn `while True` và sử dụng `asyncio.sleep(180)` để tự động lặp lại quy trình cào mỗi 3 phút một lần.
- Có cơ chế **Retry Connection** trong code kết nối CSDL để tránh Crash crawler khi PostgreSQL chưa khởi động kịp trong Docker.

## 6. Tính Năng Tích Hợp Google Drive
Dự án được bổ sung tính năng **Lưu trữ PDF tự động vào Google Drive**:
- **Công tắc UI**: Trên giao diện Web (Viewer), có một công tắc "Tự động tải & lưu Google Drive". Khi bật công tắc này, các nút bấm tải sẽ chuyển sang chế độ `Xem file PDF`. Đặc biệt, trạng thái bật/tắt này được phân tách độc lập cho từng tab phân loại và tự động lưu vào bảng `user_settings` trong cơ sở dữ liệu PostgreSQL để luôn được ghi nhớ kể cả khi tải lại trang.
- **Cơ chế hoạt động**: Khi người dùng thao tác, hệ thống sẽ:
  1. Sử dụng Playwright tải file PDF về thư mục tạm cục bộ của máy chủ (`downloads/`).
  2. Sử dụng `google-api-python-client` và `credentials.json` (Service Account) để upload trực tiếp file PDF này lên thư mục Google Drive do người dùng chỉ định thông qua HTTP (đảm bảo tốc độ cao, không phụ thuộc vào việc mount volume FUSE vốn dễ gây lỗi).
  3. API Google Drive trả về một `webViewLink`.
  4. Hệ thống cập nhật tự động đường link này vào database (cột `pdf_path` của bảng `announcements`) và mở trực tiếp link trên trình duyệt cho người dùng.
- **Cách thiết lập**: 
  - Yêu cầu tạo Google Service Account và tải file khóa JSON về lưu tại `viewer/credentials.json`.
  - Chia sẻ thư mục Drive mong muốn với địa chỉ email của Service Account với quyền "Người chỉnh sửa".
  - Cập nhật biến `folder_id` trong mã nguồn tương ứng.

## 7. Khắc phục lỗi thường gặp (Troubleshooting)
- **Lỗi `socket hang up` khi tải PDF**: Lỗi này xảy ra khi Backend (Playwright) mất kết nối hoặc không thể kết nối tới trình duyệt Chromium qua cổng CDP (9222).
  - **Nguyên nhân cốt lõi**: Container `lscr.io/linuxserver/chromium` sử dụng biến môi trường `CHROME_CLI` để nhận các tham số dòng lệnh (không phải `CLI_ARGS`). Nếu dùng sai tên biến, Chromium sẽ khởi động mà không mở cổng debug 9222, dẫn tới việc proxy `socat` liên tục từ chối kết nối và ngắt socket.
  - **Cách khắc phục**: Đảm bảo trong `docker-compose.yml` service `browser` sử dụng chính xác biến môi trường `CHROME_CLI=--remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 --no-sandbox --disable-dev-shm-usage`.

- **Lỗi `File bị 0 byte hoặc không tải được`**: 
  - **Nguyên nhân cốt lõi**: Cơ chế tải file stream mặc định của Playwright (`page.expect_download()`) qua giao thức CDP gặp lỗi trên các cấu trúc container phân lập (có thể do cập nhật Chromium 130+ chặn stream tải từ các POST request). Khi đó, Chromium vẫn ghi nhận có lệnh tải, nhưng luồng stream gửi ngược về cho Playwright (Python) liên tục bị ngắt kết nối hoặc rỗng, dẫn đến việc hàm `download.save_as()` lưu một file 0 byte giả mạo.
  - **Cách khắc phục triệt để**: Trong `docker-compose.yml`, tiến hành **mount lại volume** `./downloads:/config/Downloads` cho container `browser`. Trong mã nguồn, loại bỏ hàm `expect_download` của Playwright, thay thế bằng việc chủ động gọi `Page.setDownloadBehavior` qua CDP. Chromium sẽ chịu trách nhiệm tải file trực tiếp xuống đĩa cứng với tốc độ gốc, còn script Python chỉ việc đứng chờ file hoàn thành. Điều này loại trừ hoàn toàn việc tạo ra các file 0 byte do lỗi mạng nội bộ.

- **Lỗi `Hết thời gian chờ (Hoặc không tìm thấy kết quả)` (Timeout Error)**:
  - **Nguyên nhân cốt lõi**: Trình duyệt Chromium có thể bị treo (hang) hoặc rơi vào trạng thái zombie sau nhiều ngày hoạt động liên tục (memory leak hoặc kẹt CDP session). Khi đó, Playwright gọi hàm `page.goto()` hoặc `page.wait_for_selector()` sẽ không nhận được phản hồi và văng lỗi Timeout sau 30 giây.
  - **Cách khắc phục**: Chạy lệnh `docker compose down && docker compose up -d` để khởi động lại sạch sẽ toàn bộ cụm container thay vì chỉ `docker restart`, giúp giải phóng hoàn toàn Network namespace và khôi phục trạng thái ổn định cho `browser` và `browser_proxy`.

- **Lỗi "Không thể giải mã Captcha (2Captcha API trả về rỗng)"**:
  - **Nguyên nhân**: Dịch vụ 2Captcha đôi khi phản hồi rất chậm khi tải hệ thống, vượt qua mức chờ mặc định của code (ví dụ 30 lần thử x 3s = 90 giây). Khi hết thời gian, script sẽ trả về rỗng khiến tiến trình bị lỗi.
  - **Cách khắc phục**: Cần nâng `max_retries` trong vòng lặp chờ giải Captcha lên cao hơn (ví dụ 60 lần ~ 180s) để đảm bảo luôn bắt được token khi API bị chậm.

- **Lỗi "File bị 0 byte hoặc không tải được" (Bất chấp đã dùng Playwright stream)**:
  - **Nguyên nhân cốt lõi**: Các phiên bản trước đó lầm tưởng nguyên nhân 0 byte là do xung đột quyền ghi đè, và cố gắng dùng `expect_download` của Playwright để stream qua Websocket. Tuy nhiên thực tế, cơ chế stream CDP từ remote browser sang container khác là không ổn định và hay bị `ECONNREFUSED` hoặc bị hủy luồng (canceled), khiến nó luôn trả về file rỗng.
  - **Cách khắc phục**: Từ bỏ việc dùng Playwright làm trung gian truyền tải file. Thiết lập Chromium tải gốc (Native Downloader) thông qua `Page.setDownloadBehavior`, lưu ý luôn đảm bảo thư mục đích `/config/Downloads` có đầy đủ quyền ghi (`chown abc:abc`) cho user mặc định của LinuxServer. Tốc độ sẽ nhanh nhất và cam kết không bị lỗi stream đứt gãy.

- **Lỗi không hiển thị dữ liệu ở một số Tab (dù DB có dữ liệu)**:
  - **Nguyên nhân**: Truy vấn SQL ở backend cũ chỉ lấy `LIMIT 100`. Nếu crawler chạy liên tục ở trang mặc định (Đăng ký mới), 100 bản ghi này sẽ bị chiếm dụng toàn bộ bởi "Đăng ký mới". Ngoài ra, chuỗi văn bản lấy từ DB đôi khi sai lệch với tên Tab (VD: Tab tên "ĐĂNG KÝ THAY ĐỔI" nhưng DB lưu là "Thay đổi nội dung ĐKDN").
  - **Cách khắc phục**: Tăng `LIMIT` lên 500 trong `app.py`. Sửa file `index.html` của Viewer để map đúng các từ khóa ("Thay đổi nội dung", "Chuyển đổi loại hình", v.v...) vào Tab tương ứng.

- **Lỗi "Executable doesn't exist at /ms-playwright/..." khi khởi động Container Crawler**:
  - **Nguyên nhân**: Trong `requirements.txt` không khóa phiên bản `playwright` nên pip tự động tải phiên bản mới nhất (vd: 1.48+ hoặc 1.63), trong khi `Dockerfile` sử dụng base image cũ (vd: `v1.43.0-jammy`). Sự chênh lệch phiên bản này khiến module Python không tìm thấy các file nhị phân của trình duyệt ở đường dẫn nó mong muốn. (Ngoài ra, cố nâng base image lên bản mới có thể dính lỗi GPG apt update do server Ubuntu cũ).
  - **Cách khắc phục**: Phải đồng bộ cứng phiên bản bằng cách ghi rõ `playwright==1.43.0` vào `requirements.txt` để khớp chính xác với `FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy` trong `Dockerfile`.

- **Lỗi tải file PDF trả về 0 byte (Mặc dù đã cấu hình đúng CDP Stream)**:
  - **Nguyên nhân cốt lõi**: Trên hệ thống Cổng thông tin quốc gia, đôi khi một doanh nghiệp sẽ có **nhiều bản ghi trùng lặp** được hiển thị cùng một lúc. Trong số đó, có thể một số bản ghi bị lỗi hệ thống (tệp PDF đính kèm bị rỗng/0 byte). Nếu script tải PDF mặc định chỉ sử dụng bộ chọn `.first()` để lấy bản ghi đầu tiên, nó sẽ click vào nút tải của bản ghi bị lỗi này và luôn thu về file 0 byte, trong khi bản ghi đúng nằm ở ngay bên dưới.
  - **Cách khắc phục**: Cập nhật logic tìm kiếm nút bấm trong file `viewer/pdf_downloader.py`. Thay vì dùng hàm `first()`, hệ thống cần đếm toàn bộ các nút PDF trên trang (`pdf_btns.count()`), sau đó dùng vòng lặp `for` để thử click tải từng nút một. Nếu tệp tải về có dung lượng `> 0 byte`, tiến trình thành công và kết thúc. Nếu file là 0 byte hoặc gặp lỗi, vòng lặp tự động bắt `Exception` và chuyển qua tải bằng nút tiếp theo cho tới khi lấy được file chuẩn. Đồng thời, cấu trúc rẽ nhánh fallback đã được cập nhật: nếu toàn bộ nút tải trực tiếp (GetPDF) trả về file rỗng, hệ thống sẽ tự động đi vào trang chi tiết (CmdView) để thử tải tiếp thay vì bỏ cuộc.

- **Lỗi tải nhầm file PDF do trùng Mã số doanh nghiệp (Caching & Selector sai hàng)**:
  - **Nguyên nhân cốt lõi**: Một doanh nghiệp có thể đăng nhiều thông báo vào các thời điểm khác nhau. Nếu logic tải (hoặc cache) chỉ dựa vào `Mã số doanh nghiệp` (`ma_so_dn`), khi người dùng bấm tải bản ghi thứ 2, hệ thống sẽ trả về file cache của bản ghi thứ 1, hoặc Playwright sẽ tìm trên web và luôn click vào kết quả đầu tiên tìm thấy. Điều này dẫn đến tải sai nội dung.
  - **Cách khắc phục**:
    1. **Key Cache Độc Lập:** Trích xuất chính xác `Thời gian đăng báo` (`published_time`) từ giao diện frontend và gửi xuống API. Trong backend, định dạng thời gian thành `safe_published_time` và nối vào tên file cache (VD: `{ma_so_dn}_{safe_published_time}_0.pdf`). Nhờ vậy mỗi bản ghi sẽ có một khóa cache độc nhất.
    2. **Định vị đích danh (Precision Selector):** Khi dùng Playwright để tìm nút tải, script sẽ dùng bộ chọn CSS trỏ thẳng vào đúng hàng `<tr>` chứa chuỗi thời gian tương ứng (`tr:has(td:has-text('{published_time}'))`). Khi đó script sẽ chỉ thao tác giới hạn trong phạm vi các nút tải của chính bản ghi đó, bảo đảm tính chính xác 100%.

## 8. Tối ưu hóa Lưu Trữ (Storage Management)
- Hệ thống tự động tạo các thư mục lưu trữ theo ngày (định dạng `YYYY-MM-DD`) bên trong thư mục `/tmp` (để hứng luồng tải stream) và `/downloads/` (để lưu trữ chính thức).
- Tính năng này giúp hạn chế tình trạng quá tải (bottleneck) số lượng file trong một thư mục duy nhất, dễ dàng quản lý, backup và dọn dẹp các bản ghi cũ theo cronjob. API được thiết lập dùng Dynamic Routing (`/download/<path:filename>`) để phục vụ file xuyên suốt qua các cấp thư mục con.
