"""
Module for extracting keywords from target events recommendations.
"""

import json
import re
import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def extract_keywords_from_target_events(target_events_text: str, question_engine) -> List[str]:
    """
    Extract relevant keywords from the target events recommendation.
    
    Args:
        target_events_text: The target events recommendation text
        question_engine: The question engine for generating with Gemini
        
    Returns:
        A list of keywords extracted from the target events text
    """
    try:
        # Use Gemini to extract keywords from the target events text
        prompt = f"""
        Extract the most relevant keywords for event search from the following target events recommendation. 
        Focus on specific event types, industries, and roles mentioned in the text.
        Return only a JSON array of exactly 15 keywords or short phrases, with no explanation.
        """
        
        response = await question_engine.generate_with_gemini(
            prompt=prompt,
            context=target_events_text,
            max_tokens=200
        )
        
        if response:
            # Try to parse the response as JSON
            try:
                # Clean up the response to extract just the JSON array
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    event_keywords = json.loads(json_str)
                    logger.info(f"Extracted {len(event_keywords)} keywords from target events: {event_keywords}")
                    return event_keywords
            except Exception as e:
                logger.error(f"Error parsing keywords from target events: {str(e)}")
        
        # Fallback: Extract words that might be event types or industries
        event_types = [
            "conference", "trade show", "meetup", "hackathon", "workshop", "summit", 
            "expo", "fair", "forum", "symposium", "seminar", "webinar", "pitch event"
        ]
        
        # Extract words that match event types
        event_keywords = []
        for event_type in event_types:
            if event_type in target_events_text.lower():
                event_keywords.append(event_type)
        
        # Add some industry-specific words if found
        words = re.findall(r'\b[A-Za-z][A-Za-z-]+\b', target_events_text)
        for word in words:
            if len(word) > 5 and word.lower() not in [w.lower() for w in event_keywords]:
                event_keywords.append(word.lower())
        
        # Limit to 15 keywords
        event_keywords = event_keywords[:15]
        logger.info(f"Extracted {len(event_keywords)} keywords using fallback method: {event_keywords}")
        return event_keywords
        
    except Exception as e:
        logger.error(f"Error extracting keywords from target events: {str(e)}")
        return []
