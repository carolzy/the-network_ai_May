#!/usr/bin/env python3
import asyncio
import json
import logging
from core.flow_controller import FlowController
from event_search_agent import search_events_with_keywords
from app import search_tradeshows_with_gemini

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_elevenlabs_structured_data():
    """
    Test the structured data generation and event search for ElevenLabs with specific goals.
    This simulates selecting "find buyers" and "find business partners" as primary goals.
    """
    # Create a flow controller instance with ElevenLabs data
    flow_controller = FlowController()
    flow_controller.company_name = "ElevenLabs"
    flow_controller.website = "elevenlabs.io"
    # Let the system generate the user_summary during the run
    
    # Set the goals - simulating user selection of "find buyers" and "find business partners"
    flow_controller.selected_goals = ["find_buyers", "business_partners"]
    flow_controller.primary_goal = "find_buyers"
    
    # Generate the target events recommendation
    logger.info("Generating target events recommendation for ElevenLabs...")
    ui_data = await flow_controller.generate_target_events_recommendation()
    
    # Log the structure to verify all required fields are present
    logger.info(f"Generated UI data structure keys: {list(ui_data.keys())}")
    
    # Verify the required structured fields exist
    required_fields = [
        'multi_factor_analysis', 
        'key_differentiators', 
        'target_customers', 
        'who_to_target', 
        'event_strategies', 
        'specific_events'
    ]
    
    missing_fields = [field for field in required_fields if field not in ui_data]
    if missing_fields:
        logger.error(f"Missing required fields in UI data: {missing_fields}")
    else:
        logger.info("All required structured fields are present in the UI data")
    
    # Check the event_strategies field specifically
    if 'event_strategies' in ui_data:
        logger.info(f"Event strategies keys: {list(ui_data['event_strategies'].keys())}")
        
        # Check if our selected goals are in the event strategies
        for goal in flow_controller.selected_goals:
            if goal in ui_data['event_strategies']:
                logger.info(f"Goal '{goal}' found in event strategies")
            else:
                logger.error(f"Goal '{goal}' NOT found in event strategies")
    
    # Check the who_to_target field
    if 'who_to_target' in ui_data and isinstance(ui_data['who_to_target'], list):
        logger.info(f"Number of target groups: {len(ui_data['who_to_target'])}")
        for i, target in enumerate(ui_data['who_to_target']):
            if isinstance(target, dict):
                logger.info(f"Target group {i+1}: {target.get('group_title', 'No title')}")
    
    # Now test the event search with the structured data
    logger.info("Testing event search with structured data...")
    
    # Extract keywords from the UI data
    keywords = []
    if 'keywords' in ui_data and isinstance(ui_data['keywords'], list):
        keywords = [k.get('text') if isinstance(k, dict) else k for k in ui_data['keywords']]
    
    # Search for tradeshows using the structured data
    tradeshows = await search_tradeshows_with_gemini(
        user_summary=flow_controller.user_summary,
        keywords=keywords[:10],  # Use first 10 keywords
        target_events="",  # Not using legacy text
        product_url="elevenlabs.io",
        event_data_json=ui_data  # Pass the structured data
    )
    
    logger.info(f"Found {len(tradeshows)} tradeshows with structured data")
    if tradeshows:
        logger.info(f"Sample tradeshow: {tradeshows[0].get('event_name', 'Unknown')}")
    
    # Search for local events using the structured data
    local_events = await search_events_with_keywords(
        keywords=keywords[:10],
        user_summary=flow_controller.user_summary,
        user_type="founder",
        location="sf",
        max_results=10,
        target_events="",
        event_data_json=ui_data  # Pass the structured data
    )
    
    # Handle local_events which might be a dict with 'local_events' key
    if isinstance(local_events, dict) and 'local_events' in local_events:
        local_events_list = local_events['local_events']
        logger.info(f"Found {len(local_events_list)} local events with structured data")
        if local_events_list and len(local_events_list) > 0:
            logger.info(f"Sample local event: {local_events_list[0].get('event_name', 'Unknown')}")
    else:
        logger.info(f"Local events structure: {type(local_events)}")
        logger.info(f"Local events data: {local_events}")
    
    # Print a summary of the test results
    logger.info("\nTest Summary:")
    logger.info(f"- UI data generated: {'Yes' if ui_data else 'No'}")
    logger.info(f"- All required fields present: {'Yes' if not missing_fields else 'No'}")
    logger.info(f"- Selected goals found in event strategies: {'Yes' if all(goal in ui_data.get('event_strategies', {}) for goal in flow_controller.selected_goals) else 'No'}")
    logger.info(f"- Tradeshows found: {len(tradeshows)}")
    logger.info(f"- Local events found: {len(local_events)}")
    
    return ui_data, tradeshows, local_events

if __name__ == "__main__":
    logger.info("Starting ElevenLabs structured data test...")
    ui_data, tradeshows, local_events = asyncio.run(test_elevenlabs_structured_data())
    
    # Display detailed content of each structured data field
    logger.info("\n\n==== DETAILED STRUCTURED DATA CONTENT ====\n")
    
    # Multi-factor analysis
    if 'multi_factor_analysis' in ui_data:
        logger.info("MULTI-FACTOR ANALYSIS:")
        for key, value in ui_data['multi_factor_analysis'].items():
            logger.info(f"  {key}: {value[:200]}..." if isinstance(value, str) and len(value) > 200 else f"  {key}: {value}")
    
    # Key differentiators
    if 'key_differentiators' in ui_data:
        logger.info("\nKEY DIFFERENTIATORS:")
        for diff in ui_data['key_differentiators']:
            if isinstance(diff, dict):
                logger.info(f"  {diff.get('title', 'No title')}: {diff.get('description', 'No description')[:150]}...")
            else:
                logger.info(f"  {diff}")
    
    # Target customers
    if 'target_customers' in ui_data:
        logger.info("\nTARGET CUSTOMERS:")
        for customer in ui_data['target_customers']:
            if isinstance(customer, dict):
                logger.info(f"  {customer.get('title', 'No title')}: {customer.get('description', 'No description')[:150]}...")
            else:
                logger.info(f"  {customer}")
    
    # Who to target
    if 'who_to_target' in ui_data:
        logger.info("\nWHO TO TARGET:")
        for target in ui_data['who_to_target']:
            if isinstance(target, dict):
                logger.info(f"  {target.get('group_title', 'No title')}: {target.get('group_description', 'No description')[:150]}...")
            else:
                logger.info(f"  {target}")
    
    # Event strategies
    if 'event_strategies' in ui_data:
        logger.info("\nEVENT STRATEGIES:")
        for strategy_key, strategy_value in ui_data['event_strategies'].items():
            logger.info(f"  Strategy for {strategy_key}:")
            if isinstance(strategy_value, dict):
                for k, v in strategy_value.items():
                    logger.info(f"    {k}: {v[:150]}..." if isinstance(v, str) and len(v) > 150 else f"    {k}: {v}")
            else:
                logger.info(f"    {strategy_value}")
    
    # Specific events
    if 'specific_events' in ui_data:
        logger.info("\nSPECIFIC EVENTS:")
        for event in ui_data['specific_events']:
            if isinstance(event, dict):
                logger.info(f"  {event.get('event_name', 'No name')}: {event.get('event_description', 'No description')[:150]}...")
            else:
                logger.info(f"  {event}")
    
    # Business profile
    if 'business_profile' in ui_data:
        logger.info("\nBUSINESS PROFILE:")
        logger.info(f"  {ui_data['business_profile'][:200]}..." if len(ui_data['business_profile']) > 200 else f"  {ui_data['business_profile']}")
    
    # Save the results to a file for inspection
    with open("elevenlabs_test_results.json", "w") as f:
        json.dump({
            "ui_data": ui_data,
            "tradeshows_count": len(tradeshows) if isinstance(tradeshows, list) else 0,
            "local_events": local_events if isinstance(local_events, list) else {}
        }, f, indent=2)
    
    logger.info("\nTest completed. Results saved to elevenlabs_test_results.json")
