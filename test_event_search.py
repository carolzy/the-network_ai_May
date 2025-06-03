import asyncio
import json
import logging
from dotenv import load_dotenv
from core.flow_controller import FlowController
from event_search_agent import search_events_with_keywords
from app import search_tradeshows_with_gemini

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_event_search_with_structured_data():
    """Test event search with structured data for ElevenLabs"""
    
    # Load environment variables
    load_dotenv()
    
    # Sample business profile for ElevenLabs
    business_profile = """
    ElevenLabs is a leading voice AI company that specializes in creating realistic and emotionally expressive 
    synthetic voices for content creators, publishers, and entertainment companies. Their technology enables 
    users to clone voices, generate natural-sounding speech in multiple languages, and create voice content 
    at scale. ElevenLabs offers a platform that allows users to convert text to speech with customizable 
    voices that maintain human-like quality and emotional range.
    """
    
    # Sample keywords
    keywords = ["voice AI", "synthetic voices", "text-to-speech", "AI voices", "voice cloning", 
                "content creation", "audio generation", "speech synthesis"]
    
    # Sample structured event data JSON
    event_data_json = {
        "business_profile": {
            "company_name": "ElevenLabs",
            "industry": "Voice AI Technology",
            "product_description": "AI-powered voice synthesis platform"
        },
        "multi_factor_analysis": {
            "unique_value_proposition": "Highly realistic and emotionally expressive AI voices",
            "market_position": "Leading provider in the voice AI space"
        },
        "key_differentiators": [
            "Superior voice quality with emotional range",
            "Multilingual capabilities",
            "Voice cloning technology",
            "API for developers"
        ],
        "target_customers": [
            {
                "industry": "Media & Entertainment",
                "company_name": "Netflix, Spotify, YouTube creators",
                "size": "Large enterprises and individual creators",
                "why_good_fit": "Need high-quality voices for content production"
            },
            {
                "industry": "Publishing",
                "company_name": "Audiobook publishers",
                "size": "Medium to large",
                "why_good_fit": "Require realistic voices for audiobook narration"
            },
            {
                "industry": "Gaming",
                "company_name": "Game development studios",
                "size": "All sizes",
                "why_good_fit": "Need diverse character voices for games"
            }
        ],
        "who_to_target": [
            {
                "group_title": "Content Creators",
                "group_detail": "YouTube creators, podcasters, and digital storytellers who need to scale voice content"
            },
            {
                "group_title": "Media Production Companies",
                "group_detail": "Film studios, animation studios, and audio production houses looking for efficient voice solutions"
            },
            {
                "group_title": "Software Developers",
                "group_detail": "Developers integrating voice capabilities into applications and platforms"
            }
        ],
        "event_strategies": {
            "lead_generation": {
                "goal_title": "Generate qualified leads from content creation industry",
                "event_types": [
                    {
                        "type_title": "Industry conferences",
                        "why_works": "Direct access to decision-makers in media and entertainment"
                    },
                    {
                        "type_title": "Technology expos",
                        "why_works": "Showcase voice technology to potential enterprise clients"
                    }
                ]
            },
            "partnership_building": {
                "goal_title": "Form strategic partnerships with content platforms",
                "event_types": [
                    {
                        "type_title": "Media tech summits",
                        "why_works": "Connect with platform executives looking for voice innovation"
                    }
                ]
            },
            "brand_awareness": {
                "goal_title": "Increase brand visibility in AI and creative tech space",
                "event_types": [
                    {
                        "type_title": "AI conferences",
                        "why_works": "Position as thought leader in voice AI"
                    },
                    {
                        "type_title": "Creator conventions",
                        "why_works": "Direct exposure to end users of voice technology"
                    }
                ]
            }
        },
        "specific_events": [
            "NAB Show",
            "CES",
            "SXSW",
            "Game Developers Conference",
            "AI Summit",
            "VidCon",
            "Podcast Movement"
        ]
    }
    
    # Create a raw text version for backward compatibility testing
    target_events_text = """
    Goals: Generate qualified leads, form strategic partnerships, increase brand awareness
    
    Target Events:
    1. NAB Show - Major broadcasting event to connect with media companies
    2. CES - Technology showcase to demonstrate voice AI innovations
    3. SXSW - Creative industries event to reach content creators
    4. Game Developers Conference - Connect with game studios needing voice actors
    5. AI Summit - Position as thought leader in AI voice technology
    6. VidCon - Direct access to YouTube creators and digital content producers
    7. Podcast Movement - Reach podcasters who need voice solutions
    """
    
    logger.info("Testing search_tradeshows_with_gemini with structured data...")
    
    # Test search_tradeshows_with_gemini with structured data
    tradeshows_with_structured = await search_tradeshows_with_gemini(
        user_summary=business_profile,
        keywords=keywords,
        target_events=target_events_text,
        product_url="https://elevenlabs.io",
        user_type="founder",
        location="sf",
        event_data_json=event_data_json
    )
    
    logger.info(f"Found {len(tradeshows_with_structured)} tradeshows with structured data")
    
    # Test search_events_with_keywords with structured data
    logger.info("Testing search_events_with_keywords with structured data...")
    local_events_result = await search_events_with_keywords(
        keywords=keywords,
        location="sf bay area",
        user_summary=business_profile,
        target_events=target_events_text,
        event_data_json=event_data_json
    )
    
    local_events = local_events_result.get('local_events', [])
    logger.info(f"Found {len(local_events)} local events with structured data")
    
    # Print sample results
    if tradeshows_with_structured:
        logger.info("\nSample Tradeshow Result:")
        sample_tradeshow = tradeshows_with_structured[0]
        logger.info(f"Title: {sample_tradeshow.get('title', 'Unknown')}")
        logger.info(f"Date: {sample_tradeshow.get('date', 'Unknown')}")
        logger.info(f"Location: {sample_tradeshow.get('location', 'Unknown')}")
        logger.info(f"Conversion Score: {sample_tradeshow.get('conversion_score', 'Unknown')}")
        logger.info(f"Website: {sample_tradeshow.get('website', 'Unknown')}")
    
    if local_events:
        logger.info("\nSample Local Event Result:")
        sample_event = local_events[0]
        logger.info(f"Name: {sample_event.get('name', 'Unknown')}")
        logger.info(f"Date: {sample_event.get('date', 'Unknown')}")
        logger.info(f"Location: {sample_event.get('location', 'Unknown')}")
        logger.info(f"Conversion Score: {sample_event.get('conversion_score', 'Unknown')}")
        logger.info(f"URL: {sample_event.get('url', 'Unknown')}")
    
    logger.info("\nTest completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_event_search_with_structured_data())
