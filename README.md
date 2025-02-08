# Web Crawler API

A FastAPI-based web crawler API that provides URL crawling and markdown generation capabilities with API key authentication via Airtable.

## Features

- API Key authentication using Airtable
- URL crawling to extract links and images
- Markdown generation with content filtering
- Easy deployment to Coolify

## Setup

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your Airtable configuration:
```env
AIRTABLE_API_KEY=your_airtable_api_key
AIRTABLE_BASE_ID=your_base_id
AIRTABLE_TABLE_NAME=your_table_id
```

4. Run the server:
```bash
python api.py
```

## API Endpoints

### Authentication
- `GET /auth/validate-key` - Validate an API key
- `GET /auth/request-key` - Get information about requesting an API key

### Crawling
- `POST /crawl` - Crawl a URL for links and images
- `POST /markdown` - Generate markdown from a URL with content filtering

## API Usage

All endpoints require an API key in the `X-API-Key` header.

### Example Requests

1. Crawl a URL:
```bash
curl -X POST "http://localhost:8000/crawl" \
     -H "X-API-Key: YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}'
```

2. Generate markdown:
```bash
curl -X POST "http://localhost:8000/markdown" \
     -H "X-API-Key: YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://example.com",
       "threshold": 0.45,
       "threshold_type": "dynamic",
       "min_word_threshold": 5
     }'
```

## Deployment

### Coolify Deployment

1. In Coolify, create a new Python service
2. Connect your GitHub repository
3. Set the following environment variables:
   - `AIRTABLE_API_KEY`
   - `AIRTABLE_BASE_ID`
   - `AIRTABLE_TABLE_NAME`
4. Set the build command: `pip install -r requirements.txt`
5. Set the start command: `python api.py`

## License

MIT License
