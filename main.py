import asyncio  # For running asynchronous scraping tasks
import os  # Used to access environment variables and filesystem
import json  # For handling credentials in JSON format
import pandas as pd  # Used for handling data and saving Excel files
from datetime import datetime, timedelta  # To calculate "yesterday"
from oogoo_used import OogooUsed  # Scraper class for used cars
from oogoo_certified import OogooCertified  # Scraper class for certified cars
from SavingOnDrive import SavingOnDrive  # Class for uploading files to Google Drive

# Ensure that the required environment variable is set for Google Drive credentials
if 'OGO_GCLOUD_KEY_JSON' not in os.environ:
    raise EnvironmentError("OGO_GCLOUD_KEY_JSON not found.")

class ScraperMain:
    def __init__(self):
        # Set the date string for yesterday (used for filtering and folder naming)
        self.yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # Lists to store filtered data for used and certified cars
        self.data_used = []
        self.data_certified = []

        # Semaphore to limit concurrent browser sessions (max 5 at once)
        self.semaphore = asyncio.Semaphore(5)

    async def scrape_used(self):
        # Start scraping used car listings
        print("Scraping used cars...")
        for page in range(1, 3):  # Loop through pages 1 and 2
            url = f"https://oogoocar.com/ar/explore/used/all/all/all/all/list/0/basic?page={page}"
            scraper = OogooUsed(url)  # Instantiate the used car scraper
            try:
                # Limit concurrent access using semaphore
                async with self.semaphore:
                    cars = await scraper.get_car_details()
                self.filter_data(cars, "used")  # Filter by yesterday's date
            except Exception as e:
                print(f"Error scraping used cars on page {page}: {e}")

    async def scrape_certified(self):
        # Start scraping certified car listings
        print("Scraping certified cars...")
        for page in range(1, 3):  # Loop through pages 1 and 2
            url = f"https://oogoocar.com/ar/explore/featured/all/all/certified/all/list/0/basic?page={page}"
            scraper = OogooCertified(url)  # Instantiate the certified car scraper
            try:
                async with self.semaphore:
                    cars = await scraper.get_car_details()
                self.filter_data(cars, "certified")
            except Exception as e:
                print(f"Error scraping certified cars on page {page}: {e}")

    def filter_data(self, cars, category):
        # Filter scraped cars to include only those published "yesterday"
        for car in cars:
            date_published = car.get("date_published", "").split()[0]  # Extract just the date part
            if date_published == self.yesterday:
                if category == "used":
                    self.data_used.append(car)
                else:
                    self.data_certified.append(car)

    def save_to_excel(self):
        # Save filtered car data into Excel files
        print("Saving data to Excel...")
        files = []

        # Save used car data if available
        if self.data_used:
            files.append(self.create_excel("Used", self.data_used))

        # Save certified car data if available
        if self.data_certified:
            files.append(self.create_excel("Certified", self.data_certified))

        if not files:
            print("No data to save.")
        return files  # Return list of saved Excel file names

    def create_excel(self, name, data):
        # Create an Excel file for a given dataset
        file_name = f"{name}.xlsx"
        df = pd.DataFrame(data)  # Convert list of dicts to DataFrame
        with pd.ExcelWriter(file_name, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=name.lower(), index=False)  # Save to Excel
        print(f"Saved {file_name}")
        return file_name
    
    def upload_to_drive(self, files):
        # Upload the generated Excel files to Google Drive
        print("Uploading to Google Drive...")
    
        # Load credentials from environment variable
        credentials_json = os.environ.get('OGO_GCLOUD_KEY_JSON')
        if not credentials_json:
            raise EnvironmentError("OGO_GCLOUD_KEY_JSON environment variable not found.")
    
        # Debug print to show that credentials are loaded correctly
        print(f"Loaded OGO_GCLOUD_KEY_JSON: {len(credentials_json)} characters")

        credentials_dict = json.loads(credentials_json)  # Parse JSON string to dictionary

        print(f"Excel files: {files}")

        # Initialize Google Drive uploader
        drive_saver = SavingOnDrive(credentials_dict)
        drive_saver.authenticate()

        # Define the parent folder and subfolder name for organizing uploads
        folder_name = self.yesterday
        parent_folder_id = '11MyzXZ_I4Sh7hDdk9eH0sABdtVt5tUwY'  # Predefined parent folder
    
        # Create a dated subfolder
        folder_id = drive_saver.create_folder(folder_name, parent_folder_id)
        print(f"Created folder '{folder_name}' with ID: {folder_id}")
    
        # Upload each file to the folder
        for file_name in files:
            drive_saver.upload_file(file_name, folder_id)
            print(f"Uploaded {file_name} to Google Drive.")

        print("Files uploaded successfully.")

    async def run(self):
        # Orchestrate the entire workflow
        await asyncio.gather(self.scrape_used(), self.scrape_certified())  # Run both scraping tasks concurrently
        files = self.save_to_excel()  # Save filtered results to Excel
        print(f"Files to upload: {files}")
        if files:
            self.upload_to_drive(files)  # Upload to Google Drive if files exist
            print("Data uploaded.")
        else:
            print("No data to upload.")


if __name__ == "__main__":
    # Entry point: create an instance and run the full workflow
    scraper = ScraperMain()
    asyncio.run(scraper.run())

