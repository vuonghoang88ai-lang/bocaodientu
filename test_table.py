import asyncio
from playwright.async_api import async_playwright
import socket

async def main():
    async with async_playwright() as p:
        browser_ip = socket.gethostbyname('browser')
        browser = await p.chromium.connect_over_cdp(f"http://{browser_ip}:9223")
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        
        await page.goto("https://bocaodientu.dkkd.gov.vn/egazette/Forms/Egazette/ANNOUNCEMENTSListingInsUpd.aspx")
        await page.select_option("select[id$='ANNOUNCEMENT_TYPE_IDFilterFld']", "AMEND")
        await page.fill("input[id$='ENT_GDT_CODEFld']", "0111484476")
        
        # Tiêm token (cần thay bằng token thật nếu web chặn, nhưng web này có khi cho click tìm mà chưa chặn captcha list? ko, cần captcha)
        # Thay vì giải captcha, ta sẽ để code tự giải captcha như trong file gốc
        pass
