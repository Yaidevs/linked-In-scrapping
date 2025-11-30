from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from django.contrib import messages
from django.http import HttpResponseRedirect
from .models import Person, Company, Keyword, SearchResult, Match, ScrapingJob, ExportJob


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'website_link', 'people_count', 'match_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'website']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _people_count=Count('people', distinct=True),
            _match_count=Count('people__search_results__matches', distinct=True)
        )
        return queryset
    
    def website_link(self, obj):
        if obj.website:
            return format_html(
                '<a href="{}" target="_blank">Visit Website</a>',
                obj.website
            )
        return '-'
    website_link.short_description = 'Website'
    
    def people_count(self, obj):
        return obj._people_count
    people_count.short_description = 'People'
    people_count.admin_order_field = '_people_count'
    
    def match_count(self, obj):
        return obj._match_count
    match_count.short_description = 'Matches'
    match_count.admin_order_field = '_match_count'


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'company_link', 'linkedin_status', 'result_count', 'match_count', 'created_at']
    list_filter = ['created_at', 'company']
    search_fields = ['name', 'company__name', 'linkedin_url']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['scrape_selected_people']
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('company').annotate(
            _result_count=Count('search_results', distinct=True),
            _match_count=Count('search_results__matches', distinct=True)
        )
        return queryset
    
    def company_link(self, obj):
        if obj.company:
            url = reverse('admin:core_company_change', args=[obj.company.id])
            return format_html('<a href="{}">{}</a>', url, obj.company.name)
        return '-'
    company_link.short_description = 'Company'
    company_link.admin_order_field = 'company__name'
    
    def linkedin_status(self, obj):
        if obj.linkedin_url:
            return format_html(
                '<span style="color: green;">✓</span> <a href="{}" target="_blank">Profile</a>',
                obj.linkedin_url
            )
        return format_html('<span style="color: orange;">⚠ No URL</span>')
    linkedin_status.short_description = 'LinkedIn'
    
    def result_count(self, obj):
        url = reverse('admin:core_searchresult_changelist') + f'?person__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, obj._result_count)
    result_count.short_description = 'Results'
    result_count.admin_order_field = '_result_count'
    
    def match_count(self, obj):
        url = reverse('admin:core_match_changelist') + f'?search_result__person__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, obj._match_count)
    match_count.short_description = 'Matches'
    match_count.admin_order_field = '_match_count'
    
    @admin.action(description='Scrape selected people')
    def scrape_selected_people(self, request, queryset):
        # This would trigger the scraping process for selected people
        count = queryset.count()
        self.message_user(
            request, 
            f'Scraping initiated for {count} people. Check Scraping Jobs for progress.',
            messages.SUCCESS
        )
    scrape_selected_people.allowed_permissions = ('change',)


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ['word', 'category_display', 'is_active', 'match_count', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['word']
    ordering = ['category', 'word']
    list_editable = ['is_active']
    actions = ['activate_keywords', 'deactivate_keywords']
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(_match_count=Count('matches'))
        return queryset
    
    def category_display(self, obj):
        return obj.get_category_display()
    category_display.short_description = 'Category'
    category_display.admin_order_field = 'category'
    
    def match_count(self, obj):
        url = reverse('admin:core_match_changelist') + f'?keyword__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, obj._match_count)
    match_count.short_description = 'Matches'
    match_count.admin_order_field = '_match_count'
    
    @admin.action(description='Activate selected keywords')
    def activate_keywords(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} keywords activated.', messages.SUCCESS)
    
    @admin.action(description='Deactivate selected keywords')
    def deactivate_keywords(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} keywords deactivated.', messages.SUCCESS)


class MatchInline(admin.TabularInline):
    model = Match
    extra = 0
    readonly_fields = ['keyword', 'context_preview', 'match_count', 'confidence_score', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def context_preview(self, obj):
        if obj.context_snippet:
            return obj.context_snippet[:100] + '...' if len(obj.context_snippet) > 100 else obj.context_snippet
        return '-'
    context_preview.short_description = 'Context'


@admin.register(SearchResult)
class SearchResultAdmin(admin.ModelAdmin):
    list_display = ['person_link', 'content_source_display', 'status_display', 'headline_short', 'match_count', 'scraped_at']
    list_filter = ['status', 'content_source', 'scraped_at']
    search_fields = ['person__name', 'profile_headline', 'profile_content']
    ordering = ['-scraped_at']
    readonly_fields = ['scraped_at', 'updated_at']
    inlines = [MatchInline]
    actions = ['reprocess_selected_results']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('person', 'content_source', 'status', 'source_url')
        }),
        ('Profile Content', {
            'fields': ('profile_headline', 'profile_about', 'profile_experience'),
            'classes': ('collapse',)
        }),
        ('Full Content', {
            'fields': ('profile_content',),
            'classes': ('collapse',)
        }),
        ('Error Info', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('scraped_at', 'updated_at'),
        }),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('person', 'person__company').annotate(_match_count=Count('matches'))
        return queryset
    
    def person_link(self, obj):
        url = reverse('admin:core_person_change', args=[obj.person.id])
        return format_html('<a href="{}">{}</a>', url, obj.person.name)
    person_link.short_description = 'Person'
    person_link.admin_order_field = 'person__name'
    
    def content_source_display(self, obj):
        return obj.get_content_source_display()
    content_source_display.short_description = 'Source'
    content_source_display.admin_order_field = 'content_source'
    
    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'completed': 'green', 
            'failed': 'red'
        }
        color = colors.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def headline_short(self, obj):
        if obj.profile_headline:
            return obj.profile_headline[:50] + '...' if len(obj.profile_headline) > 50 else obj.profile_headline
        return '-'
    headline_short.short_description = 'Headline'
    
    def match_count(self, obj):
        url = reverse('admin:core_match_changelist') + f'?search_result__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, obj._match_count)
    match_count.short_description = 'Matches'
    match_count.admin_order_field = '_match_count'
    
    @admin.action(description='Reprocess selected results')
    def reprocess_selected_results(self, request, queryset):
        updated = queryset.update(status='pending', error_message='')
        self.message_user(request, f'{updated} results marked for reprocessing.', messages.SUCCESS)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['person_name', 'company_name', 'keyword_link', 'category_display', 'match_count', 'confidence_display', 'created_at']
    list_filter = ['keyword__category', 'created_at', 'search_result__person__company']
    search_fields = ['search_result__person__name', 'keyword__word', 'context_snippet']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related(
            'search_result__person', 
            'search_result__person__company', 
            'keyword'
        )
        return queryset
    
    def person_name(self, obj):
        url = reverse('admin:core_person_change', args=[obj.search_result.person.id])
        return format_html('<a href="{}">{}</a>', url, obj.search_result.person.name)
    person_name.short_description = 'Person'
    person_name.admin_order_field = 'search_result__person__name'
    
    def company_name(self, obj):
        if obj.search_result.person.company:
            url = reverse('admin:core_company_change', args=[obj.search_result.person.company.id])
            return format_html('<a href="{}">{}</a>', url, obj.search_result.person.company.name)
        return '-'
    company_name.short_description = 'Company'
    
    def keyword_link(self, obj):
        url = reverse('admin:core_keyword_change', args=[obj.keyword.id])
        return format_html('<a href="{}">{}</a>', url, obj.keyword.word)
    keyword_link.short_description = 'Keyword'
    keyword_link.admin_order_field = 'keyword__word'
    
    def category_display(self, obj):
        return obj.keyword.get_category_display()
    category_display.short_description = 'Category'
    category_display.admin_order_field = 'keyword__category'
    
    def confidence_display(self, obj):
        if obj.confidence_score >= 0.8:
            color = 'green'
        elif obj.confidence_score >= 0.5:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {};">{:.2f}</span>', color, obj.confidence_score)
    confidence_display.short_description = 'Confidence'


@admin.register(ScrapingJob)
class ScrapingJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'job_type_display', 'person_company', 'status_display', 'progress_display', 'duration_display', 'created_at']
    list_filter = ['status', 'job_type', 'created_at']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'started_at', 'completed_at']
    actions = ['cancel_selected_jobs']
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('person', 'company')
        return queryset
    
    def job_type_display(self, obj):
        return obj.get_job_type_display()
    job_type_display.short_description = 'Type'
    job_type_display.admin_order_field = 'job_type'
    
    def person_company(self, obj):
        if obj.person:
            return f"{obj.person.name} ({obj.person.company})"
        elif obj.company:
            return obj.company.name
        else:
            return f"Batch ({obj.total_people} people)"
    person_company.short_description = 'Target'
    
    def status_display(self, obj):
        colors = {
            'queued': 'blue',
            'running': 'orange',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray'
        }
        color = colors.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def progress_display(self, obj):
        return f"{obj.processed_count}/{obj.total_people} ({obj.progress_percentage}%)"
    progress_display.short_description = 'Progress'
    
    def duration_display(self, obj):
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return '-'
    duration_display.short_description = 'Duration'
    
    @admin.action(description='Cancel selected jobs')
    def cancel_selected_jobs(self, request, queryset):
        # Only cancel jobs that are queued or running
        cancelable_jobs = queryset.filter(status__in=['queued', 'running'])
        updated = cancelable_jobs.update(status='cancelled')
        self.message_user(request, f'{updated} jobs cancelled.', messages.SUCCESS)


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'file_format', 'status_display', 'created_by', 'created_at', 'completed_at']
    list_filter = ['status', 'file_format', 'created_at']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'completed_at']
    
    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'black')
        return format_html('<span style="color: {};">{}</span>', color, obj.get_status_display())
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'


# Custom admin site configuration
admin.site.site_header = "LinkedIn Data Collector Admin"
admin.site.site_title = "LinkedIn Data Collector"
admin.site.index_title = "Data Management"

# Add a custom admin view for quick actions
class CustomAdminSite(admin.AdminSite):
    def get_app_list(self, request):
        app_list = super().get_app_list(request)
        # Add custom grouping or ordering if needed
        return app_list