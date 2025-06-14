# backend/tools/management/commands/test_searxng.py

import httpx
import json
import os
import re
from django.core.management.base import BaseCommand

SEARXNG_INTERNAL_URL = os.environ.get("SEARXNG_INTERNAL_URL", "http://searxng:8080")
TEST_QUERY = "what is the capital of France"

class Command(BaseCommand):
    help = "Tests the connection and functionality of the searxng service using session-based approach."

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO(f"--- Running Searxng Health Check ---"))
        self.stdout.write(f"Target URL: {SEARXNG_INTERNAL_URL}")
        self.stdout.write(f"Test Query: '{TEST_QUERY}'")
        self.stdout.write("-" * 35)

        base_url = SEARXNG_INTERNAL_URL.rstrip('/')
        
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                # Step 1: Get the main page to establish session and get any CSRF tokens
                self.stdout.write("1. Getting main page to establish session...")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
                
                main_response = client.get(f"{base_url}/", headers=headers)
                self.stdout.write(f"   Main page status: {main_response.status_code}")
                
                if main_response.status_code != 200:
                    self.stdout.write(f"   Failed to get main page: {main_response.text[:500]}")
                    return

                # Step 2: Extract any CSRF token or form data from the main page
                csrf_token = None
                csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', main_response.text)
                if csrf_match:
                    csrf_token = csrf_match.group(1)
                    self.stdout.write(f"   Found CSRF token: {csrf_token[:20]}...")

                # Step 3: Try the search with proper session cookies and headers
                self.stdout.write("2. Attempting search with session...")
                
                search_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'application/json, text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Referer': f"{base_url}/",
                    'Connection': 'keep-alive',
                    'X-Requested-With': 'XMLHttpRequest',  # This might help
                    'Cache-Control': 'no-cache',
                }
                
                search_params = {
                    'q': TEST_QUERY,
                    'format': 'json',
                    'categories': 'general',
                }
                
                if csrf_token:
                    search_params['csrf_token'] = csrf_token

                # Try multiple approaches
                search_methods = [
                    ('GET /search', 'GET', f"{base_url}/search", search_params),
                    ('POST /search', 'POST', f"{base_url}/search", search_params),
                    ('GET /', 'GET', f"{base_url}/", search_params),
                    ('POST /', 'POST', f"{base_url}/", search_params),
                ]
                
                for method_name, method, url, params in search_methods:
                    try:
                        self.stdout.write(f"   Trying {method_name}...")
                        
                        if method == 'GET':
                            search_response = client.get(url, params=params, headers=search_headers)
                        else:
                            search_response = client.post(url, data=params, headers=search_headers)
                        
                        self.stdout.write(f"   {method_name} status: {search_response.status_code}")
                        
                        if search_response.status_code == 200:
                            try:
                                data = search_response.json()
                                results = data.get("results", [])
                                
                                if results:
                                    self.stdout.write(self.style.SUCCESS(f"\nSUCCESS! Found working method: {method_name}"))
                                    self.stdout.write(f"Found {len(results)} results. Sample result:")
                                    self.stdout.write(f"  Title: {results[0].get('title', 'N/A')}")
                                    self.stdout.write(f"  URL: {results[0].get('url', 'N/A')}")
                                    self.stdout.write(f"  Content: {results[0].get('content', 'N/A')[:100]}...")
                                    return
                                else:
                                    self.stdout.write(f"   {method_name}: Got JSON but no results")
                                    
                            except json.JSONDecodeError:
                                # Maybe it returned HTML, let's check if it's a search results page
                                if 'results' in search_response.text.lower() or len(search_response.text) > 1000:
                                    self.stdout.write(f"   {method_name}: Got HTML response (might be working)")
                                    self.stdout.write(f"   Response length: {len(search_response.text)} chars")
                                else:
                                    self.stdout.write(f"   {method_name}: Got non-JSON response: {search_response.text[:200]}...")
                        else:
                            self.stdout.write(f"   {method_name}: HTTP {search_response.status_code}")
                            if search_response.status_code == 403:
                                self.stdout.write(f"   Still getting 403 Forbidden")
                                
                    except Exception as e:
                        self.stdout.write(f"   {method_name}: Exception - {e}")

                self.stderr.write(self.style.ERROR(
                    "\nERROR: All search methods failed. SearXNG is blocking programmatic access."
                ))

        except httpx.ConnectError as e:
            self.stderr.write(self.style.ERROR(
                f"\nERROR: Connection failed. Cannot reach searxng at {SEARXNG_INTERNAL_URL}"
            ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"\nUnexpected error: {e}"))
        
        self.stdout.write(self.style.HTTP_INFO("\n--- Health Check Complete ---"))