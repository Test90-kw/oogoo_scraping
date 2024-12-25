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
        self.cars = []

    async def scrape_link(self, card):
        """Extract car link from card"""
        try:
            link_element = await card.query_selector('a')
            if link_element:
                return await link_element.get_attribute('href')
            return None
        except Exception as e:
            logging.error(f"Error scraping link: {e}")
            return None

    async def scrape_brand(self, card):
        """Extract car brand from card"""
        try:
            brand_element = await card.query_selector('.car-title h3')
            if brand_element:
                return await brand_element.inner_text()
            return None
        except Exception as e:
            logging.error(f"Error scraping brand: {e}")
            return None

    async def scrape_title(self, card):
        """Extract car title from card"""
        try:
            title_element = await card.query_selector('.car-title p')
            if title_element:
                return await title_element.inner_text()
            return None
        except Exception as e:
            logging.error(f"Error scraping title: {e}")
            return None
    
    async def scrape_time_list(self, page):
        try:
            time_list_element = await page.query_selector('.time-list')
            if not time_list_element:
                return "No times found"

            times = await time_list_element.query_selector_all('ul li')
            time_texts = [await time.inner_text() for time in times]
            return ", ".join(time_texts)
        except Exception as e:
            logging.error(f"Error scraping time list: {e}")
            return "Error"

    async def scrape_location(self, page):
        try:
            location_element = await page.query_selector('.inner-map iframe')
            if location_element:
                src = await location_element.get_attribute('src')
                return src
            return "No location found"
        except Exception as e:
            logging.error(f"Error scraping location: {e}")
            return "Error"

    async def scrape_phone_number(self, page):
        try:
            phone_element = await page.query_selector('.detail-contact-info.max-md\\:hidden a.call')
            if phone_element:
                properties = await phone_element.get_attribute('mpt-properties')
                data = json.loads(properties)
                return data.get('mobile')
            return "No phone number found"
        except Exception as e:
            logging.error(f"Error scraping phone number: {e}")
            return "Error"

    async def scrape_more_details(self, link):
        if not link:
            return {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                full_url = f"https://oogoocar.com{link}" if not link.startswith('http') else link
                await page.goto(full_url, wait_until="domcontentloaded")
                await page.wait_for_selector('.showroom-details', timeout=30000)
                
                details = {
                    'time list': await self.scrape_time_list(page),
                    'location': await self.scrape_location(page),
                    'phone_number': await self.scrape_phone_number(page),
                }
                return details
            except Exception as e:
                logging.error(f"Error scraping details from {link}: {e}")
                return {}
            finally:
                await browser.close()

    # async def scrape_more_details(self, link):
    #     """Extract additional details from car page"""
    #     if not link:
    #         return {}

    #     async with async_playwright() as p:
    #         browser = await p.chromium.launch(headless=True)
    #         page = await browser.new_page()

    #         try:
    #             full_url = f"https://oogoocar.com{link}" if not link.startswith('http') else link
    #             await page.goto(full_url, wait_until="domcontentloaded")
    #             await page.wait_for_selector('.showroom-details', timeout=30000)

    #             details = {}
                
    #             # Price
    #             price_element = await page.query_selector('.price-tag')
    #             if price_element:
    #                 details['price'] = await price_element.inner_text()

    #             # Specifications
    #             specs = await page.query_selector_all('.specifications-list li')
    #             for spec in specs:
    #                 label_elem = await spec.query_selector('.label')
    #                 value_elem = await spec.query_selector('.value')
    #                 if label_elem and value_elem:
    #                     label = await label_elem.inner_text()
    #                     value = await value_elem.inner_text()
    #                     details[label.lower().replace(' ', '_')] = value

    #             return details

    #         except Exception as e:
    #             logging.error(f"Error scraping details from {link}: {e}")
    #             return {}
    #         finally:
    #             await browser.close()

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
                    logging.info(f"Found {len(car_cards)} car cards")
                    
                    for card in car_cards:
                        link = await self.scrape_link(card)
                        brand = await self.scrape_brand(card)
                        title = await self.scrape_title(card)

                        details = await self.scrape_more_details(link)

                        car_data = {
                            'brand': brand,
                            'title': title,
                            'link': link,
                            **details
                        }
                        self.cars.append(car_data)
                        logging.info(f"Scraped data for {brand} {title}")

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

    def upload_to_drive(self, file_path):
        """Upload the Excel file to Google Drive"""
        try:
            credentials_json = os.environ.get('SHOWROOMS_GCLOUD_KEY_JSON')
            if not credentials_json:
                raise EnvironmentError("SHOWROOMS_GCLOUD_KEY_JSON environment variable not found")
            
            credentials_dict = json.loads(credentials_json)

            drive_saver = SavingOnDrive(credentials_dict)
            drive_saver.authenticate()

            parent_folder_id = '1hLSbEqCR9A0DJiZrhivYeJyqVhZnpVHg'
            today_folder = drive_saver.create_folder(datetime.now().strftime('%Y-%m-%d'), parent_folder_id)
            
            file_id = drive_saver.upload_file(file_path, today_folder)
            logging.info(f"File uploaded to Google Drive with ID: {file_id}")
            
            # Cleanup
            try:
                os.remove(file_path)
                logging.info(f"Cleaned up local file: {file_path}")
            except Exception as e:
                logging.error(f"Error cleaning up file: {str(e)}")

        except Exception as e:
            logging.error(f"Error uploading to Google Drive: {str(e)}")


async def main():
    try:
        # Your scraping code here
        scraper = OogooShowroomScraping("https://oogoocar.com/ar/explore/showrooms")
        data = await scraper.get_car_details()
        
        # Save to Excel
        if data:
            excel_file = scraper.save_to_excel()
            
            if excel_file:
                # Upload to Google Drive
                scraper.upload_to_drive(excel_file)
        else:
            logging.warning("No data was scraped")
            
    except Exception as e:
        logging.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
