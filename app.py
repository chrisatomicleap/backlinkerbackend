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

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")

app = Flask(__name__)
logger.info("Flask app initialized")

# Configure CORS
CORS(app, resources={
    r"/*": {
        "origins": ["https://backlinkoutreachtool.netlify.app"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})
logger.info("CORS configured")

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'https://backlinkoutreachtool.netlify.app')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response

@app.route('/health', methods=['GET'])
def health_check():
    logger.debug("Health check endpoint called")
    return jsonify({"status": "healthy"}), 200

def scrape_single_url(scraper, url, company_name, backlink_url):
    """Scrape a single URL with timeout handling."""
    try:
        logger.info(f"Starting to scrape URL: {url}")
        result = scraper.scrape_url(url)
        
        # Add URL to result
        result['url'] = url
        logger.debug(f"Scraping result for {url}: {json.dumps(result, indent=2)}")
        
        # Generate outreach email
        try:
            logger.info(f"Generating outreach email for URL: {url}")
            result['outreach_email'] = scraper.generate_outreach_email(
                business_name=result.get('business_name', ''),
                company_name=company_name,
                backlink_url=backlink_url
            )
            logger.info(f"Generated outreach email for URL: {url}")
            logger.debug(f"Email content: {result['outreach_email']}")
        except Exception as e:
            logger.error(f"Error generating outreach email for {url}: {str(e)}")
            logger.error(traceback.format_exc())
            result['outreach_email'] = f"Error generating email: {str(e)}"
        
        return result
    except Exception as e:
        logger.error(f"Error scraping {url}: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'url': url,
            'error': str(e),
            'business_name': '',
            'emails': [],
            'phones': [],
            'social_links': {},
            'outreach_email': ''
        }

@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        logger.info("Received scrape request")
        data = request.get_json()
        logger.debug(f"Request data: {json.dumps(data, indent=2)}")
        
        urls = data.get('urls', [])
        company_name = data.get('companyName', '')
        backlink_url = data.get('backlinkUrl', '')
        
        logger.info(f"Processing request for {len(urls)} URLs")
        logger.debug(f"Company Name: {company_name}")
        logger.debug(f"Backlink URL: {backlink_url}")
        
        # Initialize scraper with OpenAI API key
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            logger.error("OpenAI API key not found")
            return jsonify({"error": "OpenAI API key not configured"}), 500
            
        logger.info("Initializing WebScraper")
        scraper = WebScraper(openai_api_key)
        
        # Use ThreadPoolExecutor for parallel processing
        results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            logger.info(f"Starting parallel processing with {len(urls)} URLs")
            future_to_url = {
                executor.submit(scrape_single_url, scraper, url, company_name, backlink_url): url 
                for url in urls
            }
            
            for future in as_completed(future_to_url):
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"Completed scraping URL: {result.get('url')}")
                    logger.debug(f"Result: {json.dumps(result, indent=2)}")
                except Exception as e:
                    url = future_to_url[future]
                    logger.error(f"Error processing {url}: {str(e)}")
                    logger.error(traceback.format_exc())
                    results.append({
                        'url': url,
                        'error': str(e),
                        'business_name': '',
                        'emails': [],
                        'phones': [],
                        'social_links': {},
                        'outreach_email': ''
                    })
        
        logger.info(f"Completed all processing. Returning {len(results)} results")
        logger.info(f"Results: {json.dumps(results, indent=2)}")
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error in scrape endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    if os.environ.get('FLASK_ENV') == 'production':
        app.run(host='0.0.0.0', port=port)
    else:
        app.run(host='0.0.0.0', port=port, debug=True)
