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

async def download_pdf_auto(ma_so_dn: str, announcement_type_vi: str, download_dir: str = "./downloads"):
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        
    INPUT_MA_SO_DN_SELECTOR = "input[id$='ENT_GDT_CODEFld']"
    TABLE_RESULT_SELECTOR = "table#ctl00_C_CtlList, table.table" 
    PDF_DOWNLOAD_BUTTON_SELECTOR = "input#ctl00_C_btnDownload, input[type='image'][src*='pdf'], a[id*='CmdView']" 
    
    print(f"[*] Bắt đầu tiến trình tải PDF (Tự động 2Captcha) cho MST: {ma_so_dn}, Loại: {announcement_type_vi}", flush=True)
    
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
            pdf_btn = page.locator("input[id$='_LnkGetPDFActive']").first
            
            # Kiểm tra xem có nút PDF không
            if await pdf_btn.count() == 0:
                # Nếu không có nút trực tiếp, thử ấn nút Xem chi tiết (nếu tồn tại luồng cũ)
                detail_btn = page.locator("a[id$='_CmdView']").first
                if await detail_btn.count() > 0:
                    await detail_btn.click()
                    await page.wait_for_load_state('networkidle')
                    pdf_btn = page.locator("input#ctl00_C_btnDownload, input[type='image'][src*='pdf']").first
            
            # Chờ download hoàn tất với Playwright's native download manager
            async with page.expect_download(timeout=60000) as download_info:
                await pdf_btn.click()
                
            download = await download_info.value
            
            file_name = f"{ma_so_dn}.pdf"
            file_path = os.path.join(download_dir, file_name)
            
            print(f"[*] Đang ghi file xuống {file_path} bằng Playwright native...", flush=True)
            # Lưu file an toàn
            await download.save_as(file_path)
            
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                print("[-] Không tìm thấy file hoặc file bị 0 byte từ volume share", flush=True)
                return {"success": False, "error": "File bị 0 byte hoặc không tải được"}
            
            print("[+] Tải file thành công!", flush=True)
            
            await context.close()
            await browser.close()
            
            return {
                "success": True,
                "ma_so_dn": ma_so_dn,
                "file_path": file_path,
                "message": "Download success"
            } "error": "File bị 0 byte hoặc không tải được"}

            
            print("[+] Tải file thành công!", flush=True)
            
            await context.close()
            await browser.close()
            
            return {
                "success": True,
                "ma_so_dn": ma_so_dn,
                "file_path": file_path,
                "message": "Download success"
            }
            
    except PlaywrightTimeoutError as e:
        return {"success": False, "error": f"Hết thời gian chờ (Hoặc không tìm thấy kết quả)."}
    except Exception as e:
        return {"success": False, "error": f"Lỗi không xác định: {str(e)}"}
