import logging
import asyncio
from playwright.async_api import async_playwright
import nest_asyncio
import pandas as pd
from datetime import datetime
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
        self.showrooms = []

    async def scrape_link(self, card):
        """Extract showroom link from card"""
        try:
            link_element = await card.query_selector('.list-item-car')
            if link_element:
                href = await link_element.get_attribute('href')
                return f"https://oogoocar.com{href}" if href else None
            return None
        except Exception as e:
            logging.error(f"Error scraping link: {e}")
            return None

    async def scrape_brand(self, card):
        """Extract showroom name"""
        try:
            name_element = await card.query_selector('.info-showroom h3')
            if name_element:
                return await name_element.inner_text()
            return None
        except Exception as e:
            logging.error(f"Error scraping showroom name: {e}")
            return None

    async def scrape_title(self, card):
        """Extract showroom description"""
        try:
            desc_element = await card.query_selector('.info-showroom p')
            if desc_element:
                return await desc_element.inner_text()
            return None
        except Exception as e:
            logging.error(f"Error scraping description: {e}")
            return None

    async def scrape_working_hours(self, page):
        """Extract working hours"""
        try:
            hours_list = await page.query_selector('.working-hours ul')
            if hours_list:
                hours = await hours_list.query_selector_all('li')
                return "\n".join([await hour.inner_text() for hour in hours])
            return "No working hours found"
        except Exception as e:
            logging.error(f"Error scraping working hours: {e}")
            return "Error"

    async def scrape_location(self, page):
        """Extract location"""
        try:
            location_element = await page.query_selector('.showroom-location')
            if location_element:
                return await location_element.inner_text()
            return "No location found"
        except Exception as e:
            logging.error(f"Error scraping location: {e}")
            return "Error"

    async def scrape_contact_info(self, page):
        """Extract contact information"""
        try:
            contact_element = await page.query_selector('.contact-info')
            if contact_element:
                phone = await contact_element.query_selector('.phone-number')
                return await phone.inner_text() if phone else "No phone found"
            return "No contact info found"
        except Exception as e:
            logging.error(f"Error scraping contact info: {e}")
            return "Error"

    async def scrape_more_details(self, link):
        """Extract additional showroom details"""
        if not link:
            return {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(link, wait_until="domcontentloaded")
                await page.wait_for_selector('.showroom-details', timeout=30000)
                
                details = {
                    'working_hours': await self.scrape_working_hours(page),
                    'location': await self.scrape_location(page),
                    'contact_info': await self.scrape_contact_info(page),
                }
                return details
            except Exception as e:
                logging.error(f"Error scraping details from {link}: {e}")
                return {}
            finally:
                await browser.close()

    async def get_showroom_details(self):
        """Main method to scrape showroom details"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for attempt in range(self.retries):
                try:
                    await page.goto(self.url, wait_until="domcontentloaded")
                    await page.wait_for_selector('.list-item-car', timeout=30000)

                    # Get all showroom links
                    showroom_links = await page.query_selector_all('.list-item-car a')
                    links = []
                    for link in showroom_links:
                        href = await link.get_attribute('href')
                        if href:
                            full_link = f"https://oogoocar.com{href}"
                            links.append(full_link)

                    logging.info(f"Found {len(links)} showroom links")

                    # Scrape details for each showroom
                    for link in links:
                        try:
                            details = await self.scrape_more_details(link)
                            showroom_data = {
                                'link': link,
                                **details
                            }
                            self.showrooms.append(showroom_data)
                            logging.info(f"Scraped data for showroom at {link}")
                        except Exception as e:
                            logging.error(f"Error scraping showroom at {link}: {e}")

                    break
                except Exception as e:
                    logging.error(f"Attempt {attempt + 1} failed: {e}")
                    if attempt + 1 == self.retries:
                        logging.error("Max retries reached")
                        break

            await browser.close()
            return self.showrooms

    def save_to_excel(self):
        """Save scraped data to Excel file"""
        if not self.showrooms:
            logging.warning("No data to save to Excel")
            return None

        # Create DataFrame
        df = pd.DataFrame(self.showrooms)
        
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

async def main():
    try:
        scraper = OogooShowroomScraping("https://oogoocar.com/ar/explore/showrooms")
        data = await scraper.get_showroom_details()
        
        if data:
            excel_file = scraper.save_to_excel()
            if excel_file:
                # Get credentials from environment variable
                credentials_json = os.environ.get('SHOWROOMS_GCLOUD_KEY_JSON')
                if not credentials_json:
                    raise EnvironmentError("SHOWROOMS_GCLOUD_KEY_JSON environment variable not found")
                
                credentials_dict = json.loads(credentials_json)
                
                # Initialize Google Drive uploader
                drive_saver = SavingOnDrive(credentials_dict)
                drive_saver.authenticate()
                
                # Upload file
                parent_folder_id = '1hLSbEqCR9A0DJiZrhivYeJyqVhZnpVHg'
                today_folder = drive_saver.create_folder(
                    datetime.now().strftime('%Y-%m-%d'),
                    parent_folder_id
                )
                
                file_id = drive_saver.upload_file(excel_file, today_folder)
                logging.info(f"File uploaded to Google Drive with ID: {file_id}")
                
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
