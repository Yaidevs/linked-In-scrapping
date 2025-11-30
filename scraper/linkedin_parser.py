# import time
# import requests
# from bs4 import BeautifulSoup
# from django.conf import settings


# class LinkedInParser:
#     HEADERS = {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
#         'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
#         'Accept-Language': 'en-US,en;q=0.5',
#         'Accept-Encoding': 'gzip, deflate, br',
#         'Connection': 'keep-alive',
#         'Upgrade-Insecure-Requests': '1',
#         'Cache-Control': 'max-age=0',
#     }
    
#     AUTH_WALL_INDICATORS = [
#         'authwall',
#         'login',
#         'sign in to linkedin',
#         'join now',
#         'sign up',
#         'uas/login',
#         'checkpoint/lg/login',
#     ]
    
#     def __init__(self):
#         self.delay = getattr(settings, 'SCRAPING_DELAY', 2.0)
    
#     def scrape_profile(self, linkedin_url):
#         if not linkedin_url:
#             return self._empty_profile(error='No URL provided')
        
#         try:
#             time.sleep(self.delay)
            
#             response = requests.get(
#                 linkedin_url,
#                 headers=self.HEADERS,
#                 timeout=30,
#                 allow_redirects=True
#             )
#             response.raise_for_status()
            
#             if self._is_auth_wall(response.text, response.url):
#                 return self._empty_profile(
#                     error='LinkedIn requires authentication',
#                     auth_wall=True,
#                     url=linkedin_url
#                 )
            
#             return self._parse_html(response.text, linkedin_url)
            
#         except requests.exceptions.Timeout:
#             return self._empty_profile(error='Request timed out', url=linkedin_url)
#         except requests.exceptions.ConnectionError as e:
#             return self._empty_profile(error=f'Connection error: {str(e)}', url=linkedin_url)
#         except requests.exceptions.HTTPError as e:
#             status_code = e.response.status_code if e.response else 'unknown'
#             if status_code == 404:
#                 return self._empty_profile(error='Profile not found (404)', url=linkedin_url)
#             elif status_code == 403:
#                 return self._empty_profile(error='Access forbidden (403)', url=linkedin_url)
#             elif status_code == 429:
#                 return self._empty_profile(error='Rate limited - too many requests', url=linkedin_url)
#             return self._empty_profile(error=f'HTTP error {status_code}', url=linkedin_url)
#         except requests.exceptions.RequestException as e:
#             return self._empty_profile(error=str(e), url=linkedin_url)
    
#     def _is_auth_wall(self, html_content, final_url):
#         html_lower = html_content.lower()
#         url_lower = final_url.lower()
        
#         for indicator in self.AUTH_WALL_INDICATORS:
#             if indicator in url_lower or indicator in html_lower[:5000]:
#                 return True
        
#         soup = BeautifulSoup(html_content[:10000], 'lxml')
#         title = soup.find('title')
#         if title:
#             title_text = title.get_text().lower()
#             if 'login' in title_text or 'sign in' in title_text or 'sign up' in title_text:
#                 return True
        
#         return False
    
#     def _parse_html(self, html_content, url):
#         soup = BeautifulSoup(html_content, 'lxml')
        
#         for script in soup(["script", "style", "noscript"]):
#             script.decompose()
        
#         profile_data = {
#             'headline': '',
#             'about': '',
#             'experience': '',
#             'full_content': '',
#             'url': url,
#             'error': None,
#             'auth_wall': False,
#         }
        
#         title_tag = soup.find('title')
#         if title_tag:
#             title_text = title_tag.get_text(strip=True)
#             if ' | ' in title_text:
#                 parts = title_text.split(' | ')
#                 if len(parts) >= 2:
#                     profile_data['headline'] = parts[0].strip()
        
#         headline_selectors = [
#             'h2.top-card-layout__headline',
#             '.top-card-layout__headline',
#             'h1.top-card-layout__title',
#             '.pv-text-details__left-panel h1',
#             '.text-heading-xlarge',
#         ]
#         for selector in headline_selectors:
#             element = soup.select_one(selector)
#             if element:
#                 profile_data['headline'] = element.get_text(strip=True)
#                 break
        
#         about_selectors = [
#             '.core-section-container__content',
#             '.pv-about-section',
#             'section.summary',
#             '[data-section="summary"]',
#             '.pv-shared-text-with-see-more',
#         ]
#         for selector in about_selectors:
#             element = soup.select_one(selector)
#             if element:
#                 profile_data['about'] = element.get_text(strip=True)[:2000]
#                 break
        
#         experience_selectors = [
#             '.experience-section',
#             '.pv-experience-section',
#             'section[data-section="experience"]',
#             '#experience-section',
#             '.pv-profile-card',
#         ]
#         experience_parts = []
#         for selector in experience_selectors:
#             elements = soup.select(selector)
#             for element in elements:
#                 text = element.get_text(separator=' ', strip=True)
#                 if text and len(text) > 50:
#                     experience_parts.append(text[:2000])
#         profile_data['experience'] = ' | '.join(experience_parts)[:5000]
        
#         meta_description = soup.find('meta', {'name': 'description'})
#         if meta_description:
#             desc = meta_description.get('content', '')
#             if desc:
#                 if not profile_data['about']:
#                     profile_data['about'] = desc
#                 if not profile_data['headline'] and ' - ' in desc:
#                     profile_data['headline'] = desc.split(' - ')[0].strip()
        
#         og_description = soup.find('meta', {'property': 'og:description'})
#         if og_description and not profile_data['about']:
#             profile_data['about'] = og_description.get('content', '')
        
#         body = soup.find('body')
#         if body:
#             full_text = body.get_text(separator=' ', strip=True)
#             full_text = ' '.join(full_text.split())
#             profile_data['full_content'] = full_text[:10000]
        
#         if not profile_data['full_content'] and not profile_data['headline']:
#             profile_data['error'] = 'Could not extract profile content - page may be empty or blocked'
        
#         return profile_data
    
#     def _empty_profile(self, error=None, auth_wall=False, url=''):
#         return {
#             'headline': '',
#             'about': '',
#             'experience': '',
#             'full_content': '',
#             'url': url,
#             'error': error,
#             'auth_wall': auth_wall,
#         }
    
#     def scrape_batch(self, urls):
#         results = {}
#         for url in urls:
#             results[url] = self.scrape_profile(url)
#         return results


import time
import requests
import logging
from bs4 import BeautifulSoup
from django.conf import settings
from typing import Dict, List, Optional
from urllib.parse import urlparse
import random

logger = logging.getLogger(__name__)


class LinkedInParser:
    # Enhanced headers to mimic real browser behavior
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
        'DNT': '1',
    }
    
    # Expanded auth wall detection
    AUTH_WALL_INDICATORS = [
        'authwall',
        'login',
        'sign in to linkedin',
        'join linkedin',
        'join now',
        'sign up',
        'uas/login',
        'checkpoint/lg/login',
        'checkpoint/challenge',
        'restricted',
        'verification',
        'security check',
        'unlock',
    ]
    
    # Common LinkedIn profile selectors (updated for current structure)
    SELECTORS = {
        'headline': [
            'h2.top-card-layout__headline',
            '.top-card-layout__headline',
            'h1.top-card-layout__title',
            '.text-heading-xlarge',
            '.pv-text-details__left-panel h1',
            '.ph5 h1',
            '.inline-show-more-text--is-collapsed',
        ],
        'about': [
            '.core-section-container__content',
            '.pv-about-section',
            'section.summary',
            '[data-section="summary"]',
            '.pv-shared-text-with-see-more',
            '.display-flex .text-body-medium',
            '.pv-about__summary-text',
        ],
        'experience': [
            '.experience-section',
            '.pv-experience-section',
            'section[data-section="experience"]',
            '#experience-section',
            '.pv-profile-card',
            '.pv-position-entity',
            '.experience-item',
        ],
        'education': [
            '.education-section',
            '.pv-education-section',
            'section[data-section="education"]',
        ],
        'skills': [
            '.skill-categories-section',
            '.pv-skill-categories-section',
            '.pv-skill-category-entity',
        ]
    }
    
    def __init__(self):
        self.delay = getattr(settings, 'SCRAPING_DELAY', 2.0)
        self.max_retries = getattr(settings, 'LINKEDIN_MAX_RETRIES', 2)
        self.timeout = getattr(settings, 'LINKEDIN_TIMEOUT', 30)
        self.max_content_length = getattr(settings, 'MAX_CONTENT_LENGTH', 15000)
        
        # Session for connection reuse
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        
        # Rotating user agents
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
    
    def scrape_profile(self, linkedin_url: str) -> Dict:
        """
        Scrape LinkedIn profile data from public profile URL
        
        Args:
            linkedin_url: LinkedIn profile URL
        
        Returns:
            Dictionary with profile data or error information
        """
        if not linkedin_url or not self._is_valid_linkedin_url(linkedin_url):
            return self._empty_profile(error='Invalid LinkedIn URL')
        
        logger.info(f"Scraping LinkedIn profile: {linkedin_url}")
        
        for attempt in range(self.max_retries):
            try:
                # Random delay between requests
                delay = self.delay + random.uniform(0.5, 2.0)
                time.sleep(delay)
                
                # Rotate user agent
                self.session.headers['User-Agent'] = random.choice(self.user_agents)
                
                response = self.session.get(
                    linkedin_url,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                
                if response.status_code == 404:
                    return self._empty_profile(
                        error='Profile not found (404)', 
                        url=linkedin_url
                    )
                
                if response.status_code == 429:
                    logger.warning(f"Rate limited on attempt {attempt + 1}")
                    if attempt < self.max_retries - 1:
                        time.sleep(10)  # Longer wait for rate limiting
                        continue
                    else:
                        return self._empty_profile(
                            error='Rate limited - too many requests', 
                            url=linkedin_url
                        )
                
                response.raise_for_status()
                
                # Check for authentication wall
                if self._is_auth_wall(response.text, response.url):
                    logger.warning(f"Auth wall detected for: {linkedin_url}")
                    return self._empty_profile(
                        error='LinkedIn requires authentication',
                        auth_wall=True,
                        url=linkedin_url
                    )
                
                # Parse successful response
                profile_data = self._parse_html(response.text, linkedin_url)
                logger.info(f"Successfully scraped profile: {linkedin_url}")
                return profile_data
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1} for {linkedin_url}")
                if attempt == self.max_retries - 1:
                    return self._empty_profile(
                        error='Request timed out', 
                        url=linkedin_url
                    )
                    
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error for {linkedin_url}: {e}")
                if attempt == self.max_retries - 1:
                    return self._empty_profile(
                        error=f'Connection error: {str(e)}', 
                        url=linkedin_url
                    )
                    
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else 'unknown'
                logger.error(f"HTTP error {status_code} for {linkedin_url}: {e}")
                if attempt == self.max_retries - 1:
                    if status_code == 403:
                        return self._empty_profile(
                            error='Access forbidden (403) - profile may be private', 
                            url=linkedin_url
                        )
                    return self._empty_profile(
                        error=f'HTTP error {status_code}', 
                        url=linkedin_url
                    )
                    
            except Exception as e:
                logger.error(f"Unexpected error scraping {linkedin_url}: {e}")
                if attempt == self.max_retries - 1:
                    return self._empty_profile(
                        error=f'Unexpected error: {str(e)}', 
                        url=linkedin_url
                    )
            
            # Exponential backoff for retries
            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)
        
        return self._empty_profile(error='Max retries exceeded', url=linkedin_url)
    
    def _is_valid_linkedin_url(self, url: str) -> bool:
        """Validate that URL is a LinkedIn profile URL"""
        try:
            parsed = urlparse(url)
            return (parsed.netloc.endswith('linkedin.com') and 
                    '/in/' in parsed.path)
        except Exception:
            return False
    
    def _is_auth_wall(self, html_content: str, final_url: str) -> bool:
        """Detect if LinkedIn is showing an authentication wall"""
        html_lower = html_content.lower()
        url_lower = final_url.lower()
        
        # Check URL for auth indicators
        for indicator in self.AUTH_WALL_INDICATORS:
            if indicator in url_lower:
                return True
        
        # Check HTML content for auth indicators
        for indicator in self.AUTH_WALL_INDICATORS:
            if indicator in html_lower[:5000]:
                return True
        
        # Parse HTML for additional checks
        soup = BeautifulSoup(html_content[:10000], 'lxml')
        
        # Check page title
        title = soup.find('title')
        if title:
            title_text = title.get_text().lower()
            auth_indicators = ['login', 'sign in', 'sign up', 'join linkedin']
            if any(indicator in title_text for indicator in auth_indicators):
                return True
        
        # Check for login form elements
        login_selectors = [
            'input[type="password"]',
            'form[action*="login"]',
            '.login-form',
            '#username',
            '#password',
        ]
        for selector in login_selectors:
            if soup.select_one(selector):
                return True
        
        # Check for restricted content messages
        restricted_texts = [
            'see more by signing in',
            'join now to see',
            'sign up to view',
            'this profile is not available',
        ]
        body_text = soup.get_text().lower()
        for text in restricted_texts:
            if text in body_text:
                return True
        
        return False
    
    def _parse_html(self, html_content: str, url: str) -> Dict:
        """Parse LinkedIn profile HTML and extract structured data"""
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Remove unwanted elements
        for element in soup(["script", "style", "noscript", "meta", "link"]):
            element.decompose()
        
        profile_data = {
            'headline': '',
            'about': '',
            'experience': '',
            'education': '',
            'skills': '',
            'full_content': '',
            'url': url,
            'error': None,
            'auth_wall': False,
            'content_quality': 'low',  # low, medium, high
        }
        
        # Extract headline
        profile_data['headline'] = self._extract_headline(soup)
        
        # Extract about section
        profile_data['about'] = self._extract_about(soup)
        
        # Extract experience
        profile_data['experience'] = self._extract_experience(soup)
        
        # Extract education
        profile_data['education'] = self._extract_education(soup)
        
        # Extract skills
        profile_data['skills'] = self._extract_skills(soup)
        
        # Extract full content (cleaned)
        profile_data['full_content'] = self._extract_full_content(soup)
        
        # Determine content quality
        profile_data['content_quality'] = self._assess_content_quality(profile_data)
        
        # Check if we got any meaningful content
        if (not profile_data['full_content'] and 
            not profile_data['headline'] and 
            not profile_data['about']):
            profile_data['error'] = 'Could not extract profile content - page may be empty or blocked'
        
        logger.debug(f"Extracted profile data: {len(profile_data['full_content'])} chars, quality: {profile_data['content_quality']}")
        
        return profile_data
    
    def _extract_headline(self, soup: BeautifulSoup) -> str:
        """Extract profile headline"""
        for selector in self.SELECTORS['headline']:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text and len(text) > 5:
                    return text[:500]
        
        # Fallback: try to extract from title tag
        title = soup.find('title')
        if title:
            title_text = title.get_text(strip=True)
            if ' | ' in title_text:
                return title_text.split(' | ')[0].strip()[:500]
        
        return ""
    
    def _extract_about(self, soup: BeautifulSoup) -> str:
        """Extract about/summary section"""
        for selector in self.SELECTORS['about']:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(separator=' ', strip=True)
                if text and len(text) > 20:
                    return text[:2000]
        
        # Check meta descriptions
        for meta_name in ['description', 'og:description']:
            meta = soup.find('meta', {'name': meta_name}) or soup.find('meta', {'property': meta_name})
            if meta and meta.get('content'):
                content = meta.get('content', '').strip()
                if content and len(content) > 20:
                    return content[:2000]
        
        return ""
    
    def _extract_experience(self, soup: BeautifulSoup) -> str:
        """Extract experience section"""
        experience_parts = []
        
        for selector in self.SELECTORS['experience']:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(separator=' ', strip=True)
                if text and len(text) > 30:  # More than just a title
                    experience_parts.append(text[:1500])
        
        return ' | '.join(experience_parts)[:5000]
    
    def _extract_education(self, soup: BeautifulSoup) -> str:
        """Extract education section"""
        education_parts = []
        
        for selector in self.SELECTORS['education']:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(separator=' ', strip=True)
                if text and len(text) > 20:
                    education_parts.append(text[:1000])
        
        return ' | '.join(education_parts)[:2000]
    
    def _extract_skills(self, soup: BeautifulSoup) -> str:
        """Extract skills section"""
        skills_parts = []
        
        for selector in self.SELECTORS['skills']:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(separator=' ', strip=True)
                if text and len(text) > 10:
                    skills_parts.append(text[:500])
        
        return ' | '.join(skills_parts)[:1000]
    
    def _extract_full_content(self, soup: BeautifulSoup) -> str:
        """Extract and clean full page content"""
        # Try main content areas first
        main_selectors = [
            'main',
            '.core-rail',
            '.scaffold-layout__main',
            '.pv-profile-section',
            'body'
        ]
        
        for selector in main_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(separator=' ', strip=True)
                if text and len(text) > 100:
                    # Clean and normalize text
                    text = ' '.join(text.split())
                    return text[:self.max_content_length]
        
        return ""
    
    def _assess_content_quality(self, profile_data: Dict) -> str:
        """Assess the quality of extracted content"""
        content_length = len(profile_data['full_content'])
        has_headline = bool(profile_data['headline'])
        has_about = bool(profile_data['about'])
        has_experience = bool(profile_data['experience'])
        
        if content_length > 1000 and (has_headline or has_about or has_experience):
            return 'high'
        elif content_length > 200 and (has_headline or has_about):
            return 'medium'
        else:
            return 'low'
    
    def _empty_profile(self, error: Optional[str] = None, auth_wall: bool = False, url: str = '') -> Dict:
        """Return empty profile data with error information"""
        return {
            'headline': '',
            'about': '',
            'experience': '',
            'education': '',
            'skills': '',
            'full_content': '',
            'url': url,
            'error': error,
            'auth_wall': auth_wall,
            'content_quality': 'none',
        }
    
    def scrape_batch(self, urls: List[str]) -> Dict[str, Dict]:
        """Scrape multiple LinkedIn profiles"""
        results = {}
        total = len(urls)
        
        logger.info(f"Starting batch scrape of {total} profiles")
        
        for i, url in enumerate(urls, 1):
            logger.info(f"Scraping {i}/{total}: {url}")
            results[url] = self.scrape_profile(url)
            
            # Progress logging
            if i % 10 == 0:
                success_count = sum(1 for r in results.values() if not r.get('error'))
                logger.info(f"Progress: {i}/{total}, Success: {success_count}/{i}")
        
        # Final statistics
        success_count = sum(1 for r in results.values() if not r.get('error'))
        auth_wall_count = sum(1 for r in results.values() if r.get('auth_wall'))
        
        logger.info(f"Batch scrape completed: {success_count}/{total} successful, {auth_wall_count} auth walls")
        
        return results


# Global instance for reuse
linkedin_parser = LinkedInParser()