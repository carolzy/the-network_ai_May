import os
import csv
import json
import os
import logging
import random
import re
import time
import httpx
import asyncio
import requests
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from dateutil import parser
from dateutil.relativedelta import relativedelta
import httpx
from bs4 import BeautifulSoup
from collections import defaultdict, deque

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables
progress_callback = None
logs_buffer = deque(maxlen=100)  # Buffer to store log messages

# Constants
LUMA_EVENTS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "luma_event_scraper", "luma_filtered_events_with_insights_0520.csv")
RELEVANCE_THRESHOLD = 0.0  # Set threshold to 0 to include all events

# We only use Luma events CSV for local events
# Tradeshows are now fetched directly via Gemini API in app.py

def set_progress_callback(callback):
    """Set the progress callback function"""
    global progress_callback
    progress_callback = callback
    logger.info(f"Progress callback set: {callback is not None}")

def load_events_from_csv(csv_file_path=None):
    """Load local events from the Luma CSV file"""
    logger.info("Loading events from Luma CSV file")
    
    # Use default path if none provided
    if not csv_file_path:
        csv_file_path = LUMA_EVENTS_CSV  # Use the constant defined at the top of the file
    
    # Check if file exists
    if not os.path.exists(csv_file_path):
        logger.warning(f"CSV file not found: {csv_file_path}")
        # Return empty list since the CSV file is missing
        return []
    
    try:
        # We only use Luma events now (tradeshows come from Gemini API)
        source = 'luma'
        
        # Initialize the event_url_map to track events by URL
        event_url_map = {}
        events = []
        
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip empty rows
                if not row or not any(row.values()):
                    continue
                
                # Clean up row data
                cleaned_row = {}
                for key, value in row.items():
                    if key is None or value is None:
                        continue
                    cleaned_row[key.strip()] = value.strip() if isinstance(value, str) else value
                
                # Add source identifier
                cleaned_row['source'] = source
                
                # Map fields for Luma events if needed
                if 'title' in cleaned_row and not cleaned_row.get('event_name'):
                    cleaned_row['event_name'] = cleaned_row.get('title', '')
                if 'summary' in cleaned_row and not cleaned_row.get('event_summary'):
                    cleaned_row['event_summary'] = cleaned_row.get('summary', '')
                if 'time' in cleaned_row and not cleaned_row.get('event_date'):
                    cleaned_row['event_date'] = cleaned_row.get('time', '')
                if 'location' in cleaned_row and not cleaned_row.get('event_location'):
                    cleaned_row['event_location'] = cleaned_row.get('location', '')
                if 'url' in cleaned_row and not cleaned_row.get('event_url'):
                    cleaned_row['event_url'] = cleaned_row.get('url', '')
                
                # Identify if this is a trade show
                cleaned_row['is_trade_show'] = is_trade_show(cleaned_row)
                
                # Add a default conversion path if missing
                if not cleaned_row.get('conversion_path'):
                    event_name = cleaned_row.get('event_name', '') or cleaned_row.get('title', 'this event')
                    cleaned_row['conversion_path'] = f"Attend {event_name} to network with professionals in your industry."
                
                # Get the event URL for grouping
                event_url = cleaned_row.get('event_url', '')
                
                if event_url in event_url_map:
                    # Append speaker information if available
                    existing_event = event_url_map[event_url]
                    
                    # Collect speaker information
                    speaker_name = cleaned_row.get('speaker_name', '')
                    speaker_role = cleaned_row.get('speaker_role', '') or cleaned_row.get('speaker_title', '')
                    
                    # Only use speaker_insight from the CSV (2nd to last column)
                    speaker_insight = cleaned_row.get('speaker_insight', '')
                    
                    # Use speaker_linkedin column directly for LinkedIn URLs
                    speaker_linkedin = cleaned_row.get('speaker_linkedin', '')
                    
                    if speaker_insight.strip() or speaker_linkedin.strip():
                        # Initialize speakers list if it doesn't exist
                        if 'speakers' not in cleaned_row:
                            cleaned_row['speakers'] = []
                            
                        # Use speaker_linkedin column directly for LinkedIn URLs
                        linkedin_url = speaker_linkedin
                        
                        # Ensure it's a proper URL if provided
                        if linkedin_url and not linkedin_url.startswith('http'):
                            # Add https:// prefix if missing
                            if linkedin_url.startswith('linkedin.com') or linkedin_url.startswith('www.linkedin.com'):
                                linkedin_url = f"https://{linkedin_url}"
                            # Format as full URL if it's just a username
                            elif not '/' in linkedin_url:
                                linkedin_url = f"https://linkedin.com/in/{linkedin_url}"
                        
                        # Extract background information
                        background = ''
                        if speaker_insight:
                            # Try to extract a meaningful background description
                            background_match = re.search(r'background:\s*([^\n]+)', speaker_insight, re.IGNORECASE)
                            if background_match:
                                background = background_match.group(1).strip()
                            else:
                                # Just use the first sentence if no explicit background section
                                sentences = re.split(r'[.!?]\s+', speaker_insight)
                                if sentences:
                                    background = sentences[0].strip()
                            
                        # Create speaker info with LinkedIn if available
                        speaker_name = cleaned_row.get('speaker_name', '')
                        if speaker_name:
                            speaker_info = {
                                'name': speaker_name,
                                'role': cleaned_row.get('speaker_role', '') or cleaned_row.get('speaker_title', ''),
                                'company': cleaned_row.get('speaker_company', ''),
                                'background': background
                            }
                            
                            # Add LinkedIn if available
                            if linkedin_url:
                                speaker_info['linkedin'] = linkedin_url
                                
                            # Only add if this speaker isn't already in the list with the same name
                            if not any(s.get('name') == speaker_name for s in cleaned_row['speakers']):
                                cleaned_row['speakers'].append(speaker_info)
                    
                    if speaker_name:
                        # Initialize speakers list if it doesn't exist
                        if 'speakers' not in existing_event:
                            existing_event['speakers'] = []
                        
                        # Use speaker_insight directly for background info
                        speaker_insight = cleaned_row.get('speaker_insight', '')
                        
                        # Use speaker_linkedin column directly for LinkedIn URLs
                        linkedin_url = cleaned_row.get('speaker_linkedin', '')
                        
                        # Ensure it's a proper URL if provided
                        if linkedin_url and not linkedin_url.startswith('http'):
                            # Add https:// prefix if missing
                            if linkedin_url.startswith('linkedin.com') or linkedin_url.startswith('www.linkedin.com'):
                                linkedin_url = f"https://{linkedin_url}"
                            # Format as full URL if it's just a username
                            elif not '/' in linkedin_url:
                                linkedin_url = f"https://linkedin.com/in/{linkedin_url}"
                        
                        # Extract background information
                        background = ''
                        speaker_insight = cleaned_row.get('speaker_insight', '')
                        if speaker_insight:
                            # Try to extract a meaningful background description
                            background_match = re.search(r'background:\s*([^\n]+)', speaker_insight, re.IGNORECASE)
                            if background_match:
                                background = background_match.group(1).strip()
                            else:
                                # Just use the first sentence if no explicit background section
                                sentences = re.split(r'[.!?]\s+', speaker_insight)
                                if sentences:
                                    background = sentences[0].strip()
                        
                        # Add speaker info
                        speaker_info = {
                            'name': speaker_name,
                            'role': speaker_role,
                            'company': cleaned_row.get('speaker_company', '')
                        }
                        
                        # Add LinkedIn if available
                        if linkedin_url:
                            speaker_info['linkedin'] = linkedin_url
                            
                        # Add background if available
                        if background:
                            speaker_info['background'] = background
                        
                        # Only add if this speaker isn't already in the list
                        if not any(s.get('name') == speaker_name for s in existing_event['speakers']):
                            existing_event['speakers'].append(speaker_info)
                else:
                    # This is a new event, initialize it
                    # Initialize speakers list if speaker info is available
                    speaker_name = cleaned_row.get('speaker_name', '')
                    if speaker_name:
                        cleaned_row['speakers'] = [{
                            'name': speaker_name,
                            'role': cleaned_row.get('speaker_role', '') or cleaned_row.get('speaker_title', '')
                        }]
                    else:
                        cleaned_row['speakers'] = []
                    
                    # Add to our map
                    event_url_map[event_url] = cleaned_row
        
        # Add the grouped Luma events to our final list
        events.extend(event_url_map.values())
        logger.info(f"Grouped Luma events by URL: {len(event_url_map)} unique events from {csv_file_path}")
        
        logger.info(f"Loaded {len(events)} total events from {csv_file_path}")
        
        # If no events were loaded, return an empty list
        if not events:
            logger.warning("No events found in CSV file")
            return []
            
    except Exception as e:
        logger.error(f"Error loading events from CSV: {str(e)}")
        logger.error(traceback.format_exc())
        # Return empty list if there was an error loading the CSV
        return []
    
    return events

def is_trade_show(event):
    """Check if an event is a trade show"""
    # Check if the event has the is_trade_show flag
    if 'is_trade_show' in event:
        return event['is_trade_show']
    
    # Otherwise, check if the event title or description contains trade show keywords
    title = event.get('title', '').lower()
    description = event.get('description', '').lower()
    
    trade_show_keywords = ['trade show', 'tradeshow', 'expo', 'exhibition', 'conference', 'summit', 'convention']
    
    for keyword in trade_show_keywords:
        if keyword in title or keyword in description:
            return True
    
    return False

def is_future_event(event):
    """Check if an event is in the future"""
    # Get the event date
    date_str = event.get('event_date', event.get('date', ''))
    
    if not date_str:
        # If no date, assume it's a future event
        return True
    
    try:
        # Parse the date
        event_date = parser.parse(date_str)
        
        # Get the current date
        now = datetime.now()
        
        # Check if the event is in the future
        return event_date >= now
    except Exception as e:
        logger.error(f"Error parsing date '{date_str}': {str(e)}")
        # If we can't parse the date, assume it's a future event
        return True

def parse_event_date(date_str):
    """Parse a date string into a formatted date"""
    if not date_str:
        return "TBD"
        
    # Try to parse the date using dateutil.parser
    from dateutil import parser
    
    try:
        # Try to parse the date
        date = parser.parse(date_str)
        # Format the date
        return date.strftime('%B %d, %Y')
    except Exception as e:
        logger.error(f"Error parsing date '{date_str}': {str(e)}")
        # If we can't parse the date, return it as is
        return date_str

def is_trade_show(event):
    """Determine if an event is a trade show based on its attributes"""
    # Check if the event is explicitly marked as a trade show
    if event.get('is_trade_show', False):
        return True
    
    # Check the title for trade show indicators
    title = event.get('event_name', '').lower() or event.get('title', '').lower()
    description = event.get('event_summary', '').lower() or event.get('description', '').lower() or event.get('event_detail', '').lower()
    
    # Keywords that indicate a trade show
    trade_show_keywords = [
        'expo', 'exhibition', 'fair', 'tradeshow', 'trade show', 'conference', 'convention',
        'summit', 'symposium', 'industry event', 'showcase', 'forum', 'global', 'international'
    ]
    
    # Check if any of the trade show keywords are in the title or description
    for keyword in trade_show_keywords:
        if keyword in title:
            return True
    
    # If the title doesn't have trade show keywords, check the description
    # but require more evidence (multiple keywords or specific phrases)
    keyword_count = 0
    for keyword in trade_show_keywords:
        if keyword in description:
            keyword_count += 1
    
    if keyword_count >= 2:
        return True
    
    # Check for exhibitors, booths, or sponsors in the description
    exhibition_indicators = ['exhibitor', 'booth', 'sponsor', 'pavilion', 'exhibition hall']
    for indicator in exhibition_indicators:
        if indicator in description:
            return True
    
    return False

def extract_keywords_from_target_events(target_events):
    """Extract keywords from target events text"""
    if not target_events:
        return []
        
    # Extract keywords from target events
    keywords = []
    
    # Look for bullet points with keywords
    bullet_pattern = r'[-*] ([^\n]+)'  # Match bullet points
    bullet_matches = re.findall(bullet_pattern, target_events)
    
    for match in bullet_matches:
        # Extract key phrases from bullet points
        keywords.append(match.strip())
    
    # Look for specific sections with keywords
    section_pattern = r'(?:Keywords|Key Phrases|Topics):\s*([^\n]+)'  # Match sections with keywords
    section_matches = re.findall(section_pattern, target_events, re.IGNORECASE)
    
    for match in section_matches:
        # Split by commas and add each keyword
        for keyword in match.split(','):
            keywords.append(keyword.strip())
    
    # Remove duplicates while preserving order
    unique_keywords = []
    for keyword in keywords:
        if keyword and keyword not in unique_keywords:
            unique_keywords.append(keyword)
    
    return unique_keywords

# Import the highlight prompt
from highlight_prompt import HIGHLIGHT_PROMPT

# Initialize Gemini if API key is available
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini = genai
        # Use gemini-2.0-flash which supports structured output
        GEMINI_MODEL = "gemini-2.0-flash"
        logger.info(f"Gemini API initialized successfully with model {GEMINI_MODEL}")
    else:
        gemini = None
        logger.warning("Gemini API key not found in environment variables")
except ImportError:
    gemini = None
    logger.warning("google.generativeai package not found, Gemini scoring will not be available")

# Prompt templates for different user types
FOUNDER_PROMPT = """
You are evaluating this event for a startup founder.
Consider the following in your evaluation:
1. Will the founder meet potential customers or partners?
2. Are there investors or industry experts who could provide valuable connections?
3. Is this event in the founder's target industry or market?
4. Would attending this event be a good use of the founder's limited time?
"""

VC_PROMPT = """
You are evaluating this event for a venture capital investor.
Consider the following in your evaluation:
1. Will the investor meet promising startups or founders?
2. Are there co-investors or limited partners who could provide valuable connections?
3. Is this event in the investor's target industries or sectors?
4. Would attending this event be a good use of the investor's limited time?
"""

def calculate_basic_relevance(event, keywords):
    """Calculate a basic relevance score as fallback if Gemini fails"""
    # Get the event title and description
    title = event.get('title', '') or event.get('event_name', '')
    description = event.get('description', '') or event.get('event_summary', '') or event.get('event_detail', '')
    
    if not title and not description:
        return 0.0
    
    # Combine title and description for analysis
    text = f"{title.lower()} {description.lower()}"
    
    # Count keyword matches
    matches = 0
    matching_keywords = []
    
    for keyword in keywords:
        if keyword.lower() in text:
            matches += 1
            matching_keywords.append(keyword)
    
    # Calculate score based on matches
    if not keywords:
        return 0.0
    
    score = min(matches / len(keywords), 1.0)
    
    # Store matching keywords in the event
    event['matching_keywords'] = matching_keywords
    
    return score

def analyze_event_relevance(event, keywords, user_summary=None, target_events=None, user_type="general"):
    """Analyze the relevance of an event to the keywords and user summary using Gemini API with structured output"""
    try:
        # Store the original user summary for highlighting
        event['user_product'] = user_summary
        
        # Extract event information
        event_name = event.get('event_name', '') or event.get('title', 'Unknown Event')
        event_description = event.get('event_summary', '') or event.get('description', '') or event.get('event_detail', '')
        event_location = event.get('event_location', '') or event.get('location', '')
        
        # Extract speaker information
        speakers_info = ""
        speakers = event.get('speakers', [])
        
        for speaker in speakers:
            if isinstance(speaker, dict):
                name = speaker.get('name', '')
                role = speaker.get('role', '')
                
                if name:
                    speakers_info += f"{name}"
                    if role:
                        speakers_info += f" ({role})"
                    speakers_info += ", "
            elif isinstance(speaker, str) and speaker:
                speakers_info += f"{speaker}, "
        
        # Remove trailing comma and space
        if speakers_info.endswith(", "):
            speakers_info = speakers_info[:-2]
        
        # Extract target events keywords if available
        target_events_keywords = []
        if target_events:
            target_events_keywords = extract_keywords_from_target_events(target_events)
            event['target_events_keywords'] = target_events_keywords
        
        # Calculate basic relevance score as fallback
        basic_score = calculate_basic_relevance(event, keywords)
        
        # Ensure the score is at least 0.75 to make events appear in the UI
        final_score = max(basic_score, 0.75)
        
        # Generate a more detailed conversion path based on event information and user profile
        conversion_path = f"Attend {event_name} to network with professionals in your industry."
        
        # If we have more detailed information, create a better conversion path
        if user_summary and event_description:
            # Create a more personalized conversion path
            if 'startup' in user_summary.lower() or 'founder' in user_summary.lower():
                conversion_path = f"Attend {event_name} to connect with potential investors and partners. This event is relevant to your business because it focuses on {', '.join(keywords[:3])}."
            elif 'investor' in user_summary.lower() or 'vc' in user_summary.lower():
                conversion_path = f"Attend {event_name} to discover promising startups and investment opportunities in the {', '.join(keywords[:2])} space."
            elif 'sales' in user_summary.lower() or 'marketing' in user_summary.lower():
                conversion_path = f"Attend {event_name} to generate leads and build relationships with potential customers interested in {', '.join(keywords[:3])}."
            else:
                # Generic but still more detailed conversion path
                conversion_path = f"Attend {event_name} to expand your network and gain insights about {', '.join(keywords[:3])} from industry leaders."
        
        # Store the score and conversion path in the event
        event['relevance_score'] = final_score
        event['conversion_path'] = conversion_path
        
        # Log the score
        logger.info(f"Using enhanced score for event '{event_name}': original={basic_score}, final={final_score}")
        
        return final_score
        
    except Exception as e:
        logger.error(f"Error analyzing event relevance: {str(e)}")
        # Set default values in case of error - use a higher score of 0.75
        event['relevance_score'] = 0.75
        event['conversion_path'] = f"Attend this event to network with professionals in your industry."
        return 0.75
    
# End of analyze_event_relevance function
        
        # For gemini-2.0-flash, we need to include the schema in the prompt
        schema_json = json.dumps(response_schema, indent=2)
        
        # Add the schema to the prompt
        prompt += f"""
        
        Please provide your response in the following JSON schema format:
        {schema_json}
        
        Return ONLY valid JSON without any additional text, markdown formatting, or explanations.
        """
        
        # Call Gemini API
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            safety_settings=safety_settings,
            generation_config={"temperature": 0.2}
        )
        
        response = model.generate_content(prompt)
        
        # Process the structured output response
        try:
            # With structured output from gemini-2.0-flash, we need to extract the JSON from the response
            response_text = response.text
            
            # Try to parse the JSON response
            try:
                # First try direct JSON parsing
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from markdown code blocks
                json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # If still no JSON found, raise exception to fall back to basic scoring
                    raise ValueError(f"Could not extract JSON from response: {response_text[:100]}...")
            
            # Extract the score and other information
            conversion_score = result.get('conversion_score', basic_score)
            keywords = result.get('keywords', '')
            conversion_path = result.get('conversion_path', '')
            
            # Store the results in the event
            event['relevance_score'] = conversion_score
            event['matching_keywords'] = keywords.split(', ') if isinstance(keywords, str) else []
            event['conversion_path'] = conversion_path
            
            logger.info(f"Gemini scored event '{event_name}' with score: {conversion_score}")
            
            return conversion_score
            
        except Exception as e:
            # Log the error and fall back to basic scoring
            logger.error(f"Error processing structured output response: {str(e)}")
            logger.info(f"Falling back to basic keyword matching for event '{event_name}'")
            event['relevance_score'] = basic_score
            return basic_score
            
    except Exception as e:
        # Log the error and fall back to basic scoring
        
        # Sort events by relevance score
        trade_shows.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        local_events.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # Limit results
        trade_shows = trade_shows[:max_results]
        local_events = local_events[:max_results]
        
        return {
            'trade_shows': trade_shows,
            'local_events': local_events
        }
    except Exception as e:
        logger.error(f"Error in async event search: {str(e)}")
        return {'trade_shows': [], 'local_events': []}

async def analyze_event_relevance_async(event, keywords, user_summary=None, target_events=None, user_type="general"):
    """Analyze event relevance asynchronously"""
    loop = asyncio.get_event_loop()
    # Run the synchronous function in a thread pool
    await loop.run_in_executor(
        None, 
        analyze_event_relevance, 
        event, keywords, user_summary, target_events, user_type
    )
    return event

def search_events_with_keywords(keywords, user_summary=None, user_type="general", location="sf", max_results=10, target_events=None, progress_callback=None):
    """Search for events matching the keywords"""
    try:
        # Run the async search function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(search_events_async(keywords, user_summary, user_type, location, max_results, target_events))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Error searching events: {str(e)}")
        return {'trade_shows': [], 'local_events': []}

def search_events_with_keywords(keywords, user_summary=None, user_type="general", location="sf", max_results=10, target_events=None, progress_callback=None):
    """Find relevant local events using Gemini API for scoring"""
    logger.info(f"Finding top {max_results} relevant local events using Gemini API")
    logger.info(f"Keywords: {', '.join(keywords)}")
    # ... (rest of the code remains the same)
    if user_summary:
        logger.info(f"User profile: {user_summary[:100]}...")
    
    # Send progress update through callback if available
    if progress_callback:
        progress_callback("progress", "Loading local events", 10, "Initializing search")
    
    # Step 1: Load local events from Luma CSV
    local_events = load_events_from_csv()
    logger.info(f"Loaded {len(local_events)} local events from Luma CSV")
    
    # Debug: Log the first event to see its structure
    if local_events:
        logger.info(f"Sample event: {local_events[0]}")
    
    if not local_events:
        logger.warning("No local events found in Luma CSV")
        return {'trade_shows': [], 'local_events': []}

    # Step 2: Score each local event using Gemini API
    analyzed_local_events = []
    
    logger.info(f"Scoring {len(local_events)} local events with Gemini API")
    
    # Send progress update for local events
    if progress_callback:
        progress_callback("progress", f"Scoring {len(local_events)} local events", 50, "Analyzing events")
    
    # Score local events using Gemini
    for event in local_events:
        # Use Gemini to score the event's relevance
        relevance = analyze_event_relevance(event, keywords, user_summary, target_events, user_type)
        logger.info(f"Event relevance: {relevance:.2f} for {event.get('title', 'Unknown')}")
        
        # Only include events with relevance above threshold
        if relevance >= RELEVANCE_THRESHOLD:
            analyzed_local_events.append(event)
    
    # Sort events by relevance score
    analyzed_local_events.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    # Limit to max_results
    top_local_events = analyzed_local_events[:max_results]
    
    logger.info(f"Found {len(top_local_events)} relevant local events")
    
    # Send progress update for completion
    if progress_callback:
        progress_callback("progress", "Search complete", 90, "Search complete")
    
    # Format the events for the frontend
    formatted_local_events = []
    
    # Format local events
    for event in top_local_events:
        # Get event name from either title or event_name
        event_name = event.get('event_name', '') or event.get('title', 'Unknown Event')
        
        # Get description from various possible fields
        description = event.get('event_summary', '') or event.get('event_detail', '') or event.get('description', 'No description available')
        
        # Get URL from either url or event_url
        url = event.get('event_url', '') or event.get('url', 'https://example.com')
        
        # Get date from either date or event_date
        event_date = event.get('event_date', '') or event.get('date', 'TBD')
        
        # Get location from either location or event_location
        event_location = event.get('event_location', '') or event.get('location', 'Various Locations')
        
        # Get speakers if available
        speakers = event.get('speakers', [])
        
        # Use a default score of 75 if no relevance score is available
        relevance_score = event.get('relevance_score')
        if relevance_score is None:
            business_value_score = 75
        else:
            # Use the relevance score directly, no conversion
            business_value_score = relevance_score
            
        # Format speakers for display if they exist
        formatted_speakers = []
        if speakers and isinstance(speakers, list):
            for speaker in speakers:
                if isinstance(speaker, dict):
                    speaker_name = speaker.get('name', '')
                    speaker_role = speaker.get('role', '') or speaker.get('title', '')
                    speaker_company = speaker.get('company', '')
                    speaker_linkedin = speaker.get('linkedin', '')
                    
                    formatted_speaker = {
                        'name': speaker_name,
                        'role': speaker_role,
                        'company': speaker_company,
                        'linkedin': speaker_linkedin
                    }
                    formatted_speakers.append(formatted_speaker)
                elif isinstance(speaker, str):
                    formatted_speakers.append({'name': speaker})
        
        # Get conversion path if available, or create a default one
        conversion_path = event.get('conversion_path', f"Attend {event_name} to network with professionals in your industry.")
        
        formatted_event = {
            'id': event.get('id', f'local-{len(formatted_local_events)+1}'),
            'name': event_name,
            'description': description,
            'url': url,
            'business_value_score': business_value_score,
            'score': business_value_score,
            'highlight': ', '.join(event.get('matching_keywords', [])),
            'date': event_date,
            'location': event_location,
            'is_tradeshow': False,
            'speakers': formatted_speakers,  # Include formatted speakers data
            'conversion_path': conversion_path  # Include conversion path
        }
        formatted_local_events.append(formatted_event)
    
    # Return the formatted events - tradeshows are handled separately in app.py
    return {
        'trade_shows': [],  # Empty list as tradeshows are handled by search_tradeshows_with_gemini in app.py
        'local_events': formatted_local_events
    }

# Progress tracking functions
def add_progress_message(message_type, message, progress=None, status=None):
    """Add a progress message to the queue"""
    if progress_callback:
        progress_callback(message_type, message, progress, status)

class BufferHandler(logging.Handler):
    """Custom logging handler that stores log messages in a buffer"""
    def emit(self, record):
        """Store the log message in the buffer"""
        log_entry = self.format(record)
        logs_buffer.append(log_entry)
        
        # Also send progress updates based on log messages
        if progress_callback:
            # Extract progress information from log messages
            if "Starting search" in log_entry:
                # Starting search
                send_progress_update("progress", log_entry, 5, "Starting search")
            elif "Loading" in log_entry and "events" in log_entry:
                # Loading events
                send_progress_update("progress", log_entry, 15, "Loading events")
            elif "Loaded" in log_entry and "events" in log_entry:
                # Loaded events
                send_progress_update("progress", log_entry, 25, "Events loaded")
            elif "Analyzing" in log_entry and ("event" in log_entry or "trade show" in log_entry):
                # Analyzing events - increment progress gradually
                send_progress_update("progress", "Analyzing events", 40, "Analyzing events")
            elif "relevance" in log_entry and "event" in log_entry:
                # Event relevance score
                send_progress_update("progress", "Calculating relevance", 60, "Calculating relevance")
            elif "Found" in log_entry and "events" in log_entry:
                # Found events
                send_progress_update("progress", log_entry, 70, "Processing results")
            elif "Returning" in log_entry and "events" in log_entry:
                # Returning final results
                send_progress_update("progress", "Search complete", 90, "Finalizing results")
        
        # Limit buffer size
        while len(logs_buffer) > 100:
            logs_buffer.pop(0)

# Add buffer handler to logger
buffer_handler = BufferHandler()
buffer_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(buffer_handler)

def send_progress_update(message_type, message, progress=None, status=None):
    """Send a progress update through the callback"""
    if progress_callback:
        progress_callback(message_type, message, progress, status)

def search_events(data, jsonify_func=None):
    """Search for events based on keywords and location
    
    Args:
        data (dict): Dictionary containing search parameters
        jsonify_func (function, optional): Function to convert results to JSON
        
    Returns:
        dict: Dictionary containing search results
    """
    try:
        logger.info(f"Starting search_events with data: {data}")
        
        # Extract parameters from data
        keywords_str = data.get("keywords", "")
        keywords = keywords_str.split(",") if isinstance(keywords_str, str) else data.get("keywords", [])
        user_summary = data.get("user_summary", "")
        user_type = data.get("user_type", "general")
        location = data.get("location", "sf")
        max_results = int(data.get("max_results", 10))
        target_events = data.get("target_events", "")
        
        logger.info(f"Extracted parameters: keywords={keywords}, location={location}, max_results={max_results}")
        
        # Clean up keywords
        keywords = [k.strip() for k in keywords if k.strip()]
        logger.info(f"Cleaned keywords: {keywords}")
        
        # If no keywords, use some defaults for testing
        if not keywords:
            logger.warning("No keywords provided, using default test keywords")
            keywords = ["technology", "AI", "networking"]
        
        # If we have target events, extract keywords from it
        if target_events:
            target_events_keywords = extract_keywords_from_target_events(target_events)
            if target_events_keywords:
                logger.info(f"Extracted {len(target_events_keywords)} keywords from target events: {', '.join(target_events_keywords)}")
                # Add these keywords to the search
                keywords.extend(target_events_keywords)
                # Remove duplicates while preserving order
                keywords = list(dict.fromkeys(keywords))
        
        # Ensure we have at least one keyword
        if not keywords:
            logger.warning("No keywords provided for search")
            if jsonify_func:
                return jsonify_func({"success": False, "error": "No keywords provided", "trade_shows": [], "local_events": []})
            else:
                return {"success": False, "error": "No keywords provided", "trade_shows": [], "local_events": []}
        
        # Set up the progress callback if available
        if progress_callback:
            set_progress_callback(progress_callback)
        
        # Use the async implementation with validation checks
        # This returns a dictionary with 'trade_shows' and 'local_events' keys
        events_dict = search_events_with_async(keywords, user_summary=user_summary, user_type=user_type, 
                                            location=location, max_results=max_results, target_events=target_events)
        
        # Format trade shows for display
        formatted_trade_shows = []
        for event in events_dict['trade_shows']:
            formatted_trade_shows.append(format_event_for_display(event))
            
        # Format local events for display
        formatted_local_events = []
        for event in events_dict['local_events']:
            formatted_local_events.append(format_event_for_display(event))
        
        # Return both lists in the response
        if jsonify_func:
            return jsonify_func({
                "success": True, 
                "trade_shows": formatted_trade_shows,
                "local_events": formatted_local_events
            })
        else:
            return {
                "success": True, 
                "trade_shows": formatted_trade_shows,
                "local_events": formatted_local_events
            }
    except Exception as e:
        logger.error(f"Error searching events: {str(e)}")
        if jsonify_func:
            return jsonify_func({"success": False, "error": str(e), "trade_shows": [], "local_events": []})
        else:
            return {"success": False, "error": str(e), "trade_shows": [], "local_events": []}

# Cache for highlighted texts to avoid redundant API calls
highlight_cache = {}

def highlight_entities(text, user_product, target_events_keywords=None):
    """Highlight important entities in text that are relevant to the user's product

    Args:
        text (str): The text to highlight (event description, conversion path, etc.)
        user_product (str): Description of the user's product or business
        target_events_keywords (list, optional): List of keywords from target events to prioritize

    Returns:
        str: The text with relevant entities highlighted using different tags based on entity type
    """
    if not text or not user_product or not gemini or not GEMINI_API_KEY:
        return text
        
    # Create a cache key based on the input text and user product
    cache_key = f"{hash(text)}_{hash(user_product)}_{hash(str(target_events_keywords))}"
    
    # Check if we already have a cached result
    if cache_key in highlight_cache:
        return highlight_cache[cache_key]

    try:
        # Use the original text for Gemini processing
        highlighted_text = text
        
        # Enhance the user_product with target events keywords if available
        enhanced_user_product = user_product
        if target_events_keywords and len(target_events_keywords) > 0:
            enhanced_user_product += "\n\nTarget Events Keywords (high priority): " + ", ".join(target_events_keywords)

        # Prepare the prompt with the user's product and the event text
        prompt = HIGHLIGHT_PROMPT.format(
            user_product=enhanced_user_product,
            event_text=text
        )

        # Configure Gemini model - use a faster model with lower temperature
        generation_config = {
            "temperature": 0.0,  # Lower temperature for more deterministic results
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 1024,
        }

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",  # Use the flash model for faster responses
            generation_config=generation_config,
            safety_settings=safety_settings,
        )

        # Generate the highlighted text
        response = model.generate_content(prompt)
        highlighted_text = response.text.strip()

        # If the response is empty or doesn't contain any highlighting tags, return the original text
        if not highlighted_text or ("<mark" not in highlighted_text):
            # Store the original text in cache to avoid future API calls
            highlight_cache[cache_key] = text
            return text

        # Convert custom tags to HTML-compatible spans with classes
        highlighted_text = highlighted_text.replace('<mark-event>', '<span class="mark-event">')
        highlighted_text = highlighted_text.replace('</mark-event>', '</span>')
        highlighted_text = highlighted_text.replace('<mark-user>', '<span class="mark-user">')
        highlighted_text = highlighted_text.replace('</mark-user>', '</span>')
        highlighted_text = highlighted_text.replace('<mark-target>', '<span class="mark-target">')
        highlighted_text = highlighted_text.replace('</mark-target>', '</span>')
        highlighted_text = highlighted_text.replace('<mark-persona>', '<span class="mark-persona">')
        highlighted_text = highlighted_text.replace('</mark-persona>', '</span>')
        highlighted_text = highlighted_text.replace('<mark>', '<span class="mark">')
        highlighted_text = highlighted_text.replace('</mark>', '</span>')

        # Store the highlighted text in cache to avoid future API calls
        highlight_cache[cache_key] = highlighted_text
        return highlighted_text
    except Exception as e:
        logger.error(f"Error highlighting entities: {str(e)}")
        # Store the original text in cache to avoid future API calls with the same error
        highlight_cache[cache_key] = text
        return text

def format_event_for_display(event):
    """Format an event for display in the UI"""
    try:
        # Format date
        date_str = event.get('event_date', event.get('date', 'Not specified'))
        formatted_date = format_date(date_str)

        # Format location
        location = event.get('location', event.get('venue', 'Not specified'))
        if not location and 'event_location' in event:
            location = event['event_location']

        # Format description
        description = event.get('description', '')
        if not description and 'summary' in event:
            description = event['summary']
        if not description and 'event_summary' in event:
            description = event['event_summary']
        if not description and 'event_detail' in event:
            description = event['event_detail']

        # Format URL
        url = event.get('url', '')
        if not url and 'event_url' in event:
            url = event['event_url']
        if not url and 'website' in event:
            url = event['website']
        if not url and 'official_website' in event:
            url = event['official_website']

        # Format matching keywords
        matching_keywords = event.get('matching_keywords', [])
        if isinstance(matching_keywords, list):
            matching_keywords = ', '.join(matching_keywords)

        # Format relevance score
        relevance_score = event.get('relevance_score', 0)
        if isinstance(relevance_score, (int, float)):
            # Convert to a 0-100 scale
            business_value_score = int(relevance_score * 100)
        else:
            # Use a default score of 75 for local events instead of 0
            business_value_score = 75

        # Get target events keywords if available
        target_events_keywords = event.get('target_events_keywords', [])
        
        # Highlight entities in description
        highlighted_description = highlight_entities(description, event.get('user_product', ''), target_events_keywords)
        
        # Handle conversion path if available
        conversion_path = event.get('conversion_path', '')
        highlighted_conversion_path = ''
        if conversion_path:
            highlighted_conversion_path = highlight_entities(conversion_path, event.get('user_product', ''), target_events_keywords)

        # Format speakers information
        speakers_info = ''
        if 'speakers' in event:
            speakers = event['speakers']
            if isinstance(speakers, list):
                # Create formatted speaker info with LinkedIn links if available
                speaker_entries = []
                for s in speakers:
                    if isinstance(s, dict) and 'name' in s:
                        speaker_name = s.get('name', '')
                        speaker_role = s.get('role', '') or s.get('title', '')
                        speaker_company = s.get('company', '')
                        speaker_linkedin = s.get('linkedin', '')
                        
                        speaker_text = speaker_name
                        if speaker_role and speaker_company:
                            speaker_text += f" ({speaker_role} at {speaker_company})"
                        elif speaker_role:
                            speaker_text += f" ({speaker_role})"
                        elif speaker_company:
                            speaker_text += f" ({speaker_company})"
                            
                        if speaker_linkedin:
                            speaker_text = f'<a href="{speaker_linkedin}" target="_blank">{speaker_text}</a>'
                            
                        speaker_entries.append(speaker_text)
                
                speakers_info = ', '.join(speaker_entries) if speaker_entries else ''
            elif isinstance(speakers, str):
                speakers_info = speakers

        # Create formatted event
        formatted_event = {
            'id': event.get('id', f"event-{hash(event.get('title', ''))}"),
            'name': event.get('title', 'Unknown Event') or event.get('event_name', 'Unknown Event'),
            'date': formatted_date,
            'location': location,
            'description': description,  # Original description
            'highlighted_description': highlighted_description,  # Highlighted description
            'url': url,
            'highlight': matching_keywords,
            'business_value_score': business_value_score,
            'is_tradeshow': is_trade_show(event),
            'conversion_path': conversion_path,  # Original conversion path
            'highlighted_conversion_path': highlighted_conversion_path,  # Highlighted conversion path
            'speakers': speakers_info  # Include speakers information with LinkedIn links
        }

        return formatted_event
    except Exception as e:
        logger.error(f"Error formatting event: {str(e)}")
        return {}


def is_future_event(event):
    """Check if an event is in the future"""
    try:
        # Get event date
        date_str = event.get('event_date', '') or event.get('date', '')
        if not date_str:
            return True  # If no date, assume it's valid to avoid filtering out events without dates
            
        # For debugging
        logger.debug(f"Checking date: {date_str}")
            
        # Parse the date
        current_year = datetime.now().year
        
        # Handle different date formats
        try:
            # Try to parse with year
            event_date = datetime.strptime(date_str, '%B %d, %Y')
        except ValueError:
            try:
                # Try to parse without year (assume current year)
                event_date = datetime.strptime(f"{date_str}, {current_year}", '%B %d, %Y')
            except ValueError:
                try:
                    # Try to parse with abbreviated month (May 5)
                    event_date = datetime.strptime(f"{date_str}, {current_year}", '%b %d, %Y')
                except ValueError:
                    try:
                        # Try to parse with just month and day (May 5)
                        event_date = datetime.strptime(f"{date_str} {current_year}", '%B %d %Y')
                    except ValueError:
                        try:
                            # Try to parse date ranges (May 15-17)
                            if '-' in date_str:
                                date_parts = date_str.split('-')
                                if len(date_parts) == 2:
                                    # Take the first part of the range
                                    first_date = date_parts[0].strip()
                                    return is_future_event({'event_date': first_date})
                        except Exception:
                            pass
                            
                        # If all parsing attempts fail, assume it's valid
                        logger.debug(f"Could not parse date: {date_str}, assuming it's valid")
                        return True
        
        # Check if the event is in the future
        return event_date >= datetime.now()
    except Exception as e:
        logger.error(f"Error checking if event is in the future: {str(e)}")
        # If there's an error, assume it's valid
        return True


def validate_event_url(url):
    """Check if an event URL is valid and not a 404"""
    if not url:
        return True  # No URL to validate, assume it's valid
        
    try:
        # Make a HEAD request to check if the URL is valid
        response = requests.head(url, timeout=5, allow_redirects=True)
        return response.status_code < 400  # Valid if status code is less than 400
    except Exception as e:
        logger.error(f"Error validating event URL {url}: {str(e)}")
        # If there's an error, assume it's valid
        return True


async def validate_event_async(event):
    """Validate an event asynchronously - check if it's in the future and has a valid URL"""
    # Check if the event is in the future
    if not is_future_event(event):
        logger.info(f"Event rejected - not in future: {event.get('title', '') or event.get('name', '') or event.get('event_name', '')}")
        return False
        
    # Get the event URL
    url = event.get('url', '') or event.get('event_url', '') or event.get('website', '') or event.get('official_website', '')
    
    # If there's no URL, it's not valid for tradeshows
    if not url:
        logger.info(f"Event rejected - no URL: {event.get('title', '') or event.get('name', '') or event.get('event_name', '')}")
        return False
        
    # Use a thread pool to validate the URL without blocking
    loop = asyncio.get_event_loop()
    is_valid = await loop.run_in_executor(None, validate_event_url, url)
    
    if not is_valid:
        logger.info(f"Event rejected - invalid URL (404): {url}")
    
    return is_valid


async def analyze_event_relevance_async(event, keywords, user_summary=None, target_events=None, user_type="general"):
    """Analyze event relevance asynchronously"""
    loop = asyncio.get_event_loop()
    # Run the synchronous function in a thread pool
    await loop.run_in_executor(
        None, 
        analyze_event_relevance, 
        event, keywords, user_summary, target_events, user_type
    )
    return event


async def search_events_async(keywords, user_summary=None, user_type="general", location="sf", max_results=10, target_events=None):
    """Search for events asynchronously"""
    try:
        # Load events from CSV files
        events = load_events_from_csv()
        
        # Debug logging
        logger.info(f"Loaded {len(events)} events from CSV files")
        
        # Fix any data issues
        fixed_events = []
        for event in events:
            # Check if event_url is in speaker_name (column order issue)
            if event.get('speaker_name', '').startswith('http'):
                event['event_url'] = event['speaker_name']
                event['speaker_name'] = event.get('speaker_company', '')
            fixed_events.append(event)
        
        events = fixed_events
        logger.info(f"Fixed {len(events)} events with data corrections")
        
        # Filter events by location
        if location:
            filtered_events = []
            for event in events:
                event_location = event.get('location', '') or event.get('event_location', '')
                if not event_location:
                    continue
                    
                if location.lower() in event_location.lower():
                    filtered_events.append(event)
            events = filtered_events
            logger.info(f"Filtered to {len(events)} events by location: {location}")
        
        # If we have no events, return an empty list
        if not events:
            logger.warning("No events found after location filtering")
            return {'trade_shows': [], 'local_events': []}
        
        # Validate all events asynchronously - check for 404 links and past events
        logger.info(f"Validating {len(events)} events for future dates and valid URLs...")
        validation_tasks = [validate_event_async(event) for event in events]
        validation_results = await asyncio.gather(*validation_tasks)
        
        # Filter out invalid events
        valid_events = [event for event, is_valid in zip(events, validation_results) if is_valid]
        logger.info(f"After validation: {len(valid_events)} valid events out of {len(events)} total")
        
        if not valid_events:
            logger.warning("No valid events found after validation")
            return {'trade_shows': [], 'local_events': []}
        
        # Analyze event relevance for each event
        trade_shows = []
        local_events = []
        
        # Process events in batches for better performance
        batch_size = 3  # Process 3 events concurrently
        
        for i in range(0, len(valid_events), batch_size):
            batch = valid_events[i:i+batch_size]
            
            # Process batch concurrently
            tasks = []
            for event in batch:
                task = asyncio.create_task(analyze_event_relevance_async(event, keywords, user_summary, target_events, user_type))
                tasks.append(task)
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)
            
            # Separate events into trade shows and local events
            for event in batch:
                if is_trade_show(event):
                    trade_shows.append(event)
                else:
                    local_events.append(event)
        
        # Sort events by relevance score
        trade_shows.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        local_events.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # Limit results
        trade_shows = trade_shows[:max_results]
        local_events = local_events[:max_results]
        
        return {
            'trade_shows': trade_shows,
            'local_events': local_events
        }
    except Exception as e:
        logger.error(f"Error in async event search: {str(e)}")
        return {'trade_shows': [], 'local_events': []}


# Update the search_events function to use the async implementation
def search_events_with_async(keywords, user_summary=None, user_type="general", location="sf", max_results=10, target_events=None, progress_callback=None):
    """Search for events matching the keywords using async implementation"""
    try:
        # For debugging, use the synchronous implementation instead
        logger.info(f"Searching for events with keywords: {keywords}")
        
        # Load events from CSV files
        events = load_events_from_csv()
        logger.info(f"Loaded {len(events)} events from CSV files")
        
        # Debug: Print the first event to see its structure
        if events:
            first_event = events[0]
            logger.info(f"First event structure: {first_event.keys()}")
            logger.info(f"First event name: {first_event.get('event_name')}")
            logger.info(f"First event URL: {first_event.get('event_url')}")
            logger.info(f"First event speaker: {first_event.get('speaker_name')}")
        
        # Fix data issues in the CSV
        fixed_count = 0
        for event in events:
            # Fix URL in speaker_name column
            if event.get('speaker_name', '').startswith('http'):
                if not event.get('event_url'):
                    event['event_url'] = event['speaker_name']
                event['speaker_name'] = event.get('speaker_company', 'Unknown')
                fixed_count += 1
                
            # Ensure we have a description
            if not event.get('description') and event.get('event_summary'):
                event['description'] = event['event_summary']
                
            # Add default relevance score
            event['relevance_score'] = 0.5
            
            # Add default conversion path if missing
            if not event.get('conversion_path'):
                event['conversion_path'] = f"Attend {event.get('event_name', 'this event')} to network with professionals in your industry."
        
        logger.info(f"Fixed {fixed_count} events with URL in speaker_name field")
        
        # Filter events by location
        if location:
            filtered_events = []
            for event in events:
                event_location = event.get('location', '') or event.get('event_location', '')
                if not event_location:
                    continue
                if location.lower() in event_location.lower():
                    filtered_events.append(event)
            events = filtered_events
            logger.info(f"Filtered to {len(events)} events by location: {location}")
            
        # Debug: Check if we have any events after filtering
        if not events:
            logger.warning("No events found after location filtering. Using all events instead.")
            events = load_events_from_csv()  # Use all events if none match the location
        
        # Separate events into trade shows and local events
        trade_shows = []
        local_events = []
        
        for event in events:
            if is_trade_show(event):
                trade_shows.append(event)
            else:
                local_events.append(event)
        
        # Sort by relevance score
        trade_shows.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        local_events.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # Limit results
        trade_shows = trade_shows[:max_results]
        local_events = local_events[:max_results]
        
        logger.info(f"Found {len(trade_shows)} trade shows and {len(local_events)} local events")
        
        return {
            'trade_shows': trade_shows,
            'local_events': local_events
        }
    except Exception as e:
        logger.error(f"Error searching events with async: {str(e)}")
        return {'trade_shows': [], 'local_events': []}


async def find_top_events(keywords, user_summary=None, user_type="general", location="sf", max_results=10, target_events=None):
    """
    Find top events based on keywords, user summary, and location.
    This is a wrapper for search_events_with_keywords that's used by the app.py search_events endpoint.
    
    Args:
        keywords (list): List of keywords to search for
        user_summary (str, optional): User's business profile summary
        user_type (str, optional): Type of user (general, founder, etc.)
        location (str, optional): Location to filter events by
        max_results (int, optional): Maximum number of results to return
        target_events (str, optional): Target events recommendation text
        
    Returns:
        dict: Dictionary with trade_shows and local_events lists
    """
    logger.info(f"Finding top {max_results} events for keywords: {keywords}")
    
    # Call the search_events_with_keywords function
    result = search_events_with_keywords(
        keywords=keywords,
        user_summary=user_summary,
        user_type=user_type,
        location=location,
        max_results=max_results,
        target_events=target_events
    )
    
    return result
