# Web Scraper Backend

Backend service for the web scraper application, built with Flask and deployed on AWS App Runner.

## Features

- Web scraping with BeautifulSoup4
- Contact information extraction
- OpenAI integration for email generation
- Concurrent request processing
- Docker containerization
- AWS App Runner deployment

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
Create a `.env` file with:
```env
OPENAI_API_KEY=your_openai_api_key
```

3. Run locally:
```bash
python app.py
```

## API Endpoints

- `POST /scrape`: Scrape websites for contact information
  - Input: JSON with `urls`, `companyName`, and `backlinkUrl`
  - Output: Array of scraping results with contact info and generated emails

- `GET /health`: Health check endpoint
  - Output: `{"status": "healthy"}`

## Deployment

The application is automatically deployed to AWS App Runner via GitHub Actions when pushing to the main branch.

Required GitHub Secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `OPENAI_API_KEY`
- `APPRUNNER_SERVICE_ROLE_ARN`

## Development

1. Build Docker image:
```bash
docker build -t web-scraper-backend .
```

2. Run Docker container:
```bash
docker run -p 5000:5000 web-scraper-backend
```
