import requests
import time
from urllib.parse import urlencode
from django.core.management.base import BaseCommand

# The internal URL for the searxng service from within the Docker network
SEARXNG_URL = "http://searxng:8080"

class Command(BaseCommand):
    help = 'Tests the connection and JSON search functionality of the SearXNG service.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO(f"🚀 Starting SearXNG Test Suite for {SEARXNG_URL}"))
        
        if not self.wait_for_service():
            self.stdout.write(self.style.ERROR("❌ Test failed: SearXNG service did not become available."))
            return

        self.test_json_search()

    def wait_for_service(self, timeout=30):
        self.stdout.write("⏳ Waiting for SearXNG service to be ready...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{SEARXNG_URL}/", timeout=5)
                if response.status_code == 200:
                    self.stdout.write(self.style.SUCCESS("✅ SearXNG service is ready!"))
                    return True
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(2)
        
        return False

    def test_json_search(self, query="artificial intelligence", category="general"):
        self.stdout.write(self.style.HTTP_INFO(f"\n🔍 Testing JSON search for: '{query}'"))
        
        params = {'q': query, 'format': 'json', 'categories': category}
        
        try:
            url = f"{SEARXNG_URL}/search"
            self.stdout.write(f"   Making request to: {url}?{urlencode(params)}")
            
            response = requests.get(url, params=params, timeout=15)
            self.stdout.write(f"   Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if results:
                    self.stdout.write(self.style.SUCCESS("✅ JSON Search successful!"))
                    self.stdout.write(f"   Number of results found: {len(results)}")
                    
                    self.stdout.write(self.style.HTTP_INFO("\n--- Top 3 Results ---"))
                    for i, result in enumerate(results[:3], 1):
                        self.stdout.write(self.style.SQL_KEYWORD(f"   {i}. {result.get('title', 'No title')}"))
                        self.stdout.write(f"      URL: {result.get('url', 'No URL')}")
                        self.stdout.write(f"      Content: {result.get('content', 'No content')[:100]}...")
                    self.stdout.write(self.style.SUCCESS("\n🎯 Test PASSED."))
                else:
                    self.stdout.write(self.style.WARNING("⚠️ JSON Search returned 200 OK, but no results were found."))
                    self.stdout.write(self.style.ERROR("🎯 Test FAILED."))
                return True
            else:
                self.stdout.write(self.style.ERROR(f"❌ JSON Search failed with status {response.status_code}"))
                self.stdout.write(f"   Response: {response.text[:500]}")
                self.stdout.write(self.style.ERROR("🎯 Test FAILED."))
                return False
                
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f"❌ JSON Search failed with an exception: {e}"))
            self.stdout.write(self.style.ERROR("🎯 Test FAILED."))
            return False