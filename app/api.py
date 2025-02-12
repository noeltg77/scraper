from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from app.auth import get_api_key, router as auth_router, init_airtable

# Initialize FastAPI app
app = FastAPI(
    title="Web Crawler API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Define media extensions to filter out
media_extensions = {
    # Images
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff',
    # Audio
    '.mp3', '.wav', '.ogg', '.m4a', '.aac',
    # Video
    '.mp4', '.webm', '.avi', '.mov', '.wmv', '.flv',
    # Documents
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.rar', '.7z', '.tar', '.gz',
    # Other media
    '.swf', '.woff', '.woff2', '.ttf', '.eot'
}

# Utility functions
def normalize_url(url: str) -> str:
    """Normalize URL by removing fragments, trailing slashes, and standardizing protocol."""
    # Remove any hash fragments first
    url = url.split('#')[0]
    # Remove trailing slash
    url = url.rstrip('/')
    # Remove 'www.' if present
    url = url.replace('www.', '')
    # Remove default ports
    url = url.replace(':80/', '/').replace(':443/', '/')
    # Ensure consistent protocol
    if url.startswith('http://'):
        url = 'https://' + url[7:]
    return url.lower()

def is_media_url(url: str) -> bool:
    """Check if URL points to a media file."""
    lower_url = url.lower()
    return any(lower_url.endswith(ext) for ext in media_extensions)

def is_same_url(url1: str, url2: str) -> bool:
    """Compare two URLs after normalization."""
    return normalize_url(url1) == normalize_url(url2)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    await init_airtable()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # In production, you might want to restrict this
)

# Include the auth router first
app.include_router(auth_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify the API is running.
    Does not require authentication.
    """
    return {"status": "healthy", "message": "API is running"}

# Define request/response models
class CrawlRequest(BaseModel):
    url: HttpUrl

class LinkInfo(BaseModel):
    url: str
    domain: str
    type: str

class CrawlResponse(BaseModel):
    success: bool
    url: str
    internal_links: Optional[List[LinkInfo]] = None
    external_links: Optional[List[LinkInfo]] = None
    images: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None

class MarkdownRequest(BaseModel):
    url: HttpUrl
    threshold: Optional[float] = 0.45
    threshold_type: Optional[str] = "dynamic"
    min_word_threshold: Optional[int] = 5

class MarkdownResponse(BaseModel):
    success: bool
    url: str
    raw_markdown: Optional[str] = None
    fit_markdown: Optional[str] = None
    raw_markdown_length: Optional[int] = None
    fit_markdown_length: Optional[int] = None
    error_message: Optional[str] = None

class AdvancedRequest(BaseModel):
    url: HttpUrl
    threshold: Optional[float] = 0.45
    threshold_type: Optional[str] = "dynamic"
    min_word_threshold: Optional[int] = 5

class PageMarkdown(BaseModel):
    url: str
    raw_markdown: Optional[str] = None
    fit_markdown: Optional[str] = None
    raw_markdown_length: Optional[int] = None
    fit_markdown_length: Optional[int] = None

class AdvancedResponse(BaseModel):
    success: bool
    url: str
    pages: List[PageMarkdown] = []
    error_message: Optional[str] = None

@app.post("/crawl", response_model=CrawlResponse)
async def crawl_url(request: CrawlRequest, api_key: str = Depends(get_api_key)):
    """
    Crawl a specified URL and return links and images.
    Requires a valid API key in the X-API-Key header.
    """
    try:
        crawler_cfg = CrawlerRunConfig(
            exclude_external_links=False,
            exclude_domains=[""],
            exclude_social_media_links=False,
            exclude_external_images=True,
            wait_for_images=True,
            verbose=True
        )

        input_url = str(request.url)
        normalized_input_url = normalize_url(input_url)

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(input_url, config=crawler_cfg)

            if result.success:
                # Filter and format internal links
                internal_links = [
                    LinkInfo(
                        url=link['href'],
                        domain=link.get('domain', ''),
                        type='internal'
                    ) for link in result.links.get("internal", [])
                    if not is_media_url(link['href']) and not is_same_url(link['href'], input_url)
                ]

                # Filter and format external links
                external_links = [
                    LinkInfo(
                        url=link['href'],
                        domain=link.get('domain', ''),
                        type='external'
                    ) for link in result.links.get("external", [])
                    if not is_media_url(link['href']) and not is_same_url(link['href'], input_url)
                ]
                
                return CrawlResponse(
                    success=True,
                    url=result.url,
                    internal_links=internal_links,
                    external_links=external_links,
                    images=[{
                        "src": img["src"],
                        "alt": img.get("alt", ""),
                        "score": img.get("score", "N/A")
                    } for img in result.media.get("images", [])]
                )
            else:
                return CrawlResponse(
                    success=False,
                    url=str(request.url),
                    error_message=result.error_message
                )
    except Exception as e:
        print(f"Error in crawl_url: {str(e)}")  # Added logging
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/markdown", response_model=MarkdownResponse)
async def generate_markdown(request: MarkdownRequest, api_key: str = Depends(get_api_key)):
    """
    Generate markdown from a URL with content filtering.
    Requires a valid API key in the X-API-Key header.
    """
    try:
        # Step 1: Create a pruning filter with the same configuration as fit_markdown.py
        prune_filter = PruningContentFilter(
            threshold=request.threshold,
            threshold_type=request.threshold_type,
            min_word_threshold=request.min_word_threshold
        )

        # Step 2: Create markdown generator with the filter
        md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)

        # Step 3: Configure crawler with the markdown generator
        config = CrawlerRunConfig(
            markdown_generator=md_generator
        )

        # Run the crawler
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(str(request.url), config=config)

            if result.success:
                return MarkdownResponse(
                    success=True,
                    url=str(request.url),
                    raw_markdown=result.markdown_v2.raw_markdown,
                    fit_markdown=result.markdown_v2.fit_markdown,
                    raw_markdown_length=len(result.markdown_v2.raw_markdown),
                    fit_markdown_length=len(result.markdown_v2.fit_markdown)
                )
            else:
                return MarkdownResponse(
                    success=False,
                    url=str(request.url),
                    error_message=result.error_message
                )

    except Exception as e:
        print(f"Error in generate_markdown: {str(e)}")  # Added logging
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/advanced", response_model=AdvancedResponse)
async def advanced_crawl(request: AdvancedRequest, api_key: str = Depends(get_api_key)):
    """
    Advanced crawl that combines link discovery and markdown generation.
    First crawls the URL for internal links, then generates markdown for each link.
    Requires a valid API key in the X-API-Key header.
    """
    try:
        print(f"Starting advanced crawl for URL: {request.url}")
        
        # First, crawl the URL to get internal links
        crawler_cfg = CrawlerRunConfig(
            exclude_external_links=False,
            exclude_domains=[""],
            exclude_social_media_links=False,
            exclude_external_images=True,
            wait_for_images=True,
            verbose=True
        )

        input_url = str(request.url)
        print(f"Normalized input URL: {normalize_url(input_url)}")

        # Create markdown generator configuration
        print("Creating markdown generator configuration...")
        prune_filter = PruningContentFilter(
            threshold=request.threshold,
            threshold_type=request.threshold_type,
            min_word_threshold=request.min_word_threshold
        )
        md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)
        md_config = CrawlerRunConfig(
            markdown_generator=md_generator,
            verbose=True
        )

        # Create a semaphore to limit concurrent requests
        # Adjust this number based on your needs and server capacity
        semaphore = asyncio.Semaphore(5)  # Process 5 URLs concurrently

        print("Initializing crawler...")
        async with AsyncWebCrawler() as crawler:
            # First get all internal links
            print("Crawling for internal links...")
            result = await crawler.arun(input_url, config=crawler_cfg)
            
            if not result.success:
                print(f"Failed to crawl initial URL: {result.error_message}")
                return AdvancedResponse(
                    success=False,
                    url=input_url,
                    error_message=f"Failed to crawl initial URL: {result.error_message}"
                )

            # Get unique internal links
            internal_urls = {
                normalize_url(link['href']) for link in result.links.get("internal", [])
                if not is_media_url(link['href']) and not is_same_url(link['href'], input_url)
            }
            internal_urls.add(normalize_url(input_url))  # Include the original URL
            
            print(f"Found {len(internal_urls)} unique internal URLs to process")
            print(f"URLs to process: {internal_urls}")

            # Pre-warm the browser with a quick request
            print("Pre-warming browser...")
            await crawler.arun(input_url, config=md_config)

            # Helper function to process a single URL with semaphore
            async def process_url(url: str) -> Optional[PageMarkdown]:
                async with semaphore:  # Limit concurrent requests
                    try:
                        print(f"Processing URL: {url}")
                        md_result = await crawler.arun(url, config=md_config)
                        if md_result.success:
                            print(f"Successfully generated markdown for {url}")
                            return PageMarkdown(
                                url=url,  # Keep the original URL in the response
                                raw_markdown=md_result.markdown_v2.raw_markdown,
                                fit_markdown=md_result.markdown_v2.fit_markdown,
                                raw_markdown_length=len(md_result.markdown_v2.raw_markdown),
                                fit_markdown_length=len(md_result.markdown_v2.fit_markdown)
                            )
                        else:
                            print(f"Failed to generate markdown for {url}: {md_result.error_message}")
                            return None
                    except Exception as e:
                        print(f"Error processing URL {url}: {str(e)}")
                        return None

            # Process URLs concurrently with controlled parallelism
            tasks = [process_url(url) for url in internal_urls]
            results = await asyncio.gather(*tasks)
            
            # Filter out None results (failed URLs)
            pages = [page for page in results if page is not None]

            print(f"Successfully processed {len(pages)} pages")
            return AdvancedResponse(
                success=True,
                url=input_url,
                pages=pages
            )

    except Exception as e:
        print(f"Error in advanced_crawl: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import socket
    
    # Get the host machine's IP address
    hostname = socket.gethostname()
    host_ip = socket.gethostbyname(hostname)
    
    print(f"Starting API server...")
    print(f"Server hostname: {hostname}")
    print(f"Server IP: {host_ip}")
    print(f"Documentation available at: http://{host_ip}:8002/docs")
    
    # Configure uvicorn with proxy settings and application import string
    uvicorn.run(
        "app.api:app",  # Use the import string format
        host="0.0.0.0",
        port=8002,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*",
        server_header=False,
        timeout_keep_alive=65,
        workers=4
    ) 
