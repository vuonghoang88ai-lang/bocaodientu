import asyncio
from pdf_downloader import download_pdf_auto

async def main():
    res = await download_pdf_auto("0111484476", "Thay đổi nội dung ĐKDN", "./downloads")
    print("Result:", res)

asyncio.run(main())
