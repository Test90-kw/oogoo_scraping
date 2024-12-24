import logging
import asyncio
from playwright.async_api import async_playwright
import nest_asyncio
import pandas as pd
from datetime import datetime, timedelta
import json
from SavingOnDrive import SavingOnDrive
import os

# Allow nested event loops
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('showrooms_scraper.log'),
        logging.StreamHandler()
    ]
)

class OogooShowroomScraping:
    def __init__(self, url, retries=3):
        self.url = url
        self.retries = retries
        self.cars = []

    async def get_car_details(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            page.set_default_navigation_timeout(3000000)
            page.set_default_timeout(3000000)

            for attempt in range(self.retries):
                try:
                    await page.goto(self.url, wait_until="domcontentloaded")
                    await page.wait_for_selector('.list-item-car.item-logo', timeout=3000000)

                    car_cards = await page.query_selector_all('.list-item-car.item-logo')
                    for card in car_cards:
                        link = await self.scrape_link(card)
                        brand = await self.scrape_brand(card)
                        title = await self.scrape_title(card)

                        details = await self.scrape_more_details(link)

                        self.cars.append({
                            'brand': brand,
                            'title': title,
                            'link': link,
                            **details
                        })

                    break

                except Exception as e:
                    logging.error(f"Attempt {attempt + 1} failed for {self.url}: {e}")
                    if attempt + 1 == self.retries:
                        logging.error(f"Max retries reached for {self.url}. Returning partial results.")
                        break
                finally:
                    await page.close()
                    if attempt + 1 < self.retries:
                        page = await browser.new_page()

            await browser.close()
            return self.cars

    def save_to_excel(self):
        """Save scraped data to Excel file"""
        if not self.cars:
            logging.warning("No data to save to Excel")
            return None

        # Create DataFrame
        df = pd.DataFrame(self.cars)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_filename = f'showrooms_data_{timestamp}.xlsx'
        
        try:
            # Save to Excel
            df.to_excel(excel_filename, index=False, engine='openpyxl')
            logging.info(f"Data saved to {excel_filename}")
            return excel_filename
        except Exception as e:
            logging.error(f"Error saving to Excel: {e}")
            return None

    def upload_to_drive(self, credentials_dict):
        """Upload Excel file to Google Drive"""
        try:
            # Save data to Excel first
            excel_file = self.save_to_excel()
            if not excel_file:
                return False

            # Initialize Google Drive uploader
            drive_saver = SavingOnDrive(credentials_dict)
            drive_saver.authenticate()

            # Upload file
            parent_folder_id = '1hLSbEqCR9A0DJiZrhivYeJyqVhZnpVHg'
            
            # Create dated folder
            today = datetime.now().strftime('%Y-%m-%d')
            folder_id = drive_saver.create_folder(today, parent_folder_id)
            
            # Upload Excel file
            file_id = drive_saver.upload_file(excel_file, folder_id)
            
            # Clean up local file
            try:
                os.remove(excel_file)
                logging.info(f"Local file {excel_file} cleaned up")
            except Exception as e:
                logging.error(f"Error cleaning up local file: {e}")

            logging.info(f"File uploaded successfully to Google Drive folder '{today}'")
            return True

        except Exception as e:
            logging.error(f"Error uploading to Google Drive: {e}")
            return False

async def main():
    try:
        # Get credentials from environment variable
        credentials_json = os.environ.get('SHOWROOMS_GCLOUD_KEY_JSON')
        if not credentials_json:
            raise EnvironmentError("SHOWROOMS_GCLOUD_KEY_JSON environment variable not found")
        
        credentials_dict = json.loads(credentials_json)
        
        # Initialize Google Drive uploader
        drive_saver = SavingOnDrive(credentials_dict)
        drive_saver.authenticate()
        
        # Your scraping code here
        scraper = OogooShowroomScraping("https://oogoocar.com/ar/explore/showrooms")
        data = await scraper.get_car_details()
        
        # Save to Excel
        if data:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_file = f'showrooms_data_{timestamp}.xlsx'
            
            df = pd.DataFrame(data)
            df.to_excel(excel_file, index=False)
            
            # Upload to specific folder in Google Drive
            parent_folder_id = '1hLSbEqCR9A0DJiZrhivYeJyqVhZnpVHg'
            today_folder = drive_saver.create_folder(
                datetime.now().strftime('%Y-%m-%d'),
                parent_folder_id
            )
            
            drive_saver.upload_file(excel_file, today_folder)
            logging.info(f"Successfully uploaded {excel_file} to Google Drive")
            
            # Cleanup
            try:
                os.remove(excel_file)
                logging.info(f"Cleaned up local file: {excel_file}")
            except Exception as e:
                logging.error(f"Error cleaning up file: {str(e)}")
        else:
            logging.warning("No data was scraped")
            
    except Exception as e:
        logging.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
