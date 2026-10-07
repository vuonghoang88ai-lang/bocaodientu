import asyncio
from playwright.async_api import async_playwright
import socket

async def main():
    async with async_playwright() as p:
        browser_ip = socket.gethostbyname('browser')
        browser = await p.chromium.connect_over_cdp(f"http://{browser_ip}:9223")
        page = await browser.new_page()
        await page.goto("https://bocaodientu.dkkd.gov.vn/egazette/Forms/Egazette/ANNOUNCEMENTSListingInsUpd.aspx")
        options = await page.evaluate("""
            Array.from(document.querySelectorAll('select[id$="ANNOUNCEMENT_TYPE_IDFilterFld"] option')).map(o => ({text: o.innerText.trim(), value: o.value}))
        """)
        print(options)
        await browser.close()

asyncio.run(main())
