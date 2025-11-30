# from django.urls import path
# from . import views

# app_name = 'core'

# urlpatterns = [
#     path('', views.dashboard, name='dashboard'),
#     path('export/results/', views.export_results_csv, name='export_results'),
#     path('export/matches/', views.export_matches_csv, name='export_matches'),
#     path('export/people/', views.export_people_csv, name='export_people'),
#     path('api/scrape/<int:person_id>/', views.scrape_person, name='scrape_person'),
#     path('api/scrape-all/', views.scrape_all_pending, name='scrape_all'),
#     path('api/stats/', views.get_stats, name='get_stats'),
# ]


from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Main dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Export endpoints
    path('export/results/', views.export_results_csv, name='export_results'),
    path('export/matches/', views.export_matches_csv, name='export_matches'),
    path('export/people/', views.export_people_csv, name='export_people'),
    
    # Scraping API endpoints
    path('api/scrape/<int:person_id>/', views.scrape_person, name='scrape_person'),
    path('api/scrape-all/', views.scrape_all_pending, name='scrape_all'),
    path('api/scrape-batch/', views.scrape_batch, name='scrape_batch'),
    path('api/scrape-company-websites/', views.scrape_company_websites, name='scrape_company_websites'),
    
    # Job management endpoints
    path('api/jobs/', views.get_job_status, name='get_jobs'),
    path('api/jobs/<int:job_id>/', views.get_job_status, name='get_job_status'),
    
    # Stats and data endpoints
    path('api/stats/', views.get_stats, name='get_stats'),
    
    # New endpoints from enhanced views:
    path('api/analyze-keywords/', views.analyze_keywords, name='analyze_keywords'),
    path('api/batch-analyze/', views.batch_analyze_keywords, name='batch_analyze'),
    path('api/match-summary/<int:search_result_id>/', views.get_match_summary, name='get_match_summary'),
]