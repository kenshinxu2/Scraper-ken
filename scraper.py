"""Web scraper for aniwaves.ru"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote_plus


class AniWavesScraper:
    def __init__(self):
        self.base_url = "https://aniwaves.ru"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    
    def search_anime(self, query):
        """Search for anime by name"""
        try:
            search_url = f"{self.base_url}/search?keyword={quote_plus(query)}"
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Find anime items
            anime_items = soup.find_all('div', class_='item')
            
            for item in anime_items[:10]:  # Limit to 10 results
                try:
                    link = item.find('a', class_='film-poster')
                    if not link:
                        continue
                    
                    anime_url = self.base_url + link.get('href', '')
                    title_elem = item.find('h3', class_='film-name')
                    title = title_elem.text.strip() if title_elem else "Unknown"
                    
                    img = item.find('img')
                    poster = img.get('data-src') or img.get('src', '') if img else ''
                    
                    # Check for sub/dub
                    badges = item.find_all('span', class_='badge')
                    has_sub = any('sub' in b.text.lower() for b in badges)
                    has_dub = any('dub' in b.text.lower() for b in badges)
                    
                    results.append({
                        'title': title,
                        'url': anime_url,
                        'poster': poster,
                        'has_sub': has_sub,
                        'has_dub': has_dub
                    })
                except Exception:
                    continue
            
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def get_anime_details(self, anime_url):
        """Get anime details including episodes"""
        try:
            response = self.session.get(anime_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Get title
            title_elem = soup.find('h1', class_='film-name')
            title = title_elem.text.strip() if title_elem else "Unknown"
            
            # Get description
            desc_elem = soup.find('div', class_='film-description')
            description = desc_elem.text.strip() if desc_elem else ""
            
            # Get episodes
            episodes = []
            ep_list = soup.find('div', class_='episodes-list')
            
            if ep_list:
                ep_items = ep_list.find_all('a', class_='episode-item')
                for ep in ep_items:
                    ep_num = ep.get('data-number', '')
                    ep_title = ep.text.strip()
                    ep_url = self.base_url + ep.get('href', '')
                    if ep_num:
                        episodes.append({
                            'number': int(ep_num) if ep_num.isdigit() else ep_num,
                            'title': ep_title,
                            'url': ep_url
                        })
            
            # Alternative: check for ajax episode loading
            if not episodes:
                film_id = self._extract_film_id(response.text)
                if film_id:
                    episodes = self._get_episodes_ajax(film_id)
            
            # Check for sub/dub availability
            servers = soup.find_all('div', class_='server-item')
            has_sub = any('sub' in s.get('data-type', '').lower() for s in servers)
            has_dub = any('dub' in s.get('data-type', '').lower() for s in servers)
            
            return {
                'title': title,
                'description': description,
                'episodes': sorted(episodes, key=lambda x: x['number'] if isinstance(x['number'], int) else 0),
                'has_sub': has_sub or True,  # Default to True
                'has_dub': has_dub or False,
                'film_id': film_id if 'film_id' in locals() else None
            }
        except Exception as e:
            print(f"Details error: {e}")
            return None
    
    def _extract_film_id(self, html):
        """Extract film ID from page HTML"""
        match = re.search(r'filmId\s*[=:]\s*["\']?(\d+)', html)
        if match:
            return match.group(1)
        match = re.search(r'data-id\s*=\s*["\'](\d+)', html)
        if match:
            return match.group(1)
        return None
    
    def _get_episodes_ajax(self, film_id):
        """Get episodes via AJAX endpoint"""
        try:
            ajax_url = f"{self.base_url}/ajax/episode/list/{film_id}"
            response = self.session.get(ajax_url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                html = data.get('html', data.get('result', ''))
                soup = BeautifulSoup(html, 'html.parser')
                
                episodes = []
                ep_items = soup.find_all('a', class_='episode-item')
                for ep in ep_items:
                    ep_num = ep.get('data-number', '')
                    ep_title = ep.text.strip()
                    ep_id = ep.get('data-id', '')
                    if ep_num:
                        episodes.append({
                            'number': int(ep_num) if ep_num.isdigit() else ep_num,
                            'title': ep_title,
                            'id': ep_id
                        })
                return episodes
        except Exception as e:
            print(f"AJAX error: {e}")
        return []
    
    def get_video_sources(self, episode_url, episode_id=None, version="sub"):
        """Get video sources for an episode"""
        try:
            # If we have episode_id, use AJAX endpoint
            if episode_id:
                ajax_url = f"{self.base_url}/ajax/episode/servers"
                params = {'episodeId': episode_id, 'type': version}
                response = self.session.get(ajax_url, params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    html = data.get('html', data.get('result', ''))
                    return self._parse_video_sources(html)
            
            # Otherwise scrape episode page
            response = self.session.get(episode_url, timeout=30)
            response.raise_for_status()
            
            return self._parse_video_sources(response.text)
        except Exception as e:
            print(f"Video sources error: {e}")
            return {}
    
    def _parse_video_sources(self, html):
        """Parse video sources from HTML"""
        sources = {}
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for video sources in different formats
            # Method 1: data-src attributes
            server_items = soup.find_all('div', class_='server-item')
            for server in server_items:
                quality = server.get('data-quality', '720p')
                src = server.get('data-src', '')
                if src:
                    sources[quality] = src
            
            # Method 2: JSON embedded in script
            scripts = soup.find_all('script')
            for script in scripts:
                text = script.string if script else ''
                if text and 'sources' in text:
                    # Extract JSON with sources
                    match = re.search(r'sources\s*:\s*(\[.*?\])', text, re.DOTALL)
                    if match:
                        import json
                        try:
                            src_list = json.loads(match.group(1))
                            for src in src_list:
                                if isinstance(src, dict):
                                    quality = src.get('label', '720p')
                                    url = src.get('file', '')
                                    if url:
                                        sources[quality] = url
                        except:
                            pass
            
            # Method 3: Direct video tag
            video = soup.find('video')
            if video:
                src = video.get('src', '')
                if src:
                    sources['720p'] = src
                
                # Check source tags
                for source in video.find_all('source'):
                    quality = source.get('label', source.get('res', '720p'))
                    src = source.get('src', '')
                    if src:
                        sources[quality] = src
                        
        except Exception as e:
            print(f"Parse error: {e}")
        
        return sources
    
    def download_video(self, video_url, output_path):
        """Download video from URL"""
        try:
            response = self.session.get(video_url, stream=True, timeout=120)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            print(f"Download error: {e}")
            return False


# Global scraper instance
scraper = AniWavesScraper()
