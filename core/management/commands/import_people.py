import csv
from django.core.management.base import BaseCommand
from core.models import Person


class Command(BaseCommand):
    help = 'Import people from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file containing people',
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        
        created_count = 0
        updated_count = 0
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                if not reader.fieldnames or 'name' not in reader.fieldnames:
                    f.seek(0)
                    reader = csv.reader(f)
                    for row in reader:
                        if row:
                            name = row[0].strip()
                            company = row[1].strip() if len(row) > 1 else ''
                            linkedin_url = row[2].strip() if len(row) > 2 else ''
                            
                            person, created = Person.objects.get_or_create(
                                name=name,
                                company=company,
                                defaults={'linkedin_url': linkedin_url}
                            )
                            
                            if created:
                                created_count += 1
                            else:
                                updated_count += 1
                else:
                    for row in reader:
                        name = row.get('name', '').strip()
                        if not name:
                            continue
                            
                        company = row.get('company', '').strip()
                        linkedin_url = row.get('linkedin_url', '').strip()
                        
                        person, created = Person.objects.get_or_create(
                            name=name,
                            company=company,
                            defaults={'linkedin_url': linkedin_url}
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
            self.stdout.write(self.style.ERROR(f'Error importing people: {e}'))
