from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from auth import get_api_key, router as auth_router

# Initialize FastAPI app
app = FastAPI(title="Web Crawler API")

# Include the auth router first
app.include_router(auth_router)

# Define request/response models
class CrawlRequest(BaseModel):
    url: HttpUrl

class CrawlResponse(BaseModel):
    success: bool
    url: str
    internal_links: Optional[List[str]] = None
    external_links: Optional[List[str]] = None
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
    raw_markdown_length: Optional[int] = None
    fit_markdown_length: Optional[int] = None
    fit_markdown: Optional[str] = None
    raw_markdown: Optional[str] = None  # Added to help with debugging
    error_message: Optional[str] = None

@app.post("/crawl", response_model=CrawlResponse)
async def crawl_url(request: CrawlRequest, api_key: str = Depends(get_api_key)):
    """
    Crawl a specified URL and return links and images.
    Requires a valid API key in the X-API-Key header.
    """
    crawler_cfg = CrawlerRunConfig(
        exclude_external_links=False,
        exclude_domains=[""],
        exclude_social_media_links=False,
        exclude_external_images=True,
        wait_for_images=True,
        verbose=True
    )

    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(str(request.url), config=crawler_cfg)

            if result.success:
                return CrawlResponse(
                    success=True,
                    url=result.url,
                    internal_links=result.links.get("internal", []),
                    external_links=result.links.get("external", []),
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
            markdown_generator=md_generator,
            exclude_external_links=False,  # Match the settings from fit_markdown.py
            exclude_domains=[""],
            exclude_social_media_links=False,
            exclude_external_images=True,
            wait_for_images=True,
            verbose=True
        )

        # Run the crawler
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(str(request.url), config=config)

            if result.success:
                return MarkdownResponse(
                    success=True,
                    url=str(request.url),
                    raw_markdown_length=len(result.markdown_v2.raw_markdown),
                    fit_markdown_length=len(result.markdown_v2.fit_markdown),
                    fit_markdown=result.markdown_v2.fit_markdown,
                    raw_markdown=result.markdown_v2.raw_markdown  # Added for debugging
                )
            else:
                return MarkdownResponse(
                    success=False,
                    url=str(request.url),
                    error_message=result.error_message
                )

    except Exception as e:
        print(f"Error processing markdown: {str(e)}")  # Added for debugging
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
