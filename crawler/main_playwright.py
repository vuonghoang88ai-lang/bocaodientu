import asyncio
import os
import aiohttp
from playwright.async_api import async_playwright
from database import init_db, Announcement

URL = 'https://bocaodientu.dkkd.gov.vn/egazette/Forms/Egazette/DefaultAnnouncements.aspx'
API_KEY = "e55595e6f7d990ed4309c188a7074caa"
SITE_KEY = "6LewYU4UAAAAAD9dQ51Cj_A_1uHLOXw9wJIxi9x0" # Đã cập nhật Sitekey thật của trang web

async def solve_recaptcha(api_key: str, website_url: str, site_key: str, max_retries: int = 60) -> str:
    create_task_url = "https://api.2captcha.com/createTask"
    get_result_url = "https://api.2captcha.com/getTaskResult"
    
    create_task_payload = {
        "clientKey": api_key,
        "task": {
            "type": "RecaptchaV3TaskProxyless",
            "websiteURL": website_url,
            "websiteKey": site_key,
            "minScore": 0.3
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(create_task_url, json=create_task_payload) as response:
                create_data = await response.json(content_type=None)
                if create_data.get("errorId") != 0:
                    print(f"Lỗi khi tạo task: {create_data}")
                    return None
                task_id = create_data.get("taskId")

            for attempt in range(max_retries):
                await asyncio.sleep(3)
                async with session.post(get_result_url, json={"clientKey": api_key, "taskId": task_id}) as result_res:
                    result_data = await result_res.json(content_type=None)
                    if result_data.get("status") == "ready":
                        return result_data.get("solution", {}).get("gRecaptchaResponse")
            print(f"Lỗi: Hết thời gian chờ 2Captcha sau {max_retries} lần thử.")
    except Exception as e:
        print(f"Lỗi Captcha: {e}")
    return None

async def process_pdf_download(page, download_selector, company_name):
    # Lấy token
    print("[*] Đang giải mã Captcha...")
    token = await solve_recaptcha(API_KEY, URL, SITE_KEY)
    if not token:
        print("[-] Giải mã Captcha thất bại")
        return None

    # Tiêm token
    await page.evaluate(f"""(token) => {{
        const input = document.getElementById('g-recaptcha-response');
        if (input) {{
            input.value = token;
            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
    }}""", token)
    
    print("[*] Đã tiêm token. Chờ tải file...")
    
    # Bấm nút và bắt luồng tải về
    try:
        async with page.expect_download(timeout=30000) as download_info:
            await page.click(download_selector)
        
        download = await download_info.value
        save_dir = os.path.join(os.getcwd(), 'downloads')
        os.makedirs(save_dir, exist_ok=True)
        
        safe_name = "".join([c for c in company_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        save_path = os.path.join(save_dir, f"{safe_name}.pdf")
        
        await download.save_as(save_path)
        print(f"[+] Đã lưu PDF tại: {save_path}")
        return save_path
    except Exception as e:
        print(f"[-] Lỗi tải PDF: {e}")
        return None

async def crawl_playwright(max_pages=2):
    print("Initializing Database...")
    db_session = init_db()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-setuid-sandbox'
            ]
        ) # Chạy ẩn và tối ưu cho Docker server
        context = await browser.new_context(accept_downloads=True, ignore_https_errors=True)
        page = await context.new_page()
        
        try:
            print(f"Bắt đầu crawl từ: {URL}")
            await page.goto(URL)
            
            # Sang tab Đăng ký thay đổi (Tuỳ chỉnh theo UI của web)
            await page.click("a[href*='ctl00$C$RptProdGroups$ctl01$LnkActiveAnnType']")
            await page.wait_for_load_state('networkidle')
            
            for p_idx in range(1, max_pages + 1):
                print(f"=== Đang xử lý trang {p_idx} ===")
                
                # Tìm các dòng dữ liệu
                rows = await page.locator("table#ctl00_C_CtlList tr").all()
                for row in rows[1:]: # Bỏ qua header
                    # Phân tích thông tin text
                    cells = await row.locator("td").all()
                    if len(cells) < 4: continue
                    
                    time_str = await cells[0].inner_text()
                    company_raw = await cells[1].inner_text()
                    location = await cells[2].inner_text()
                    ann_type = await cells[3].inner_text()
                    
                    # Bộ chọn mới cho nút "Xem" chi tiết dựa trên phân tích HTML thực tế
                    detail_btn = row.locator("a[id$='_CmdView']") 
                    if await detail_btn.count() > 0:
                        await detail_btn.first.click()
                        await page.wait_for_load_state('networkidle')
                        
                        # Gọi hàm xử lý Captcha và PDF trên giao diện tải về
                        pdf_selector = "input#ctl00_C_btnDownload" # Nút tải thực tế
                        pdf_path = await process_pdf_download(page, pdf_selector, company_raw)
                        
                        # Trở lại màn hình danh sách (nếu tải xong web điều hướng hoặc cần bấm back)
                        # await page.go_back()
                    else:
                        pdf_path = None
                    
                    # Lưu DB
                    db_ann = Announcement(
                        published_time=time_str.strip(),
                        company_name=company_raw.strip(),
                        location=location.strip(),
                        announcement_type=ann_type.strip(),
                        pdf_path=pdf_path
                    )
                    db_session.add(db_ann)
                    db_session.commit()
                
                # Next page logic ở đây (bấm phân trang ctl00_C_CtlList)
                # ...
                
        finally:
            db_session.close()
            await browser.close()

import time

async def main_loop():
    while True:
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Bắt đầu chu kỳ cào dữ liệu mới...")
        try:
            await crawl_playwright()
        except Exception as e:
            print(f"[-] Lỗi trong quá trình cào dữ liệu: {e}")
        
        print("[*] Hoàn thành chu kỳ. Đợi 3 phút (180s) cho chu kỳ tiếp theo...")
        await asyncio.sleep(180)

if __name__ == "__main__":
    asyncio.run(main_loop())
