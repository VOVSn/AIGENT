import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction # For atomic operations
from aigents.models import Prompt, Aigent # Import your models

# Determine the path to the fixtures directory relative to the project's BASE_DIR
# BASE_DIR in settings.py is AIGENT/backend/
# So, backend/fixtures/initial_data.json
DEFAULT_FIXTURE_PATH = settings.BASE_DIR / "fixtures" / "initial_data.json"

class Command(BaseCommand):
    help = 'Seeds the database with initial data for Prompts and Aigents from a JSON file.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fixture_path',
            type=str,
            default=str(DEFAULT_FIXTURE_PATH),
            help='Path to the JSON fixture file to load data from.',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing Prompts and Aigents with the same name.',
        )


    @transaction.atomic # Ensures all or no database operations are committed
    def handle(self, *args, **options):
        fixture_path = Path(options['fixture_path'])
        overwrite = options['overwrite']

        if not fixture_path.exists():
            self.stderr.write(self.style.ERROR(f"Fixture file not found: {fixture_path}"))
            return

        try:
            with open(fixture_path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            self.stderr.write(self.style.ERROR(f"Invalid JSON in fixture file: {fixture_path}"))
            return
        except IOError:
            self.stderr.write(self.style.ERROR(f"Could not read fixture file: {fixture_path}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Starting data seeding from {fixture_path}..."))

        # Seed Prompts
        prompts_data = data.get("prompts", [])
        created_prompts_map = {} # To store created prompt objects by name

        if prompts_data:
            self.stdout.write(self.style.HTTP_INFO("Seeding Prompts..."))
            for prompt_data in prompts_data:
                prompt_name = prompt_data.get("name")
                if not prompt_name:
                    self.stderr.write(self.style.WARNING("Skipping prompt with no name."))
                    continue

                if overwrite:
                    prompt, created = Prompt.objects.update_or_create(
                        name=prompt_name,
                        defaults={'template_str': prompt_data.get("template_str", "")}
                    )
                    action = "Created" if created else "Updated"
                else:
                    prompt, created = Prompt.objects.get_or_create(
                        name=prompt_name,
                        defaults={'template_str': prompt_data.get("template_str", "")}
                    )
                    action = "Created" if created else "Skipped (exists)"

                if created or (overwrite and not created): # Log if created or if updated
                    self.stdout.write(self.style.SUCCESS(f"{action} Prompt: {prompt.name}"))
                elif not created and not overwrite:
                    self.stdout.write(self.style.NOTICE(f"{action} Prompt: {prompt.name}"))

                created_prompts_map[prompt.name] = prompt # Store for Aigent linking
        else:
            self.stdout.write(self.style.NOTICE("No prompts found in the fixture to seed."))


        # Seed Aigents
        aigents_data = data.get("aigents", [])
        if aigents_data:
            self.stdout.write(self.style.HTTP_INFO("Seeding Aigents..."))
            for aigent_data in aigents_data:
                aigent_name = aigent_data.get("name")
                if not aigent_name:
                    self.stderr.write(self.style.WARNING("Skipping aigent with no name."))
                    continue

                # Prepare Aigent defaults
                defaults = {
                    "is_active": aigent_data.get("is_active", False),
                    "system_persona_prompt": aigent_data.get("system_persona_prompt", ""),
                    "ollama_model_name": aigent_data.get("ollama_model_name", "llama3:latest"),
                    "ollama_endpoints": aigent_data.get("ollama_endpoints", [settings.OLLAMA_DEFAULT_ENDPOINT]), # Use .env default if not in fixture
                    "ollama_temperature": aigent_data.get("ollama_temperature"),
                    "ollama_context_length": aigent_data.get("ollama_context_length"),
                    "aigent_state": aigent_data.get("aigent_state", {}),
                    "request_timeout_seconds": aigent_data.get("request_timeout_seconds", 60),
                }

                # Link to default_prompt_template
                prompt_template_name = aigent_data.get("default_prompt_template_name")
                if prompt_template_name:
                    prompt_obj = created_prompts_map.get(prompt_template_name)
                    if prompt_obj:
                        defaults["default_prompt_template"] = prompt_obj
                    else:
                        self.stderr.write(self.style.WARNING(
                            f"Prompt template '{prompt_template_name}' not found for Aigent '{aigent_name}'. Skipping linking."
                        ))
                else:
                    defaults["default_prompt_template"] = None


                if overwrite:
                    # Special handling for is_active to ensure only one is active
                    if defaults.get("is_active"):
                         Aigent.objects.filter(is_active=True).exclude(name=aigent_name).update(is_active=False)

                    aigent, created = Aigent.objects.update_or_create(
                        name=aigent_name,
                        defaults=defaults
                    )
                    action = "Created" if created else "Updated"
                else:
                    # If not overwriting and is_active is true, ensure it doesn't conflict if another is active
                    if defaults.get("is_active") and Aigent.objects.filter(is_active=True).exists():
                        if not Aigent.objects.filter(name=aigent_name, is_active=True).exists():
                            self.stdout.write(self.style.NOTICE(
                                f"An active Aigent already exists. Setting '{aigent_name}' to inactive to avoid conflict (use --overwrite to change)."
                            ))
                            defaults["is_active"] = False # Prevent conflict

                    aigent, created = Aigent.objects.get_or_create(
                        name=aigent_name,
                        defaults=defaults
                    )
                    action = "Created" if created else "Skipped (exists)"

                if created or (overwrite and not created):
                    self.stdout.write(self.style.SUCCESS(f"{action} Aigent: {aigent.name} (Active: {aigent.is_active})"))
                elif not created and not overwrite:
                     self.stdout.write(self.style.NOTICE(f"{action} Aigent: {aigent.name}"))

        else:
            self.stdout.write(self.style.NOTICE("No aigents found in the fixture to seed."))

        self.stdout.write(self.style.SUCCESS("Data seeding completed."))