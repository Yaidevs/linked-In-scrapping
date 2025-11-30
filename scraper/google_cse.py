# import os
# import time
# import requests
# from django.conf import settings


# class GoogleCSEService:
#     BASE_URL = "https://www.googleapis.com/customsearch/v1"
    
#     def __init__(self):
#         self.api_key = getattr(settings, 'GOOGLE_CSE_API_KEY', '') or os.environ.get('GOOGLE_CSE_API_KEY', '')
#         self.cx = getattr(settings, 'GOOGLE_CSE_CX', '') or os.environ.get('GOOGLE_CSE_CX', '')
#         self.delay = getattr(settings, 'SCRAPING_DELAY', 2.0)
    
#     def search_linkedin_profile(self, person_name, company=None, num_results=5):
#         if not self.api_key or not self.cx:
#             return self._mock_search_results(person_name, company)
        
#         query = f"{person_name} site:linkedin.com/in"
#         if company:
#             query = f"{person_name} {company} site:linkedin.com/in"
        
#         params = {
#             'key': self.api_key,
#             'cx': self.cx,
#             'q': query,
#             'num': min(num_results, 10),
#         }
        
#         try:
#             response = requests.get(self.BASE_URL, params=params, timeout=30)
#             response.raise_for_status()
#             data = response.json()
            
#             results = []
#             for item in data.get('items', []):
#                 link = item.get('link', '')
#                 if 'linkedin.com/in/' in link:
#                     results.append({
#                         'title': item.get('title', ''),
#                         'link': link,
#                         'snippet': item.get('snippet', ''),
#                     })
            
#             time.sleep(self.delay)
#             return results
            
#         except requests.exceptions.RequestException as e:
#             print(f"Google CSE API error: {e}")
#             return []
    
#     def _mock_search_results(self, person_name, company=None):
#         name_slug = person_name.lower().replace(' ', '-')
#         return [{
#             'title': f"{person_name} - LinkedIn",
#             'link': f"https://www.linkedin.com/in/{name_slug}",
#             'snippet': f"View {person_name}'s profile on LinkedIn.",
#         }]
    
#     def search_batch(self, people_list, company=None):
#         results = {}
#         for person in people_list:
#             name = person if isinstance(person, str) else person.name
#             comp = company if company else (person.company if hasattr(person, 'company') else None)
#             results[name] = self.search_linkedin_profile(name, comp)
#         return results


import os
import time
import requests
import logging
from django.conf import settings
from typing import List, Dict, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class GoogleCSEService:
    BASE_URL = "https://www.googleapis.com/customsearch/v1"
    
    def __init__(self):
        self.api_key = getattr(settings, 'GOOGLE_CSE_API_KEY', '') or os.environ.get('GOOGLE_CSE_API_KEY', '')
        self.cx = getattr(settings, 'GOOGLE_CSE_CX', '') or os.environ.get('GOOGLE_CSE_CX', '')
        self.delay = getattr(settings, 'SCRAPING_DELAY', 2.0)
        self.max_retries = getattr(settings, 'GOOGLE_CSE_MAX_RETRIES', 3)
        self.timeout = getattr(settings, 'GOOGLE_CSE_TIMEOUT', 30)
        
        # Rate limiting
        self.last_request_time = 0
        self.request_count = 0
        self.daily_limit = 100  # Free tier limit
        
        self._validate_credentials()
    
    def _validate_credentials(self):
        """Validate that we have the necessary credentials"""
        if not self.api_key:
            logger.warning("Google CSE API key not found. Using mock mode.")
        if not self.cx:
            logger.warning("Google CSE CX (Search Engine ID) not found. Using mock mode.")
    
    def _rate_limit(self):
        """Implement rate limiting to respect API quotas"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Ensure minimum delay between requests
        if time_since_last < self.delay:
            sleep_time = self.delay - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        # Check daily limit (basic implementation)
        if self.request_count >= self.daily_limit:
            logger.warning("Daily API limit reached. Using mock mode.")
            return False
        
        self.last_request_time = time.time()
        self.request_count += 1
        return True
    
    def _build_search_query(self, person_name: str, company: Optional[str] = None) -> str:
        """Build optimized search query for LinkedIn profiles"""
        # Clean and format the name
        name_parts = person_name.strip().split()
        base_query = " OR ".join([f'"{part}"' for part in name_parts])
        
        # Add company if provided
        if company:
            company_clean = company.replace('S.A.', '').replace('Inc.', '').strip()
            base_query += f' "{company_clean}"'
        
        # Add LinkedIn domain restriction
        base_query += " site:linkedin.com/in"
        
        return base_query
    
    def search_linkedin_profile(self, person_name: str, company: Optional[str] = None, 
                              num_results: int = 5) -> List[Dict]:
        """
        Search for LinkedIn profiles using Google Custom Search
        
        Args:
            person_name: Full name of the person to search for
            company: Company name to narrow search (optional)
            num_results: Number of results to return (max 10)
        
        Returns:
            List of search results with title, link, and snippet
        """
        if not self.api_key or not self.cx:
            logger.info(f"Using mock search for: {person_name}")
            return self._mock_search_results(person_name, company)
        
        # Apply rate limiting
        if not self._rate_limit():
            return self._mock_search_results(person_name, company)
        
        query = self._build_search_query(person_name, company)
        
        params = {
            'key': self.api_key,
            'cx': self.cx,
            'q': query,
            'num': min(num_results, 10),  # Google CSE max is 10
            'fields': 'items(title,link,snippet)',
        }
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Searching Google CSE for: {person_name} (attempt {attempt + 1})")
                
                response = requests.get(
                    self.BASE_URL, 
                    params=params, 
                    timeout=self.timeout,
                    headers={'User-Agent': 'LinkedIn-Data-Collector/1.0'}
                )
                
                if response.status_code == 403:
                    logger.error("Google CSE API quota exceeded")
                    return self._mock_search_results(person_name, company)
                
                response.raise_for_status()
                data = response.json()
                
                results = self._process_search_results(data, person_name)
                
                logger.info(f"Found {len(results)} results for {person_name}")
                return results
                
            except requests.exceptions.Timeout:
                logger.warning(f"Google CSE timeout for {person_name} (attempt {attempt + 1})")
                if attempt == self.max_retries - 1:
                    return self._mock_search_results(person_name, company)
                
            except requests.exceptions.ConnectionError:
                logger.error(f"Google CSE connection error for {person_name}")
                if attempt == self.max_retries - 1:
                    return self._mock_search_results(person_name, company)
                
            except requests.exceptions.HTTPError as e:
                logger.error(f"Google CSE HTTP error for {person_name}: {e}")
                if response.status_code in [403, 429]:  # Quota exceeded or rate limited
                    return self._mock_search_results(person_name, company)
                if attempt == self.max_retries - 1:
                    return []
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Google CSE request error for {person_name}: {e}")
                if attempt == self.max_retries - 1:
                    return self._mock_search_results(person_name, company)
            
            # Exponential backoff
            time.sleep(2 ** attempt)
        
        return []
    
    def _process_search_results(self, data: Dict, person_name: str) -> List[Dict]:
        """Process and filter Google CSE results"""
        results = []
        
        for item in data.get('items', []):
            link = item.get('link', '')
            title = item.get('title', '')
            snippet = item.get('snippet', '')
            
            # Validate this is a LinkedIn profile
            if not self._is_valid_linkedin_url(link):
                continue
            
            # Score the result relevance
            relevance_score = self._calculate_relevance(person_name, title, snippet)
            
            results.append({
                'title': title,
                'link': link,
                'snippet': snippet,
                'relevance_score': relevance_score,
                'verified': relevance_score > 0.7  # High confidence match
            })
        
        # Sort by relevance score
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results
    
    def _is_valid_linkedin_url(self, url: str) -> bool:
        """Validate that the URL is a LinkedIn profile"""
        linkedin_patterns = [
            'linkedin.com/in/',
            'linkedin.com/pub/',
        ]
        return any(pattern in url.lower() for pattern in linkedin_patterns)
    
    def _calculate_relevance(self, person_name: str, title: str, snippet: str) -> float:
        """Calculate relevance score for search results"""
        score = 0.0
        name_lower = person_name.lower()
        title_lower = title.lower()
        snippet_lower = snippet.lower()
        
        # Check for exact name match in title
        if name_lower in title_lower:
            score += 0.6
        
        # Check for individual name parts
        name_parts = name_lower.split()
        matching_parts = sum(1 for part in name_parts if part in title_lower or part in snippet_lower)
        if len(name_parts) > 0:
            score += (matching_parts / len(name_parts)) * 0.3
        
        # Bonus for LinkedIn-specific terms
        linkedin_terms = ['linkedin', 'profile', 'connect']
        if any(term in title_lower for term in linkedin_terms):
            score += 0.1
        
        return min(score, 1.0)
    
    def _mock_search_results(self, person_name: str, company: Optional[str] = None) -> List[Dict]:
        """Generate mock search results for testing/fallback"""
        name_slug = person_name.lower().replace(' ', '-')
        company_info = f" at {company}" if company else ""
        
        return [{
            'title': f"{person_name} | LinkedIn",
            'link': f"https://www.linkedin.com/in/{name_slug}",
            'snippet': f"View {person_name}'s LinkedIn profile{company_info}. This is a mock result.",
            'relevance_score': 0.5,
            'verified': False,
            'is_mock': True
        }]
    
    def search_batch(self, people_list: List, company: Optional[str] = None) -> Dict:
        """
        Search for multiple people in batch
        
        Args:
            people_list: List of person names or Person objects
            company: Optional company to narrow all searches
        
        Returns:
            Dictionary mapping person names to search results
        """
        results = {}
        
        for i, person in enumerate(people_list):
            name = person if isinstance(person, str) else person.name
            comp = company if company else (person.company.name if hasattr(person, 'company') else None)
            
            logger.info(f"Batch search progress: {i + 1}/{len(people_list)} - {name}")
            
            results[name] = self.search_linkedin_profile(name, comp)
            
            # Extra delay between batch requests
            if i < len(people_list) - 1:
                time.sleep(self.delay * 1.5)
        
        return results
    
    def get_usage_stats(self) -> Dict:
        """Get current API usage statistics"""
        return {
            'request_count': self.request_count,
            'daily_limit': self.daily_limit,
            'remaining_requests': max(0, self.daily_limit - self.request_count),
            'using_mock_mode': not (self.api_key and self.cx)
        }


# Singleton instance for reuse
google_cse_service = GoogleCSEService()