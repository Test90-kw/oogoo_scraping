import asyncio
from playwright.async_api import async_playwright
import logging
import re
from datetime import datetime, timedelta
import json

# Configure logging
logging.basicConfig(
    filename='scraper.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class OogooUsed:
    def __init__(self, url, retries=3):
        self.url = url
        self.retries = retries

    async def get_car_details(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            page.set_default_navigation_timeout(300000)
            page.set_default_timeout(300000)

            cars = []

            for attempt in range(self.retries):
                try:
                    await page.goto(self.url, wait_until="domcontentloaded")
                    await page.wait_for_selector('.list-item-car', timeout=300000)

                    car_cards = await page.query_selector_all('.list-item-car')
                    for card in car_cards:
                        link = await self.scrape_link(card)
                        brand = await self.scrape_brand(card)
                        price = await self.scrape_price(card)
                        title = await self.scrape_title(card)
                        details = await self.scrape_more_details(link, page)

                        cars.append({
                            'brand': brand,
                            'price': price,
                            'link': link,
                            'title': title,
                            **details
                        })
                        await asyncio.sleep(1)  # Delay to avoid rate-limiting

                    break

                except Exception as e:
                    logging.error(f"Attempt {attempt + 1} failed for {self.url}: {e}")
                    if attempt + 1 == self.retries:
                        logging.warning(f"Max retries reached for {self.url}. Returning partial results.")
                        break
                finally:
                    if attempt + 1 < self.retries:
                        await page.close()
                        page = await context.new_page()

            await context.close()
            await browser.close()
            return cars

    async def scrape_brand(self, card):
        try:
            element = await card.query_selector('.brand-car span')
            return await element.inner_text() if element else None
        except Exception as e:
            logging.error(f"Error scraping brand: {e}")
            return None

    async def scrape_price(self, card):
        try:
            element = await card.query_selector('.price span')
            return await element.inner_text() if element else None
        except Exception as e:
            logging.error(f"Error scraping price: {e}")
            return None

    async def scrape_link(self, card):
        try:
            element = await card.query_selector('a')
            href = await element.get_attribute('href') if element else None
            return f"https://oogoocar.com{href}" if href else None
        except Exception as e:
            logging.error(f"Error scraping link: {e}")
            return None

    async def scrape_title(self, card):
        try:
            title_element = await card.query_selector('.title-car')
            if not title_element:
                return {"model": None, "distance": None}

            model = await title_element.query_selector('span:nth-child(1)')
            distance = await title_element.query_selector('span:nth-child(2)')

            model_text = await model.inner_text() if model else "Model not found"
            distance_text = await distance.inner_text() if distance else "Distance not found"

            return {
                "model": model_text,
                "distance": distance_text
            }
        except Exception as e:
            logging.error(f"Error scraping title: {e}")
            return {"model": None, "distance": None}

    async def scrape_more_details(self, url, page):
        if not url or not url.startswith("https://oogoocar.com"):
            logging.warning(f"Invalid URL: {url}")
            return {
                'submitter': None,
                'specification': {},
                'description': "No Description Found",
                'phone_number': None,
                'ad_id': None,
                'relative_date': None,
                'date_published': None,
            }

        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            submitter = await self.scrape_submitter(page)
            specification = await self.scrape_specification(page)
            description = await self.scrape_description(page)
            phone_number = await self.scrape_phone_number(page)
            ad_id = await self.scrape_id(page)
            relative_date = await self.scrape_relative_date(page)
            date_published = self.get_publish_date_arabic(relative_date)

            return {
                'submitter': submitter,
                'specification': specification,
                'description': description,
                'phone_number': phone_number,
                'ad_id': ad_id,
                'relative_date': relative_date,
                'date_published': date_published,
            }

        except Exception as e:
            logging.error(f"Error while scraping details from {url}: {e}")
            return {
                'submitter': None,
                'specification': {},
                'description': "No Description Found",
                'phone_number': None,
                'ad_id': None,
                'relative_date': None,
                'date_published': None,
            }

    async def scrape_submitter(self, page):
        try:
            element = await page.query_selector('.car-ad-posted figcaption')
            if not element:
                return None

            label = await element.query_selector('label')
            relative_date = await element.query_selector('p')

            return {
                'submitter': await label.inner_text() if label else None,
                'relative_date': await relative_date.inner_text() if relative_date else None
            }
        except Exception as e:
            logging.error(f"Error scraping submitter: {e}")
            return None

    async def scrape_specification(self, page):
        try:
            elements = await page.query_selector_all('.specification ul li')
            specifications = {}
            for element in elements:
                x = await element.query_selector('h3')
                y = await element.query_selector('p')
                if x and y:
                    specifications[await x.inner_text()] = await y.inner_text()
            return specifications
        except Exception as e:
            logging.error(f"Error scraping specification: {e}")
            return {}

    async def scrape_description(self, page):
        try:
            selector = '#description-section'
            await page.wait_for_selector(selector, timeout=30000, state='visible')
            element = await page.query_selector(selector)
            description = await element.inner_text() if element else "No Description Found"
            logging.info(f"Scraped description: {description[:50]}...")
            return description.strip() if description else "No Description Found"
        except Exception as e:
            logging.error(f"Error scraping description: {e}")
            return "No Description Found"

    async def scrape_phone_number(self, page):
        try:
            element = await page.query_selector('.detail-contact-info .whatsapp')
            if element:
                properties = await element.get_attribute('mpt-properties')
                if properties:
                    data = json.loads(properties)
                    return data.get('mobile', None)
            return None
        except Exception as e:
            logging.error(f"Error scraping phone number: {e}")
            return None

    async def scrape_id(self, page):
        try:
            element = await page.query_selector('.detail-contact-info .whatsapp')
            if element:
                properties = await element.get_attribute('mpt-properties')
                if properties:
                    data = json.loads(properties)
                    return data.get('AdId', None)
            return None
        except Exception as e:
            logging.error(f"Error scraping ad ID: {e}")
            return None

    async def scrape_relative_date(self, page):
        try:
            element = await page.query_selector('.car-ad-posted figcaption p')
            return await element.inner_text() if element else None
        except Exception as e:
            logging.error(f"Error scraping relative date: {e}")
            return None

    def get_publish_date_arabic(self, relative_date):
        try:
            current_time = datetime.now()

            # Arabic regex patterns for matching relative time
            hour_pattern = r'نُشر منذ (\d+) ساعة'
            day_pattern = r'نُشر منذ (\d+) يوم'
            one_day_pattern = r'نُشر منذ يوم'
            two_days_pattern = r'نُشر منذ يومين'
            three_days_pattern = r'نُشر منذ (\d+) أيام'

            # Match for hours
            match_hour = re.search(hour_pattern, relative_date) if relative_date else None
            if match_hour:
                hours_ago = int(match_hour.group(1))
                publish_time = current_time - timedelta(hours=hours_ago)
                return publish_time.strftime("%Y-%m-%d %H:%M:%S")

            # Match for "one day ago"
            if relative_date and re.search(one_day_pattern, relative_date):
                publish_time = current_time - timedelta(days=1)
                return publish_time.strftime("%Y-%m-%d %H:%M:%S")

            # Match for "two days ago"
            if relative_date and re.search(two_days_pattern, relative_date):
                publish_time = current_time - timedelta(days=2)
                return publish_time.strftime("%Y-%m-%d %H:%M:%S")

            # Match for "three or more days ago"
            match_three_days = re.search(three_days_pattern, relative_date) if relative_date else None
            if match_three_days:
                days_ago = int(match_three_days.group(1))
                publish_time = current_time - timedelta(days=days_ago)
                return publish_time.strftime("%Y-%m-%d %H:%M:%S")

            # Default to "more than 3 days ago"
            publish_time = current_time - timedelta(days=3)
            return publish_time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logging.error(f"Error parsing publish date: {e}")
            return None



# import asyncio
# from playwright.async_api import async_playwright
# import nest_asyncio
# import re
# from datetime import datetime, timedelta
# import json

# # Allow nested event loops (useful in Jupyter)
# nest_asyncio.apply()

# class OogooUsed:
#     def __init__(self, url, retries=3):
#         self.url = url
#         self.retries = retries

#     async def get_car_details(self):
#         async with async_playwright() as p:
#             browser = await p.chromium.launch(headless=True)
#             page = await browser.new_page()

#             page.set_default_navigation_timeout(3000000)
#             page.set_default_timeout(3000000)

#             cars = []

#             for attempt in range(self.retries):
#                 try:
#                     await page.goto(self.url, wait_until="domcontentloaded")
#                     await page.wait_for_selector('.list-item-car', timeout=3000000)

#                     car_cards = await page.query_selector_all('.list-item-car')
#                     for card in car_cards:
#                         link = await self.scrape_link(card)
#                         brand = await self.scrape_brand(card)
#                         price = await self.scrape_price(card)
#                         title = await self.scrape_title(card)
#                         details = await self.scrape_more_details(link)

#                         cars.append({
#                             'brand': brand,
#                             'price': price,
#                             'link': link,
#                             'title': title,
#                             **details
#                         })

#                     break

#                 except Exception as e:
#                     print(f"Attempt {attempt + 1} failed for {self.url}: {e}")
#                     if attempt + 1 == self.retries:
#                         print(f"Max retries reached for {self.url}. Returning partial results.")
#                         break
#                 finally:
#                     await page.close()
#                     if attempt + 1 < self.retries:
#                         page = await browser.new_page()

#             await browser.close()
#             return cars

#     async def scrape_brand(self, card):
#         element = await card.query_selector('.brand-car span')
#         return await element.inner_text() if element else None

#     async def scrape_price(self, card):
#         element = await card.query_selector('.price span')
#         return await element.inner_text() if element else None

#     async def scrape_link(self, card):
#         element = await card.query_selector('a')
#         href = await element.get_attribute('href') if element else None
#         return f"https://oogoocar.com{href}" if href else None

#     async def scrape_more_details(self, url):
#         try:
#             async with async_playwright() as p:
#                 browser = await p.chromium.launch(headless=True)
#                 page = await browser.new_page()

#                 await page.goto(url, wait_until="domcontentloaded")

#                 submitter = await self.scrape_submitter(page)
#                 specification = await self.scrape_specification(page)
#                 description = await self.scrape_description(page)
#                 phone_number = await self.scrape_phone_number(page)
#                 ad_id = await self.scrape_id(page)
#                 relative_date = await self.scrape_relative_date(page)
#                 date_published = self.get_publish_date_arabic(relative_date)

#                 await browser.close()

#                 return {
#                     'submitter': submitter,
#                     'specification': specification,
#                     'description': description,
#                     'phone_number': phone_number,
#                     'ad_id': ad_id,
#                     'relative_date': relative_date,
#                     'date_published': date_published,
#                 }

#         except Exception as e:
#             print(f"Error while scraping details from {url}: {e}")
#             return {}

#     async def scrape_submitter(self, page):
#         element = await page.query_selector('.car-ad-posted figcaption')
#         if not element:
#             return None

#         label = await element.query_selector('label')
#         relative_date = await element.query_selector('p')

#         return {
#             'submitter': await label.inner_text() if label else None,
#             'relative_date': await relative_date.inner_text() if relative_date else None
#         }

#     async def scrape_specification(self, page):
#         elements = await page.query_selector_all('.specification ul li')

#         specifications = {}
#         for element in elements:
#             x = await element.query_selector('h3')
#             y = await element.query_selector('p')
#             if x and y:
#                 specifications[await x.inner_text()] = await y.inner_text()

#         return specifications

#     async def scrape_description(self, page):
#         try:
#             # Wait for the description section to appear (simplified selector)
#             selector = '#description-section'  # Directly target the <pre> tag by its ID
#             await page.wait_for_selector(selector, timeout=15000)  # Ensure it's available
#             # Extract the inner text of the description
#             element = await page.query_selector(selector)
#             description = await element.inner_text() if element else "No Description Found"
#             return description
#         except Exception as e:
#             print(f"Error scraping description: {e}")
#             return "Error in extracting description"

#     async def scrape_title(self, card):
#         try:
#             # Scrape the model and distance from the title section
#             title_element = await card.query_selector('.title-car')
#             if not title_element:
#                 return {"model": None, "distance": None}

#             model = await title_element.query_selector('span:nth-child(1)')
#             distance = await title_element.query_selector('span:nth-child(2)')

#             # Extract text for both model and distance
#             model_text = await model.inner_text() if model else "Model not found"
#             distance_text = await distance.inner_text() if distance else "Distance not found"

#             return {
#                 "model": model_text,
#                 "distance": distance_text
#             }

#         except Exception as e:
#             print(f"Error scraping title: {e}")
#             return {"model": "Error", "distance": "Error"}

#     async def scrape_phone_number(self, page):
#         element = await page.query_selector('.detail-contact-info .whatsapp')
#         if element:
#             properties = await element.get_attribute('mpt-properties')
#             data = json.loads(properties)
#             return data.get('mobile')
#         return None

#     async def scrape_id(self, page):
#         element = await page.query_selector('.detail-contact-info .whatsapp')
#         if element:
#             properties = await element.get_attribute('mpt-properties')
#             data = json.loads(properties)
#             return data.get('AdId')
#         return None

#     async def scrape_relative_date(self, page):
#         element = await page.query_selector('.car-ad-posted figcaption p')
#         return await element.inner_text() if element else None

#     # Method to get publish date from Arabic relative date
#     def get_publish_date_arabic(self,relative_date):
#         current_time = datetime.now()

#         # Arabic regex patterns for matching relative time
#         hour_pattern = r'نُشر منذ (\d+) ساعة'
#         day_pattern = r'نُشر منذ (\d+) يوم'
#         one_day_pattern = r'نُشر منذ يوم'
#         two_days_pattern = r'نُشر منذ يومين'
#         three_days_pattern = r'نُشر منذ (\d+) أيام'

#         # Match for hours
#         match_hour = re.search(hour_pattern, relative_date)
#         if match_hour:
#             hours_ago = int(match_hour.group(1))
#             publish_time = current_time - timedelta(hours=hours_ago)
#             return publish_time.strftime("%Y-%m-%d %H:%M:%S")

#         # Match for "one day ago"
#         if re.search(one_day_pattern, relative_date):
#             publish_time = current_time - timedelta(days=1)
#             return publish_time.strftime("%Y-%m-%d %H:%M:%S")

#         # Match for "two days ago"
#         if re.search(two_days_pattern, relative_date):
#             publish_time = current_time - timedelta(days=2)
#             return publish_time.strftime("%Y-%m-%d %H:%M:%S")

#         # Match for "three days ago"
#         match_three_days = re.search(three_days_pattern, relative_date)
#         if match_three_days:
#             days_ago = int(match_three_days.group(1))
#             publish_time = current_time - timedelta(days=days_ago)
#             return publish_time.strftime("%Y-%m-%d %H:%M:%S")

#         # Default to "more than 3 days ago"
#         publish_time = current_time - timedelta(days=3)
#         return publish_time.strftime("%Y-%m-%d %H:%M:%S")


# # if __name__ == "__main__":
# #     scraper = OogooUsed("https://oogoocar.com/ar/explore/used/all/all/all/all/list/0/basic?page=1") # 1 & 2

# #     cars = asyncio.run(scraper.get_car_details())

# #     for car in cars:
# #         print(car)
