from dotenv import load_dotenv
import os
import requests
from urllib.parse import quote_plus
from typing import Optional, Dict, Any, List

load_dotenv()

def _make_api_request(url: str, **kwargs) -> Optional[Dict[str, Any]]:
    api_key = os.getenv("BRIGHTDATA_API_KEY")
    # print(api_key,'api_key')

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None
    except Exception as e:
        print(f"Unknown error: {e}")
        return None

def serp_search(query: str, engine: str = "google") -> Optional[Dict[str, Any]]:
    if engine == "google":
        base_url = "https://www.google.com/search"
    elif engine == "bing":
        base_url = "https://www.bing.com/search"
    else:
        raise ValueError(f"Unknown engine {engine}")

    url = "https://api.brightdata.com/request"

    payload = {
        "zone": "serp_api1",
        "url": f"{base_url}?q={quote_plus(query)}&brd_json=1",
        "format": "raw"
    }

    full_response = _make_api_request(url, json=payload)
    if not full_response:
        return None

    extracted_data = {
        "knowledge": full_response.get("knowledge", {}),
        "organic": full_response.get("organic", []),
    }
    return extracted_data

def scrape_with_web_unlocker(url: str, zone: str = "web_unlocker1", fmt: str = "json") -> Optional[Dict[str, Any]]:
    """
    Scrapes a webpage using Bright Data Web Unlocker API.

    Args:
        url (str): The target URL to scrape (e.g., Glassdoor reviews page).
        zone (str): Bright Data zone configured for Web Unlocker.
        fmt (str): Response format (json or raw). Defaults to 'json'.

    Returns:
        dict: The parsed response from Bright Data API, or None if request fails.
    """
    api_url = "https://api.brightdata.com/request"
    payload = {
        "zone": zone,
        "url": url,
        "format": fmt
    }

    try:
        response = _make_api_request(api_url, json=payload)
        return response
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None
