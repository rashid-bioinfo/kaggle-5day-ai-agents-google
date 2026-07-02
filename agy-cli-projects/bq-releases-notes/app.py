import logging
import time
import re
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# In-memory cache for parsed release notes
# Structure: { "last_fetched": float, "data": list }
_cache = {
    "last_fetched": 0.0,
    "data": []
}
CACHE_DURATION_SECONDS = 600  # 10 minutes cache

FEED_URL = "https://docs.cloud.google.com/feeds/bigquery-release-notes.xml"
ATOM_NS = "{http://www.w3.org/2005/Atom}"

def parse_entry_content(content_html):
    """
    Parses the entry content HTML (which contains multiple <h3> tags followed by descriptions)
    and splits it into individual update records.
    """
    if not content_html:
        return []
        
    soup = BeautifulSoup(content_html, "html.parser")
    updates = []
    current_type = "Update"
    current_elems = []
    
    # Iterate through child elements of the HTML content
    for child in soup.contents:
        if child == "\n" or (isinstance(child, str) and not child.strip()):
            continue
            
        # If we hit an h3, it marks the beginning of a new release note update type
        if child.name == "h3":
            if current_elems:
                # Save previous update block
                html_str = "".join(str(e) for e in current_elems).strip()
                text_str = "".join(e.get_text() if hasattr(e, "get_text") else str(e) for e in current_elems).strip()
                updates.append({
                    "type": current_type,
                    "content_html": html_str,
                    "content_text": text_str
                })
                current_elems = []
            current_type = child.get_text().strip()
        else:
            current_elems.append(child)
            
    # Add the last update block if any elements exist
    if current_elems or current_type != "Update":
        html_str = "".join(str(e) for e in current_elems).strip()
        text_str = "".join(e.get_text() if hasattr(e, "get_text") else str(e) for e in current_elems).strip()
        updates.append({
            "type": current_type,
            "content_html": html_str,
            "content_text": text_str
        })
        
    return updates

def fetch_and_parse_feed(force_refresh=False):
    """
    Fetches the BigQuery Release Notes RSS/Atom feed and parses it.
    Uses in-memory cache if it is still valid and refresh is not forced.
    """
    now = time.time()
    if not force_refresh and _cache["data"] and (now - _cache["last_fetched"] < CACHE_DURATION_SECONDS):
        logger.info("Returning cached release notes data")
        return _cache["data"]
        
    logger.info(f"Fetching fresh release notes from: {FEED_URL}")
    try:
        response = requests.get(FEED_URL, headers={"User-Agent": "BigQueryReleaseNotesApp/1.0"}, timeout=10)
        response.raise_for_status()
        
        # Parse XML
        root = ET.fromstring(response.content)
        
        entries = root.findall(f"{ATOM_NS}entry")
        parsed_updates = []
        
        for entry in entries:
            # Basic metadata
            date_str = entry.find(f"{ATOM_NS}title").text
            updated_str = entry.find(f"{ATOM_NS}updated").text
            entry_id = entry.find(f"{ATOM_NS}id").text
            
            # Extract link href
            link_elem = entry.find(f"{ATOM_NS}link")
            link_url = ""
            if link_elem is not None:
                link_url = link_elem.attrib.get("href", "")
                
            content_elem = entry.find(f"{ATOM_NS}content")
            content_html = content_elem.text if content_elem is not None else ""
            
            # Parse individual updates within this entry
            individual_updates = parse_entry_content(content_html)
            
            for index, update in enumerate(individual_updates):
                # Generate a unique hash or id for this specific update item
                clean_type = update["type"].lower()
                unique_id = f"{date_str.replace(' ', '_')}_{clean_type}_{index}"
                
                # If there's an anchor in the entry_id or if we can make a specific anchor
                # The official release notes page links use the date as anchor, e.g., #June_15_2026
                date_anchor = date_str.replace(" ", "_").replace(",", "")
                update_link = f"https://cloud.google.com/bigquery/docs/release-notes#{date_anchor}"
                
                parsed_updates.append({
                    "id": unique_id,
                    "date": date_str,
                    "updated_raw": updated_str,
                    "type": update["type"],
                    "content_html": update["content_html"],
                    "content_text": update["content_text"],
                    "url": update_link
                })
                
        # Update cache
        _cache["data"] = parsed_updates
        _cache["last_fetched"] = now
        logger.info(f"Successfully fetched and parsed {len(parsed_updates)} individual updates.")
        return parsed_updates
        
    except Exception as e:
        logger.error(f"Error fetching or parsing feed: {e}", exc_info=True)
        # Fallback to cache if available, even if expired
        if _cache["data"]:
            logger.warning("Returning expired cache due to fetch failure")
            return _cache["data"]
        raise e

@app.route("/")
def index():
    """Renders the main page."""
    return render_template("index.html")

@app.route("/api/releases")
def get_releases():
    """API endpoint to get the parsed release notes."""
    force_refresh = request.args.get("refresh", "false").lower() == "true"
    try:
        releases = fetch_and_parse_feed(force_refresh=force_refresh)
        return jsonify({
            "status": "success",
            "count": len(releases),
            "last_fetched": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(_cache["last_fetched"])),
            "releases": releases
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
