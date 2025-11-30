from django.db import models

class Company(models.Model):
    name = models.CharField(max_length=200)
    website = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def total_people(self):
        return self.people.count()

    @property
    def total_matches(self):
        return Match.objects.filter(search_result__person__company=self).count()


class Person(models.Model):
    name = models.CharField(max_length=200)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='people')
    linkedin_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "People"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.company})" if self.company else self.name

    @property
    def total_matches(self):
        return Match.objects.filter(search_result__person=self).count()

    @property
    def has_linkedin_url(self):
        return bool(self.linkedin_url and self.linkedin_url.strip())


class Keyword(models.Model):
    CATEGORY_CHOICES = [
        ('skill', 'Skill'),
        ('title', 'Job Title'),
        ('industry', 'Industry'),
        ('technology', 'Technology'),
        ('certification', 'Certification'),
        ('education', 'Education'),
        ('other', 'Other'),
    ]
    
    word = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, blank=True, default='other')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'word']

    def __str__(self):
        return f"{self.word} [{self.category}]" if self.category else self.word

    @property
    def match_count(self):
        return self.matches.count()


class SearchResult(models.Model):
    CONTENT_SOURCE_CHOICES = [
        ('linkedin', 'LinkedIn Profile'),
        ('company_website', 'Company Website'),
        ('google_search', 'Google Search Results'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='search_results')
    content_source = models.CharField(max_length=20, choices=CONTENT_SOURCE_CHOICES, default='linkedin')
    profile_content = models.TextField(blank=True)
    profile_headline = models.CharField(max_length=500, blank=True)
    profile_about = models.TextField(blank=True)
    profile_experience = models.TextField(blank=True)
    source_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scraped_at']

    def __str__(self):
        return f"Search result for {self.person.name} - {self.status}"

    @property
    def match_count(self):
        return self.matches.count()

    @property
    def has_content(self):
        return bool(self.profile_content.strip())


class Match(models.Model):
    search_result = models.ForeignKey(SearchResult, on_delete=models.CASCADE, related_name='matches')
    keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE, related_name='matches')
    context_snippet = models.TextField()
    source_url = models.URLField()
    match_count = models.PositiveIntegerField(default=1)
    confidence_score = models.FloatField(default=1.0)  # 0.0 to 1.0 for match relevance
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['search_result', 'keyword']
        verbose_name_plural = "Matches"

    def __str__(self):
        return f"{self.keyword.word} found in {self.search_result.person.name}'s profile"

    @property
    def person_name(self):
        return self.search_result.person.name

    @property
    def company_name(self):
        return self.search_result.person.company.name


class ScrapingJob(models.Model):
    JOB_TYPE_CHOICES = [
        ('single', 'Single Person'),
        ('batch', 'Batch Processing'),
        ('company_websites', 'Company Websites'),
    ]
    
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='batch')
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='scraping_jobs', null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='scraping_jobs', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    total_people = models.PositiveIntegerField(default=0)
    processed_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.person:
            return f"Job for {self.person.name} - {self.status}"
        elif self.company:
            return f"Job for {self.company.name} - {self.status}"
        return f"Batch job ({self.total_people} people) - {self.status}"

    @property
    def progress_percentage(self):
        if self.total_people == 0:
            return 0
        return int((self.processed_count / self.total_people) * 100)

    @property
    def duration(self):
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


class ExportJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
    ]
    
    file_name = models.CharField(max_length=255)
    file_format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='excel')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    file_path = models.CharField(max_length=500, blank=True)
    filters_applied = models.JSONField(default=dict, blank=True)  # Store filter criteria
    error_message = models.TextField(blank=True)
    created_by = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Export: {self.file_name} - {self.status}"








# from django.db import models



# class Person(models.Model):
#     name = models.CharField(max_length=200)
#     company = models.CharField(max_length=200, blank=True)
#     linkedin_url = models.URLField(blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         verbose_name_plural = "People"
#         ordering = ['-created_at']

#     def __str__(self):
#         return f"{self.name} ({self.company})" if self.company else self.name

#     @property
#     def total_matches(self):
#         return Match.objects.filter(search_result__person=self).count()


# class Keyword(models.Model):
#     CATEGORY_CHOICES = [
#         ('skill', 'Skill'),
#         ('title', 'Job Title'),
#         ('industry', 'Industry'),
#         ('technology', 'Technology'),
#         ('certification', 'Certification'),
#         ('education', 'Education'),
#         ('other', 'Other'),
#     ]
    
#     word = models.CharField(max_length=100, unique=True)
#     category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, blank=True, default='other')
#     is_active = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         ordering = ['category', 'word']

#     def __str__(self):
#         return f"{self.word} [{self.category}]" if self.category else self.word


# class SearchResult(models.Model):
#     STATUS_CHOICES = [
#         ('pending', 'Pending'),
#         ('completed', 'Completed'),
#         ('failed', 'Failed'),
#     ]
    
#     person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='search_results')
#     profile_content = models.TextField(blank=True)
#     profile_headline = models.CharField(max_length=500, blank=True)
#     profile_about = models.TextField(blank=True)
#     profile_experience = models.TextField(blank=True)
#     source_url = models.URLField(blank=True)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
#     error_message = models.TextField(blank=True)
#     scraped_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         ordering = ['-scraped_at']

#     def __str__(self):
#         return f"Search result for {self.person.name} - {self.status}"

#     @property
#     def match_count(self):
#         return self.matches.count()


# class Match(models.Model):
#     search_result = models.ForeignKey(SearchResult, on_delete=models.CASCADE, related_name='matches')
#     keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE, related_name='matches')
#     context_snippet = models.TextField()
#     source_url = models.URLField()
#     match_count = models.PositiveIntegerField(default=1)
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         ordering = ['-created_at']
#         unique_together = ['search_result', 'keyword']

#     def __str__(self):
#         return f"{self.keyword.word} found in {self.search_result.person.name}'s profile"


# class ScrapingJob(models.Model):
#     STATUS_CHOICES = [
#         ('queued', 'Queued'),
#         ('running', 'Running'),
#         ('completed', 'Completed'),
#         ('failed', 'Failed'),
#         ('cancelled', 'Cancelled'),
#     ]
    
#     person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='scraping_jobs', null=True, blank=True)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
#     total_people = models.PositiveIntegerField(default=0)
#     processed_count = models.PositiveIntegerField(default=0)
#     success_count = models.PositiveIntegerField(default=0)
#     error_count = models.PositiveIntegerField(default=0)
#     error_message = models.TextField(blank=True)
#     started_at = models.DateTimeField(null=True, blank=True)
#     completed_at = models.DateTimeField(null=True, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         ordering = ['-created_at']

#     def __str__(self):
#         if self.person:
#             return f"Job for {self.person.name} - {self.status}"
#         return f"Batch job ({self.total_people} people) - {self.status}"

#     @property
#     def progress_percentage(self):
#         if self.total_people == 0:
#             return 0
#         return int((self.processed_count / self.total_people) * 100)


#     # def __str__(self):
#     #     return f"{self.keyword.word} found in {self.search_result.person.name}'s profile"
