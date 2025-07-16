import asyncio
from playwright.async_api import async_playwright  # Async Playwright for browser automation
import nest_asyncio  # Allow nested event loops (important in Jupyter or nested async environments)
import re  # Regular expressions for parsing relative dates
from datetime import datetime, timedelta  # Date and time manipulation
import json  # For parsing JSON attributes from HTML

# Allow nested event loops (useful when running in notebooks or nested async environments)
nest_asyncio.apply()

class OogooCertified:
    def __init__(self, url, retries=3):
        # Initialize with target URL and retry count for scraping failures
        self.url = url
        self.retries = retries

    async def get_car_details(self):
        """
        Main method to scrape car listings from the provided URL.
        Extracts metadata and calls detail page scraping for each car.
        """
        async with async_playwright() as p:
            # Launch Chromium in headless mode
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Set high timeouts for slower network/pages
            page.set_default_navigation_timeout(3000000)
            page.set_default_timeout(3000000)

            cars = []  # Store all car dictionaries

            for attempt in range(self.retries):  # Retry loop for robustness
                try:
                    # Navigate to the listing page and wait until DOM is loaded
                    await page.goto(self.url, wait_until="domcontentloaded")
                    await page.wait_for_selector('.list-item-car', timeout=3000000)

                    # Get all car card elements
                    car_cards = await page.query_selector_all('.list-item-car')

                    for card in car_cards:
                        # Extract basic metadata
                        link = await self.scrape_link(card)
                        brand = await self.scrape_brand(card)
                        price = await self.scrape_price(card)
                        title = await self.scrape_title(card)
                        details = await self.scrape_more_details(link)  # Scrape detail page

                        # Merge all data into one dictionary
                        cars.append({
                            'brand': brand,
                            'price': price,
                            'link': link,
                            'title': title,
                            **details
                        })

                    break  # Exit retry loop on success

                except Exception as e:
                    # Log error and retry if needed
                    print(f"Attempt {attempt + 1} failed for {self.url}: {e}")
                    if attempt + 1 == self.retries:
                        print(f"Max retries reached for {self.url}. Returning partial results.")
                        break
                finally:
                    await page.close()
                    if attempt + 1 < self.retries:
                        page = await browser.new_page()  # Start new page for next attempt

            await browser.close()
            return cars  # Return the list of cars collected

    async def scrape_brand(self, card):
        # Extract car brand text from the card
        element = await card.query_selector('.brand-car span')
        return await element.inner_text() if element else None

    async def scrape_price(self, card):
        # Extract car price text from the card
        element = await card.query_selector('.price span')
        return await element.inner_text() if element else None

    async def scrape_link(self, card):
        # Extract the relative link and build full URL
        element = await card.query_selector('a')
        href = await element.get_attribute('href') if element else None
        return f"https://oogoocar.com{href}" if href else None

    async def scrape_title(self, card):
        """
        Extract model and distance info shown in the title section of the card.
        Returns a dictionary with model and distance strings.
        """
        try:
            title_element = await card.query_selector('.title-car')
            if not title_element:
                return {"model": None, "distance": None}

            # Extract model and distance span elements
            model = await title_element.query_selector('span:nth-child(1)')
            distance = await title_element.query_selector('span:nth-child(2)')

            # Return texts with fallbacks
            model_text = await model.inner_text() if model else "Model not found"
            distance_text = await distance.inner_text() if distance else "Distance not found"

            return {
                "model": model_text,
                "distance": distance_text
            }

        except Exception as e:
            # Log and return error fallback
            print(f"Error scraping title: {e}")
            return {"model": "Error", "distance": "Error"}

    async def scrape_more_details(self, url):
        """
        Opens the detail page for a car and extracts:
        submitter info, specifications, description, phone number, ad ID, and publish date.
        """
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                await page.goto(url, wait_until="domcontentloaded")

                # Extract all detailed info
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
            # On failure, log and return empty dict
            print(f"Error while scraping details from {url}: {e}")
            return {}

    async def scrape_submitter(self, page):
        # Extract submitter name and date posted from detail page
        element = await page.query_selector('.car-ad-posted figcaption')
        if not element:
            return None

        label = await element.query_selector('label')  # Submitter name
        relative_date = await element.query_selector('p')  # Posted time

        return {
            'submitter': await label.inner_text() if label else None,
            'relative_date': await relative_date.inner_text() if relative_date else None
        }

    async def scrape_specification(self, page):
        # Extract car specifications as key-value pairs
        elements = await page.query_selector_all('.specification ul li')

        specifications = {}
        for element in elements:
            x = await element.query_selector('h3')  # Spec key
            y = await element.query_selector('p')   # Spec value
            if x and y:
                specifications[await x.inner_text()] = await y.inner_text()

        return specifications

    async def scrape_description(self, page):
        """
        Scrape the full description of the car from the detail page.
        Handles any error by returning an error message.
        """
        try:
            selector = '#description-section'  # The <pre> tag with the description
            await page.wait_for_selector(selector, timeout=15000)
            element = await page.query_selector(selector)
            description = await element.inner_text() if element else "No Description Found"
            return description
        except Exception as e:
            print(f"Error scraping description: {e}")
            return "Error in extracting description"

    async def scrape_phone_number(self, page):
        # Extract phone number from custom attribute inside .whatsapp button
        element = await page.query_selector('.detail-contact-info .whatsapp')
        if element:
            properties = await element.get_attribute('mpt-properties')
            data = json.loads(properties)
            return data.get('mobile')
        return None

    async def scrape_id(self, page):
        # Extract ad ID from the same custom JSON attribute
        element = await page.query_selector('.detail-contact-info .whatsapp')
        if element:
            properties = await element.get_attribute('mpt-properties')
            data = json.loads(properties)
            return data.get('AdId')
        return None

    async def scrape_relative_date(self, page):
        # Extract the relative published time (e.g., "نُشر منذ يوم")
        element = await page.query_selector('.car-ad-posted figcaption p')
        return await element.inner_text() if element else None

    def get_publish_date_arabic(self, relative_date):
        """
        Converts relative Arabic time phrases into a full datetime string (e.g., "2 days ago" → 2024-07-15 13:00:00).
        """
        current_time = datetime.now()

        # Arabic regex patterns for relative times
        hour_pattern = r'نُشر منذ (\d+) ساعة'
        day_pattern = r'نُشر منذ (\d+) يوم'
        one_day_pattern = r'نُشر منذ يوم'
        two_days_pattern = r'نُشر منذ يومين'
        three_days_pattern = r'نُشر منذ (\d+) أيام'

        # Check if published hours ago
        match_hour = re.search(hour_pattern, relative_date)
        if match_hour:
            hours_ago = int(match_hour.group(1))
            publish_time = current_time - timedelta(hours=hours_ago)
            return publish_time.strftime("%Y-%m-%d %H:%M:%S")

        # One day ago
        if re.search(one_day_pattern, relative_date):
            publish_time = current_time - timedelta(days=1)
            return publish_time.strftime("%Y-%m-%d %H:%M:%S")

        # Two days ago
        if re.search(two_days_pattern, relative_date):
            publish_time = current_time - timedelta(days=2)
            return publish_time.strftime("%Y-%m-%d %H:%M:%S")

        # Three or more days ago (matched using number)
        match_three_days = re.search(three_days_pattern, relative_date)
        if match_three_days:
            days_ago = int(match_three_days.group(1))
            publish_time = current_time - timedelta(days=days_ago)
            return publish_time.strftime("%Y-%m-%d %H:%M:%S")

        # Default fallback: assume 3 days ago
        publish_time = current_time - timedelta(days=3)
        return publish_time.strftime("%Y-%m-%d %H:%M:%S")
