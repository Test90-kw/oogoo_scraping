import asyncio
from playwright.async_api import async_playwright
from SavingOnDrive import SavingOnDrive
from bs4 import BeautifulSoup
import nest_asyncio
import json
import logging
import pandas as pd
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)

# Allow nested event loops
nest_asyncio.apply()

class OogooNewCarScraper:
    def __init__(self, url):
        self.url = url
        self.tab_data = {}

    async def scrape_data(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(self.url)
                await page.wait_for_selector('div.detail-title-left')
                soup = BeautifulSoup(await page.content(), 'html.parser')

                result = {
                    'title': await self.extract_title(soup),
                    'distance': await self.extract_distance(soup),
                    'case': await self.extract_case(soup),
                    'submitter': await self.extract_submitter(soup),
                    'relative_date': await self.extract_relative_date(soup),
                    'specifications': await self.extract_specifications(soup),
                    'tabbed_data': await self.extract_tabbed_data(soup),
                }

                return json.dumps(result, ensure_ascii=False, indent=2)
            finally:
                await browser.close()

    async def extract_title(self, soup):
        title_div = soup.find('div', class_='detail-title-left')
        if title_div and title_div.find('h1'):
            return title_div.find('h1').text.strip()
        return None

    async def extract_distance(self, soup):
        """Extract the distance."""
        info_div = soup.find('div', class_='detail-title-left')
        if info_div:
            items = info_div.find_all('li')
            if len(items) >= 1:
                return items[0].text.strip()
        return None

    async def extract_case(self, soup):
        """Extract the case (e.g., new, used)."""
        info_div = soup.find('div', class_='detail-title-left')
        if info_div:
            items = info_div.find_all('li')
            if len(items) >= 2:
                return items[1].text.strip()
        return None

    async def extract_submitter(self, soup):
        """Extract the submitter."""
        submitter_div = soup.find('div', class_='car-ad-posted')
        if submitter_div:
            return submitter_div.find('label').text.strip()
        return None

    async def extract_relative_date(self, soup):
        """Extract the relative date."""
        submitter_div = soup.find('div', class_='car-ad-posted')
        if submitter_div:
            return submitter_div.find('p').text.strip()
        return None    
    
    async def extract_specifications(self, soup):
        specifications = {}
        spec_div = soup.find('div', class_='specification')
        if spec_div:
            items = spec_div.find_all('li')
            for item in items:
                figcaption = item.find('figcaption')
                if figcaption:
                    h3_tag = figcaption.find('h3')
                    p_tag = figcaption.find('p')
                    if h3_tag and p_tag:
                        key = h3_tag.text.strip()
                        value = p_tag.text.strip()
                        specifications[key] = value
        return specifications

    async def extract_tabbed_data(self, page):
        tab_data = {}
        try:
            # Wait for the tabbing UI to load
            await page.wait_for_selector('.tabbing-ui')
        
            # Find all tabs
            tabs = await page.query_selector_all('.tab-list .tab button')

            # Iterate over each tab
            for index, tab in enumerate(tabs):
                try:
                    # Wait for the tab to become visible
                    await tab.wait_for_element_state('visible')
                
                    # Scroll to the tab (optional)
                    await tab.scroll_into_view_if_needed()
                    await asyncio.sleep(1)  # Small delay to ensure it's fully in view
                
                    # Close any blocking elements (if present)
                    try:
                        # Attempt to find and close any overlay (adjust the selector as needed)
                        close_button = await page.query_selector('.overlay-close-button-selector')
                        if close_button:
                            await close_button.click()
                            await asyncio.sleep(1)  # Wait for the overlay to disappear
                    except Exception as ex:
                        print(f"No blocking overlay detected for tab {index + 1}: {ex}")
                
                    # Click the tab using Playwright
                    await tab.click()
                
                    # Wait for the content to load completely
                    await page.wait_for_selector('.tabbing-body .tabbing-content')  # Adjust this selector based on the content
                    await asyncio.sleep(3)  # Wait a bit longer for the first tab's content to load
                
                    # Extract the data from the active tabbing body
                    active_tab_content = await page.query_selector('.tabbing-body .tabbing-content')

                    # Check if the content is a list of <li> elements
                    list_items = await active_tab_content.query_selector_all('li')

                    # Initialize a dictionary to store each tab's specific data
                    tab_dict = {}
                    counter = 1
                    for item in list_items:
                        p_element = await item.query_selector('p')
                        i_element = await item.query_selector('i')
                        span_element = await item.query_selector('span')
                    
                        # Case 1: <li> contains both <p> and <span>
                        if p_element and span_element:
                            key = await p_element.text_content()
                            value = await span_element.text_content()
                            tab_dict[key] = value
                    
                        # Case 2: <li> contains only <i> and <span>
                        elif i_element and span_element:
                            key = str(counter)
                            value = await span_element.text_content()
                            # Store the extracted value under the same key
                            tab_dict[key] = value
                            counter += 1
                
                    # Store the extracted data for this tab in the main dictionary
                    tab_data_key = await tab.text_content()
                    self.tab_data[tab_data_key] = tab_dict

                except Exception as e:
                    print(f"Error clicking tab {index + 1} ({await tab.text_content()}): {e}")
        except Exception as e:
            logging.error(f"Error extracting tabbed data: {e}")
        return tab_data

    # async def extract_tabbed_data(self, soup):
    #     tab_data = {}
    #     try:
    #         # Wait for the tabbing UI to load
    #         await page.wait_for_selector('.tabbing-ui')
    #         # Find all tabs
    #         tabs = await page.query_selector_all('.tab-list .tab button')
    #         # Iterate over each tab
    #         for index, tab in enumerate(tabs):
    #             try:
    #                 # Wait for the tab to become visible
    #                 await tab.wait_for_element_state('visible')
                    
    #                 # Scroll to the tab (optional)
    #                 await tab.scroll_into_view_if_needed()
    #                 await asyncio.sleep(1)  # Small delay to ensure it's fully in view
                    
    #                 # Close any blocking elements (if present)
    #                 try:
    #                     # Attempt to find and close any overlay (adjust the selector as needed)
    #                     close_button = await page.query_selector('.overlay-close-button-selector')
    #                     if close_button:
    #                         await close_button.click()
    #                         await asyncio.sleep(1)  # Wait for the overlay to disappear
    #                 except Exception as ex:
    #                     print(f"No blocking overlay detected for tab {index + 1}: {ex}")
                    
    #                 # Click the tab using Playwright
    #                 await tab.click()
    #                  # Wait for the content to load completely
    #                 await page.wait_for_selector('.tabbing-body .tabbing-content')  # Adjust this selector based on the content
    #                 await asyncio.sleep(3)  # Wait a bit longer for the first tab's content to load
                    
    #                 # Extract the data from the active tabbing body
    #                 active_tab_content = await page.query_selector('.tabbing-body .tabbing-content')

    #                 # Check if the content is a list of <li> elements
    #                 list_items = await active_tab_content.query_selector_all('li')

    #                 # Initialize a dictionary to store each tab's specific data
    #                 tab_dict = {}
    #                 counter = 1
    #                 for item in list_items:
    #                     p_element = await item.query_selector('p')
    #                     i_element = await item.query_selector('i')
    #                     span_element = await item.query_selector('span')
                        
    #                     # Case 1: <li> contains both <p> and <span>
    #                     if p_element and span_element:
    #                         key = await p_element.text_content()
    #                         value = await span_element.text_content()
    #                         tab_dict[key] = value
                        
    #                     # Case 2: <li> contains only <i> and <span>
    #                     elif i_element and span_element:
    #                         key = str(counter)
    #                         value = await span_element.text_content()
    #                         # Store the extracted value under the same key
    #                         tab_dict[key] = value
    #                         counter += 1
    #                 # Store the extracted data for this tab in the main dictionary
    #                 tab_data_key = await tab.text_content()
    #                 self.tab_data[tab_data_key] = tab_dict

    #             except Exception as e:
    #                 print(f"Error clicking tab {index + 1} ({await tab.text_content()}): {e}")
    #     except Exception as e:
    #         logging.error(f"Error extracting tabbed data: {e}")
    #     return tab_data


class DetailsScraping:
    def __init__(self, url, retries=3):
        self.url = url
        self.retries = retries
        self.showrooms_data = []

    async def get_car_details(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            page.set_default_navigation_timeout(3000000)
            page.set_default_timeout(3000000)

            try:
                await page.goto(self.url, wait_until="domcontentloaded")
                await page.wait_for_selector('.list-item-car.item-logo', timeout=3000000)

                car_cards = await page.query_selector_all('.list-item-car.item-logo')
                
                for card in car_cards:
                    showroom_data = {
                        'brand': await self.scrape_brand(card),
                        'title': await self.scrape_title(card),
                        'link': await self.scrape_link(card)
                    }
                    
                    print("\nShowroom Basic Info:")
                    print(json.dumps(showroom_data, ensure_ascii=False, indent=2))

                    if showroom_data['link']:
                        details = await self.scrape_more_details(showroom_data['link'])
                        print("\nShowroom Details:")
                        print(json.dumps(details, ensure_ascii=False, indent=2))

                        car_links = await self.get_cars_from_showroom(showroom_data['link'])
                        cars_count = len(car_links)
                        print(f"\nFound {cars_count} cars in showroom")

                        cars_data = []
                        for car_link in car_links:
                            print(f"\nProcessing car: {car_link}")
                            car_scraper = OogooNewCarScraper(car_link)
                            car_details = await car_scraper.scrape_data()
                            cars_data.append({
                                'link': car_link,
                                'details': json.loads(car_details)
                            })

                        showroom_complete_data = {
                            'brand': showroom_data['brand'],
                            'title': showroom_data['title'],
                            'link': showroom_data['link'],
                            'location': details['location'],
                            'time_list': details['time_list'],
                            'phone_number': details['phone_number'],
                            'cars_count': cars_count,
                            'cars': cars_data
                        }
                        
                        self.showrooms_data.append(showroom_complete_data)

            except Exception as e:
                logging.error(f"Error in main scraping process: {e}")
            finally:
                await browser.close()

            excel_file = self.save_to_excel()
            if excel_file:
                self.upload_to_drive(excel_file)

    async def scrape_brand(self, card):
        element = await card.query_selector('.brand-car span')
        return await element.inner_text() if element else None

    async def scrape_title(self, card):
        element = await card.query_selector('.title-car span')
        return await element.inner_text() if element else None

    async def scrape_link(self, card):
        element = await card.query_selector('a')
        href = await element.get_attribute('href') if element else None
        return f"https://oogoocar.com{href}" if href else None

    async def get_cars_from_showroom(self, showroom_url):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(showroom_url, wait_until="networkidle")
                await page.wait_for_selector('.list-content', timeout=30000)
                
                car_cards = await page.query_selector_all('.list-content .list-item-car a')
                car_links = [await car.get_attribute('href') for car in car_cards]
                return [f"https://oogoocar.com{link}" for link in car_links if link]

            except Exception as e:
                logging.error(f"Error getting cars from showroom: {e}")
                return []
            finally:
                await browser.close()

    async def scrape_more_details(self, url):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded")
                
                location = await self.scrape_location(page)
                time_list = await self.scrape_time_list(page)
                phone_number = await self.scrape_phone_number(page)

                return {
                    'location': location,
                    'time_list': time_list,
                    'phone_number': phone_number
                }
            except Exception as e:
                logging.error(f"Error scraping details from {url}: {e}")
                return {}
            finally:
                await browser.close()

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
            logging.error(f"Error scraping phone: {e}")
            return "Error"

    def save_to_excel(self):
        """Save scraped data to Excel file"""
        if not self.showrooms_data:
            logging.warning("No data to save to Excel")
            return None

        # Prepare data for DataFrame
        excel_data = []
        for showroom in self.showrooms_data:
            cars_info = []
            for car in showroom['cars']:
                car_info = {
                    'link': car['link'],
                    'title': car['details'].get('title'),
                    'distance': car['details'].get('distance'),
                    'case': car['details'].get('case'),
                    'submitter': car['details'].get('submitter'),
                    'relative_date': car['details'].get('relative_date'),
                    'specifications': car['details'].get('specifications'),
                    'tabbed_data': json.dumps(car['details'].get('tabbed_data', {})),
                }
                cars_info.append(car_info)

            row_data = {
                'brand': showroom['brand'],
                'title': showroom['title'],
                'link': showroom['link'],
                'location': showroom['location'],
                'time_list': showroom['time_list'],
                'phone_number': showroom['phone_number'],
                'cars_count': showroom['cars_count'],
                'cars': json.dumps(cars_info, ensure_ascii=False)
            }
            excel_data.append(row_data)

        df = pd.DataFrame(excel_data)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_filename = f'showrooms_data_{timestamp}.xlsx'
        
        try:
            with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
                worksheet = writer.sheets['Sheet1']
                for idx, col in enumerate(df.columns):
                    worksheet.column_dimensions[chr(65 + idx)].width = 30

            logging.info(f"Data saved to {excel_filename}")
            return excel_filename
        except Exception as e:
            logging.error(f"Error saving to Excel: {e}")
            return None

    def upload_to_drive(self, file_path):
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
            
            try:
                os.remove(file_path)
                logging.info(f"Cleaned up local file: {file_path}")
            except Exception as e:
                logging.error(f"Error cleaning up file: {str(e)}")

        except Exception as e:
            logging.error(f"Error uploading to Google Drive: {str(e)}")

async def main():
    url = "https://oogoocar.com/ar/explore/showrooms"
    scraper = DetailsScraping(url)
    await scraper.get_car_details()

if __name__ == "__main__":
    asyncio.run(main())
