from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import sys
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import time
import traceback
import logging
from web_scraper import WebScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure CORS
CORS(app, resources={
    r"/*": {
        "origins": ["https://backlinkoutreachtool.netlify.app"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'https://backlinkoutreachtool.netlify.app')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response

# Initialize WebScraper with OpenAI API key from environment
openai_api_key = os.getenv('OPENAI_API_KEY')
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is required")

scraper = WebScraper(openai_api_key)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

def scrape_single_url(scraper, url, company_name, backlink_url):
    """Scrape a single URL with timeout handling."""
    try:
        print(f"Starting to scrape URL: {url}")
        result = scraper.scrape_url(url)
        if result:
            print(f"Successfully scraped URL: {url}")
            print(f"Scraping result: {json.dumps(result, indent=2)}")
            
            if 'error' not in result:
                print(f"Generating outreach email for {result.get('business_name', '')}")
                result['outreach_email'] = scraper.generate_outreach_email(
                    business_name=result.get('business_name', ''),
                    company_name=company_name,
                    backlink_url=backlink_url
                )
                print(f"Email generated successfully for {url}")
            return result
        else:
            print(f"No result returned for URL: {url}")
            return {
                'url': url,
                'error': 'No data could be extracted',
                'business_name': url.replace('www.', '').split('/')[0]
            }
    except Exception as e:
        print(f"Error processing URL {url}: {str(e)}")
        print("Traceback:", traceback.format_exc())
        return {
            'url': url,
            'error': str(e),
            'business_name': url.replace('www.', '').split('/')[0]
        }

@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        print("Received scrape request")
        data = request.json
        print(f"Request data: {json.dumps(data, indent=2)}")
        
        urls = data.get('urls', [])
        company_name = data.get('companyName', '')
        backlink_url = data.get('backlinkUrl', '')

        if not isinstance(urls, list) or not urls:
            print("Invalid input: urls must be a non-empty array")
            return jsonify({'error': 'Invalid input: urls must be a non-empty array'}), 400

        print(f"Processing {len(urls)} URLs")
        
        results = []
        
        # Use ThreadPoolExecutor to handle multiple URLs concurrently with timeouts
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all tasks
            future_to_url = {
                executor.submit(
                    scrape_single_url, 
                    scraper, 
                    url, 
                    company_name, 
                    backlink_url
                ): url for url in urls
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_url, timeout=12):  # 12 second timeout
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        print(f"Added result for {url}")
                except TimeoutError:
                    error_result = {
                        'url': url,
                        'error': 'Processing timed out',
                        'business_name': url.replace('www.', '').split('/')[0]
                    }
                    results.append(error_result)
                    print(f"Timeout processing {url}")
                except Exception as e:
                    error_result = {
                        'url': url,
                        'error': str(e),
                        'business_name': url.replace('www.', '').split('/')[0]
                    }
                    results.append(error_result)
                    print(f"Error processing {url}: {str(e)}")
                    print("Traceback:", traceback.format_exc())

        print(f"Completed processing. Returning {len(results)} results")
        print(f"Results: {json.dumps(results, indent=2)}")
        return jsonify(results)

    except Exception as e:
        print(f"Server error: {str(e)}")
        print("Traceback:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Get port from environment variable or default to 5000
    port = int(os.environ.get('PORT', 5000))
    
    # In production, host on 0.0.0.0
    if os.environ.get('FLASK_ENV') == 'production':
        app.run(host='0.0.0.0', port=port)
    else:
        app.run(host='0.0.0.0', port=port, debug=True)
