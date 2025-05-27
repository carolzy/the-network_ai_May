"""
Find Events on Luma
"""

from dotenv import load_dotenv
import asyncio
import os
import sys
import json
from pydantic import SecretStr
from utils import print_agent_history
from langchain_openai import ChatOpenAI
from browser_use import Agent
from browser_use.browser import BrowserSession, BrowserProfile
from playwright.sync_api import sync_playwright

# Different prompts for experiment
from prompts import event_task_prompt as event_task_prompt
# from prompts import simple_event_task_prompt as event_task_prompt
from utils import test_openai_connection

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

os.environ["OPENAI_API_KEY"] = "042ca35c-beaf-4f5b-8033-9170556e5251"


def init_llm():
    browser_profile = BrowserProfile(
        # NOTE: you need to close your chrome browser - so that this can open your browser in debug mode
        executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        user_data_dir='~/.config/browseruse/profiles/default',
        headless=False,
    )
    browser_session = BrowserSession(browser_profile=browser_profile)

    # Initialize the model
    llm = ChatOpenAI(
        base_url="https://api.sambanova.ai/v1",
        api_key=SecretStr("042ca35c-beaf-4f5b-8033-9170556e5251"),
        model='DeepSeek-V3-0324',
        # model='DeepSeek-R1',
        # model='Llama-4-Maverick-17B-128E-Instruct',
        # browser_session=browser_session,
        temperature=0.0,
    )

    return llm


def find_events(
    llm,
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

    # Format the task with user parameters
    # task = event_task_prompt.format(
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
        save_conversation_path="logs/conversation",  # For debugging only.
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

        # await event_agent.browser_session.close()
    # Run the agent
    asyncio.run(run_agent())


if __name__ == '__main__':
    # Test if the LLM is working correctly
    # test_openai_connection()

    llm = init_llm()
    # Example usage
    find_events(
        llm,
        user_intent="I want to find an event about AI, our company is focused on speech generation.",
        user_location=None,  # "San Francisco"
        user_featured_calendars=None,  # "AI"
        user_category=None,  # "AI"
    )
