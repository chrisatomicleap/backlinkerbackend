import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from web_scraper import WebScraper
from concurrent.futures import ThreadPoolExecutor
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        company_name = data.get('companyName', '')
        backlink_url = data.get('backlinkUrl', '')
        openai_key = data.get('openaiKey', '')
        user_name = data.get('userName', '')
        user_organization = data.get('userOrganization', '')

        logger.info("Received scrape request")
        logger.debug(f"Request data: {data}")
        
        if not urls:
            logger.error("No URLs provided")
            return jsonify({"error": "No URLs provided"}), 400
            
        if not company_name:
            logger.error("No company name provided")
            return jsonify({"error": "Company name is required"}), 400
            
        if not backlink_url:
            logger.error("No backlink URL provided")
            return jsonify({"error": "Backlink URL is required"}), 400
            
        if not openai_key:
            logger.error("No OpenAI API key provided")
            return jsonify({"error": "OpenAI API key is required"}), 400

        if not user_name:
            logger.error("No user name provided")
            return jsonify({"error": "User name is required"}), 400

        if not user_organization:
            logger.error("No user organization provided")
            return jsonify({"error": "User organization is required"}), 400

        logger.info(f"Processing request for {len(urls)} URLs")
        logger.debug(f"Company Name: {company_name}")
        logger.debug(f"Backlink URL: {backlink_url}")

        # Initialize the scraper with user's OpenAI key
        logger.info("Initializing WebScraper")
        scraper = WebScraper(openai_key)

        # Process URLs in parallel
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for url in urls:
                future = executor.submit(
                    scrape_single_url,
                    scraper,
                    url,
                    company_name,
                    backlink_url,
                    user_name,
                    user_organization
                )
                futures.append(future)
            
            # Collect results as they complete
            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error processing URL: {str(e)}")
                    results.append({
                        "error": str(e),
                        "url": "Unknown URL"
                    })

        return jsonify(results)

    except Exception as e:
        logger.error(f"Error in scrape endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

def scrape_single_url(scraper, url, company_name, backlink_url, user_name, user_organization):
    try:
        logger.info(f"Starting to scrape URL: {url}")
        result = scraper.scrape_url(url)
        
        if result.get('error'):
            logger.error(f"Error scraping {url}: {result['error']}")
            return result

        logger.info(f"Generating outreach email for {url}")
        email = scraper.generate_outreach_email(
            result.get('business_name', ''),
            company_name,
            backlink_url,
            user_name,
            user_organization
        )
        
        result['outreach_email'] = email
        return result

    except Exception as e:
        logger.error(f"Error processing {url}: {str(e)}")
        return {
            "url": url,
            "error": str(e)
        }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
