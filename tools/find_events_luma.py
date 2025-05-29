"""
Find Events on Luma - Legacy Interface
This module provides backward compatibility for the old event search interface.
New code should use event_search.py directly.

DEPRECATED: This module is maintained for backward compatibility only.
Please use event_search.py and the EventSearch class directly for new code.
"""

import os
import json
import asyncio
import warnings
from event_search import EventSearch


def find_events(
    llm=None,  # Kept for backward compatibility
    user_intent: str = None,
    user_location: str = None,
    user_featured_calendars: str = None,
    user_category: str = None,
    output_file: str = 'results/event_results.json'
) -> None:
    """
    Search for events on Luma based on user criteria and save results to a JSON file.
    This is a legacy interface that uses the new EventSearch class internally.

    DEPRECATED: This function is maintained for backward compatibility only.
    Please use event_search.py and the EventSearch class directly for new code.

    Args:
        llm: Ignored, kept for backward compatibility
        user_intent (str): The user's search intent or interest
        user_location (str, optional): Location to search for events.
            Defaults to None.
        user_featured_calendars (str, optional): Featured calendar to filter by.
            Defaults to None.
        user_category (str, optional): Category to filter events by.
            Defaults to None.
        output_file (str, optional): Path to save the results.
            Defaults to 'results/event_results.json'.
    """
    warnings.warn(
        "find_events() is deprecated. Please use event_search.py and the "
        "EventSearch class directly for new code.",
        DeprecationWarning,
        stacklevel=2
    )

    if not user_intent:
        raise ValueError("user_intent is required")

    # Initialize the new EventSearch class
    api_key = os.getenv(
        "OPENAI_API_KEY",
        "042ca35c-beaf-4f5b-8033-9170556e5251"
    )
    event_search = EventSearch(api_key)

    async def run_search():
        # Use the new search_events method
        events = await event_search.search_events(
            query=user_intent,
            location=user_location,
            category=user_category,
            max_results=5
        )

        # Ensure results directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Save results to file
        with open(output_file, 'w') as f:
            json.dump([event.dict() for event in events], f, indent=2)

        # Print results
        for event in events:
            print(f"\nEvent: {event.title}")
            print(f"Date: {event.date}")
            print(f"Location: {event.location}")
            print(f"URL: {event.url}")
            if event.speakers:
                print("\nSpeakers:")
                for speaker in event.speakers:
                    print(
                        f"- {speaker['name']} "
                        f"({speaker['title']} at {speaker['company']})"
                    )

    # Run the search
    asyncio.run(run_search())
