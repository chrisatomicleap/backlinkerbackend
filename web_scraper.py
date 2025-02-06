import re
import json
import time
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import validators
from tqdm import tqdm
import os
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()

class WebScraper:
    def __init__(self, openai_api_key: str = None, delay: float = 2.0):
        """Initialize the scraper with configurable delay between requests."""
        self.delay = delay
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Set OpenAI API key
        if openai_api_key:
            openai.api_key = openai_api_key
        else:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set")
            openai.api_key = api_key
            
        # Reset any proxy settings that might be in the environment
        os.environ.pop('OPENAI_PROXY', None)
        os.environ.pop('OPENAI_HTTP_PROXY', None)
        os.environ.pop('OPENAI_HTTPS_PROXY', None)
        
        # Company and backlink information
        self.company_name = "Tanglewood Care Homes"
        self.backlink_url = "https://www.tanglewoodcarehomes.co.uk/understanding-dementia-care-guide-for-families-residents/"

    def extract_emails(self, text: str) -> List[str]:
        """Extract email addresses from text using regex."""
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        text = text.replace(' [at] ', '@').replace(' [dot] ', '.')
        emails = re.findall(email_pattern, text)
        valid_emails = []
        for email in emails:
            email = email.strip('.,')
            if validators.email(email):
                valid_emails.append(email)
        return list(set(valid_emails))

    def extract_phones(self, text: str) -> List[str]:
        """Extract phone numbers from text using regex."""
        phone_patterns = [
            r'\+\d{1,3}[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # International format
            r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',  # (123) 456-7890
            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # 123-456-7890
            r'\d{5}\s\d{6}'  # UK format
        ]
        
        phones = []
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            phones.extend(matches)
        return list(set(phones))

    def extract_social_links(self, soup: BeautifulSoup, base_url: str) -> Dict[str, str]:
        """Extract social media links from the page."""
        social_patterns = {
            'facebook': r'facebook\.com',
            'twitter': r'twitter\.com|x\.com',
            'linkedin': r'linkedin\.com',
            'instagram': r'instagram\.com'
        }
        
        social_links = {}
        for platform, pattern in social_patterns.items():
            links = soup.find_all('a', href=re.compile(pattern, re.I))
            if links:
                social_links[platform] = urljoin(base_url, links[0]['href'])
        
        return social_links

    def extract_business_name(self, soup: BeautifulSoup, url: str) -> str:
        """Extract business name from common locations in the HTML."""
        # Try to find business name in common locations
        name_locations = [
            soup.find('meta', property='og:site_name'),
            soup.find('meta', property='og:title'),
            soup.find('title')
        ]
        
        for location in name_locations:
            if location:
                name = location.get('content', '') or location.string
                if name:
                    # Clean up the name
                    name = re.sub(r'\s*[|-]\s*.+$', '', name.strip())
                    return name
        
        # If no name found, use the domain name
        domain = urlparse(url).netloc
        domain = re.sub(r'^www\.', '', domain)
        domain = domain.split('.')[0].replace('-', ' ').title()
        return domain

    def extract_address(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract physical address from the page."""
        address_patterns = [
            r'\d+[a-zA-Z]?[\s,]+(?:[a-zA-Z]+[\s,]*)+(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|way|court|ct|place|pl)[\s,]+(?:[a-zA-Z]+[\s,]*)+(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)[\s,]+\d{5}(?:-\d{4})?',  # US format
            r'\d+[a-zA-Z]?[\s,]+(?:[a-zA-Z]+[\s,]*)+(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|way|court|ct|place|pl)[\s,]+(?:[a-zA-Z]+[\s,]*)+(?:[A-Z]{1,2}\d{1,2}\s\d[A-Z]{2})',  # UK format
        ]
        
        # Try schema.org data first
        schema = soup.find('script', type='application/ld+json')
        if schema:
            try:
                data = json.loads(schema.string)
                if isinstance(data, dict):
                    address = data.get('address')
                    if address:
                        if isinstance(address, str):
                            return address
                        elif isinstance(address, dict):
                            parts = []
                            for key in ['streetAddress', 'addressLocality', 'addressRegion', 'postalCode']:
                                if address.get(key):
                                    parts.append(address[key])
                            if parts:
                                return ', '.join(parts)
            except:
                pass

        # Look for address in text content
        text = soup.get_text(' ', strip=True)
        for pattern in address_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(0)

        # Look for address in specific elements
        address_containers = soup.find_all(['div', 'p', 'address'], 
            class_=re.compile(r'address|location|contact', re.I))
        for container in address_containers:
            text = container.get_text(strip=True)
            for pattern in address_patterns:
                match = re.search(pattern, text, re.I)
                if match:
                    return match.group(0)

        return None

    def extract_page_content(self, soup: BeautifulSoup) -> str:
        """Extract relevant text content from the page."""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text content
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        text = ' '.join(text.split())
        return text[:5000]  # Limit to first 5000 characters

    def find_contact_page(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Find the contact page URL if it exists."""
        contact_patterns = [
            r'contact',
            r'about\-us',
            r'get\-in\-touch',
            r'reach\-us'
        ]
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.text.lower()
            
            for pattern in contact_patterns:
                if re.search(pattern, href, re.I) or re.search(pattern, text, re.I):
                    return urljoin(base_url, href)
        return None

    def scrape_url(self, url: str) -> Dict:
        """Scrape a website for contact details using requests and BeautifulSoup."""
        try:
            # Validate URL
            if not validators.url(url):
                raise ValueError(f"Invalid URL: {url}")

            # Make the request with a shorter timeout
            response = requests.get(url, headers=self.headers, timeout=10, proxies=None)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract all text content
            text_content = soup.get_text()
            
            # Get the base URL for resolving relative links
            base_url = response.url
            
            # Extract information
            business_name = self.extract_business_name(soup, url)
            emails = self.extract_emails(text_content)
            phones = self.extract_phones(text_content)
            social_links = self.extract_social_links(soup, base_url)
            
            # Compile results
            result = {
                'business_name': business_name,
                'emails': emails,
                'phones': phones,
                'social_links': social_links,
                'url': url
            }
            
            # Add a shorter delay between requests
            time.sleep(1)
            
            return result
            
        except requests.Timeout:
            print(f"Timeout while scraping {url}")
            return {
                'url': url,
                'error': 'Request timed out',
                'business_name': urlparse(url).netloc.replace('www.', '')
            }
        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")
            return {
                'url': url,
                'error': str(e),
                'business_name': urlparse(url).netloc.replace('www.', '')
            }

    def generate_outreach_email(self, business_name: str, company_name: str, backlink_url: str) -> str:
        """Generate an outreach email using OpenAI API."""
        try:
            if not business_name or not company_name or not backlink_url:
                raise ValueError("Missing required parameters for email generation")

            if not openai.api_key:
                raise ValueError("OpenAI API key is not set")

            prompt = f"""
            Write a friendly and professional outreach email to {business_name}.
            The email should:
            1. Introduce {company_name}
            2. Request to add our backlink ({backlink_url})
            3. Explain the mutual benefits
            4. Keep it concise and natural
            5. End with a clear call to action
            """

            # Create completion without proxy settings
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional outreach specialist writing an email to request a backlink."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )

            if not response.choices or not response.choices[0].message:
                raise ValueError("No response from OpenAI API")

            return response.choices[0].message['content'].strip()

        except openai.error.AuthenticationError as e:
            print(f"OpenAI Authentication Error: {str(e)}")
            return "Error: OpenAI API key is invalid"
        except openai.error.APIError as e:
            print(f"OpenAI API Error: {str(e)}")
            return "Error: OpenAI API is currently unavailable"
        except ValueError as e:
            print(f"Value Error: {str(e)}")
            return f"Error: {str(e)}"
        except Exception as e:
            print(f"Unexpected error generating email: {str(e)}")
            return "Error: An unexpected error occurred while generating the email"

def main():
    """Main function to test the scraper."""
    scraper = WebScraper()
    
    # Test URLs
    test_urls = [
        "https://example.com",
        "https://example.org"
    ]
    
    results = []
    for url in tqdm(test_urls, desc="Scraping websites"):
        result = scraper.scrape_url(url)
        if result:
            results.append(result)
    
    # Save results to JSON file
    with open('scraping_results.json', 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
