import os
import asyncio
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials.json')

def upload_to_drive_sync(file_path: str, file_name: str, folder_id: str) -> str:
    """Uploads a file to Google Drive and returns the webViewLink."""
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError("Không tìm thấy file credentials.json")
        
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        
    service = build('drive', 'v3', credentials=creds)
    
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='application/pdf', resumable=True)
    
    # Upload the file
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()
    
    # Make the file viewable by anyone with the link
    service.permissions().create(
        fileId=file.get('id'),
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()
    
    return file.get('webViewLink')

async def upload_to_drive_async(file_path: str, file_name: str, folder_id: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, upload_to_drive_sync, file_path, file_name, folder_id)
