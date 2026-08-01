from django.core.management.base import BaseCommand
from lipaidox.content_classification.models import PlatformCategory

class Command(BaseCommand):
    help = 'Seeds the platform categories from the frontend specification'

    def handle(self, *args, **kwargs):
        categories = [
            ('Fitness & Wellness',  'fitness-wellness',  1),
            ('Lifestyle',           'lifestyle',         2),
            ('Fashion & Beauty',    'fashion-beauty',    3),
            ('Cooking & Food',      'cooking-food',      4),
            ('Education',           'education',         5),
            ('Gaming',              'gaming',            6),
            ('Music',               'music',             7),
            ('Travel',              'travel',            8),
        ]

        for name, slug, order in categories:
            category, created = PlatformCategory.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'sort_order': order}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created category: {name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Category already exists: {name}'))

        self.stdout.write(self.style.SUCCESS('Seeding complete!'))
