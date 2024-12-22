import asyncio
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from oogoo_used import OogooUsed
from oogoo_certified import OogooCertified
from SavingOnDrive import SavingOnDrive

# Check if the environment variable is set
if 'OOGOO_GCLOUD_KEY_JSON' not in os.environ:
    raise EnvironmentError("OOGOO_GCLOUD_KEY_JSON not found.")

class ScraperMain:
    def __init__(self):
        self.yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self.data_used = []
        self.data_certified = []
        self.semaphore = asyncio.Semaphore(5)  # Limit concurrency

    async def scrape_used(self):
        print("Scraping used cars...")
        for page in range(1, 3):
            url = f"https://oogoocar.com/ar/explore/used/all/all/all/all/list/0/basic?page={page}"
            scraper = OogooUsed(url)
            try:
                async with self.semaphore:
                    cars = await scraper.get_car_details()
                self.filter_data(cars, "used")
            except Exception as e:
                print(f"Error scraping used cars on page {page}: {e}")

    async def scrape_certified(self):
        print("Scraping certified cars...")
        for page in range(1, 3):
            url = f"https://oogoocar.com/ar/explore/featured/all/all/certified/all/list/0/basic?page={page}"
            scraper = OogooCertified(url)
            try:
                async with self.semaphore:
                    cars = await scraper.get_car_details()
                self.filter_data(cars, "certified")
            except Exception as e:
                print(f"Error scraping certified cars on page {page}: {e}")

    def filter_data(self, cars, category):
        for car in cars:
            date_published = car.get("date_published", "").split()[0]
            if date_published == self.yesterday:
                if category == "used":
                    self.data_used.append(car)
                else:
                    self.data_certified.append(car)

    def save_to_excel(self):
        print("Saving data to Excel...")
        files = []
        if self.data_used:
            files.append(self.create_excel("Used", self.data_used))
        if self.data_certified:
            files.append(self.create_excel("Certified", self.data_certified))

        if not files:
            print("No data to save.")
        return files

    def create_excel(self, name, data):
        file_name = f"{name}.xlsx"
        df = pd.DataFrame(data)
        with pd.ExcelWriter(file_name, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=name.lower(), index=False)
        print(f"Saved {file_name}")
        return file_name

    def upload_to_drive(self, files):
        print("Uploading to Google Drive...")
        credentials_json = os.environ.get('OOGOO_GCLOUD_KEY_JSON')
        if not credentials_json:
            raise EnvironmentError("OOGOO_GCLOUD_KEY_JSON not found.")
        credentials_dict = json.loads(credentials_json)
    
        # Use the SavingOnDrive class to upload the files to Google Drive
        drive_saver = SavingOnDrive(credentials_dict)
        drive_saver.authenticate()
    
        # Folder name based on the date (yesterday)
        # folder_name = self.yesterday
        # folder_id = drive_saver.create_folder(folder_name)  # Create folder without parent folder ID (it's handled in SavingOnDrive)

        # Upload the files to the created folder
        # for file_name in files:
        #     drive_saver.upload_file(file_name, folder_id)
        
        print(f"Files uploaded successfully to folder '{folder_name}' on Google Drive.")


    async def run(self):
        await asyncio.gather(self.scrape_used(), self.scrape_certified())
        files = self.save_to_excel()
        if files:
            self.upload_to_drive(files)
            print("data to upload.")
        else:
            print("No data to upload.")

if __name__ == "__main__":
    scraper = ScraperMain()
    asyncio.run(scraper.run())
