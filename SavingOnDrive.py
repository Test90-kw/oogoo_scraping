import os  # Provides functions to interact with the operating system (e.g., environment variables)
import json  # Handles JSON encoding and decoding (used for credentials)
from google.oauth2.service_account import Credentials  # Auth module for using service account credentials
from googleapiclient.discovery import build  # Used to construct a Google Drive API client
from googleapiclient.http import MediaFileUpload  # Handles file uploads to Google Drive
from datetime import datetime, timedelta  # Used for time calculations and formatting (e.g., folder names)


class SavingOnDrive:
    def __init__(self, credentials_dict):
        # Initialize the class with service account credentials and scope
        self.credentials_dict = credentials_dict
        self.scopes = ['https://www.googleapis.com/auth/drive']  # Full access to Google Drive
        self.service = None  # Will be initialized during authentication

    def authenticate(self):
        # Authenticate and create a Drive API service client
        creds = Credentials.from_service_account_info(self.credentials_dict, scopes=self.scopes)
        self.service = build('drive', 'v3', credentials=creds)  # Connect to Drive API v3

    def create_folder(self, folder_name, parent_folder_id=None):
        # Create a new folder in Drive under an optional parent folder
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'  # Specify folder MIME type
        }
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]  # Place inside specified parent folder

        # Create the folder and return its unique Drive ID
        folder = self.service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

    def upload_file(self, file_name, folder_id):
        # Upload a local file to a specific folder in Drive
        file_metadata = {'name': file_name, 'parents': [folder_id]}  # File name and destination
        media = MediaFileUpload(file_name, resumable=True)  # Prepare file for upload
        file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')  # Return uploaded file ID

    def save_files(self, files):
        # Upload multiple files to a folder named by yesterday's date
        parent_folder_id = '1tWEWGQzsJhAO-VzdAI2arYey6H1EwMjV'  # Static folder ID where subfolders are created

        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')  # Format folder name as YYYY-MM-DD
        folder_id = self.create_folder(yesterday, parent_folder_id)  # Create dated subfolder under parent

        for file_name in files:
            self.upload_file(file_name, folder_id)  # Upload each file to the created folder

        print(f"Files uploaded successfully to folder '{yesterday}' on Google Drive.")  # Confirmation message

