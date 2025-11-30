import csv
from django.core.management.base import BaseCommand
from core.models import Keyword


class Command(BaseCommand):
    help = 'Import keywords from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file containing keywords',
        )
        parser.add_argument(
            '--category',
            type=str,
            default='other',
            help='Default category for keywords without one',
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        default_category = options['category']
        
        created_count = 0
        updated_count = 0
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                if 'word' not in reader.fieldnames:
                    reader = csv.reader(open(csv_file, 'r', encoding='utf-8'))
                    for row in reader:
                        if row:
                            word = row[0].strip()
                            category = row[1].strip() if len(row) > 1 else default_category
                            
                            keyword, created = Keyword.objects.get_or_create(
                                word=word,
                                defaults={'category': category, 'is_active': True}
                            )
                            
                            if created:
                                created_count += 1
                            else:
                                updated_count += 1
                else:
                    for row in reader:
                        word = row.get('word', '').strip()
                        if not word:
                            continue
                            
                        category = row.get('category', default_category).strip() or default_category
                        is_active = row.get('is_active', 'true').lower() in ('true', '1', 'yes')
                        
                        keyword, created = Keyword.objects.get_or_create(
                            word=word,
                            defaults={'category': category, 'is_active': is_active}
                        )
                        
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
            
            self.stdout.write(self.style.SUCCESS(
                f'Import completed: {created_count} created, {updated_count} already existed'
            ))
            
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {csv_file}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error importing keywords: {e}'))
