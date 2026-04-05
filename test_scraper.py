import requests
from bs4 import BeautifulSoup
import re

def search_anime(query):
    url = f"https://www.animedubhindi.me/?s={query.replace(' ', '+')}"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    results = []
    for article in soup.find_all('article'):
        title_tag = article.find('h2', class_='entry-title') or article.find('h3', class_='entry-title')
        if title_tag and title_tag.find('a'):
            results.append({
                "title": title_tag.find('a').text.strip(),
                "url": title_tag.find('a')['href']
            })
    return results

def get_episodes(anime_url):
    r = requests.get(anime_url)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Find the download page link
    download_btn = soup.find('a', string=re.compile(r'Download / Watch', re.I))
    if not download_btn:
        for a in soup.find_all('a', href=True):
            if 'links.animedubhindi.me' in a['href']:
                download_page_url = a['href']
                break
        else:
            return None
    else:
        download_page_url = download_btn['href']
        
    print(f"Download Page: {download_page_url}")
    r2 = requests.get(download_page_url)
    soup2 = BeautifulSoup(r2.text, 'html.parser')
    
    episodes = {}
    current_ep = None
    
    # The structure is usually <h2>Episode: XX</h2> followed by qualities
    for element in soup2.find_all(['h2', 'h3', 'h4', 'p', 'div']):
        text = element.text.strip()
        ep_match = re.search(r'Episode:\s*(\d+)', text, re.I)
        if ep_match:
            current_ep = ep_match.group(1)
            episodes[current_ep] = {}
            continue
        
        if current_ep:
            quality_match = re.search(r'(\d+P)', text, re.I)
            if quality_match:
                quality = quality_match.group(1)
                links_container = element.find_next_sibling() if not element.find_all('a') else element
                links = {}
                for a in links_container.find_all('a', href=True):
                    server = a.text.strip()
                    if server:
                        links[server] = a['href']
                if links:
                    episodes[current_ep][quality] = links
    return episodes

if __name__ == "__main__":
    print("Testing Search...")
    res = search_anime("jujutsu kaisen")
    for i, r in enumerate(res):
        print(f"{i}: {r['title']}")
    
    if res:
        print("\nTesting Episode Scrape for first result...")
        eps = get_episodes(res[0]['url'])
        if eps:
            for ep, qualities in list(eps.items())[:2]:
                print(f"Episode {ep}: {list(qualities.keys())}")
        else:
            print("No episodes found.")
