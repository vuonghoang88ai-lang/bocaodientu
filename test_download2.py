import asyncio
import traceback
from pdf_downloader import download_pdf_auto

async def main():
    try:
        res = await download_pdf_auto("0111484476", "Thay đổi nội dung ĐKDN", "./downloads")
        print("Result:", res)
    except Exception as e:
        print("Exception:")
        traceback.print_exc()

asyncio.run(main())
