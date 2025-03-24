import requests
import time
import re
import multiprocessing
from bs4 import BeautifulSoup
from utils import log_info, get_mongo_db, save_to_mongo, update_mongo, get_selenium_browser, search_game, regions_nintendo

n_processes = 10

API_URL = "https://api.sampleapis.com/switch/games" # API endpoint
JAPAN_URL = "https://www.nintendo.com/jp/software/switch/index.html?sftab=all"

def fetch_games():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Nintendo : Error fetching games: {e}")
        time.sleep(60)
        return []

def process_nintendo_game(browser, game):
    # retrieve data by api
    title = game.get("name", "N/A")
    categories = game.get("genre", [])
    publisher = game.get("publishers")[0] if game.get("publishers") else "N/A"
    release_date = game.get("releaseDates", {})['NorthAmerica']
    
    tmp = title.replace("&", "and")
    tmp = tmp.lower()
    tmp = re.sub(r'[^a-z0-9 ]', '', tmp)
    tmp = tmp.replace(" ","-")

    game_link = "https://www.nintendo.com/us/store/products/" + tmp + "-switch/"
    
    while True:
        try:
            browser.get(game_link)
            soup = BeautifulSoup(browser.page_source, "html.parser")

            # cover image
            tmp = soup.find('img',{'alt': title + " 1"})
            header_image = tmp['src'] if tmp else "No Game Header Imgae"

            # Rating
            tmp = soup.find('h3', string='ESRB rating')
            rating = tmp.find_next('div').find('a').text.strip() if tmp else "No Rating"

            # Short description
            tmp = soup.find('meta', {'name':'description'})['content']
            short_description = tmp if tmp else "No Short Description"

            # Platform
            tmp = soup.find('div', class_='sc-1i9d4nw-14 gxzajP')
            platforms = tmp.find('span').get_text() if tmp else "No platform"

            # Screenshots 
            tmp = soup.find('div', {'class' : '-fzAB SUqIq'})
            screenshots = [img['src'] for img in tmp.find_all('img')] if tmp else []

            # Prices in different regions
            prices = {}
            # USA
            tmp = (soup.find('span', class_='W990N QS4uJ') or soup.find('div', class_='o2BsP QS4uJ'))
            tmp = tmp.text.strip() if tmp else ""
            prices["us"] = tmp.split(':')[-1].strip() if tmp else "NOT AVAILABLE SEPARATELY"

            # Brazil
            browser.get(game_link.replace("/us/",'/pt-br/'))
            soup = BeautifulSoup(browser.page_source, 'html.parser')
            tmp = (soup.find('span', class_='W990N QS4uJ') or soup.find('div', class_='o2BsP QS4uJ'))
            tmp = tmp.text.strip().replace('\xa0',' ') if tmp else ""
            prices['br'] = tmp.split(':')[-1].strip() if tmp else "NOT AVAILABLE SEPARATSELY"

            # EUA
            index = 0
            while index < len(regions_nintendo):
                region_url = regions_nintendo[index]
                if index < 3:
                    browser.get(region_url)
                    soup = search_game(browser, 'input[type="search"]', 'span[class=""]', title)
                    if soup:
                        tmp = soup.find_all('ul', class_="results")[-1]
                        tmp = tmp.find('li', class_="searchresult_row page-list-group-item col-xs-12")
                        tmp = tmp.find('p', class_='price-small')
                        price = tmp.find_all('span')[-1].text.strip() if tmp else ""
                        price.replace("*", ' ')
                    else: price = ""
                else:
                    price = prices["de"]
                prices[region_url.split('/')[3].split('-')[1]] = price if price else "NOT AVAILABLE SEPARATELY"
                index += 1

            # Japan
            browser.get(JAPAN_URL)
            search_dom = 'input[class="nc3-c-search__boxText nc3-js-megadrop__focusable nc3-js-searchBox__text"]'
            result_dom = 'div[class="nc3-c-softCard__listItemPrice"]'
            soup = search_game(browser, search_dom, result_dom, title)
            price = soup.find('div', class_='nc3-c-softCard__listItemPrice') if soup else ""
            prices['jp'] = price.text.strip() if price else "NOT AVAILABLE SEPARATELY"

            game_data = {
                    "title": title,                          
                    "categories": categories,
                    "short_description": short_description,
                    "full_description": [],
                    "screenshots": screenshots,
                    "header_image": header_image,
                    "rating": rating,
                    "publisher": publisher,
                    "platforms": platforms,
                    "release_date": release_date,
                    "prices": prices
                }
            return game_data
        except Exception as e:
            print(f"Don't worry. Fixing Error Nintendo game: {e}")
            time.sleep(60)

def process_games_range(start_index, end_index, games):
    db = get_mongo_db()
    browser = get_selenium_browser()

    for index in range(start_index, end_index):
        try:
            game_data = process_nintendo_game(browser, games[index])
            save_to_mongo(db, "nintendo_games", game_data)
        except Exception as e:
            print(f"Error processing game at index {index}: {str(e)}")

    browser.quit()

def main():
    log_info("Waiting for fetching Nintendo games...")
    games = fetch_games()

    total_games = len(games)
    if total_games == 0:
        log_info("No games found to process.")
        return
    
    # Calculate the ranges for each subprocess
    chunk_size = (total_games + n_processes - 1) // n_processes
    ranges = [(i * chunk_size, min((i + 1) * chunk_size, total_games)) for i in range(n_processes)]

    # Create and start subprocesses
    processes = []
    for start, end in ranges:
        process = multiprocessing.Process(target=process_games_range, args=(start, end, games))
        processes.append(process)
        process.start()

    # Wait for all processes to complete
    for process in processes:
        process.join()

    db = get_mongo_db()
    update_mongo(db, "nintendo_games")
    log_info("All Nintendo processes completed.")

if __name__ == "__main__":
    main()