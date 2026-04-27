from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

BASE_URL = "https://www.mechanicar.com"


def get_selenium_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # PRO-TIP: Disable image loading to drastically speed up Selenium!
    options.add_argument('--blink-settings=imagesEnabled=false')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def run_deep_scrape_generator(keyword: str, limit: int):
    driver = get_selenium_driver()
    search_url = f"{BASE_URL}/germany?search_keywords={keyword}"

    driver.get(search_url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.job_listing-clickbox"))
        )
    except:
        driver.quit()
        yield {"type": "info", "message": "No results found or page took too long to load."}
        return

    # Scroll just enough to grab the requested limit
    if limit > 10:
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(2):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height: break
            last_height = new_height

    soup = BeautifulSoup(driver.page_source, "html.parser")
    # Apply the dynamic limit right here
    links = soup.find_all("a", class_="job_listing-clickbox", limit=limit)
    urls = [urljoin(BASE_URL, a.get("href")) for a in links if a.get("href")]

    yield {"type": "info", "message": f"Found {len(urls)} garages. Starting deep scrape..."}

    try:
        for u in urls:
            driver.get(u)
            # Reduced sleep time slightly since images aren't loading
            time.sleep(1)
            dsoup = BeautifulSoup(driver.page_source, "html.parser")

            def txt(sel):
                el = dsoup.select_one(sel)
                return el.text.strip() if el else "N/A"

            phone_tag = dsoup.select_one("a[href^='tel:']")
            phone = phone_tag["href"].replace("tel:", "") if phone_tag else "N/A"

            map_tag = dsoup.select_one("#get-directions")
            map_link = map_tag["href"] if map_tag else "N/A"

            hours = {}
            for row in dsoup.select(".business-hour"):
                d = row.select_one(".day")
                t = row.select_one(".business-hour-time")
                if d and t: hours[d.text.strip()] = t.text.strip()

            data = {
                "source": "mechanicar",
                "source_url": u,
                "name": txt("h1.job_listing-title"),
                "location": txt(".job_listing-location"),
                "phone": phone,
                "extra_data": {
                    "address": txt(".job_listing-address"),
                    "map_link": map_link,
                    "services": [s.text.strip() for s in dsoup.select(".job_listing_tag-list a")],
                    "overview": txt("#listify_widget_panel_listing_content-1"),
                    "rating": txt("[itemprop='ratingValue']"),
                    "hours": hours
                }
            }
            yield {"type": "result", "data": data}

    except GeneratorExit:
        pass  # Caught if user hits STOP button
    finally:
        driver.quit()
        yield {"type": "done", "message": "Scraping complete."}