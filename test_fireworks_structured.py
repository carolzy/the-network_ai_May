import asyncio
import json
import logging
from core.flow_controller import FlowController
from event_search_agent import search_events_with_keywords
from app import search_tradeshows_with_gemini

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_fireworks_structured_data():
    """
    Test the structured data generation and event search for Fireworks.ai with specific goals.
    This simulates selecting "find buyers" and "find business partners" as primary goals.
    """
    # Create a flow controller instance with Fireworks.ai data
    flow_controller = FlowController()
    flow_controller.company_name = "Fireworks AI"
    flow_controller.website = "https://fireworks.ai"
    # Let the system generate the user_summary during the run
    
    # Set the goals - simulating user selection of "find buyers" and "find business partners"
    flow_controller.selected_goals = ["find_buyers", "business_partners"]
    flow_controller.primary_goal = "find_buyers"
    
    # Generate the target events recommendation
    logger.info("Generating target events recommendation for Fireworks.ai...")
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
        strategies = ui_data['event_strategies']
        # Check if the selected goals are present in the strategies
        for goal in flow_controller.selected_goals:
            if goal in strategies:
                logger.info(f"Found strategy for selected goal: {goal}")
            else:
                logger.warning(f"Missing strategy for selected goal: {goal}")
    
    # Check the business_profile field
    if 'business_profile' in ui_data:
        business_profile = ui_data['business_profile']
        logger.info(f"Business profile description: {business_profile.get('description', 'No description')[:100]}...")
    else:
        logger.warning("No business_profile found in UI data")
    
    # Now test the event search with the structured data
    logger.info("Testing event search with structured data...")
    
    # First, search for tradeshows
    logger.info("Searching for tradeshows...")
    # Extract keywords from the UI data
    keywords = []
    if 'who_to_target' in ui_data:
        for target in ui_data['who_to_target']:
            if 'group_title' in target:
                keywords.append(target['group_title'])
    
    # Extract specific events if available
    target_events = []
    if 'specific_events' in ui_data:
        for event in ui_data['specific_events']:
            if 'name' in event:
                target_events.append(event['name'])
    
    tradeshows = await search_tradeshows_with_gemini(
        user_summary=flow_controller.user_summary,
        keywords=keywords,
        target_events=target_events,
        product_url=flow_controller.website,
        event_data_json=ui_data  # Pass the structured data
    )
    
    logger.info(f"Found {len(tradeshows)} tradeshows with structured data")
    
    # Then, search for local events
    logger.info("Searching for local events...")
    # Use the same keywords and target_events as for tradeshows
    local_events = await search_events_with_keywords(
        keywords=keywords,
        user_summary=flow_controller.user_summary,
        user_type="founder",  # Assuming founder as default user type
        location="sf",  # Default location
        target_events=target_events,
        event_data_json=ui_data  # Pass the structured data
    )
    
    if local_events and 'events' in local_events:
        local_events_list = local_events['events']
        logger.info(f"Found {len(local_events_list)} local events with structured data")
        if local_events_list:
            logger.info(f"Sample local event: {local_events_list[0].get('name', 'Unknown')}")
    
    # Save the results to a file for inspection
    with open('fireworks_test_results.json', 'w') as f:
        json.dump({
            'ui_data': ui_data,
            'tradeshows': tradeshows,
            'local_events': local_events
        }, f, indent=2)
    
    return ui_data, tradeshows, local_events

if __name__ == "__main__":
    logger.info("Starting Fireworks.ai structured data test...")
    ui_data, tradeshows, local_events = asyncio.run(test_fireworks_structured_data())
    
    # Display detailed content of each structured data field
    logger.info("\n\n==== DETAILED STRUCTURED DATA CONTENT ====\n")
    
    # Multi-factor analysis
    logger.info("MULTI-FACTOR ANALYSIS:")
    if 'multi_factor_analysis' in ui_data:
        for key, value in ui_data['multi_factor_analysis'].items():
            logger.info(f"  {key}: {value[:100]}..." if isinstance(value, str) and len(value) > 100 else f"  {key}: {value}")
    logger.info("")
    
    # Key differentiators
    logger.info("KEY DIFFERENTIATORS:")
    if 'key_differentiators' in ui_data and ui_data['key_differentiators']:
        for diff in ui_data['key_differentiators']:
            logger.info(f"  {diff.get('icon', 'No icon')} {diff.get('text', 'No text')}")
    else:
        logger.info("  No title: No description...")
    logger.info("")
    
    # Target customers
    logger.info("TARGET CUSTOMERS:")
    if 'target_customers' in ui_data and ui_data['target_customers']:
        for customer in ui_data['target_customers']:
            logger.info(f"  {customer.get('company_name', 'No name')}: {customer.get('why_good_fit', 'No description')[:100]}...")
    else:
        logger.info("  No title: No description...")
    logger.info("")
    
    # Who to target
    logger.info("WHO TO TARGET:")
    if 'who_to_target' in ui_data and ui_data['who_to_target']:
        for target in ui_data['who_to_target']:
            logger.info(f"  {target.get('group_title', 'No title')}: {target.get('description', 'No description')[:100]}...")
    else:
        logger.info("  No title: No description...")
    logger.info("")
    
    # Event strategies
    logger.info("EVENT STRATEGIES:")
    if 'event_strategies' in ui_data:
        for goal, strategy in ui_data['event_strategies'].items():
            logger.info(f"  Strategy for {goal}:")
            logger.info(f"    goal_title: {strategy.get('goal_title', 'No title')}")
            logger.info(f"    goal_icon: {strategy.get('goal_icon', 'No icon')}")
            logger.info(f"    event_types: {strategy.get('event_types', [])}")
    logger.info("")
    
    # Specific events
    logger.info("SPECIFIC EVENTS:")
    if 'specific_events' in ui_data and ui_data['specific_events']:
        for event in ui_data['specific_events']:
            logger.info(f"  {event.get('name', 'No name')}: {event.get('description', 'No description')[:100]}...")
    else:
        logger.info("  No name: No description...")
    logger.info("")
    
    # Business profile
    logger.info("BUSINESS PROFILE:")
    if 'business_profile' in ui_data:
        logger.info(f"  {ui_data['business_profile']}")
    logger.info("")
    
    logger.info("Test completed. Results saved to fireworks_test_results.json")
    
    # Validate URLs in the results
    import httpx
    
    async def validate_urls():
        async with httpx.AsyncClient() as client:
            for tradeshow in tradeshows:
                if 'url' in tradeshow:
                    try:
                        response = await client.get(tradeshow['url'], follow_redirects=True)
                        logger.info(f"Validation of URL: {tradeshow['url']}, Status Code: {response.status_code}")
                    except Exception as e:
                        logger.error(f"Error validating URL {tradeshow['url']}: {str(e)}")
    
    asyncio.run(validate_urls())
