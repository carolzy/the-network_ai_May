"""
Find Events on Luma

This script uses Playwright and LangChain to automate the process of finding and extracting
information about events from Luma's event discovery platform. It can search for events based on
user intent, location, featured calendars, and categories.

The script uses a browser automation agent to:
1. Navigate to Luma's event discovery page
2. Search and filter events based on user criteria
3. Extract detailed information about events, speakers, and sponsors
4. Save the results in JSON format

Dependencies:
- playwright
- langchain_openai
- browser_use
- python-dotenv
"""

from dotenv import load_dotenv
import asyncio
import os
import sys
import json

from utils import print_agent_history
from langchain_openai import ChatOpenAI
from browser_use import Agent
from browser_use.browser import BrowserSession
from playwright.sync_api import sync_playwright
from prompts import event_task_prompt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


def find_events(
    user_intent: str,
    user_location: str = None,
    user_featured_calendars: str = None,
    user_category: str = None,
    output_file: str = 'results/event_results.json'
) -> None:
    """
    Search for events on Luma based on user criteria and save results to a JSON file.

    Args:
        user_intent (str): The user's search intent or interest
        user_location (str, optional): Location to search for events. Defaults to None.
        user_featured_calendars (str, optional): Featured calendar to filter by. Defaults to None.
        user_category (str, optional): Category to filter events by. Defaults to None.
        output_file (str, optional): Path to save the results. Defaults to 'results/event_results.json'.
    """
    # Initialize the model
    llm = ChatOpenAI(
        base_url="https://api.sambanova.ai/v1",
        api_key="042ca35c-beaf-4f5b-8033-9170556e5251",
        model='DeepSeek-V3-0324',
        temperature=0.0,
    )

    # Format the task with user parameters
    task = event_task_prompt.format(
        user_intent=user_intent,
        user_location=user_location if user_location else "",
        user_featured_calendars=user_featured_calendars if user_featured_calendars else "",
        user_category=user_category if user_category else ""
    )

    # Initialize the agent
    event_agent = Agent(
        task=task,
        llm=llm,
        use_vision=False,
        save_conversation_path="logs/conversation",
        initial_actions=[{'open_tab': {'url': "https://lu.ma/discover"}}],
    )

    async def run_agent():
        await event_agent.browser_session.start()
        history = await event_agent.run()
        
        # Ensure results directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Save results
        with open(output_file, 'w') as f:
            f.write(history.final_result())

    # Run the agent
    asyncio.run(run_agent())


if __name__ == '__main__':
    # Example usage
    find_events(
        user_intent="I want to find an event about AI, our company is focused on speech generation.",
        user_location=None,  # "San Francisco"
        user_featured_calendars=None,  # "AI"
        user_category=None,  # "AI"
    )
