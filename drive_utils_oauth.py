# drive_utils_oauth.py
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import os
import io

SCOPES = ['https://www.googleapis.com/auth/drive.file']
TOKEN_FILE = 'token.json'
CREDENTIAL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'credentials.json'))
FILENAME = 'portfolio_data.json'

def get_authenticated_service():
    if os.path.exists(TOKEN_FILE):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIAL_PATH, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def upload_file(service, filepath=FILENAME):
    file_metadata = {'name': FILENAME}
    media = MediaFileUpload(filepath, resumable=True)
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    return file.get('id')

def download_file(service, save_as=FILENAME):
    results = service.files().list(q=f"name='{FILENAME}'", fields="files(id)").execute()
    items = results.get('files', [])
    if not items:
        return False
    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(save_as, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    return True

print(f"🔍 credentials 경로: {CREDENTIAL_PATH}")
print(f"📁 파일 존재 여부: {os.path.exists(CREDENTIAL_PATH)}")