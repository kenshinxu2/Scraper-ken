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
            
            anime_items = soup.find_all('div', class_='item')
            if not anime_items:
                anime_items = soup.find_all('div', class_='film-poster')
            
            for item in anime_items[:10]:
                try:
                    link = item.find('a', class_='film-poster') or item.find('a')
                    if not link:
                        continue
                    
                    href = link.get('href', '')
                    if not href.startswith('http'):
                        anime_url = self.base_url + href
                    else:
                        anime_url = href
                    
                    title_elem = item.find('h3', class_='film-name') or item.find('a', class_='film-poster')
                    title = title_elem.text.strip() if title_elem and title_elem.text else link.get('title', 'Unknown')
                    if title == 'Unknown' and link.get('data-title'):
                        title = link.get('data-title')
                    
                    img = item.find('img')
                    poster = ''
                    if img:
                        poster = img.get('data-src') or img.get('src', '')
                    
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
                except Exception as e:
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
            
            title_elem = soup.find('h1', class_='film-name') or soup.find('h1')
            title = title_elem.text.strip() if title_elem else "Unknown"
            
            desc_elem = soup.find('div', class_='film-description') or soup.find('div', class_='description')
            description = desc_elem.text.strip() if desc_elem else ""
            
            episodes = []
            ep_list = soup.find('div', class_='episodes-list') or soup.find('div', id='episodes-list')
            
            if ep_list:
                ep_items = ep_list.find_all('a', class_='episode-item')
                for ep in ep_items:
                    ep_num = ep.get('data-number', '') or ep.get('data-id', '')
                    ep_title = ep.text.strip()
                    ep_url = ep.get('href', '')
                    if ep_url and not ep_url.startswith('http'):
                        ep_url = self.base_url + ep_url
                    if ep_num:
                        try:
                            num = int(ep_num) if ep_num.isdigit() else ep_num
                        except:
                            num = ep_num
                        episodes.append({
                            'number': num,
                            'title': ep_title,
                            'url': ep_url
                        })
            
            if not episodes:
                film_id = self._extract_film_id(response.text)
                if film_id:
                    episodes = self._get_episodes_ajax(film_id)
            
            servers = soup.find_all('div', class_='server-item')
            has_sub = any('sub' in s.get('data-type', '').lower() for s in servers)
            has_dub = any('dub' in s.get('data-type', '').lower() for s in servers)
            
            return {
                'title': title,
                'description': description,
                'episodes': sorted(episodes, key=lambda x: x['number'] if isinstance(x['number'], int) else 0),
                'has_sub': has_sub or True,
                'has_dub': has_dub or False,
                'film_id': film_id if 'film_id' in locals() else None
            }
        except Exception as e:
            print(f"Details error: {e}")
            return None
    
    def _extract_film_id(self, html):
        """Extract film ID from page HTML"""
        patterns = [
            r'filmId\s*[=:]\s*["\']?(\d+)',
            r'data-id\s*=\s*["\'](\d+)',
            r'film_id\s*[=:]\s*["\']?(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return None
    
    def _get_episodes_ajax(self, film_id):
        """Get episodes via AJAX endpoint"""
        try:
            ajax_url = f"{self.base_url}/ajax/episode/list/{film_id}"
            response = self.session.get(ajax_url, timeout=30)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    html = data.get('html', data.get('result', ''))
                except:
                    html = response.text
                    
                soup = BeautifulSoup(html, 'html.parser')
                
                episodes = []
                ep_items = soup.find_all('a', class_='episode-item')
                for ep in ep_items:
                    ep_num = ep.get('data-number', '')
                    ep_title = ep.text.strip()
                    ep_id = ep.get('data-id', '')
                    if ep_num:
                        try:
                            num = int(ep_num) if ep_num.isdigit() else ep_num
                        except:
                            num = ep_num
                        episodes.append({
                            'number': num,
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
            if episode_id:
                ajax_url = f"{self.base_url}/ajax/episode/servers"
                params = {'episodeId': episode_id, 'type': version}
                response = self.session.get(ajax_url, params=params, timeout=30)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        html = data.get('html', data.get('result', ''))
                    except:
                        html = response.text
                    return self._parse_video_sources(html)
            
            if episode_url:
                response = self.session.get(episode_url, timeout=30)
                response.raise_for_status()
                return self._parse_video_sources(response.text)
            
            return {}
        except Exception as e:
            print(f"Video sources error: {e}")
            return {}
    
    def _parse_video_sources(self, html):
        """Parse video sources from HTML"""
        sources = {}
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            server_items = soup.find_all('div', class_='server-item')
            for server in server_items:
                quality = server.get('data-quality', '720p')
                src = server.get('data-src', '') or server.get('data-link', '')
                if src:
                    sources[quality] = src
            
            scripts = soup.find_all('script')
            for script in scripts:
                text = script.string if script else ''
                if text and ('sources' in text or 'src' in text):
                    match = re.search(r'sources\s*[:=]\s*(\[.*?\])', text, re.DOTALL)
                    if match:
                        import json
                        try:
                            src_list = json.loads(match.group(1))
                            for src in src_list:
                                if isinstance(src, dict):
                                    quality = src.get('label', src.get('quality', '720p'))
                                    url = src.get('file', src.get('src', ''))
                                    if url:
                                        sources[quality] = url
                                elif isinstance(src, str):
                                    sources['720p'] = src
                        except:
                            pass
                    
                    match = re.search(r'"file"\s*:\s*"([^"]+)"', text)
                    if match:
                        sources['720p'] = match.group(1)
            
            video = soup.find('video')
            if video:
                src = video.get('src', '')
                if src:
                    sources['720p'] = src
                
                for source in video.find_all('source'):
                    quality = source.get('label', source.get('res', '720p'))
                    src = source.get('src', '')
                    if src:
                        sources[quality] = src
            
            iframe = soup.find('iframe')
            if iframe:
                src = iframe.get('src', '')
                if src:
                    sources['embed'] = src
                        
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


scraper = AniWavesScraper()
