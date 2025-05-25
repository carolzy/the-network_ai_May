"""
Database module for storing and retrieving target event results.
This module provides functionality to save, retrieve, and refine target event
recommendations for specific URLs over time.
"""

import os
import json
import time
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database file path
DB_DIR = Path("data")
DB_FILE = DB_DIR / "target_events_db.json"

def ensure_db_exists():
    """Ensure the database directory and file exist."""
    if not DB_DIR.exists():
        DB_DIR.mkdir(parents=True)
    
    if not DB_FILE.exists():
        with open(DB_FILE, 'w') as f:
            json.dump({}, f)

def get_url_key(url):
    """Normalize URL to use as a key in the database."""
    if not url:
        return "no_url"
    
    # Remove protocol, www, trailing slashes, etc.
    url = url.lower()
    url = url.replace("http://", "").replace("https://", "")
    url = url.replace("www.", "")
    url = url.split("/")[0]  # Just use the domain
    
    return url

def save_target_events(url, user_summary, keywords, target_events, quality_score=None):
    """
    Save target events for a URL to the database.
    
    Args:
        url (str): The URL associated with the target events
        user_summary (str): The user's business profile summary
        keywords (list): Keywords associated with the target events
        target_events (str): The target events recommendation text
        quality_score (float, optional): Quality score for the recommendation (0-1)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ensure_db_exists()
        
        # Load existing database
        with open(DB_FILE, 'r') as f:
            db = json.load(f)
        
        # Get normalized URL key
        url_key = get_url_key(url)
        
        # Get current timestamp
        timestamp = int(time.time())
        
        # Create new entry
        entry = {
            "timestamp": timestamp,
            "url": url,
            "user_summary": user_summary,
            "keywords": keywords,
            "target_events": target_events,
            "quality_score": quality_score or 0.5,  # Default score if not provided
            "user_rated": False,
            "flagged": False
        }
        
        # Add to database
        if url_key not in db:
            db[url_key] = []
        
        db[url_key].append(entry)
        
        # Save updated database
        with open(DB_FILE, 'w') as f:
            json.dump(db, f, indent=2)
        
        logger.info(f"Saved target events for URL: {url_key}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving target events: {str(e)}")
        return False

def get_target_events(url, max_entries=3):
    """
    Get target events for a URL from the database.
    
    Args:
        url (str): The URL to get target events for
        max_entries (int): Maximum number of entries to return
    
    Returns:
        list: List of target event entries for the URL
    """
    try:
        ensure_db_exists()
        
        # Load database
        with open(DB_FILE, 'r') as f:
            db = json.load(f)
        
        # Get normalized URL key
        url_key = get_url_key(url)
        
        # Get entries for URL
        entries = db.get(url_key, [])
        
        # Sort by quality score (highest first) and timestamp (newest first)
        entries.sort(key=lambda x: (x.get("quality_score", 0), x.get("timestamp", 0)), reverse=True)
        
        # Return top entries
        return entries[:max_entries]
    
    except Exception as e:
        logger.error(f"Error getting target events: {str(e)}")
        return []

def update_quality_score(url, entry_timestamp, new_score, flagged=False):
    """
    Update the quality score for a specific target events entry.
    
    Args:
        url (str): The URL associated with the entry
        entry_timestamp (int): The timestamp of the entry to update
        new_score (float): The new quality score (0-1)
        flagged (bool): Whether the entry should be flagged as low quality
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ensure_db_exists()
        
        # Load database
        with open(DB_FILE, 'r') as f:
            db = json.load(f)
        
        # Get normalized URL key
        url_key = get_url_key(url)
        
        # Get entries for URL
        entries = db.get(url_key, [])
        
        # Find and update the specific entry
        for entry in entries:
            if entry.get("timestamp") == entry_timestamp:
                entry["quality_score"] = new_score
                entry["flagged"] = flagged
                entry["user_rated"] = True
                break
        
        # Save updated database
        with open(DB_FILE, 'w') as f:
            json.dump(db, f, indent=2)
        
        logger.info(f"Updated quality score for URL: {url_key}, timestamp: {entry_timestamp}")
        return True
    
    except Exception as e:
        logger.error(f"Error updating quality score: {str(e)}")
        return False

def merge_target_events(url, max_entries=3):
    """
    Merge multiple target events entries for a URL into a single comprehensive recommendation.
    
    Args:
        url (str): The URL to merge target events for
        max_entries (int): Maximum number of entries to consider for merging
    
    Returns:
        str: Merged target events recommendation
    """
    try:
        # Get top entries for URL
        entries = get_target_events(url, max_entries)
        
        if not entries:
            return ""
        
        # If only one entry, return it directly
        if len(entries) == 1:
            return entries[0].get("target_events", "")
        
        # For multiple entries, we need to merge them
        # This is a simple implementation - in a real-world scenario,
        # you might want to use more sophisticated NLP techniques
        
        # Extract the best parts from each entry based on quality score
        merged_text = f"<h2 class='section-title'>Curated Event Recommendations</h2>\n\n"
        
        # Add a note about the merged recommendations
        merged_text += "<p><em>These recommendations have been refined based on multiple analyses to provide you with the most relevant event suggestions.</em></p>\n\n"
        
        # Extract sections from each entry
        for i, entry in enumerate(entries):
            # Skip flagged entries
            if entry.get("flagged", False):
                continue
                
            # Extract the content
            content = entry.get("target_events", "")
            
            # Add the content with a weight based on quality score
            weight = entry.get("quality_score", 0.5)
            if weight > 0.7:  # Only include high-quality content
                # Extract sections using simple heuristics
                sections = content.split("<h")
                for section in sections:
                    if len(section.strip()) > 100:  # Only include substantial sections
                        merged_text += f"<h{section}\n\n"
        
        return merged_text
    
    except Exception as e:
        logger.error(f"Error merging target events: {str(e)}")
        return ""
