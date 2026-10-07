import asyncio
import os
import socket
import aiohttp
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

URL = "https://bocaodientu.dkkd.gov.vn/egazette/Forms/Egazette/ANNOUNCEMENTSListingInsUpd.aspx"
API_KEY = "df7a0c1bec612e0cecca020e35ffaeb2"
SITE_KEY = "6LewYU4UAAAAAD9dQ51Cj_A_1uHLOXw9wJIxi9x0"

async def solve_recaptcha(api_key: str, website_url: str, site_key: str, max_retries: int = 60) -> str:
    create_task_url = "https://api.2captcha.com/createTask"
    get_result_url = "https://api.2captcha.com/getTaskResult"
    
    create_task_payload = {
        "clientKey": api_key,
        "task": {
            "type": "RecaptchaV2EnterpriseTaskProxyless",
            "websiteURL": website_url,
            "websiteKey": site_key
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(create_task_url, json=create_task_payload) as response:
                create_data = await response.json(content_type=None)
                if create_data.get("errorId") != 0:
                    print(f"Lỗi khi tạo task: {create_data}", flush=True)
                    return None
                task_id = create_data.get("taskId")

            for attempt in range(max_retries):
                await asyncio.sleep(3)
                async with session.post(get_result_url, json={"clientKey": api_key, "taskId": task_id}) as result_res:
                    result_data = await result_res.json(content_type=None)
                    if result_data.get("status") == "ready":
                        return result_data.get("solution", {}).get("gRecaptchaResponse")
            print(f"Lỗi: Hết thời gian chờ 2Captcha sau {max_retries} lần thử.", flush=True)
    except Exception as e:
        print(f"Lỗi Captcha exception: {e}", flush=True)
    return None

async def download_pdf_auto(ma_so_dn: str, announcement_type_vi: str, published_time: str, download_dir: str = "./downloads"):
    import datetime
    import glob
    
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    safe_published_time = published_time.replace("/", "-").replace(":", "-").replace(" ", "_")
    
    # 1. Logic kiểm tra file đã tồn tại: 
    # Tìm tất cả file bắt đầu bằng mã số doanh nghiệp và thời gian đăng
    existing_files = glob.glob(os.path.join(download_dir, '**', f"{ma_so_dn}_{safe_published_time}*.pdf"), recursive=True)
    for existing_file in existing_files:
        if os.path.isfile(existing_file) and os.path.getsize(existing_file) > 0:
            print(f"[*] File cho MST {ma_so_dn} lúc {published_time} đã tồn tại tại {existing_file}. Bỏ qua tải lại.", flush=True)
            # Tạo đường dẫn tương đối để API backend có thể mapping
            rel_path = os.path.relpath(existing_file, download_dir)
            rel_path = rel_path.replace("\\", "/")
            return {"success": True, "ma_so_dn": ma_so_dn, "file_path": existing_file, "rel_path": rel_path, "message": "File already exists"}
            
    # 2. Logic tạo thư mục theo ngày
    daily_download_dir = os.path.join(download_dir, today_str)
    if not os.path.exists(daily_download_dir):
        os.makedirs(daily_download_dir)
        
    daily_tmp_dir = os.path.join("/tmp", today_str)
    if not os.path.exists(daily_tmp_dir):
        os.makedirs(daily_tmp_dir)
        
    INPUT_MA_SO_DN_SELECTOR = "input[id$='ENT_GDT_CODEFld']"
    TABLE_RESULT_SELECTOR = "table#ctl00_C_CtlList, table.table" 
    
    print(f"[*] Bắt đầu tiến trình tải PDF cho MST: {ma_so_dn}, Thời gian: {published_time}, Loại: {announcement_type_vi}", flush=True)
    
    type_map = {
        "Đăng ký mới": "NEW",
        "Đăng ký thay đổi": "AMEND",
        "Giải thể": "CORP",
        "HTX, LHHTX, các ĐVTT và tổ hợp tác": "COOP",
        "Loại khác": "OTHER",
        "Thông báo thay đổi": "CHANTC",
        "Vi phạm/ Thu hồi": "REVOKE"
    }
    mapped_type = type_map.get(announcement_type_vi, "AMEND")
    
    try:
        async with async_playwright() as p:
            # Resolve browser to IP to avoid Chromium's Host header restrictions
            browser_ip = socket.gethostbyname('browser')
            browser = await p.chromium.connect_over_cdp(f"http://{browser_ip}:9223")
            
            context = await browser.new_context(
                accept_downloads=True,
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()
            
            # Đã gỡ bỏ CDP setDownloadBehavior để tránh xung đột với Playwright's native download manager
            
            await page.goto(URL, wait_until="domcontentloaded")
            await page.wait_for_selector("select[id$='ANNOUNCEMENT_TYPE_IDFilterFld']", state="visible", timeout=30000)
            
            # 1. Chọn Loại công bố
            current_type = await page.evaluate("document.querySelector('select[id$=\"ANNOUNCEMENT_TYPE_IDFilterFld\"]').value")
            if current_type != mapped_type:
                async with page.expect_navigation(timeout=60000):
                    await page.select_option("select[id$='ANNOUNCEMENT_TYPE_IDFilterFld']", mapped_type)
            
            # Đợi load xong form mới
            await page.wait_for_selector(INPUT_MA_SO_DN_SELECTOR, state="visible", timeout=30000)
            
            # 2. Điền mã số DN (như ảnh 2)
            await page.fill(INPUT_MA_SO_DN_SELECTOR, ma_so_dn)
            
            # 3. Cập nhật thời gian động: lấy trước 5 ngày và sau 5 ngày so với thời điểm hiện tại
            import datetime
            today = datetime.datetime.now()
            five_days_ago = today - datetime.timedelta(days=5)
            five_days_later = today + datetime.timedelta(days=5)
            from_date = five_days_ago.strftime("%d/%m/%Y")
            to_date = five_days_later.strftime("%d/%m/%Y")
            
            # Điền vào input và kích hoạt các event để datepicker nhận giá trị
            await page.fill("input[id$='PUBLISH_DATEFilterFldFrom']", from_date)
            await page.evaluate(f"document.querySelector('input[id$=\"PUBLISH_DATEFilterFldFrom\"]').dispatchEvent(new Event('change', {{ bubbles: true }}));")
            
            await page.fill("input[id$='PUBLISH_DATEFilterFldTo']", to_date)
            await page.evaluate(f"document.querySelector('input[id$=\"PUBLISH_DATEFilterFldTo\"]').dispatchEvent(new Event('change', {{ bubbles: true }}));")
            
            # --- AUTO CAPTCHA SOLVING ---
            print("[*] Đang giải Captcha tự động...", flush=True)
            token = await solve_recaptcha(API_KEY, URL, SITE_KEY)
            
            if not token:
                return {"success": False, "error": "Không thể giải mã Captcha (2Captcha API trả về rỗng)"}
                
            await page.evaluate(f"""(token) => {{
                const input = document.getElementById('g-recaptcha-response');
                if (input) {{
                    input.value = token;
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}""", token)
            
            print("[*] Đã tiêm token, đang chờ trang nhận diện Captcha và điền đủ trường...", flush=True)
            
            # Vòng lặp chờ đủ các trường và captcha. Tự động điền lại nếu trang bị reset.
            for _ in range(15): # Chờ tối đa 15s
                mst_val = await page.input_value("input[id$='ENT_GDT_CODEFld']")
                tu_ngay_val = await page.input_value("input[id$='PUBLISH_DATEFilterFldFrom']")
                den_ngay_val = await page.input_value("input[id$='PUBLISH_DATEFilterFldTo']")
                loai_val = await page.evaluate("document.querySelector('select[id$=\"ANNOUNCEMENT_TYPE_IDFilterFld\"]').value")
                token_val = await page.evaluate("document.getElementById('g-recaptcha-response').value")
                
                all_correct = True
                
                # Kiểm tra và điền lại nếu mất dữ liệu
                if loai_val != mapped_type:
                    await page.evaluate(f"document.querySelector('select[id$=\"ANNOUNCEMENT_TYPE_IDFilterFld\"]').value = '{mapped_type}';")
                    all_correct = False
                if mst_val != ma_so_dn:
                    await page.fill("input[id$='ENT_GDT_CODEFld']", ma_so_dn)
                    all_correct = False
                if tu_ngay_val != from_date:
                    await page.fill("input[id$='PUBLISH_DATEFilterFldFrom']", from_date)
                    await page.evaluate(f"document.querySelector('input[id$=\"PUBLISH_DATEFilterFldFrom\"]').dispatchEvent(new Event('change', {{ bubbles: true }}));")
                    all_correct = False
                if den_ngay_val != to_date:
                    await page.fill("input[id$='PUBLISH_DATEFilterFldTo']", to_date)
                    await page.evaluate(f"document.querySelector('input[id$=\"PUBLISH_DATEFilterFldTo\"]').dispatchEvent(new Event('change', {{ bubbles: true }}));")
                    all_correct = False
                if not token_val:
                    # Tiêm lại token nếu mất
                    await page.evaluate(f"""(token) => {{
                        const input = document.getElementById('g-recaptcha-response');
                        if (input) {{
                            input.value = token;
                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    }}""", token)
                    all_correct = False
                    
                if all_correct:
                    break
                await asyncio.sleep(1)
            
            # Đã gỡ bỏ lệnh ghi đè window.ValidateFilter theo yêu cầu
            # Script sẽ tự động chạy qua hàm ValidateFilter() nguyên bản của trang web.
            
            # Bấm nút Tìm kiếm (BtnFilter) và đợi trang tải lại
            async with page.expect_navigation(timeout=60000):
                await page.click("input[id$='BtnFilter']")
            
            await page.wait_for_selector(TABLE_RESULT_SELECTOR, state="visible", timeout=60000)
            
            print("[*] Đã tìm thấy kết quả! Tiến hành tải PDF trực tiếp từ danh sách...", flush=True)
            
            # Selector mới chuẩn xác theo nút PDF ở danh sách kết quả
            print(f"[*] Đã tìm thấy kết quả! Tìm đúng hàng có thời gian: {published_time}...", flush=True)
            
            # Selector cho các nút PDF chỉ trong hàng tương ứng
            row_locator = page.locator(f"table#ctl00_C_CtlList tr:has(td:has-text('{published_time}'))")
            pdf_btns = row_locator.locator("input[id$='_LnkGetPDFActive']")
            count = await pdf_btns.count()
            
            for i in range(count):
                try:
                    # Set download behavior to save directly to shared volume
                    client = await page.context.new_cdp_session(page)
                    await client.send('Page.setDownloadBehavior', {
                        'behavior': 'allow',
                        'downloadPath': '/config/Downloads'
                    })
                    
                    before_files = set(os.listdir(download_dir))
                    
                    await pdf_btns.nth(i).click()
                    
                    # Wait for new file to appear
                    new_file = None
                    for _ in range(60):
                        await asyncio.sleep(1)
                        current_files = set(os.listdir(download_dir))
                        new_files = current_files - before_files
                        finished_files = [f for f in new_files if not f.endswith('.crdownload')]
                        if finished_files:
                            new_file = finished_files[0]
                            break
                            
                    if new_file:
                        file_name = f"{ma_so_dn}_{safe_published_time}_{i}.pdf"
                        file_path = os.path.join(daily_download_dir, file_name)
                        
                        import shutil
                        downloaded_path = os.path.join(download_dir, new_file)
                        if os.path.exists(downloaded_path) and os.path.getsize(downloaded_path) > 0:
                            shutil.move(downloaded_path, file_path)
                            await context.close()
                            await browser.close()
                            rel_path = os.path.relpath(file_path, download_dir).replace("\\", "/")
                            return {"success": True, "ma_so_dn": ma_so_dn, "file_path": file_path, "rel_path": rel_path, "message": "Download success"}
                        else:
                            print(f"[-] Nút thứ {i+1} trả về file 0 byte, thử nút tiếp theo...", flush=True)
                            if os.path.exists(downloaded_path):
                                os.remove(downloaded_path)
                    else:
                        print(f"[-] Nút thứ {i+1} không sinh ra file tải về, thử nút tiếp theo...", flush=True)
                except Exception as e:
                    print(f"[-] Nút thứ {i+1} lỗi: {e}, thử nút tiếp theo...", flush=True)
                    continue

            # Fallback: xem chi tiết nếu tất cả nút ở ngoài đều lỗi hoặc không có. Thử tìm tất cả các thẻ 'a' hoặc '_CmdView'
            detail_btns = row_locator.locator("a, [id$='_CmdView']")
            count_detail = await detail_btns.count()
            if count_detail > 0:
                for i in range(count_detail):
                    try:
                        await detail_btns.nth(i).click()
                        await page.wait_for_load_state('networkidle')
                        pdf_btn = page.locator("input#ctl00_C_btnDownload, input[type='image'][src*='pdf']").first
                        if await pdf_btn.count() > 0:
                            async with page.expect_download(timeout=60000) as download_info:
                                await pdf_btn.click()
                            download = await download_info.value
                            file_name = f"{ma_so_dn}_{safe_published_time}_detail_{i}.pdf"
                            file_path = os.path.join(daily_download_dir, file_name)
                            temp_file_path = os.path.join(daily_tmp_dir, f"temp_{file_name}")
                            await download.save_as(temp_file_path)
                            if os.path.exists(temp_file_path) and os.path.getsize(temp_file_path) > 0:
                                import shutil
                                shutil.move(temp_file_path, file_path)
                                await context.close()
                                await browser.close()
                                rel_path = os.path.relpath(file_path, download_dir).replace("\\", "/")
                                return {"success": True, "ma_so_dn": ma_so_dn, "file_path": file_path, "rel_path": rel_path, "message": "Download success"}
                            else:
                                print(f"[-] Detail thứ {i+1} trả về file 0 byte, thử chi tiết tiếp theo...", flush=True)
                        await page.go_back()
                        await page.wait_for_load_state('networkidle')
                    except Exception as e:
                        print(f"[-] Detail thứ {i+1} lỗi: {e}, thử nút tiếp theo...", flush=True)
                        try:
                            await page.go_back()
                            await page.wait_for_load_state('networkidle')
                        except:
                            pass
                        continue
            
            return {"success": False, "error": "File gốc trên máy chủ của Cổng Thông Tin bị lỗi (0 byte) và không có bản ghi dự phòng hợp lệ."}
            
    except PlaywrightTimeoutError as e:
        return {"success": False, "error": f"Hết thời gian chờ (Hoặc không tìm thấy kết quả)."}
    except Exception as e:
        return {"success": False, "error": f"Lỗi không xác định: {str(e)}"}
