from bs4 import BeautifulSoup
import requests
import multiprocessing
import re
import time
import itertools
from utils import log_info, save_to_mongo, get_mongo_db, update_mongo, regions_playstation
from requests.adapters import HTTPAdapter

n_processes = 200  # Adjust based on your system's performance
PLAYSTATION_URL = "https://store.playstation.com/en-us/pages/browse/1"

# Load proxies from file
with open("proxies.txt") as f:
    PROXIES = [line.strip() for line in f if line.strip()]

chunk_size = (len(PROXIES) + n_processes - 1) // n_processes
proxy_chunks = [PROXIES[i * chunk_size:(i + 1) * chunk_size] for i in range(n_processes)]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.playstation.com/",
    "Origin": "https://www.playstation.com",
    "DNT": "1",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive"
}

# Set up a requests session with proxy and retry logic
def create_session(proxy_list):
    proxy = next(itertools.cycle(proxy_list))
    session = requests.Session()
    session.proxies = {"http": proxy, "https": proxy}
    session.headers.update(HEADERS)
    session.mount('https://', HTTPAdapter(max_retries=3))
    return session

def get_total_pages(proxy_list):
    while True:
        try:
            session = create_session(proxy_list)
            response = session.get(PLAYSTATION_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            ol_tag = soup.select_one('ol.psw-l-space-x-1.psw-l-line-center.psw-list-style-none')
            total_pages = int(ol_tag.select('li')[-1].find('span', class_="psw-fill-x").text.strip())
            return total_pages
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching total pages: {e}")
            if response.status_code == 403:
                print("Access denied. Trying with a new proxy...")
                time.sleep(10)
                continue
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(10)
            continue

def fetch_page_links(start_page, end_page, proxy_list):
    links = []
    for i in range(start_page, end_page):
        try:
            url = f"https://store.playstation.com/en-us/pages/browse/{i + 1}"
            session = create_session(proxy_list)
            response = session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            all_links = [a['href'] for a in soup.find_all('a', href=True)]
            filtered_links = [link for link in all_links if re.match(r"/en-us/concept/\d+", link)]
            links.extend(filtered_links)
        except requests.RequestException as e:
            print(f"Error fetching page {i + 1}: {e}")
    return links

def fetch_playstation_games(total_pages):
    chunk_size = (total_pages + n_processes - 1) // n_processes
    ranges = [(i * chunk_size, min((i + 1) * chunk_size, total_pages)) for i in range(n_processes)]

    with multiprocessing.Pool(processes=n_processes) as pool:
        results = pool.starmap(fetch_page_links, [(start, end, proxy_chunks[i]) for i, (start, end) in enumerate(ranges)])

    return [link for sublist in results for link in sublist]

def process_playstation_game(game, proxy_list):
    try:
        url = f"https://store.playstation.com{game}"
        session = create_session(proxy_list)
        response = session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        def get_text_safe(tag):
            return tag.text.strip() if tag else "N/A"

        game_details = {
            "title": get_text_safe(soup.find(attrs={"data-qa": "mfe-game-title#name"})),
            "short_description": get_text_safe(soup.find(attrs={"class": "psw-l-switcher psw-with-dividers"})),
            "full_description": get_text_safe(soup.find(attrs={"data-qa": "pdp#overview"})),
            "header_image": soup.find('img', {'data-qa': 'gameBackgroundImage#heroImage#preview'})['src']
                            if soup.find('img', {'data-qa': 'gameBackgroundImage#heroImage#preview'}) else "N/A",
            "rating": get_text_safe(soup.find(attrs={"data-qa": "mfe-star-rating#overall-rating#average-rating"})),
            "publisher": get_text_safe(soup.find(attrs={'data-qa': "gameInfo#releaseInformation#publisher-value"})),
            "platforms": get_text_safe(soup.find(attrs={'data-qa': 'gameInfo#releaseInformation#platform-value'})),
            "release_date": get_text_safe(soup.find(attrs={'data-qa': 'gameInfo#releaseInformation#releaseDate-value'})),
            "categories": [span.text.strip() for span in soup.find(attrs={'data-qa': 'gameInfo#releaseInformation#genre-value'}).find_all('span')] if soup.find(attrs={'data-qa': 'gameInfo#releaseInformation#genre-value'}) else [],
            "prices": fetch_game_prices(game, proxy_list),
        }
        return game_details
    except requests.RequestException as e:
        print(f"Network error fetching game {game}: {e}")
    except Exception as e:
        print(f"Error processing game {game}: {e}")

def fetch_game_prices(game, proxy_list):
    prices = {"us": "N/A"}
    for region in regions_playstation:
        while True:
            try:
                region_url = f"https://store.playstation.com{game.replace('en-us', region)}"
                session = create_session(proxy_list)
                response = session.get(region_url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                price_tag = soup.find(attrs={"data-qa": "mfeCtaMain#offer0#finalPrice"})
                prices[region.split('-')[1]] = price_tag.text.strip() if price_tag else "Not Available"
                break
            except requests.RequestException as e:
                time.sleep(5)
    return prices

def process_games_range(start_index, end_index, games, proxy_list):
    db = get_mongo_db()

    for index in range(start_index, end_index):
        try:
            game_data = process_playstation_game(games[index], proxy_list)
            if game_data:
                save_to_mongo(db, "playstation_games", game_data)
            else:
                print(f"Missing data for game {index}")
        except Exception as e:
            print(f"Error processing game at index {index}: {e}")

def main():
    log_info("Waiting for fetching Playstation games...")
    total_pages = get_total_pages(PROXIES)
    games = fetch_playstation_games(total_pages)

    total_games = len(games)
    if total_games == 0:
        log_info("No games found to process.")
        return

    log_info(f"Fetched {total_games} games in Playstation.")
    chunk_size = (total_games + n_processes - 1) // n_processes
    ranges = [(i * chunk_size, min((i + 1) * chunk_size, total_games)) for i in range(n_processes)]

    with multiprocessing.Pool(processes=n_processes) as pool:
        pool.starmap(process_games_range, [(start, end, games, proxy_chunks[i]) for i, (start, end) in enumerate(ranges)])

    db = get_mongo_db()
    update_mongo(db, "playstation_games")
    log_info("All Playstation processes completed.")

if __name__ == "__main__":
    main()
