import os
import logging
import time
from bs4 import BeautifulSoup
from pymongo import MongoClient
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

load_dotenv()

chromedriver_path = os.getenv("chromedriver_path")
chrome_path = os.getenv("chrome_path")

regions_playstation = [
    # 'en-us',
    'en-eu',
    'de-at',
    'es-ar',
    'ar-bh',
    'fr-be',
    'pt-br',
    'en-gb',
    'de-de',
    'en-hk',
    'en-gr',
    'en-in',
    'es-es',
    'it-it',
    'ar-qa',
    'en-kw',
    'ar-lb',
    'de-lu',
    'nl-nl',
    'ar-ae',
    'ar-om',
    'pl-pl',
    'pt-pt',
    "ro-ro",
    'ar-sa',
    'sl-si',
    'sk-sk',
    'tr-tr',
    'fi-fi',
    'fr-fr',
    'en-za'
]

regions_steam = [
        "us",  # United States
        "gb",  # United Kingdom
        "eu",  # European Union
        "jp",  # Japan
        "in",  # India
        "br",  # Brazil
        "au",  # Australia
        "ca",  # Canada
        "ru",  # Russia
        "cn",  # China
        "kr",  # South Korea
        "mx",  # Mexico
        "za",  # South Africa
        "ar",  # Argentina
        "tr",  # Turkey
        "id",  # Indonesia
        "sg",  # Singapore
        "ph",  # Philippines
        "th",  # Thailand
        "my",  # Malaysia
        "nz",  # New Zealand
        "sa",  # Saudi Arabia
        "ae",  # United Arab Emirates
    ]

regions_xbox = [
        # "en-us",  # United States as default
        "en-gb",  # United Kingdom      
        "en-eu",  # European Union      
        "en-in",  # India               
        "pt-br",  # Brazil              
        "en-au",  # Australia           
        "en-ca",  # Canada
        "ru-ru",  # Russia              
        "zh-cn",  # China               
        "es-mx",  # Mexico              
        "en-za",  # South Africa         
        "es-ar",  # Argentina
        "tr-tr",  # Turkey               
        "ar-sa",  # Saudi Arabia         
        "ar-ae",  # United Arab Emirates 
        "en-hu",  # Hungary              
        "es-co",  # Colombia             
        "en-pl",  # Poland              
        "en-no",  # Norway              
    ]

regions_nintendo = [
    "https://www.nintendo.com/en-gb/Search/Search-299117.html?f=147394-86", # United Kingdom
    "https://www.nintendo.com/de-ch/Suche-/Suche-299117.html?f=147394-86", # Switzerland
    "https://www.nintendo.com/de-de/Suche-/Suche-299117.html?f=147394-86", # Germany
    "https://www.nintendo.com/fr-fr/Rechercher/Rechercher-299117.html?f=147394-5-81", # France
    "https://www.nintendo.com/it-it/Cerca/Cerca-299117.html?f=147394-86", # Italy
    "https://www.nintendo.com/es-es/Buscar/Buscar-299117.html?f=147394-86", # Spain
    "https://www.nintendo.com/nl-nl/Zoeken/Zoeken-299117.html?f=147394-86", # Netherlands
    "https://www.nintendo.com/pt-pt/Pesquisar/Pesquisa-299117.html?f=147394-86", # Portugal
    "https://www.nintendo.com/de-at/Suche-/Suche-299117.html?f=147394-86", # Austria
]

# Database configuration
def get_mongo_db():
    mongo_uri = os.getenv("MONGO_URI")
    client = MongoClient(mongo_uri)
    db = client["test"]
    return db

def update_mongo(db, collection_name):
    db[collection_name].drop()
    db[f"{collection_name}_tmp"].rename(collection_name)

def save_to_mongo(db, collection_name, data):
    collection = db[f"{collection_name}_tmp"]
    collection.insert_one(data)
    # title = data.get("title")
    # if title:
    #     collection = db[collection_name]
    #     existing_data = collection.find_one({"title" : title})
    #     if existing_data:
    #         collection.update_one(
    #             {"_id": existing_data["_id"]},
    #             {"$set": data}
    #         )
    #     else:
    #         collection.insert_one(data)

def get_selenium_browser(retries=3):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--enable-unsafe-swiftshader")
    options.add_argument("--disable-software-rasterizer") # Prevent fallback errors
    options.add_argument("--disable-dev-shm-usage")  # Use shared memory
    options.add_argument("--no-sandbox")            # Avoid sandboxing (useful in Docker environments)
    options.add_argument("--max-old-space-size=4096")  # Limit memory usage (4 GB)
    # Adjust path if needed
    # options.binary_location = chrome_path
    service = Service(chromedriver_path)
    return webdriver.Chrome(service=service, options=options)

def click_loadmore_btn(browser, btn_dom):
    count = 0
    while True:
        try:
            btn = WebDriverWait(browser, 60).until(
                EC.element_to_be_clickable((By.XPATH, btn_dom))
            )
        except TimeoutException:
            print("Timeout: Load more button not found or not clickable.")
            return browser
        except Exception as e:
            print(f"Error processing game: {e}")
            print("-"*10, "! load more : exception occur : plz check the network !", "-"*10)
            time.sleep(60)
            continue
        btn = browser.find_element(By.XPATH, btn_dom)
        btn.click()
        count += 1
        if(count % 50 == 0):
            print("-"*10, "Load more button", count, " times clikced in Xbox","-"*10)

def search_game(browser, search_dom, result_dom, title):
    try:
        locator = (By.CSS_SELECTOR, search_dom)
        WebDriverWait(browser, 10).until(
            EC.presence_of_all_elements_located(locator)  # Wait for matching element
        )
        search_input = browser.find_elements(*locator)[-1]

        WebDriverWait(browser, 10).until(EC.element_to_be_clickable(search_input))
        search_input.send_keys(title)
        search_input.send_keys(Keys.RETURN)

        locator = (By.CSS_SELECTOR, result_dom)
        WebDriverWait(browser, 10).until(
            EC.visibility_of_all_elements_located(locator)
        )
        soup = BeautifulSoup(browser.page_source, 'html.parser')
        return soup
    except TimeoutException:
        return []

# Configure logging
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    filename="scraper.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# Remove unwanted logs from third-party libraries
logging.getLogger().setLevel(logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.CRITICAL)  # Suppress Flask logs
logging.getLogger('urllib3').setLevel(logging.CRITICAL)   # Suppress HTTP requests warnings
logging.getLogger('asyncio').setLevel(logging.CRITICAL)   # Suppress asyncio warnings
logging.getLogger('sqlalchemy').setLevel(logging.CRITICAL)  # Suppress SQLAlchemy warnings

def log_info(message):
    logging.info(message)