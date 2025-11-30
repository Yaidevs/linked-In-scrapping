from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from core.models import Person, SearchResult, ScrapingJob
from scraper.google_cse import GoogleCSEService
from scraper.linkedin_parser import LinkedInParser
from scraper.keyword_matcher import KeywordMatcher


class Command(BaseCommand):
    help = 'Scrape LinkedIn profiles for people in the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--person-id',
            type=int,
            help='Scrape a specific person by ID',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of people to process (default: 10)',
        )
        parser.add_argument(
            '--pending-only',
            action='store_true',
            help='Only scrape people without completed results',
        )

    def handle(self, *args, **options):
        cse_service = GoogleCSEService()
        profile_parser = LinkedInParser()
        matcher = KeywordMatcher()

        if options['person_id']:
            try:
                people = [Person.objects.get(id=options['person_id'])]
            except Person.DoesNotExist:
                raise CommandError(f"Person with ID {options['person_id']} not found")
        elif options['pending_only']:
            people = list(Person.objects.filter(
                Q(search_results__isnull=True) | Q(search_results__status='pending')
            ).distinct()[:options['limit']])
        else:
            people = list(Person.objects.all()[:options['limit']])

        if not people:
            self.stdout.write(self.style.WARNING('No people to process'))
            return

        job = ScrapingJob.objects.create(
            total_people=len(people),
            status='running',
            started_at=timezone.now()
        )

        self.stdout.write(f'Processing {len(people)} people...')

        for person in people:
            self.stdout.write(f'  Processing: {person.name}')
            
            try:
                linkedin_url = person.linkedin_url
                if not linkedin_url:
                    self.stdout.write('    Searching for LinkedIn profile...')
                    search_results = cse_service.search_linkedin_profile(person.name, person.company)
                    if search_results:
                        linkedin_url = search_results[0].get('link', '')
                        person.linkedin_url = linkedin_url
                        person.save()
                        self.stdout.write(f'    Found: {linkedin_url}')

                if linkedin_url:
                    search_result, created = SearchResult.objects.get_or_create(
                        person=person,
                        defaults={'status': 'pending'}
                    )
                    
                    if not created:
                        search_result.status = 'pending'
                        search_result.error_message = ''
                        search_result.save()

                    self.stdout.write('    Scraping profile...')
                    profile_data = profile_parser.scrape_profile(linkedin_url)
                    
                    if profile_data.get('error') or profile_data.get('auth_wall'):
                        error_msg = profile_data.get('error') or 'LinkedIn requires authentication'
                        search_result.status = 'failed'
                        search_result.error_message = error_msg
                        search_result.save()
                        job.error_count += 1
                        job.processed_count += 1
                        job.save()
                        self.stdout.write(
                            self.style.WARNING(f'    Failed: {error_msg}')
                        )
                        continue
                    
                    search_result.profile_content = profile_data.get('full_content', '')
                    search_result.profile_headline = profile_data.get('headline', '')
                    search_result.profile_about = profile_data.get('about', '')
                    search_result.profile_experience = profile_data.get('experience', '')
                    search_result.source_url = linkedin_url
                    search_result.status = 'completed'
                    search_result.save()

                    self.stdout.write('    Finding keyword matches...')
                    matches = matcher.find_matches(search_result)
                    
                    job.success_count += 1
                    job.processed_count += 1
                    job.save()
                    self.stdout.write(
                        self.style.SUCCESS(f'    Success: {len(matches)} matches found')
                    )
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
                    self.stdout.write(
                        self.style.WARNING('    No LinkedIn profile found')
                    )

            except Exception as e:
                job.error_count += 1
                job.processed_count += 1
                job.save()
                self.stdout.write(
                    self.style.ERROR(f'    Error: {str(e)}')
                )

        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save()

        self.stdout.write(self.style.SUCCESS(
            f'\nCompleted: {job.success_count} successful, {job.error_count} errors'
        ))
