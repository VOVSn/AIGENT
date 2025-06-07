import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from aigents.models import Prompt, Aigent

DEFAULT_FIXTURE_PATH = settings.BASE_DIR / "fixtures" / "initial_data.json"

class Command(BaseCommand):
    help = 'Seeds the database with initial data for Prompts and Aigents from a JSON file.'

    def add_arguments(self, parser):
        parser.add_argument('--fixture_path', type=str, default=str(DEFAULT_FIXTURE_PATH), help='Path to the JSON fixture file.')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite existing Prompts and Aigents with the same name.')

    @transaction.atomic
    def handle(self, *args, **options):
        fixture_path = Path(options['fixture_path'])
        overwrite = options['overwrite']

        if not fixture_path.exists():
            self.stderr.write(self.style.ERROR(f"Fixture file not found: {fixture_path}"))
            return

        try:
            with open(fixture_path, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.stderr.write(self.style.ERROR(f"Error reading fixture file: {e}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Starting data seeding from {fixture_path}..."))

        prompts_data = data.get("prompts", [])
        created_prompts_map = self.seed_prompts(prompts_data, overwrite)

        aigents_data = data.get("aigents", [])
        self.seed_aigents(aigents_data, created_prompts_map, overwrite)

        self.stdout.write(self.style.SUCCESS("Data seeding completed."))

    def seed_prompts(self, prompts_data, overwrite):
        created_prompts_map = {}
        if not prompts_data:
            self.stdout.write(self.style.NOTICE("No prompts found in the fixture."))
            return created_prompts_map

        self.stdout.write(self.style.HTTP_INFO("Seeding Prompts..."))
        for prompt_data in prompts_data:
            prompt_name = prompt_data.get("name")
            if not prompt_name:
                self.stderr.write(self.style.WARNING("Skipping prompt with no name."))
                continue

            defaults = {'template_str': prompt_data.get("template_str", "")}
            if overwrite:
                prompt, created = Prompt.objects.update_or_create(name=prompt_name, defaults=defaults)
                action = "Created" if created else "Updated"
            else:
                prompt, created = Prompt.objects.get_or_create(name=prompt_name, defaults=defaults)
                action = "Created" if created else "Skipped (exists)"

            style = self.style.SUCCESS if created or overwrite else self.style.NOTICE
            self.stdout.write(style(f"{action} Prompt: {prompt.name}"))
            created_prompts_map[prompt.name] = prompt
        
        return created_prompts_map

    def seed_aigents(self, aigents_data, created_prompts_map, overwrite):
        if not aigents_data:
            self.stdout.write(self.style.NOTICE("No aigents found in the fixture."))
            return

        self.stdout.write(self.style.HTTP_INFO("Seeding Aigents..."))
        for aigent_data in aigents_data:
            aigent_name = aigent_data.get("name")
            if not aigent_name:
                self.stderr.write(self.style.WARNING("Skipping aigent with no name."))
                continue

            defaults = {
                "is_active": aigent_data.get("is_active", False),
                "presentation_format": aigent_data.get("presentation_format", "markdown"),
                "system_persona_prompt": aigent_data.get("system_persona_prompt", ""),
                "ollama_model_name": aigent_data.get("ollama_model_name", "llama3:latest"),
                "ollama_endpoints": aigent_data.get("ollama_endpoints", [settings.OLLAMA_DEFAULT_ENDPOINT]),
                "ollama_temperature": aigent_data.get("ollama_temperature"),
                "ollama_context_length": aigent_data.get("ollama_context_length"),
                "aigent_state": aigent_data.get("aigent_state", {}),
                "request_timeout_seconds": aigent_data.get("request_timeout_seconds", 60),
                "default_prompt_template": created_prompts_map.get(aigent_data.get("default_prompt_template_name"))
            }

            if overwrite:
                if defaults["is_active"]:
                    Aigent.objects.filter(is_active=True).exclude(name=aigent_name).update(is_active=False)
                aigent, created = Aigent.objects.update_or_create(name=aigent_name, defaults=defaults)
                action = "Created" if created else "Updated"
            else:
                if defaults["is_active"] and Aigent.objects.filter(is_active=True).exclude(name=aigent_name).exists():
                    self.stdout.write(self.style.NOTICE(f"An active Aigent already exists. Setting '{aigent_name}' to inactive."))
                    defaults["is_active"] = False
                aigent, created = Aigent.objects.get_or_create(name=aigent_name, defaults=defaults)
                action = "Created" if created else "Skipped (exists)"
            
            style = self.style.SUCCESS if created or overwrite else self.style.NOTICE
            self.stdout.write(style(f"{action} Aigent: {aigent.name} (Active: {aigent.is_active})"))