# import re
# from django.db import transaction
# from core.models import Keyword, Match


# class KeywordMatcher:
#     def __init__(self, context_chars=100, max_contexts_per_keyword=3):
#         self.context_chars = context_chars
#         self.max_contexts_per_keyword = max_contexts_per_keyword
    
#     def find_matches(self, search_result):
#         keywords = Keyword.objects.filter(is_active=True)
        
#         content = self._build_searchable_content(search_result)
#         if not content:
#             return []
        
#         content_lower = content.lower()
#         matches_created = []
        
#         with transaction.atomic():
#             Match.objects.filter(search_result=search_result).delete()
            
#             for keyword in keywords:
#                 word = keyword.word.lower()
                
#                 pattern = r'\b' + re.escape(word) + r'\b'
#                 occurrences = list(re.finditer(pattern, content_lower, re.IGNORECASE))
                
#                 if occurrences:
#                     contexts = []
#                     for i, occurrence in enumerate(occurrences[:self.max_contexts_per_keyword]):
#                         context = self._extract_context(content, occurrence.start(), occurrence.end())
#                         contexts.append(context)
                    
#                     combined_context = ' [...] '.join(contexts)
                    
#                     if len(combined_context) > 2000:
#                         combined_context = combined_context[:1997] + '...'
                    
#                     match = Match.objects.create(
#                         search_result=search_result,
#                         keyword=keyword,
#                         context_snippet=combined_context,
#                         source_url=search_result.source_url or search_result.person.linkedin_url or '',
#                         match_count=len(occurrences)
#                     )
#                     matches_created.append(match)
        
#         return matches_created
    
#     def _build_searchable_content(self, search_result):
#         parts = []
        
#         if search_result.profile_headline:
#             parts.append(f"HEADLINE: {search_result.profile_headline}")
        
#         if search_result.profile_about:
#             parts.append(f"ABOUT: {search_result.profile_about}")
        
#         if search_result.profile_experience:
#             parts.append(f"EXPERIENCE: {search_result.profile_experience}")
        
#         if search_result.profile_content:
#             parts.append(search_result.profile_content)
        
#         return ' '.join(parts)
    
#     def _extract_context(self, content, start, end):
#         context_start = max(0, start - self.context_chars)
#         context_end = min(len(content), end + self.context_chars)
        
#         if context_start > 0:
#             space_pos = content.rfind(' ', context_start, start)
#             if space_pos != -1:
#                 context_start = space_pos + 1
        
#         if context_end < len(content):
#             space_pos = content.find(' ', end, context_end)
#             if space_pos != -1:
#                 context_end = space_pos
        
#         context = content[context_start:context_end].strip()
        
#         if context_start > 0:
#             context = '...' + context
#         if context_end < len(content):
#             context = context + '...'
        
#         return context
    
#     def analyze_keywords(self, content):
#         if not content:
#             return {}
        
#         keywords = Keyword.objects.filter(is_active=True)
#         content_lower = content.lower()
        
#         results = {}
#         for keyword in keywords:
#             word = keyword.word.lower()
#             pattern = r'\b' + re.escape(word) + r'\b'
#             matches = re.findall(pattern, content_lower, re.IGNORECASE)
            
#             if matches:
#                 results[keyword.word] = {
#                     'count': len(matches),
#                     'category': keyword.category,
#                 }
        
#         return results
    
#     def get_match_summary(self, search_result):
#         matches = Match.objects.filter(search_result=search_result).select_related('keyword')
        
#         summary = {
#             'total_matches': matches.count(),
#             'total_occurrences': sum(m.match_count for m in matches),
#             'by_category': {},
#             'keywords': []
#         }
        
#         for match in matches:
#             category = match.keyword.category or 'other'
#             if category not in summary['by_category']:
#                 summary['by_category'][category] = 0
#             summary['by_category'][category] += 1
            
#             summary['keywords'].append({
#                 'word': match.keyword.word,
#                 'category': category,
#                 'count': match.match_count,
#                 'context': match.context_snippet[:150],
#             })
        
#         return summary


import re
import logging
from django.db import transaction
from django.conf import settings
from typing import List, Dict, Optional, Tuple
from core.models import Keyword, Match, SearchResult

logger = logging.getLogger(__name__)


class KeywordMatcher:
    def __init__(self, context_chars: int = 100, max_contexts_per_keyword: int = 3):
        self.context_chars = context_chars
        self.max_contexts_per_keyword = max_contexts_per_keyword
        self.min_word_length = 3  # Minimum word length to avoid matching short words
        self.fuzzy_match_threshold = 0.8  # For future fuzzy matching implementation
    
    def find_matches(self, search_result: SearchResult) -> List[Match]:
        """
        Find keyword matches in search result content
        
        Args:
            search_result: SearchResult object to analyze
        
        Returns:
            List of created Match objects
        """
        logger.info(f"Finding keyword matches for: {search_result.person.name}")
        
        keywords = Keyword.objects.filter(is_active=True)
        if not keywords.exists():
            logger.warning("No active keywords found for matching")
            return []
        
        content = self._build_searchable_content(search_result)
        if not content:
            logger.warning(f"No content available for {search_result.person.name}")
            return []
        
        content_lower = content.lower()
        matches_created = []
        
        with transaction.atomic():
            # Clear existing matches for this search result
            deleted_count, _ = Match.objects.filter(search_result=search_result).delete()
            if deleted_count > 0:
                logger.debug(f"Cleared {deleted_count} existing matches")
            
            # Pre-compile regex patterns for performance
            keyword_patterns = self._compile_keyword_patterns(keywords)
            
            for keyword, pattern in keyword_patterns:
                occurrences = list(pattern.finditer(content_lower))
                
                if occurrences:
                    match_data = self._process_keyword_matches(
                        keyword, occurrences, content, content_lower, search_result
                    )
                    if match_data:
                        match = Match.objects.create(**match_data)
                        matches_created.append(match)
                        logger.debug(f"Created match for '{keyword.word}': {len(occurrences)} occurrences")
        
        logger.info(f"Created {len(matches_created)} matches for {search_result.person.name}")
        return matches_created
    
    def _compile_keyword_patterns(self, keywords) -> List[Tuple[Keyword, re.Pattern]]:
        """Pre-compile regex patterns for all keywords for better performance"""
        patterns = []
        for keyword in keywords:
            # Skip very short keywords to avoid false positives
            if len(keyword.word.strip()) < self.min_word_length:
                continue
                
            try:
                # Create a pattern that matches whole words, case insensitive
                pattern = re.compile(r'\b' + re.escape(keyword.word.lower()) + r'\b', re.IGNORECASE)
                patterns.append((keyword, pattern))
            except re.error as e:
                logger.error(f"Invalid regex pattern for keyword '{keyword.word}': {e}")
                continue
        
        return patterns
    
    def _process_keyword_matches(self, keyword: Keyword, occurrences: List, 
                               content: str, content_lower: str, 
                               search_result: SearchResult) -> Optional[Dict]:
        """Process matches for a single keyword and prepare match data"""
        # Calculate confidence score based on match quality
        confidence_score = self._calculate_confidence(keyword, occurrences, content_lower)
        
        # Extract context snippets
        contexts = []
        for i, occurrence in enumerate(occurrences[:self.max_contexts_per_keyword]):
            context = self._extract_context(content, occurrence.start(), occurrence.end())
            if context:
                contexts.append(context)
        
        if not contexts:
            return None
        
        # Combine contexts intelligently
        combined_context = self._combine_contexts(contexts)
        
        return {
            'search_result': search_result,
            'keyword': keyword,
            'context_snippet': combined_context,
            'source_url': search_result.source_url or getattr(search_result.person, 'linkedin_url', ''),
            'match_count': len(occurrences),
            'confidence_score': confidence_score
        }
    
    def _calculate_confidence(self, keyword: Keyword, occurrences: List, content_lower: str) -> float:
        """Calculate confidence score for keyword matches (0.0 to 1.0)"""
        base_score = 0.5
        
        # More occurrences = higher confidence
        occurrence_boost = min(len(occurrences) * 0.1, 0.3)
        
        # Longer keywords are less likely to be false positives
        length_boost = min(len(keyword.word) * 0.05, 0.2)
        
        # Category-based confidence adjustments
        category_boost = {
            'skill': 0.1,
            'technology': 0.1,
            'certification': 0.15,
            'title': 0.05,
            'industry': 0.05,
            'education': 0.08,
            'other': 0.0
        }.get(keyword.category, 0.0)
        
        return min(base_score + occurrence_boost + length_boost + category_boost, 1.0)
    
    def _build_searchable_content(self, search_result: SearchResult) -> str:
        """Build a comprehensive searchable content string from search result"""
        content_parts = []
        
        # Add content with section markers for better context
        sections = [
            ('HEADLINE', search_result.profile_headline),
            ('ABOUT', search_result.profile_about),
            ('EXPERIENCE', search_result.profile_experience),
        ]
        
        for section_name, section_content in sections:
            if section_content and section_content.strip():
                # Clean and normalize the content
                cleaned_content = self._clean_content(section_content)
                if cleaned_content:
                    content_parts.append(f"{section_name}: {cleaned_content}")
        
        # Add full content if available (without section marker)
        if search_result.profile_content and search_result.profile_content.strip():
            cleaned_full_content = self._clean_content(search_result.profile_content)
            if cleaned_full_content:
                content_parts.append(cleaned_full_content)
        
        return ' '.join(content_parts)
    
    def _clean_content(self, content: str) -> str:
        """Clean and normalize content for better matching"""
        if not content:
            return ""
        
        # Remove extra whitespace
        content = re.sub(r'\s+', ' ', content.strip())
        
        # Remove common HTML entities and special characters that might interfere
        content = re.sub(r'&[a-z]+;', ' ', content)
        content = re.sub(r'[^\w\s@.#+-]', ' ', content)
        
        return content
    
    def _extract_context(self, content: str, start: int, end: int) -> str:
        """Extract context around a match with sentence boundaries"""
        # Expand context to sentence boundaries when possible
        sentence_start = content.rfind('.', 0, start)
        if sentence_start == -1:
            sentence_start = 0
        else:
            sentence_start += 1  # Move past the period
        
        sentence_end = content.find('.', end)
        if sentence_end == -1:
            sentence_end = len(content)
        else:
            sentence_end += 1  # Include the period
        
        # Ensure we have at least some context
        context = content[sentence_start:sentence_end].strip()
        
        # Add ellipsis if we're not at the beginning/end of content
        if sentence_start > 0 and len(context) > 0:
            context = '...' + context
        if sentence_end < len(content) and len(context) > 0:
            context = context + '...'
        
        return context if context else content[max(0, start-20):min(len(content), end+20)]
    
    def _combine_contexts(self, contexts: List[str]) -> str:
        """Combine multiple context snippets intelligently"""
        if not contexts:
            return ""
        
        if len(contexts) == 1:
            return contexts[0]
        
        # Remove duplicates and very similar contexts
        unique_contexts = []
        for context in contexts:
            if not any(self._is_similar_context(context, existing) for existing in unique_contexts):
                unique_contexts.append(context)
        
        # Limit to reasonable number of contexts
        unique_contexts = unique_contexts[:self.max_contexts_per_keyword]
        
        # Join with separator that indicates multiple occurrences
        return ' [...] '.join(unique_contexts)
    
    def _is_similar_context(self, context1: str, context2: str, similarity_threshold: float = 0.7) -> bool:
        """Check if two contexts are similar (basic implementation)"""
        # Simple overlap-based similarity check
        words1 = set(context1.lower().split())
        words2 = set(context2.lower().split())
        
        if not words1 or not words2:
            return False
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        similarity = len(intersection) / len(union)
        return similarity > similarity_threshold
    
    def analyze_keywords(self, content: str) -> Dict:
        """Analyze content and return keyword statistics without saving matches"""
        if not content:
            return {}
        
        keywords = Keyword.objects.filter(is_active=True)
        content_lower = content.lower()
        
        results = {}
        keyword_patterns = self._compile_keyword_patterns(keywords)
        
        for keyword, pattern in keyword_patterns:
            matches = pattern.findall(content_lower)
            
            if matches:
                # Extract sample context
                first_match = pattern.search(content_lower)
                context = ""
                if first_match:
                    context = self._extract_context(content, first_match.start(), first_match.end())
                
                results[keyword.word] = {
                    'count': len(matches),
                    'category': keyword.category,
                    'category_display': keyword.get_category_display(),
                    'context': context[:200] + '...' if len(context) > 200 else context,
                    'is_active': keyword.is_active
                }
        
        return results
    
    def get_match_summary(self, search_result: SearchResult) -> Dict:
        """Get comprehensive summary of matches for a search result"""
        matches = Match.objects.filter(
            search_result=search_result
        ).select_related('keyword').order_by('-match_count')
        
        summary = {
            'total_matches': matches.count(),
            'total_occurrences': sum(m.match_count for m in matches),
            'by_category': {},
            'keywords': [],
            'top_matches': [],
            'confidence_score': 0.0
        }
        
        category_stats = {}
        total_confidence = 0.0
        
        for match in matches:
            category = match.keyword.category or 'other'
            
            # Update category statistics
            if category not in category_stats:
                category_stats[category] = {
                    'count': 0,
                    'occurrences': 0,
                    'keywords': set()
                }
            
            category_stats[category]['count'] += 1
            category_stats[category]['occurrences'] += match.match_count
            category_stats[category]['keywords'].add(match.keyword.word)
            
            # Add to keyword list
            summary['keywords'].append({
                'word': match.keyword.word,
                'category': category,
                'category_display': match.keyword.get_category_display(),
                'count': match.match_count,
                'confidence': match.confidence_score,
                'context': match.context_snippet[:150] + '...' if len(match.context_snippet) > 150 else match.context_snippet,
            })
            
            total_confidence += match.confidence_score
        
        # Convert category stats to final format
        for category, stats in category_stats.items():
            summary['by_category'][category] = {
                'match_count': stats['count'],
                'occurrence_count': stats['occurrences'],
                'unique_keywords': len(stats['keywords']),
                'keywords_list': list(stats['keywords'])[:5]  # Top 5 keywords
            }
        
        # Calculate average confidence
        if matches:
            summary['confidence_score'] = total_confidence / len(matches)
        
        # Get top matches by occurrence count
        summary['top_matches'] = summary['keywords'][:10]
        
        return summary
    
    def batch_analyze_keywords(self, search_results: List[SearchResult]) -> Dict:
        """Analyze keywords across multiple search results"""
        summary = {
            'total_search_results': len(search_results),
            'results_with_matches': 0,
            'total_matches': 0,
            'top_keywords': {},
            'category_distribution': {}
        }
        
        for search_result in search_results:
            match_summary = self.get_match_summary(search_result)
            
            if match_summary['total_matches'] > 0:
                summary['results_with_matches'] += 1
                summary['total_matches'] += match_summary['total_matches']
                
                # Aggregate keyword counts
                for keyword_info in match_summary['keywords']:
                    word = keyword_info['word']
                    if word not in summary['top_keywords']:
                        summary['top_keywords'][word] = 0
                    summary['top_keywords'][word] += keyword_info['count']
                
                # Aggregate category distribution
                for category, stats in match_summary['by_category'].items():
                    if category not in summary['category_distribution']:
                        summary['category_distribution'][category] = 0
                    summary['category_distribution'][category] += stats['match_count']
        
        # Sort top keywords
        summary['top_keywords'] = dict(
            sorted(summary['top_keywords'].items(), key=lambda x: x[1], reverse=True)[:10]
        )
        
        return summary


# Global instance for reuse
keyword_matcher = KeywordMatcher()