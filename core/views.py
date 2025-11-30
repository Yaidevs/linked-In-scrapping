import csv
import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, F
from django.utils import timezone
from django.core.paginator import Paginator

from .models import Person, Company, Keyword, SearchResult, Match, ScrapingJob, ExportJob
from scraper.google_cse import GoogleCSEService
from scraper.linkedin_parser import LinkedInParser
from scraper.keyword_matcher import KeywordMatcher


def dashboard(request):
    # People with stats
    people = Person.objects.select_related('company').annotate(
        result_count=Count('search_results'),
        match_count=Count('search_results__matches')
    ).order_by('-created_at')[:50]
    
    # Recent results with related data
    recent_results = SearchResult.objects.select_related(
        'person', 'person__company'
    ).prefetch_related('matches__keyword').order_by('-scraped_at')[:20]
    
    # Recent matches with context
    recent_matches = Match.objects.select_related(
        'search_result__person', 
        'search_result__person__company', 
        'keyword'
    ).order_by('-created_at')[:30]
    
    # Active keywords
    keywords = Keyword.objects.filter(is_active=True).order_by('category', 'word')
    
    # Recent scraping jobs
    recent_jobs = ScrapingJob.objects.order_by('-created_at')[:10]
    
    # Stats with enhanced metrics
    stats = {
        'total_companies': Company.objects.count(),
        'total_people': Person.objects.count(),
        'people_with_linkedin': Person.objects.exclude(linkedin_url='').count(),
        'total_keywords': Keyword.objects.filter(is_active=True).count(),
        'total_results': SearchResult.objects.filter(status='completed').count(),
        'total_matches': Match.objects.count(),
        'pending_scrapes': SearchResult.objects.filter(status='pending').count(),
        'failed_scrapes': SearchResult.objects.filter(status='failed').count(),
        'recent_matches_today': Match.objects.filter(
            created_at__date=timezone.now().date()
        ).count(),
    }
    
    context = {
        'people': people,
        'recent_results': recent_results,
        'recent_matches': recent_matches,
        'recent_jobs': recent_jobs,
        'keywords': keywords,
        'stats': stats,
    }
    
    response = render(request, 'dashboard.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required
def export_results_csv(request):
    format_type = request.GET.get('format', 'csv')
    
    if format_type == 'excel':
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename="search_results.xlsx"'
        # You would use pandas or openpyxl here for Excel export
        return export_results_excel(response)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="search_results.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Person Name', 'Company', 'LinkedIn URL', 'Content Source',
        'Headline', 'About', 'Experience', 'Status', 
        'Match Count', 'Scraped At', 'Source URL'
    ])
    
    results = SearchResult.objects.select_related(
        'person', 'person__company'
    ).annotate(match_count=Count('matches'))
    
    # Apply filters if provided
    status_filter = request.GET.get('status')
    if status_filter:
        results = results.filter(status=status_filter)
    
    source_filter = request.GET.get('source')
    if source_filter:
        results = results.filter(content_source=source_filter)
    
    for result in results:
        scraped_at = result.scraped_at.strftime('%Y-%m-%d %H:%M:%S') if result.scraped_at else ''
        writer.writerow([
            result.person.name,
            result.person.company.name,
            result.person.linkedin_url,
            result.get_content_source_display(),
            result.profile_headline,
            result.profile_about[:500] if result.profile_about else '',
            result.profile_experience[:500] if result.profile_experience else '',
            result.get_status_display(),
            result.match_count,
            scraped_at,
            result.source_url,
        ])
    
    # Create export job record
    ExportJob.objects.create(
        file_name='search_results.csv',
        file_format='csv',
        status='completed',
        filters_applied={'status': status_filter, 'source': source_filter},
        created_by=request.user.username if request.user.is_authenticated else 'anonymous',
        completed_at=timezone.now()
    )
    
    return response


@login_required
def export_matches_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="keyword_matches.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Person Name', 'Company', 'Keyword', 'Category',
        'Context Snippet', 'Source URL', 'Match Count', 
        'Confidence Score', 'Found At'
    ])
    
    matches = Match.objects.select_related(
        'search_result__person', 
        'search_result__person__company', 
        'keyword'
    )
    
    # Apply filters
    keyword_filter = request.GET.get('keyword')
    if keyword_filter:
        matches = matches.filter(keyword__word__icontains=keyword_filter)
    
    category_filter = request.GET.get('category')
    if category_filter:
        matches = matches.filter(keyword__category=category_filter)
    
    for match in matches:
        created_at = match.created_at.strftime('%Y-%m-%d %H:%M:%S') if match.created_at else ''
        writer.writerow([
            match.search_result.person.name,
            match.search_result.person.company.name,
            match.keyword.word,
            match.keyword.get_category_display(),
            match.context_snippet[:300],
            match.source_url,
            match.match_count,
            match.confidence_score,
            created_at,
        ])
    
    ExportJob.objects.create(
        file_name='keyword_matches.csv',
        file_format='csv',
        status='completed',
        filters_applied={'keyword': keyword_filter, 'category': category_filter},
        created_by=request.user.username if request.user.is_authenticated else 'anonymous',
        completed_at=timezone.now()
    )
    
    return response


@login_required
def export_people_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="people.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Name', 'Company', 'Website', 'LinkedIn URL', 
        'Has LinkedIn', 'Total Matches', 'Created At', 'Last Updated'
    ])
    
    people = Person.objects.select_related('company').annotate(
        match_count=Count('search_results__matches')
    )
    
    for person in people:
        created_at = person.created_at.strftime('%Y-%m-%d %H:%M:%S') if person.created_at else ''
        updated_at = person.updated_at.strftime('%Y-%m-%d %H:%M:%S') if person.updated_at else ''
        writer.writerow([
            person.name,
            person.company.name,
            person.company.website,
            person.linkedin_url,
            'Yes' if person.has_linkedin_url else 'No',
            person.match_count,
            created_at,
            updated_at,
        ])
    
    ExportJob.objects.create(
        file_name='people.csv',
        file_format='csv',
        status='completed',
        created_by=request.user.username if request.user.is_authenticated else 'anonymous',
        completed_at=timezone.now()
    )
    
    return response


@require_http_methods(["POST"])
def scrape_person(request, person_id):
    try:
        person = Person.objects.select_related('company').get(id=person_id)
    except Person.DoesNotExist:
        return JsonResponse({'error': 'Person not found'}, status=404)
    
    # Create scraping job
    job = ScrapingJob.objects.create(
        job_type='single',
        person=person,
        status='running',
        started_at=timezone.now()
    )
    
    cse_service = GoogleCSEService()
    parser = LinkedInParser()
    matcher = KeywordMatcher()
    
    search_result, created = SearchResult.objects.get_or_create(
        person=person,
        defaults={'status': 'pending'}
    )
    
    if not created:
        search_result.status = 'pending'
        search_result.error_message = ''
        search_result.save()
    
    try:
        linkedin_url = person.linkedin_url
        if not linkedin_url:
            search_results = cse_service.search_linkedin_profile(person.name, person.company.name)
            if search_results:
                linkedin_url = search_results[0].get('link', '')
                person.linkedin_url = linkedin_url
                person.save()
        
        if linkedin_url:
            profile_data = parser.scrape_profile(linkedin_url)
            
            if profile_data.get('error'):
                search_result.status = 'failed'
                search_result.error_message = f"Scraping error: {profile_data.get('error')}"
                search_result.save()
                job.status = 'failed'
                job.error_message = search_result.error_message
                job.completed_at = timezone.now()
                job.save()
                return JsonResponse({
                    'success': False,
                    'error': profile_data.get('error'),
                    'job_id': job.id
                })
            
            if profile_data.get('auth_wall'):
                search_result.status = 'failed'
                search_result.error_message = 'LinkedIn requires authentication - profile not publicly accessible'
                search_result.save()
                job.status = 'failed'
                job.error_message = search_result.error_message
                job.completed_at = timezone.now()
                job.save()
                return JsonResponse({
                    'success': False,
                    'error': 'LinkedIn profile requires login to view',
                    'job_id': job.id
                })
            
            search_result.profile_content = profile_data.get('full_content', '')
            search_result.profile_headline = profile_data.get('headline', '')
            search_result.profile_about = profile_data.get('about', '')
            search_result.profile_experience = profile_data.get('experience', '')
            search_result.source_url = linkedin_url
            search_result.content_source = 'linkedin'
            search_result.status = 'completed'
            search_result.save()
            
            matches = matcher.find_matches(search_result)
            
            job.status = 'completed'
            job.success_count = 1
            job.processed_count = 1
            job.completed_at = timezone.now()
            job.save()
            
            return JsonResponse({
                'success': True,
                'person_id': person.id,
                'person_name': person.name,
                'linkedin_url': linkedin_url,
                'matches_found': len(matches),
                'job_id': job.id
            })
        else:
            search_result.status = 'failed'
            search_result.error_message = 'No LinkedIn profile found via search'
            search_result.save()
            job.status = 'failed'
            job.error_message = search_result.error_message
            job.completed_at = timezone.now()
            job.save()
            return JsonResponse({
                'success': False,
                'error': 'No LinkedIn profile found',
                'job_id': job.id
            })
            
    except Exception as e:
        search_result.status = 'failed'
        search_result.error_message = str(e)
        search_result.save()
        job.status = 'failed'
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save()
        return JsonResponse({
            'success': False,
            'error': str(e),
            'job_id': job.id
        }, status=500)


@require_http_methods(["POST"])
def scrape_all_pending(request):
    """Scrape all pending people (original function)"""
    people_without_results = Person.objects.filter(
        Q(search_results__isnull=True) | Q(search_results__status='pending')
    ).distinct()[:10]
    
    job = ScrapingJob.objects.create(
        total_people=people_without_results.count(),
        status='running',
        started_at=timezone.now()
    )
    
    results = []
    cse_service = GoogleCSEService()
    parser = LinkedInParser()
    matcher = KeywordMatcher()
    
    for person in people_without_results:
        try:
            linkedin_url = person.linkedin_url
            if not linkedin_url:
                search_results = cse_service.search_linkedin_profile(person.name, person.company.name)
                if search_results:
                    linkedin_url = search_results[0].get('link', '')
                    person.linkedin_url = linkedin_url
                    person.save()
            
            if linkedin_url:
                search_result, created = SearchResult.objects.get_or_create(
                    person=person,
                    defaults={'status': 'pending'}
                )
                
                if not created:
                    search_result.status = 'pending'
                    search_result.error_message = ''
                
                profile_data = parser.scrape_profile(linkedin_url)
                
                if profile_data.get('error') or profile_data.get('auth_wall'):
                    search_result.status = 'failed'
                    search_result.error_message = profile_data.get('error') or 'LinkedIn requires authentication'
                    search_result.save()
                    job.error_count += 1
                    job.processed_count += 1
                    job.save()
                    results.append({
                        'person': person.name,
                        'status': 'failed',
                        'error': search_result.error_message
                    })
                    continue
                
                search_result.profile_content = profile_data.get('full_content', '')
                search_result.profile_headline = profile_data.get('headline', '')
                search_result.profile_about = profile_data.get('about', '')
                search_result.profile_experience = profile_data.get('experience', '')
                search_result.source_url = linkedin_url
                search_result.content_source = 'linkedin'
                search_result.status = 'completed'
                search_result.save()
                
                matches = matcher.find_matches(search_result)
                
                job.success_count += 1
                job.processed_count += 1
                job.save()
                results.append({
                    'person': person.name,
                    'status': 'success',
                    'matches': len(matches)
                })
            else:
                search_result, _ = SearchResult.objects.get_or_create(
                    person=person,
                    defaults={'status': 'failed', 'error_message': 'No LinkedIn profile found'}
                )
                if search_result.status != 'failed':
                    search_result.status = 'failed'
                    search_result.error_message = 'No LinkedIn profile found'
                    search_result.save()
                    
                job.error_count += 1
                job.processed_count += 1
                job.save()
                results.append({
                    'person': person.name,
                    'status': 'failed',
                    'error': 'No LinkedIn profile found'
                })
                
        except Exception as e:
            job.error_count += 1
            job.processed_count += 1
            job.save()
            results.append({
                'person': person.name,
                'status': 'failed',
                'error': str(e)
            })
    
    job.status = 'completed'
    job.completed_at = timezone.now()
    job.save()
    
    return JsonResponse({
        'success': True,
        'job_id': job.id,
        'total_processed': job.processed_count,
        'success_count': job.success_count,
        'error_count': job.error_count,
        'results': results
    })


@require_http_methods(["POST"])
def scrape_batch(request):
    """Scrape a batch of people with configurable limits"""
    person_ids = request.POST.getlist('person_ids[]')
    
    if person_ids:
        people = Person.objects.filter(id__in=person_ids)
    else:
        # Get people without results or with failed results
        people = Person.objects.filter(
            Q(search_results__isnull=True) | 
            Q(search_results__status='failed')
        ).distinct()[:20]
    
    job = ScrapingJob.objects.create(
        job_type='batch',
        total_people=people.count(),
        status='running',
        started_at=timezone.now()
    )
    
    results = []
    cse_service = GoogleCSEService()
    parser = LinkedInParser()
    matcher = KeywordMatcher()
    
    for person in people:
        try:
            linkedin_url = person.linkedin_url
            if not linkedin_url:
                search_results = cse_service.search_linkedin_profile(person.name, person.company.name)
                if search_results:
                    linkedin_url = search_results[0].get('link', '')
                    person.linkedin_url = linkedin_url
                    person.save()
            
            if linkedin_url:
                search_result, created = SearchResult.objects.get_or_create(
                    person=person,
                    defaults={'status': 'pending'}
                )
                
                profile_data = parser.scrape_profile(linkedin_url)
                
                if profile_data.get('error') or profile_data.get('auth_wall'):
                    search_result.status = 'failed'
                    search_result.error_message = profile_data.get('error') or 'LinkedIn requires authentication'
                    search_result.save()
                    job.error_count += 1
                    results.append({
                        'person': person.name,
                        'status': 'failed',
                        'error': search_result.error_message
                    })
                else:
                    search_result.profile_content = profile_data.get('full_content', '')
                    search_result.profile_headline = profile_data.get('headline', '')
                    search_result.profile_about = profile_data.get('about', '')
                    search_result.profile_experience = profile_data.get('experience', '')
                    search_result.source_url = linkedin_url
                    search_result.content_source = 'linkedin'
                    search_result.status = 'completed'
                    search_result.save()
                    
                    matches = matcher.find_matches(search_result)
                    
                    job.success_count += 1
                    results.append({
                        'person': person.name,
                        'status': 'success',
                        'matches': len(matches)
                    })
            else:
                search_result, _ = SearchResult.objects.get_or_create(
                    person=person,
                    defaults={
                        'status': 'failed', 
                        'error_message': 'No LinkedIn profile found'
                    }
                )
                job.error_count += 1
                results.append({
                    'person': person.name,
                    'status': 'failed',
                    'error': 'No LinkedIn profile found'
                })
                
        except Exception as e:
            job.error_count += 1
            results.append({
                'person': person.name,
                'status': 'failed',
                'error': str(e)
            })
        
        job.processed_count += 1
        job.save()
    
    job.status = 'completed'
    job.completed_at = timezone.now()
    job.save()
    
    return JsonResponse({
        'success': True,
        'job_id': job.id,
        'total_processed': job.processed_count,
        'success_count': job.success_count,
        'error_count': job.error_count,
        'results': results
    })


@require_http_methods(["POST"])
def scrape_company_websites(request):
    """Scrape company websites for keywords"""
    company_id = request.POST.get('company_id')
    
    if company_id:
        companies = Company.objects.filter(id=company_id)
    else:
        companies = Company.objects.all()[:10]  # Limit for batch processing
    
    job = ScrapingJob.objects.create(
        job_type='company_websites',
        total_people=companies.count(),
        status='running',
        started_at=timezone.now()
    )
    
    # This would integrate with your website scraper
    # For now, just create a placeholder implementation
    results = []
    
    for company in companies:
        try:
            # TODO: Implement company website scraping
            # website_scraper.scrape_company_website(company.website)
            
            # Create search result for the company
            search_result = SearchResult.objects.create(
                person=None,  # Company-level result
                content_source='company_website',
                profile_content=f"Content from {company.website}",
                source_url=company.website,
                status='completed'
            )
            
            job.success_count += 1
            results.append({
                'company': company.name,
                'status': 'success',
                'website': company.website
            })
            
        except Exception as e:
            job.error_count += 1
            results.append({
                'company': company.name,
                'status': 'failed',
                'error': str(e)
            })
        
        job.processed_count += 1
        job.save()
    
    job.status = 'completed'
    job.completed_at = timezone.now()
    job.save()
    
    return JsonResponse({
        'success': True,
        'job_id': job.id,
        'results': results
    })


def get_job_status(request, job_id=None):
    """Get status of scraping jobs"""
    if job_id:
        try:
            job = ScrapingJob.objects.get(id=job_id)
            return JsonResponse({
                'id': job.id,
                'status': job.status,
                'progress_percentage': job.progress_percentage,
                'processed_count': job.processed_count,
                'total_people': job.total_people,
                'success_count': job.success_count,
                'error_count': job.error_count,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'duration': str(job.duration) if job.duration else None,
            })
        except ScrapingJob.DoesNotExist:
            return JsonResponse({'error': 'Job not found'}, status=404)
    else:
        # Return all recent jobs
        jobs = ScrapingJob.objects.order_by('-created_at')[:20]
        job_list = []
        for job in jobs:
            job_list.append({
                'id': job.id,
                'job_type': job.job_type,
                'status': job.status,
                'progress_percentage': job.progress_percentage,
                'processed_count': job.processed_count,
                'total_people': job.total_people,
                'success_count': job.success_count,
                'error_count': job.error_count,
                'created_at': job.created_at.isoformat(),
            })
        return JsonResponse(job_list, safe=False)


def get_stats(request):
    """Enhanced stats endpoint"""
    today = timezone.now().date()
    
    stats = {
        'total_companies': Company.objects.count(),
        'total_people': Person.objects.count(),
        'people_with_linkedin': Person.objects.exclude(linkedin_url='').count(),
        'total_keywords': Keyword.objects.filter(is_active=True).count(),
        'total_results': SearchResult.objects.filter(status='completed').count(),
        'total_matches': Match.objects.count(),
        'pending_scrapes': SearchResult.objects.filter(status='pending').count(),
        'failed_scrapes': SearchResult.objects.filter(status='failed').count(),
        'matches_today': Match.objects.filter(created_at__date=today).count(),
        'top_keywords': list(Keyword.objects.annotate(
            match_count=Count('matches')
        ).filter(match_count__gt=0).order_by('-match_count').values('word', 'match_count')[:10]),
        'recent_jobs': list(ScrapingJob.objects.values(
            'id', 'job_type', 'status', 'total_people', 'processed_count', 'created_at'
        ).order_by('-created_at')[:5])
    }
    return JsonResponse(stats)


# Placeholder functions for future implementation
def analyze_keywords(request):
    """Analyze keywords in content without saving matches"""
    content = request.GET.get('content', '')
    matcher = KeywordMatcher()
    results = matcher.analyze_keywords(content)
    return JsonResponse(results)


def batch_analyze_keywords(request):
    """Analyze keywords across multiple search results"""
    search_result_ids = request.GET.getlist('search_result_ids[]')
    if search_result_ids:
        search_results = SearchResult.objects.filter(id__in=search_result_ids)
    else:
        search_results = SearchResult.objects.filter(status='completed')[:10]
    
    matcher = KeywordMatcher()
    results = matcher.batch_analyze_keywords(search_results)
    return JsonResponse(results)


def get_match_summary(request, search_result_id):
    """Get detailed match summary for a search result"""
    try:
        search_result = SearchResult.objects.get(id=search_result_id)
        matcher = KeywordMatcher()
        summary = matcher.get_match_summary(search_result)
        return JsonResponse(summary)
    except SearchResult.DoesNotExist:
        return JsonResponse({'error': 'Search result not found'}, status=404)


def export_results_excel(response):
    """Placeholder for Excel export functionality"""
    # This would use pandas or openpyxl to create Excel file
    # For now, return a simple message
    response.write("Excel export functionality would be implemented here")
    return response