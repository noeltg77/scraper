from fastapi import FastAPI, HTTPException, Security, Depends, APIRouter
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN, HTTP_503_FORBIDDEN
from pyairtable.api.table import Table
from typing import Optional
import os
from dotenv import load_dotenv
import sys
import logging
import requests
import json

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Clean the environment variables
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "").strip()
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "").strip()
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "").split('#')[0].strip()

# Initialize router
router = APIRouter(prefix="/auth", tags=["authentication"])

# Initialize table as None, will be set during startup
table = None

async def init_airtable():
    """Initialize Airtable connection during startup."""
    global table
    
    logger.info("Initializing Airtable connection...")
    logger.info(f"Table Name: '{AIRTABLE_TABLE_NAME}'")
    logger.info(f"Base ID: '{AIRTABLE_BASE_ID}'")
    logger.info(f"Airtable API Key: '{AIRTABLE_API_KEY[:5]}...'")

    if not all([AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME]):
        raise ValueError("Missing required environment variables for Airtable configuration")

    try:
        headers = {
            "Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        base_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
        logger.info(f"Testing Airtable connection: {base_url}")
        
        response = requests.get(base_url, headers=headers)
        
        if response.status_code == 200:
            records = response.json().get('records', [])
            logger.info(f"✓ Successfully connected to Airtable. Found {len(records)} records.")
            
            if records:
                fields = records[0].get('fields', {})
                logger.info(f"Available fields: {list(fields.keys())}")
            
            table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
            return True
        else:
            logger.error(f"✗ Failed to access table: {response.status_code}")
            logger.error(f"Response: {response.text}")
            raise Exception(f"Failed to access Airtable: {response.text}")
            
    except Exception as e:
        logger.error(f"Error connecting to Airtable: {str(e)}")
        raise

# API Key header configuration
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)) -> str:
    """Validate API key from header."""
    if api_key_header is None:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="No API key provided"
        )
    
    try:
        if table is None:
            raise HTTPException(
                status_code=HTTP_503_FORBIDDEN,
                detail="Airtable connection not initialized"
            )

        # Get all records
        all_records = table.all()
        logger.debug(f"Found {len(all_records)} records in table")
        
        # Simple exact match check
        for record in all_records:
            fields = record.get('fields', {})
            stored_key = fields.get('API Key', '')
            if stored_key == api_key_header:
                return api_key_header
        
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Invalid API key"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during validation: {str(e)}")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail=f"Error validating API key: {str(e)}"
        )

@router.get("/validate-key")
async def validate_api_key(api_key: str = Depends(get_api_key)):
    """Endpoint to validate an API key."""
    return {"status": "valid", "message": "API key is valid"}

@router.get("/request-key")
async def request_api_key():
    """Endpoint to request a new API key."""
    return {
        "message": "Please contact the administrator to request an API key",
        "contact": "your-email@example.com"
    } 
