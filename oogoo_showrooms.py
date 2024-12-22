import asyncio
from playwright.async_api import async_playwright
import nest_asyncio
import re
from datetime import datetime, timedelta
import json
import pandas as pd
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Allow nested event loops (useful in Jupyter)
nest_asyncio.apply()

# Google Drive API setup
CLIENT_SECRET_FILE = 'path_to_your_credentials.json'  # Path to your Google OAuth2 credentials
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class OogooShowrooms:
    def __init__(self, url, retries=3):
        self.url = url
        self.retries = retries

    async def get_car_details(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            page.set_default_navigation_timeout(3000000)
            page.set_default_timeout(3000000)

            cars = []

            for attempt in range(self.retries):
                try:
                    await page.goto(self.url, wait_until="domcontentloaded")
                    await page.wait_for_selector('.list-item-car.item-logo', timeout=3000000)

                    car_cards = await page.query_selector_all('.list-item-car.item-logo')

                    # Extract available cars information
                    available_cars = await self.scrape_available_cars(page, car_cards)

                    # Adding available cars to the final result
                    for car in available_cars:
                        link = car.get('car_link')
                        brand = car.get('brand')
                        title = car.get('title')

                        # Corrected call to scrape_car_details
                        details = await self.scrape_car_details(link)

                        cars.append({
                            'brand': brand,
                            'title': title,
                            'link': link,
                            'time_list': details.get('time list', 'No time list'),
                            'location': details.get('location', 'No location'),
                            'phone_number': details.get('phone_number', 'No phone number'),
                            'available_cars': [car]
                        })

                    break

                except Exception as e:
                    print(f"Attempt {attempt + 1} failed for {self.url}: {e}")
                    if attempt + 1 == self.retries:
                        print(f"Max retries reached for {self.url}. Returning partial results.")
                        break
                finally:
                    await page.close()
                    if attempt + 1 < self.retries:
                        page = await browser.new_page()

            await browser.close()
            return cars

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

    async def scrape_car_details(self, url):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                await page.goto(url, wait_until="domcontentloaded")

                time_list = await self.scrape_time_list(page)
                location = await self.scrape_location(page)
                phone_number = await self.scrape_phone_number(page)

                await browser.close()

                return {
                    'time list': time_list,
                    'location': location,
                    'phone_number': phone_number,
                }

        except Exception as e:
            print(f"Error while scraping details from {url}: {e}")
            return {}

    async def scrape_time_list(self, card):
        try:
            time_list_element = await card.query_selector('.time-list')
            if not time_list_element:
                return {"time list": "No times found"}

            times = await time_list_element.query_selector_all('ul li')
            time_texts = [await time.inner_text() for time in times]
            return {"time list": ", ".join(time_texts)}

        except Exception as e:
            print(f"Error scraping time list: {e}")
            return {"time list": "Error"}

    async def scrape_location(self, card):
        try:
            location_element = await card.query_selector('.inner-map iframe')
            if location_element:
                src = await location_element.get_attribute('src')
                return src
            return "No location found"
        except Exception as e:
            print(f"Error scraping location: {e}")
            return "Error"

    async def scrape_phone_number(self, card):
        try:
            phone_element = await card.query_selector('.detail-contact-info.max-md\\:hidden a.call')
            if phone_element:
                properties = await phone_element.get_attribute('mpt-properties')
                data = json.loads(properties)
                return data.get('mobile')
            return "No phone number found"
        except Exception as e:
            print(f"Error scraping phone: {e}")
            return "Error"

    async def scrape_available_cars(self, page, car_cards):
        available_cars = []

        for card in car_cards:
            try:
                properties = await self.scrape_properties(card)
                car_link = await self.scrape_car_link(card)
                brand = await self.scrape_brand(card)
                title = await self.scrape_title(card)
                price = await self.scrape_price(card)

                available_cars.append({
                    'properties': properties,
                    'car_link': car_link,
                    'brand': brand,
                    'title': title,
                    'price': price,
                })
            except Exception as e:
                print(f"Error scraping car data: {e}")

        return available_cars

    async def scrape_properties(self, card):
        element = await card.query_selector('a')
        properties = await element.get_attribute('mpt-properties') if element else None
        return json.loads(properties) if properties else {}

    async def scrape_car_link(self, card):
        element = await card.query_selector('a')
        href = await element.get_attribute('href') if element else None
        return f"https://oogoocar.com{href}" if href else None

    async def scrape_price(self, card):
        element = await card.query_selector('.price span')
        return await element.inner_text() if element else None

# if __name__ == "__main__":
#     scraper = OogooShowrooms("https://oogoocar.com/ar/explore/showrooms")
#
#     cars = asyncio.run(scraper.get_car_details())
#
#     for car in cars:
#         print(car)

    def save_to_excel(self, cars, file_path="scraped_data.xlsx"):
        # Flattening the nested structure of 'available_cars' into a DataFrame
        flat_data = []
        for car in cars:
            for available_car in car['available_cars']:
                flat_data.append({
                    'brand': car['brand'],
                    'title': car['title'],
                    'link': car['link'],
                    'time_list': car['time_list'],
                    'location': car['location'],
                    'phone_number': car['phone_number'],
                    'car_properties': available_car['properties'],
                    'car_link': available_car['car_link'],
                    'car_brand': available_car['brand'],
                    'car_title': available_car['title'],
                    'car_price': available_car['price'],
                })

        # Create DataFrame
        df = pd.DataFrame(flat_data)

        # Save the DataFrame to an Excel file
        df.to_excel(file_path, index=False, engine='openpyxl')

    # def authenticate_google_drive(self):
    #     """Authenticate and create the Google Drive service"""
    #     creds = None
    #     if os.path.exists('token.json'):
    #         creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    #
    #     if not creds or not creds.valid:
    #         if creds and creds.expired and creds.refresh_token:
    #             creds.refresh(Request())
    #         else:
    #             flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    #             creds = flow.run_local_server(port=0)
    #
    #         with open('token.json', 'w') as token:
    #             token.write(creds.to_json())
    #
    #     service = build('drive', 'v3', credentials=creds)
    #     return service
    #
    # def upload_to_drive(self, file_path, folder_id='agdhjejfnj87hdnjd'):
    #     """Upload a file to Google Drive"""
    #     service = self.authenticate_google_drive()
    #
    #     # Create the file metadata
    #     file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
    #
    #     # MediaFileUpload to upload the file
    #     media = MediaFileUpload(file_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    #
    #     # Upload the file
    #     file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    #     print(f"File uploaded to Google Drive with ID: {file['id']}")

    async def scrape_and_upload(self):
        cars = await self.get_car_details()
        self.save_to_excel(cars)
        file_path = "Showrooms.xlsx"
        # self.upload_to_drive(file_path)


if __name__ == "__main__":
    scraper = OogooShowrooms("https://oogoocar.com/ar/explore/showrooms")

    # Start scraping and uploading to Drive
    asyncio.run(scraper.scrape_and_upload())