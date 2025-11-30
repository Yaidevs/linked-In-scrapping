from django.core.management.base import BaseCommand
from core.models import Person, Keyword


class Command(BaseCommand):
    help = 'Seed sample data for testing'

    def handle(self, *args, **options):
        sample_keywords = [
            ('Python', 'skill'),
            ('JavaScript', 'skill'),
            ('Machine Learning', 'skill'),
            ('Data Science', 'skill'),
            ('AWS', 'technology'),
            ('Docker', 'technology'),
            ('Kubernetes', 'technology'),
            ('React', 'technology'),
            ('Node.js', 'technology'),
            ('PostgreSQL', 'technology'),
            ('Software Engineer', 'title'),
            ('Senior Developer', 'title'),
            ('Tech Lead', 'title'),
            ('Product Manager', 'title'),
            ('Data Analyst', 'title'),
            ('Cloud Computing', 'skill'),
            ('DevOps', 'skill'),
            ('Agile', 'skill'),
            ('Scrum', 'skill'),
            ('Project Management', 'skill'),
            ('MBA', 'education'),
            ('Computer Science', 'education'),
            ('PMP', 'certification'),
            ('AWS Certified', 'certification'),
            ('Google Cloud', 'certification'),
            ('FinTech', 'industry'),
            ('Healthcare', 'industry'),
            ('E-commerce', 'industry'),
            ('SaaS', 'industry'),
            ('Startup', 'industry'),
        ]

        keyword_count = 0
        for word, category in sample_keywords:
            keyword, created = Keyword.objects.get_or_create(
                word=word,
                defaults={'category': category, 'is_active': True}
            )
            if created:
                keyword_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Created {keyword_count} sample keywords'
        ))

        sample_people = [
            ('John Smith', 'Tech Corp'),
            ('Jane Doe', 'Innovation Labs'),
            ('Mike Johnson', 'Data Systems Inc'),
        ]

        person_count = 0
        for name, company in sample_people:
            person, created = Person.objects.get_or_create(
                name=name,
                company=company
            )
            if created:
                person_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Created {person_count} sample people'
        ))

        self.stdout.write(self.style.SUCCESS('Sample data seeding completed!'))
