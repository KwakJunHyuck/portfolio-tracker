from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io
import os
import streamlit as st
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SERVICE_ACCOUNT_FILE = 'data/service_account.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_NAME = '포트폴리오_백업'

def get_drive_service():
    try:
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        st.error(f"⚠️ Google Drive 인증 실패: {e}")
        raise

def get_folder_id(service, folder_name):
    results = service.files().list(
        q=f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false",
        spaces='drive',
        fields='files(id, name)').execute()
    folders = results.get('files', [])
    if folders:
        return folders[0]['id']
    return None

def upload_file(service, folder_id, local_path, drive_filename):
    file_metadata = {
        'name': drive_filename,
        'parents': [folder_id]
    }
    media = MediaFileUpload(local_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

def download_file(service, folder_id, drive_filename, save_path):
    query = f"'{folder_id}' in parents and name='{drive_filename}' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    if not items:
        return False
    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(save_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return True

def get_authenticated_service():
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    creds = None

    # 토큰이 존재하면 불러오기
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # 토큰이 없거나 만료되었으면 새로 인증
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # 인증 완료 후 저장
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    # 인증된 서비스 반환
    return build("drive", "v3", credentials=creds)