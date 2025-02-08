from fastapi import FastAPI, HTTPException, Security, Depends, APIRouter
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
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

# Load environment variables and clean them
load_dotenv()

# Clean the environment variables
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "").strip()
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "").strip()
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "").strip()

# Print configuration for debugging
print(f"Auth Module Configuration:")
print(f"Table Name: '{AIRTABLE_TABLE_NAME}'")
print(f"Base ID: '{AIRTABLE_BASE_ID}'")
print(f"Airtable API Key: '{AIRTABLE_API_KEY[:5]}...'")  # Only print first 5 chars for security

if not all([AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME]):
    raise ValueError("Missing required environment variables for Airtable configuration")

# Test Airtable connection directly
try:
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # First test if we can access the base
    print("\nTesting base access...")
    base_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    print(f"Accessing URL: {base_url}")
    
    response = requests.get(base_url, headers=headers)
    
    if response.status_code == 200:
        records = response.json().get('records', [])
        print(f"✓ Successfully connected to Airtable. Found {len(records)} records.")
        
        # Print field names from the first record if available
        if records:
            fields = records[0].get('fields', {})
            print(f"Available fields: {list(fields.keys())}")
            
        # Initialize table with the correct authorization
        table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
    else:
        print(f"✗ Failed to access table: {response.status_code}")
        print(f"Response: {response.text}")
        raise Exception(f"Failed to access Airtable: {response.text}")
        
except Exception as e:
    print(f"Error connecting to Airtable: {str(e)}")
    raise

# API Key header configuration
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)) -> str:
    """Validate API key from header."""
    print(f"\n--- API Key Validation ---")
    print(f"Received API Key: {api_key_header[:5]}...")  # Only print first 5 chars for security
    
    if api_key_header is None:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="No API key provided"
        )
    
    try:
        # Get all records and print them (excluding sensitive data)
        all_records = table.all()
        print(f"\nFound {len(all_records)} records in table")
        print("Records (showing first 5 chars of API keys):")
        for record in all_records:
            fields = record.get('fields', {})
            api_key = fields.get('API Key', '')
            print(f"- API Key: {api_key[:5]}... (length: {len(api_key)})")
            print(f"- Available fields: {list(fields.keys())}")  # Print available field names
        
        # Simple exact match check
        for record in all_records:
            fields = record.get('fields', {})
            stored_key = fields.get('API Key', '')
            if stored_key == api_key_header:
                print("API key match found!")
                return api_key_header
        
        print("No matching API key found")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Invalid API key"
        )
    except Exception as e:
        print(f"Error during validation: {str(e)}")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail=f"Error validating API key: {str(e)}"
        )

# Initialize router instead of app
router = APIRouter(prefix="/auth", tags=["authentication"])

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
