#!/usr/bin/env python3
"""
Test script for tradeshow search with Gemini API
"""

import os
import json
import asyncio
import re
import traceback
import logging
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def search_tradeshows_with_gemini_test():
    """Test function for searching tradeshows with Gemini API"""
    # Mock user data
    user_type = "founder"
    user_summary = "AI startup founder working on voice technology and emotional intelligence. Looking for potential customers and investors."
    keywords = ['AI', 'machine learning', 'startup']
    location = "sf"
    
    # Load Gemini API key from environment
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    if not gemini_api_key:
        logger.error("No Gemini API key found in environment variables")
        return []
    
    # Construct the prompt
    prompt = f"""Search for most relevant **15** tradeshows leveraging websites such as 10times.com for this {user_type} at their company. The tradeshows MUST happen in the future, specifically from 2025 onwards (current year is 2025). DO NOT include any events from 2024 or earlier.

User profile: {user_summary}

Keywords: {', '.join(keywords)}

Location preference: {location}

For each tradeshow, provide the following information in a structured format:
- Event Title
- Event Date (must be in 2025 or later)
- Event Location
- Event Description: Provide at least 3 detailed sentences - 1-2 sentences about the event itself (history, scope, importance) and 1-2 sentences about why it's specifically relevant to the user's business
- Event Keywords
- Conversion Path: Provide a detailed, actionable 3-4 sentence strategy for how this user can best leverage this event to achieve their goals (e.g. find future buyers/business partners etc.)
- Event Official Website: MUST provide a valid website URL for each event. If you can't find the official website, provide the most relevant website related to the event or organization.
- Conversion Score (0-100): How well this event aligns with the user's goals

EVERY event MUST have a website URL - this is critical for the application.

Ensure the Event Title is clear and properly formatted as it will be highlighted in the UI.
Make sure the Event Description is insightful and specific to the user's business needs.

Return the results as a JSON array of objects, each with the above attributes.
"""

    # Call the Gemini API
    logger.info("Calling Gemini-2.0-flash API for tradeshow search...")
    try:
        logger.info(f"Using Gemini API key: {gemini_api_key[:8]}...")
        
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_api_key}"
        
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.2,  # Lower temperature for more consistent results
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 4096  # Increased token limit for comprehensive results
            },
            # Add structured output format to ensure we get properly formatted JSON
            "systemInstruction": {
                "parts": [{
                    "text": "You must respond with a valid JSON array of objects. Each object must have these fields: Event Title, Event Date, Event Location, Event Description, Event Keywords, Conversion Path, Event Official Website, Conversion Score."
                }]
            }
        }
        
        logger.info(f"Sending request to Gemini API with prompt length: {len(prompt)}")
        logger.info(f"Prompt preview: {prompt[:200]}...")
        logger.info(f"Using Gemini URL: {gemini_url[:70]}...")
        
        async with httpx.AsyncClient() as client:
            try:
                logger.info("Sending POST request to Gemini API...")
                api_response = await client.post(
                    gemini_url,
                    json=data,
                    timeout=60.0  # Increased timeout for longer responses
                )
                logger.info(f"POST request completed with status code: {api_response.status_code}")
            except Exception as e:
                logger.error(f"Exception during HTTP request: {str(e)}")
                raise
            
        logger.info(f"Received response from Gemini API with status code: {api_response.status_code}")
        
        if api_response.status_code == 200:
            result = api_response.json()
            if "candidates" in result and len(result["candidates"]) > 0:
                content = result["candidates"][0]["content"]
                if "parts" in content and len(content["parts"]) > 0:
                    response = content["parts"][0]["text"].strip()
                    logger.info(f"Successfully received response from gemini-2.0-flash, length: {len(response)}")
                    logger.info(f"Response preview: {response[:200]}...")
                else:
                    logger.error("No text parts found in Gemini response")
                    response = ""
            else:
                logger.error(f"No candidates found in Gemini response: {result}")
                response = ""
        else:
            logger.error(f"Error calling Gemini API: {api_response.status_code} - {api_response.text}")
            response = ""
    except Exception as e:
        logger.error(f"Exception calling Gemini API directly: {str(e)}")
        logger.error(traceback.format_exc())
        response = ""
    
    logger.info(f"Gemini response received, length: {len(response) if response else 0}")
    if response:
        logger.info(f"Gemini response preview: {response[:200]}...")
    else:
        logger.warning("Empty response received from Gemini API")
    
    # Parse the JSON response
    # First, try to find JSON in the response using regex
    logger.info("Attempting to parse JSON from Gemini response...")
    
    # Try direct JSON parsing first
    try:
        logger.info("Attempting direct JSON parsing...")
        tradeshows = json.loads(response)
        logger.info(f"Direct JSON parsing successful, found {len(tradeshows)} tradeshows")
        # Log the first tradeshow as an example
        if tradeshows:
            logger.info(f"Example tradeshow: {json.dumps(tradeshows[0], indent=2)[:200]}...")
        return tradeshows
    except json.JSONDecodeError:
        logger.warning("Direct JSON parsing failed, trying regex extraction...")
    
    # Improved regex pattern to better match JSON arrays
    json_pattern = r'\[\s*\{[^\[\]]*\}(?:\s*,\s*\{[^\[\]]*\})*\s*\]'
    json_match = re.search(json_pattern, response, re.DOTALL)
    
    tradeshows = []
    
    if json_match:
        logger.info("JSON pattern found in response")
        json_str = json_match.group(0)
        logger.info(f"Extracted JSON string (first 200 chars): {json_str[:200]}...")
        try:
            tradeshows = json.loads(json_str)
            logger.info(f"Successfully parsed JSON, found {len(tradeshows)} tradeshows")
            # Log the first tradeshow as an example
            if tradeshows:
                logger.info(f"Example tradeshow: {json.dumps(tradeshows[0], indent=2)[:200]}...")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON: {str(e)}")
            logger.error(f"Problematic JSON string: {json_str[:500]}...")
            # Will use fallback data below
    else:
        # If no JSON array found, try to extract structured data manually
        logger.warning("Could not find JSON array in Gemini response, attempting manual parsing")
        event_blocks = re.split(r'\n\s*\d+\.\s*', response)
        if len(event_blocks) > 1:
            # Skip the first element as it's usually just preamble text
            event_blocks = event_blocks[1:]
            logger.info(f"Manual parsing found {len(event_blocks)} potential event blocks")
            
            # Print the full response for debugging
            logger.info("Full response for debugging:")
            logger.info(response)
            
            # Print the first event block for debugging
            if event_blocks:
                logger.info("First event block:")
                logger.info(event_blocks[0])
        else:
            logger.warning("No event blocks found in manual parsing")
    
    return tradeshows

async def main():
    tradeshows = await search_tradeshows_with_gemini_test()
    print(f"Found {len(tradeshows)} tradeshows")
    if tradeshows:
        print("First tradeshow:")
        print(json.dumps(tradeshows[0], indent=2))

if __name__ == "__main__":
    asyncio.run(main())
