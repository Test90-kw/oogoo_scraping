import asyncio  # For asynchronous execution
from playwright.async_api import async_playwright  # Controls browser via Playwright
import nest_asyncio  # Allows nested event loops (especially for environments like Jupyter)
import re  # For regular expression matching (used in Arabic date parsing)
from datetime import datetime, timedelta  # Used to convert relative dates into timestamps
import json  # To decode/encode JSON data

# Enable nested event loops (important in notebooks or embedded runtimes)
nest_asyncio.apply()

class OogooUsed:
    def __init__(self, url, retries=3):
        # Initialize the scraper with a target URL and optional retry count
        self.url = url
        self.retries = retries

    async def get_car_details(self):
        # Main async method to collect all car listings and their details
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)  # Launch browser in headless mode
            page = await browser.new_page()  # Open a new tab

            # Extend timeouts for slower pages
            page.set_default_navigation_timeout(3000000)
            page.set_default_timeout(3000000)

            cars = []  # Will store all car data

            for attempt in range(self.retries):  # Retry logic
                try:
                    await page.goto(self.url, wait_until="domcontentloaded")  # Navigate to listing page
                    await page.wait_for_selector('.list-item-car', timeout=3000000)  # Wait for car cards

                    # Get all car cards on the page
                    car_cards = await page.query_selector_all('.list-item-car')
                    for card in car_cards:
                        # Extract individual car data
                        link = await self.scrape_link(card)
                        brand = await self.scrape_brand(card)
                        price = await self.scrape_price(card)
                        title = await self.scrape_title(card)
                        details = await self.scrape_more_details(link)

                        # Combine all fields into one dict
                        cars.append({
                            'brand': brand,
                            'price': price,
                            'link': link,
                            'title': title,
                            **details
                        })

                    break  # Exit loop if successful

                except Exception as e:
                    print(f"Attempt {attempt + 1} failed for {self.url}: {e}")
                    if attempt + 1 == self.retries:
                        print(f"Max retries reached for {self.url}. Returning partial results.")
                        break
                finally:
                    await page.close()
                    if attempt + 1 < self.retries:
                        page = await browser.new_page()

            await browser.close()  # Close the browser completely
            return cars  # Return collected car data

    async def scrape_brand(self, card):
        # Extract brand name from car card
        element = await card.query_selector('.brand-car span')
        return await element.inner_text() if element else None

    async def scrape_price(self, card):
        # Extract price from car card
        element = await card.query_selector('.price span')
        return await element.inner_text() if element else None

    async def scrape_link(self, card):
        # Extract the full link to the car's detail page
        element = await card.query_selector('a')
        href = await element.get_attribute('href') if element else None
        return f"https://oogoocar.com{href}" if href else None

    async def scrape_more_details(self, url):
        # Navigate to detail page and extract more information
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                await page.goto(url, wait_until="domcontentloaded")

                # Extract various sections from the detail page
                submitter = await self.scrape_submitter(page)
                specification = await self.scrape_specification(page)
                description = await self.scrape_description(page)
                phone_number = await self.scrape_phone_number(page)
                ad_id = await self.scrape_id(page)
                relative_date = await self.scrape_relative_date(page)
                date_published = self.get_publish_date_arabic(relative_date)

                await browser.close()

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
            print(f"Error while scraping details from {url}: {e}")
            return {}

    async def scrape_submitter(self, page):
        # Extract submitter and post time
        element = await page.query_selector('.car-ad-posted figcaption')
        if not element:
            return None

        label = await element.query_selector('label')
        relative_date = await element.query_selector('p')

        return {
            'submitter': await label.inner_text() if label else None,
            'relative_date': await relative_date.inner_text() if relative_date else None
        }

    async def scrape_specification(self, page):
        # Extract car specification table (label-value format)
        elements = await page.query_selector_all('.specification ul li')

        specifications = {}
        for element in elements:
            x = await element.query_selector('h3')
            y = await element.query_selector('p')
            if x and y:
                specifications[await x.inner_text()] = await y.inner_text()

        return specifications

    async def scrape_description(self, page):
        # Extract the description section (if available)
        try:
            selector = '#description-section'  # The ID of the <pre> tag
            await page.wait_for_selector(selector, timeout=15000)  # Wait for element to load
            element = await page.query_selector(selector)
            description = await element.inner_text() if element else "No Description Found"
            return description
        except Exception as e:
            print(f"Error scraping description: {e}")
            return "Error in extracting description"

    async def scrape_title(self, card):
        # Extract model name and mileage info from title section
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
            print(f"Error scraping title: {e}")
            return {"model": "Error", "distance": "Error"}

    async def scrape_phone_number(self, page):
        # Extract phone number embedded in element's JSON
        element = await page.query_selector('.detail-contact-info .whatsapp')
        if element:
            properties = await element.get_attribute('mpt-properties')
            data = json.loads(properties)
            return data.get('mobile')
        return None

    async def scrape_id(self, page):
        # Extract ad ID from the same mpt-properties JSON
        element = await page.query_selector('.detail-contact-info .whatsapp')
        if element:
            properties = await element.get_attribute('mpt-properties')
            data = json.loads(properties)
            return data.get('AdId')
        return None

    async def scrape_relative_date(self, page):
        # Extract "published relative to now" text (Arabic)
        element = await page.query_selector('.car-ad-posted figcaption p')
        return await element.inner_text() if element else None

    def get_publish_date_arabic(self, relative_date):
        # Convert Arabic relative dates into full timestamp format
        current_time = datetime.now()

        # Regular expressions for Arabic relative dates
        hour_pattern = r'نُشر منذ (\d+) ساعة'
        day_pattern = r'نُشر منذ (\d+) يوم'
        one_day_pattern = r'نُشر منذ يوم'
        two_days_pattern = r'نُشر منذ يومين'
        three_days_pattern = r'نُشر منذ (\d+) أيام'

        match_hour = re.search(hour_pattern, relative_date)
        if match_hour:
            hours_ago = int(match_hour.group(1))
            publish_time = current_time - timedelta(hours=hours_ago)
            return publish_time.strftime("%Y-%m-%d %H:%M:%S")

        if re.search(one_day_pattern, relative_date):
            publish_time = current_time - timedelta(days=1)
            return publish_time.strftime("%Y-%m-%d %H:%M:%S")

        if re.search(two_days_pattern, relative_date):
            publish_time = current_time - timedelta(days=2)
            return publish_time.strftime("%Y-%m-%d %H:%M:%S")

        match_three_days = re.search(three_days_pattern, relative_date)
        if match_three_days:
            days_ago = int(match_three_days.group(1))
            publish_time = current_time - timedelta(days=days_ago)
            return publish_time.strftime("%Y-%m-%d %H:%M:%S")

        # Default fallback: assume it's more than 3 days ago
        publish_time = current_time - timedelta(days=3)
        return publish_time.strftime("%Y-%m-%d %H:%M:%S")
