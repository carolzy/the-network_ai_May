import logging
import time
import random
import os
import json
import uuid
import logging
import asyncio
import queue
import traceback
import re
import httpx
import urllib.parse
from pathlib import Path
from functools import partial
from quart import Quart, render_template, request, jsonify, send_file, Response, redirect, url_for
from core.flow_controller import FlowController
from core.question_engine import QuestionEngine
from dotenv import load_dotenv
import sys

# Import the website analyzer
from core.website_analyzer import analyze_website, analyze_website_with_browser as browser_analyze_website

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s',
                    handlers=[
                        logging.FileHandler("app.log"),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

# Create Quart app
app = Quart(__name__, static_folder="static", template_folder="templates")
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Add CORS headers to all responses
@app.after_request
async def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

# Version for cache busting
VERSION = str(int(time.time()))

# Initialize the flow controller
flow_controller = FlowController.get_instance()

# Initialize core components
question_engine = QuestionEngine()

@app.route("/")
async def index():
    # Simply use await directly
    await flow_controller.reset()
    return await render_template("user_type_selection.html", version=VERSION)

@app.route("/founder")
async def founder_flow():
    # Set user type to founder and reset flow
    flow_controller.user_type = "founder"
    await flow_controller.reset()
    question = await flow_controller.get_question("product")
    return await render_template("product_question.html", question=question, version=VERSION)

@app.route("/vc")
async def vc_flow():
    # Set user type to VC and reset flow
    flow_controller.user_type = "vc"
    await flow_controller.reset()
    greeting = "Something magic is brewing!"
    first_question = "Something magic is brewing!"
    initial_step = "vc_sector_focus"
    return await render_template("index.html", greeting=greeting, first_question=first_question, initial_step=initial_step, version=VERSION)

@app.route("/event_goal_question")
async def event_goal_question():
    # Render the event goal question page
    return await render_template("event_goal_question.html", version=VERSION)

@app.route("/business_profile", methods=["GET", "POST"])
async def business_profile():
    # Check if this is a form submission from event_goal_question
    if request.method == "POST":
        try:
            form = await request.form
            logger.info(f"Received form submission to business_profile: {list(form.keys())}")
            logger.info(f"Full form data: {dict(form)}")
            
            # Process the form data
            step = form.get("step")
            answer = form.get("answer", "")
            action = form.get("action", "")
            
            logger.info(f"Form data - step: {step}, action: {action}")
            logger.info(f"Form data - answer: {answer}")
            
            if step == "event_interests":
                # Validate that at least one goal is selected
                try:
                    selected_goals = json.loads(answer) if answer else []
                    if not selected_goals:
                        logger.warning("No goals selected in form submission")
                        # Redirect back to event_goal_question page
                        return redirect("/event_goal_question")
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing selected goals JSON: {answer}")
                    logger.error(f"JSON decode error: {str(e)}")
                    # Redirect back to event_goal_question page
                    return redirect("/event_goal_question")
                
                # Store the answer in the flow controller
                await flow_controller.store_answer(step, answer)
                
                # Process the primary goal if provided
                primary_goal = form.get("primary_goal", "")
                logger.info(f"Form data - primary_goal: {primary_goal}")
                
                if primary_goal:
                    logger.info(f"Setting primary goal: {primary_goal}")
                    flow_controller.primary_goal = primary_goal
                else:
                    logger.warning("No primary goal provided in form")
                    
                # Force the primary goal to be set if it's not already
                if not flow_controller.primary_goal and flow_controller.selected_goals:
                    flow_controller.primary_goal = flow_controller.selected_goals[0]
                    logger.info(f"Forcing primary goal to first selected goal: {flow_controller.primary_goal}")
                    
                # Additional validation: Ensure the primary goal is one of the selected goals
                if flow_controller.primary_goal and flow_controller.primary_goal not in flow_controller.selected_goals:
                    logger.warning(f"Primary goal '{flow_controller.primary_goal}' not in selected goals. Adding it.")
                    flow_controller.selected_goals.append(flow_controller.primary_goal)
                
                # Log final state
                logger.info(f"Final state after processing:")
                logger.info(f"  - Selected goals: {flow_controller.selected_goals}")
                logger.info(f"  - Primary goal: {flow_controller.primary_goal}")
                logger.info(f"  - Buyer focus: {flow_controller.buyer_focus}")
                logger.info(f"  - Recruitment focus: {flow_controller.recruitment_focus}")
                    
        except Exception as e:
            logger.error(f"Error processing form submission: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    # Get the business profile, target events, and keywords from the flow controller
    business_profile = flow_controller.user_summary or "No business profile available."
    product_url = flow_controller.current_product_line if flow_controller.current_product_line.startswith("http") else ""
    
    # Log the current state of the flow controller
    logger.info(f"Business profile route - User summary: {len(business_profile) if business_profile else 0} chars")
    logger.info(f"Business profile route - Keywords: {flow_controller.keywords}")
    logger.info(f"Business profile route - Selected goals: {flow_controller.selected_goals if hasattr(flow_controller, 'selected_goals') else []}")
    logger.info(f"Business profile route - Primary goal: {flow_controller.primary_goal if hasattr(flow_controller, 'primary_goal') else 'None'}")
    
    # Generate target events recommendation based on business profile and goals
    target_events = await flow_controller.generate_target_events_recommendation()
    logger.info(f"Generated target events: {len(target_events) if target_events else 0} chars")
    
    # Store the target events text in the flow controller
    flow_controller.target_events_text = target_events
    
    # Also save to the database if we have a product URL
    if product_url:
        from target_events_db import save_target_events
        save_target_events(product_url, business_profile, flow_controller.keywords, target_events)
    
    # Extract keywords from target events and update the flow_controller keywords
    from target_events_keywords import extract_keywords_from_target_events
    if target_events and len(target_events) > 50:
        event_keywords = await extract_keywords_from_target_events(target_events, flow_controller.question_engine)
        
        # Merge with existing keywords, prioritizing event keywords
        if event_keywords:
            # Keep some of the existing keywords if they exist
            existing_keywords = flow_controller.keywords[:5] if flow_controller.keywords else []
            
            # Combine event keywords with existing keywords, removing duplicates
            combined_keywords = []
            for keyword in event_keywords:
                if keyword.lower() not in [k.lower() for k in combined_keywords]:
                    combined_keywords.append(keyword)
            
            for keyword in existing_keywords:
                if keyword.lower() not in [k.lower() for k in combined_keywords]:
                    combined_keywords.append(keyword)
            
            # Update the keywords list
            flow_controller.keywords = combined_keywords[:15]  # Limit to 15 keywords
            logger.info(f"Updated keywords with target events keywords: {flow_controller.keywords}")
    
    # Get keywords - ensure we have some default keywords if none are available
    keywords = flow_controller.keywords
    if not keywords or len(keywords) == 0:
        keywords = ["networking", "events", "business"]
        flow_controller.keywords = keywords
    
    # Get location information if available
    location = flow_controller.zip_code or ""
    
    # Prepare for event search
    auto_search = True
    
    # Render the business_profile_events_fixed.html template with the current context
    return await render_template(
        "business_profile_events_fixed.html",
        user_summary=business_profile,
        target_events=target_events,
        keywords=keywords,
        location=location,
        auto_search=auto_search,
        product_url=product_url,
        version=VERSION
    )

@app.route("/business_profile_with_events")
async def business_profile_with_events():
    # Get the business profile from the flow controller
    business_profile = flow_controller.user_summary or "No business profile available."
    keywords = flow_controller.keywords
    target_events = await flow_controller.generate_target_events_recommendation() if not hasattr(flow_controller, 'target_events') else flow_controller.target_events
    primary_goal = flow_controller.primary_goal if hasattr(flow_controller, 'primary_goal') else ""
    product_url = flow_controller.current_product_line if hasattr(flow_controller, 'current_product_line') and flow_controller.current_product_line.startswith("http") else ""
    location = flow_controller.zip_code or "sf bay area"  # Default location
    
    # Search for both tradeshows and local events in parallel
    tradeshows = []
    local_events = []
    
    # Create tasks for parallel execution
    tasks = []
    
    # Task 1: Get tradeshows from Gemini API
    async def get_tradeshows():
        try:
            if business_profile and keywords:
                logger.info("Attempting to get tradeshows from Gemini API...")
                gemini_tradeshows = await search_tradeshows_with_gemini(
                    user_summary=business_profile,
                    keywords=keywords,
                    target_events=target_events,
                    product_url=product_url
                )
                logger.info(f"Found {len(gemini_tradeshows)} tradeshows using Gemini-2.0-flash")
                
                # Format tradeshows to match the expected structure in the template
                formatted_tradeshows = []
                for show in gemini_tradeshows:
                    formatted_show = {
                        'id': f"gemini-{hash(show.get('title', ''))}" if 'title' in show else f"gemini-{len(formatted_tradeshows)}",
                        'name': show.get('title', 'Unknown Event'),
                        'description': show.get('conversion_path', ''),
                        'url': show.get('website', ''),
                        'business_value_score': show.get('conversion_score', 0),  # Match expected field name
                        'score': show.get('conversion_score', 0),  # Provide both for compatibility
                        'highlight': show.get('keywords', ''),
                        'date': show.get('date', 'Upcoming'),  # Use provided date or default
                        'location': show.get('location', 'Various locations'),  # Use provided location or default
                        'is_tradeshow': True
                    }
                    formatted_tradeshows.append(formatted_show)
                
                return formatted_tradeshows
            return []
        except Exception as e:
            logger.error(f"Error searching tradeshows with Gemini: {str(e)}")
            return []
    
    # Task 2: Get local events from CSV
    async def get_local_events():
        try:
            logger.info("Searching for local events from Luma CSV...")
            from event_search_agent import search_events_with_keywords
            
            result = await search_events_with_keywords(
                keywords=keywords,
                location=location,
                user_summary=business_profile,
                target_events=target_events
            )
            
            # Extract local events from the result
            return result.get('local_events', [])
        except Exception as e:
            logger.error(f"Error searching local events: {str(e)}")
            return []
    
    # Add tasks to the list
    tasks.append(asyncio.create_task(get_tradeshows()))
    tasks.append(asyncio.create_task(get_local_events()))
    
    # Wait for both tasks to complete
    results = await asyncio.gather(*tasks)
    
    # Extract results
    tradeshows_from_gemini = results[0]
    local_events_from_csv = results[1]
    
    # Use the results from Gemini API
    tradeshows = tradeshows_from_gemini
    logger.info(f"Using {len(tradeshows)} tradeshows from Gemini API")
    
    # Use local events from CSV
    local_events = local_events_from_csv
    logger.info(f"Using {len(local_events)} local events from Luma CSV")
    
    # Validate all events (both tradeshows and local events)
    from event_search_agent import validate_event_async
    
    # Combine all events for validation
    all_events = tradeshows + local_events
    logger.info(f"Validating {len(all_events)} total events...")
    
    # Validate events in parallel
    validation_tasks = [validate_event_async(event) for event in all_events]
    validation_results = await asyncio.gather(*validation_tasks)
    
    # Filter out invalid events
    valid_events = [event for event, is_valid in zip(all_events, validation_results) if is_valid]
    logger.info(f"After validation: {len(valid_events)} valid events out of {len(all_events)} total")
    
    # Separate valid events back into tradeshows and local events
    from event_search_agent import is_trade_show
    tradeshows = [event for event in valid_events if event.get('is_tradeshow', False) or is_trade_show(event)]
    local_events = [event for event in valid_events if not (event.get('is_tradeshow', False) or is_trade_show(event))]
    
    logger.info(f"Final count: {len(tradeshows)} valid tradeshows, {len(local_events)} valid local events")
    
    # Keep top 10 tradeshows and top 10 local events separately (no combining)
    max_tradeshows = 10
    max_local_events = 10
    
    # Take the top 10 from each category
    top_tradeshows = tradeshows[:max_tradeshows] if len(tradeshows) > max_tradeshows else tradeshows
    top_local_events = local_events[:max_local_events] if len(local_events) > max_local_events else local_events
    
    logger.info(f"Final results: {len(top_tradeshows)} tradeshows and {len(top_local_events)} local events")
    
    # Pass both tradeshows and local events to the template in the format expected by the template
    return await render_template(
        'business_profile_events_fixed.html',  # Using our fixed template
        user_summary=business_profile,
        keywords=keywords,
        target_events=target_events,
        trade_shows=top_tradeshows,  # Changed to match template's expected format with underscore
        local_events=top_local_events,
        primary_goal=primary_goal,
        product_url=product_url,
        location=location,
        version=VERSION
    )



@app.route("/follow_up_question/<step>")
async def follow_up_question(step):
    # Get the follow-up question based on the step
    question = await flow_controller.get_question(step)
    
    # Render the follow-up question page
    return await render_template("follow_up_question.html", question=question, step=step, version=VERSION)

@app.route("/search/events", methods=['GET','POST'])
async def event_search():
    # Render the event search page with the chat interface and keyword generator
    await flow_controller.reset()

    # Get parameters from either form data or URL query parameters
    summary = None
    keywords = None
    location = None
    target_events = None
    product_url = None
    use_gemini = request.args.get('use_gemini', 'false').lower() == 'true'
    
    if request.method == 'POST':
        form = await request.form
        summary = form.get('summary')
        keywords = form.get('keywords')
        location = form.get('location')
        target_events = form.get('target_events')
        product_url = form.get('product_url')
        use_gemini = form.get('use_gemini', 'false').lower() == 'true'
    else:  # GET method
        summary = request.args.get('summary')
        keywords = request.args.get('keywords')
        location = request.args.get('location')
        target_events = request.args.get('target_events')
        product_url = request.args.get('product_url')

    # Ensure keywords is a list
    if keywords is None:
        keywords = []
    elif isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(',') if k.strip()]
    
    # Ensure summary is a string
    if summary is None:
        summary = ""
    
    # If target_events is not provided but we have a summary, try to get it from the flow controller
    if target_events is None and summary:
        try:
            # Store the summary in the flow controller temporarily
            flow_controller.user_summary = summary
            # Generate target events based on the summary
            target_events = await flow_controller.generate_target_events_recommendation()
        except Exception as e:
            logger.error(f"Error generating target events: {str(e)}")
            target_events = ""
    
    logger.info(f"Event search with summary: {summary[:50]}... and keywords: {keywords}")
    
    # If use_gemini is true, search for tradeshows using Gemini-2.0-flash
    tradeshows = []
    if use_gemini and summary and keywords:
        try:
            tradeshows = await search_tradeshows_with_gemini(
                user_summary=summary,
                keywords=keywords,
                target_events=target_events or "",
                product_url=product_url or ""
            )
            logger.info(f"Found {len(tradeshows)} tradeshows using Gemini-2.0-flash")
        except Exception as e:
            logger.error(f"Error searching tradeshows with Gemini: {str(e)}")
    
    context = {
        "summary": summary, 
        "keywords": keywords,
        "location": location,
        "target_events": target_events,
        "product_url": product_url,
        "use_gemini": use_gemini,
        "tradeshows": tradeshows
    }
    return await render_template("event_search.html", version=VERSION, **context)

@app.route("/landing")
async def landing_page():
    # Render the landing page with the chat interface and keyword generator
    await flow_controller.reset()
    return await render_template("landing_page.html", version=VERSION)

@app.route("/browser_visualization")
async def browser_visualization():
    # Render the browser visualization page
    await flow_controller.reset()
    return await render_template("browser_visualization.html", version=VERSION, first_question=True, initial_step="product")

@app.route("/api/onboarding", methods=["POST"])
async def onboarding_step():
    logger.info(f"Received onboarding request with Content-Type: {request.headers.get('Content-Type', 'None')}")
    
    step = None
    answer = ""
    image_data = None
    
    # Check if the request is multipart/form-data
    if request.headers.get('Content-Type', '').startswith('multipart/form-data'):
        try:
            form = await request.form
            files = await request.files
            
            logger.info(f"Form data keys: {list(form.keys())}")
            logger.info(f"Files keys: {list(files.keys())}")
            
            step = form.get("step")
            answer = form.get("answer", "")
            
            if not step:
                logger.error("Missing step parameter in form data")
                return jsonify({"success": False, "error": "Missing step parameter"})
                
            logger.info(f"Extracted step: {step}, answer: {answer}")
            
            # Check if an image was uploaded
            image_file = None
            if 'image' in files:
                image_file = files.get("image")
                
            if image_file:
                try:
                    # Read the image data
                    image_bytes = await image_file.read()
                    if len(image_bytes) > 0:
                        image_data = image_bytes
                        logger.info(f"Onboarding: {step} => {answer} with image ({len(image_bytes)} bytes)")
                    else:
                        logger.warning("Empty image file received")
                except Exception as e:
                    logger.error(f"Error reading image file: {str(e)}")
            else:
                logger.info(f"Onboarding: {step} => {answer} (no image)")
        except Exception as e:
            logger.error(f"Error processing multipart form: {str(e)}")
            return jsonify({"success": False, "error": str(e)})
    else:
        try:
            # First try to get JSON data
            data = await request.get_json()
            if data is not None:
                logger.info(f"JSON data: {data}")
                step = data.get("step")
                answer = data.get("answer", "")
                logger.info(f"Onboarding: {step} => {answer} (JSON)")
            else:
                # If not JSON, try to get form data (application/x-www-form-urlencoded)
                form = await request.form
                logger.info(f"Form data keys: {list(form.keys())}")
                step = form.get("step")
                answer = form.get("answer", "")
                logger.info(f"Onboarding: {step} => {answer} (form-urlencoded)")
        except Exception as e:
            logger.error(f"Error processing request data: {str(e)}")
            return jsonify({"success": False, "error": str(e)})
    
    # Check if we have a valid step
    if not step:
        return jsonify({"success": False, "error": "Missing step parameter"})

    await flow_controller.store_answer(step, answer, image_data)
    next_step = await flow_controller.determine_next_step(step)

    # Generate user summary after storing the answer
    user_summary = ""
    
    # If this is the website step, use website_analyzer directly
    if step == "website" and answer and len(answer.strip()) > 5:
        try:
            # Use the browser-based website analyzer if available
            use_browser = True
            
            if use_browser:
                logger.info(f"Using browser-based website analyzer to analyze website: {answer}")
                # The browser_analyze_website function will analyze the website using Cline's browser_action tool
                website_data = await browser_analyze_website(answer)
                
                if website_data:
                    logger.info(f"Browser-based website analysis successful for {answer}")
                    # Update the context with the website data
                    context = await flow_controller.get_context()
                    context.update({
                        'product': website_data.get('title', ''),
                        'differentiation': website_data.get('description', '')
                    })
                    
                    # If this is an industries page, extract industry information
                    if 'industries' in website_data and website_data['industries']:
                        logger.info(f"Extracted industries: {website_data['industries']}")
                        # You could update the context with industry information here
                        
                    # Get the updated user summary from flow_controller
                    user_summary = await flow_controller.generate_user_summary()
                else:
                    logger.warning(f"Browser-based website analysis failed for {answer}, falling back to curl-based analyzer")
                    # Fall back to the curl-based analyzer
                    await analyze_website(answer)
                    user_summary = await flow_controller.generate_user_summary()
            else:
                logger.info(f"Using curl-based website analyzer to analyze website: {answer}")
                # The analyze_website function will generate a user summary
                await analyze_website(answer)
                # Get the updated user summary from flow_controller
                user_summary = await flow_controller.generate_user_summary()
        except Exception as e:
            logger.error(f"Error using website analyzer: {str(e)}")
            # Fall back to the regular method if website_analyzer fails
            user_summary = await flow_controller.generate_user_summary()
    else:
        # Use the regular method for other steps
        user_summary = await flow_controller.generate_user_summary()

    if next_step == "complete":
        cleaned_keywords = await flow_controller.clean_keywords()
        return jsonify({
            "success": True,
            "completed": True,
            "keywords": cleaned_keywords,
            "user_summary": user_summary,
            "redirect": "/event_search_page"  # Add redirect to event search page
        })

    question = await flow_controller.get_question(next_step)
    
    # Check if this is the event_interests step to render the event goal question template
    if next_step == "event_interests":
        # Check if this is a response to the event_interests step with an action
        action = None
        if step == "event_interests":
            # Check if this is a form submission with an action parameter
            action = form.get("action") if 'form' in locals() else data.get("action") if 'data' in locals() else None
            
            if action == "see_events":
                # Log that we received the see_events action
                logger.info(f"Received 'see_events' action from form submission")
                
                # Generate business profile and target events
                if not flow_controller.user_summary:
                    flow_controller.user_summary = user_summary
                    logger.info(f"Set user_summary from current response")
                else:
                    logger.info(f"Using existing user_summary")
                
                # Skip the market step (which contains the Tanagram question)
                # Set a default value for market if it's empty
                if not flow_controller.current_sector:
                    flow_controller.current_sector = "General business"
                    logger.info(f"Set default current_sector: 'General business'")
                
                # Generate target events recommendation
                target_events = await flow_controller.generate_target_events_recommendation()
                logger.info(f"Generated target events: {len(target_events) if target_events else 0} chars")
                
                # Make sure keywords are generated
                if not flow_controller.keywords:
                    flow_controller.keywords = ["networking", "events", "business"]
                    logger.info(f"Set default keywords: {flow_controller.keywords}")
                
                # Log the data being sent to the response
                logger.info(f"Sending response with: User summary: {len(flow_controller.user_summary) if flow_controller.user_summary else 0} chars, Target events: {len(target_events) if target_events else 0} chars, Keywords: {flow_controller.keywords}")
                
                # Prepare redirect response
                response_data = {
                    "success": True,
                    "redirect": "/business_profile"
                }
                
                logger.info(f"Returning redirect response: {response_data}")
                return jsonify(response_data)
            elif action == "tell_me_more":
                # Store user data in flow controller
                if not flow_controller.user_summary:
                    flow_controller.user_summary = user_summary
                
                # Make sure keywords are generated
                if not flow_controller.keywords:
                    flow_controller.keywords = ["networking", "events", "business"]
                
                # Determine the follow-up question based on the selected goals
                follow_up_step = await flow_controller.determine_follow_up_question()
                
                # Log the data being sent to the follow-up question page
                logger.info(f"Redirecting to follow-up question with: User summary: {len(flow_controller.user_summary) if flow_controller.user_summary else 0} chars, Keywords: {flow_controller.keywords}")
                
                # Redirect to the follow-up question page
                return jsonify({
                    "success": True,
                    "step": follow_up_step,
                    "redirect": f"/follow_up_question/{follow_up_step}",
                    "keywords": flow_controller.keywords,
                    "user_summary": flow_controller.user_summary
                })
        
        # Default behavior for event_interests step (first time)
        return jsonify({
            "success": True,
            "step": next_step,
            "redirect": "/event_goal_question",
            "keywords": flow_controller.keywords,
            "user_summary": user_summary
        })
    else:
        # Regular response for other steps
        return jsonify({
            "success": True,
            "step": next_step,
            "question": question,
            "keywords": flow_controller.keywords,
            "user_summary": user_summary
        })

@app.route("/api/get_question", methods=["GET"])
async def get_question():
    step = request.args.get("step", "product")
    question = await flow_controller.get_question(step)
    return jsonify({
        "success": True,
        "question": question,
        "keywords": flow_controller.keywords  # Always include current keywords
    })

@app.route("/api/recommendations", methods=["GET"])
async def get_recommendations():
    # Return the current keywords as recommendations
    return jsonify({
        "success": True,
        "keywords": flow_controller.keywords,
        "recommendations": [
            {
                "name": "Sample Company 1",
                "description": "This is a sample company that matches your keywords.",
                "relevance": 0.9,
                "website": "https://example.com"
            },
            {
                "name": "Sample Company 2",
                "description": "Another sample company that matches your keywords.",
                "relevance": 0.8,
                "website": "https://example2.com"
            }
        ]
    })

@app.route("/api/keywords", methods=["GET"])
async def get_keywords():
    cleaned_keywords = await flow_controller.clean_keywords()
    user_summary = flow_controller.get_user_summary()
    
    return jsonify({
        "success": True,
        "keywords": cleaned_keywords,
        "user_summary": user_summary
    })

@app.route("/api/search_events", methods=["POST"])
async def search_events():
    """Search for events based on keywords and location"""
    try:
        # Get parameters from either form data or URL query parameters
        form = await request.form
        
        # Check if we have form data
        if form:
            keywords_str = form.get("keywords", "")
            keywords = keywords_str.split(",") if keywords_str else []
            user_summary = form.get("summary", "")
            user_type = form.get("user_type", "general")
            location = form.get("location", "sf")
        else:
            # Try to get JSON data as fallback
            data = await request.get_json()
            keywords_str = data.get("keywords", "")
            keywords = keywords_str.split(",") if isinstance(keywords_str, str) else data.get("keywords", [])
            # Check for both possible parameter names for the summary
            user_summary = data.get("summary", data.get("user_summary", ""))
            user_type = data.get("user_type", "general")
            location = data.get("location", "sf")
            target_events = data.get("target_events", "")
        
        # No longer limiting keywords
        # keywords = keywords[:5]
        logger.info(f"Searching with keywords: {', '.join(keywords)}")
        logger.info(f"User type: {user_type}")
        
        # Import the search_events function from the event_search_agent module
        from event_search_agent import search_events as search_events_api, find_top_events
        
        # Call the search_events function with jsonify - limit to 3 results for faster search
        data = {
            "keywords": ",".join(keywords) if isinstance(keywords, list) else keywords,
            "user_summary": user_summary,
            "user_type": user_type,
            "location": location,
            "max_results": 10,  # Increased to 10 results
            "target_events": target_events
        }
        
        # Call the event search agent to get local events
        logger.info(f"Calling event_search_agent with data: {data}")
        
        # Parse keywords from string if needed
        if isinstance(data['keywords'], str):
            keywords_list = [k.strip() for k in data['keywords'].split(',') if k.strip()]
        else:
            keywords_list = data['keywords']
            
        # Call the find_top_events function to get local events
        events_result = await find_top_events(
            keywords=keywords_list,
            user_summary=data['user_summary'],
            user_type=data['user_type'],
            location=data['location'],
            max_results=data['max_results'],
            target_events=data['target_events']
        )
        
        # Extract local events from the result
        local_events = events_result.get('local_events', [])
        logger.info(f"Found {len(local_events)} local events from event_search_agent")
        
        # Get tradeshows from Gemini API
        logger.info("Searching for tradeshows with Gemini API...")
        tradeshows = await search_tradeshows_with_gemini(
            user_summary=data['user_summary'],
            keywords=keywords_list,
            target_events=data.get('target_events', ''),
            location=data.get('location', 'sf'),
            user_type=data.get('user_type', 'founder')
        )
        
        logger.info(f"Found {len(tradeshows)} tradeshows from Gemini API")
        
        # Format tradeshows for the response
        formatted_tradeshows = []
        for i, show in enumerate(tradeshows):
            # Get the date and validate it's in 2025 or later
            event_date = show.get('Event Date', show.get('date', ''))
            
            # Temporarily disable date validation
            valid_year = True
            
            # Comment out date validation for now
            '''
            # Check if the date contains 2025 or a later year
            valid_year = False
            if event_date:
                # Look for years 2025 or later in the date string
                year_match = re.search(r'20(2[5-9]|[3-9][0-9])', event_date)
                
                # Also check for ISO format dates like 2025-11-15
                iso_date_match = re.search(r'(202[5-9]|20[3-9][0-9])[-/]\d{1,2}[-/]\d{1,2}', event_date)
                
                valid_year = bool(year_match) or bool(iso_date_match)
                
                # Log the date validation for debugging
                logger.info(f"Date validation for '{event_date}': valid_year={valid_year}")
                if not valid_year:
                    logger.warning(f"Invalid date format: {event_date} - doesn't contain a year 2025 or later")
            '''
            
            # Always include events for now (date validation disabled)
            # Get the event title from various possible field names
            event_title = show.get('Event_Title', show.get('Event Title', show.get('title', 'Unknown Event')))
            
            # Get the event description from various possible field names
            event_description = show.get('Event_Description', show.get('Event Description', show.get('description', 'No description available')))
            
            # Get the conversion path or use description as fallback
            conversion_path = show.get('Conversion_Path', show.get('Conversion Path', show.get('conversion_path', event_description)))
            
            # Get the website URL from various possible field names
            website_url = show.get('Event_Official_Website', show.get('Event Official Website', show.get('website', show.get('url', 'https://example.com'))))
            
            # Filter out hallucinated URLs
            if 'example.com' in website_url.lower() or not website_url.startswith('http'):
                # Try to find a better URL in the description or title
                description = show.get('Event_Description', show.get('Event Description', show.get('description', '')))
                url_match = re.search(r'https?://[\w.-]+\.[a-zA-Z]{2,}(?:/\S*)?', description)
                if url_match:
                    website_url = url_match.group(0)
                else:
                    # If we can't find a URL in the description, use a generic one but mark it
                    website_url = f"https://www.google.com/search?q={urllib.parse.quote(event_title)}"
            
            # Get the keywords from various possible field names
            keywords = show.get('Event_Keywords', show.get('Event Keywords', show.get('keywords', '')))
            
            # Get the location from various possible field names
            location = show.get('Event_Location', show.get('Event Location', show.get('location', 'Various Locations')))
            
            # Get the score from various possible field names
            score = show.get('Conversion_Score', show.get('Conversion Score', show.get('conversion_score', 75)))
            
            formatted_show = {
                'id': f'tradeshow-{i+1}',
                'name': event_title,
                'description': conversion_path,
                'url': website_url,
                'business_value_score': score,
                'score': score,
                'highlight': keywords,
                'date': event_date,  # Use the validated date
                'location': location,
                'is_tradeshow': True
            }
            formatted_tradeshows.append(formatted_show)
            # Since we disabled date validation, the else clause is not needed
            # else:
            #    logger.warning(f"Excluded tradeshow with invalid date: {event_date}. Event: {show.get('title', 'Unknown Event')}")
            #    # Don't add this event to formatted_tradeshows
        
        # If no tradeshows were found, log a warning but don't use fallback data
        if not formatted_tradeshows:
            logger.warning("No tradeshows found from Gemini API. Check the API response and prompt.")
        
        # Create the response
        response = {
            "success": True,
            "trade_shows": formatted_tradeshows,
            "local_events": local_events
        }
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error in search_events: {str(e)}")
        traceback.print_exc()  # Print the full traceback for debugging
        return jsonify({"success": False, "error": str(e), "trade_shows": [], "local_events": []})



@app.route("/user_info_collection")
async def user_info_collection():
    """Render the user information collection page"""
    # Get query parameters
    keywords = request.args.get('keywords', '')
    summary = request.args.get('summary', '')
    from_onboarding = request.args.get('fromOnboarding', 'false')
    
    # Render the user info collection template
    return await render_template(
        "user_info_collection.html",
        keywords=keywords,
        summary=summary,
        fromOnboarding=from_onboarding
    )

@app.route("/api/save_user_info", methods=["POST"])
async def save_user_info():
    """API endpoint to save user information"""
    try:
        data = await request.get_json()
        user_name = data.get('user_name', '')
        email = data.get('email', '')
        company_name = data.get('company_name', '')
        keywords = data.get('keywords', '')
        user_summary = data.get('user_summary', '')
        from_onboarding = data.get('from_onboarding', False)
        
        # Validate required fields
        if not user_name or not email:
            return jsonify({"success": False, "error": "Name and email are required"})
        
        # Save user information to flow controller
        result = await flow_controller.save_user_info(user_name, email, company_name)
        
        # Record this step in the user journey
        await flow_controller.record_user_journey('user_info_provided', {
            'keywords': keywords,
            'user_summary': user_summary,
            'from_onboarding': from_onboarding
        })
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error saving user information: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/bookmark_event", methods=["POST"])
async def bookmark_event():
    """API endpoint to bookmark an event"""
    try:
        data = await request.get_json()
        event_id = data.get('event_id')
        event_name = data.get('event_name')
        
        # Get user info
        user_info = await flow_controller.get_user_info()
        
        # Check if user has provided email
        if not user_info.get('has_provided_user_info'):
            return jsonify({
                "success": False, 
                "error": "Please provide your information before bookmarking events",
                "redirect": "/user_info_collection"
            })
        
        # Record the bookmark in the user journey
        await flow_controller.record_user_journey('event_bookmarked', {
            'event_id': event_id,
            'event_name': event_name
        })
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error bookmarking event: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/event_search_page")
async def event_search_page():
    """Render the event search page with keywords and user summary from onboarding"""
    # Get the latest keywords and user summary
    cleaned_keywords = await flow_controller.clean_keywords()
    # Ensure we always have a valid list of keywords
    if cleaned_keywords is None:
        cleaned_keywords = ["B2B", "Sales", "Marketing", "Technology", "Solutions"]
    user_summary = flow_controller.user_summary or "A company looking for networking opportunities."
    
    # Check if user has provided information
    user_info = await flow_controller.get_user_info()
    limited_mode = request.args.get('limited', 'false') == 'true'
    
    # If user hasn't provided info and we're not in limited mode, redirect to user info collection
    if not user_info.get('has_provided_user_info') and not limited_mode:
        # Convert keywords list to comma-separated string
        keywords_str = ','.join(cleaned_keywords) if isinstance(cleaned_keywords, list) else cleaned_keywords
        # URL encode the user summary to avoid issues with newlines and special characters
        import urllib.parse
        encoded_summary = urllib.parse.quote(user_summary)
        return redirect(f"/user_info_collection?keywords={keywords_str}&summary={encoded_summary}&fromOnboarding=true")
    
    # Determine event goal based on flow controller flags
    event_goal = "Not specified"
    if flow_controller.buyer_focus and flow_controller.recruitment_focus:
        event_goal = "Find buyers and recruit talent"
    elif flow_controller.buyer_focus:
        event_goal = "Find more buyers/users"
    elif flow_controller.recruitment_focus:
        event_goal = "Recruit talent"
    
    # Render the event search template with the keywords, user summary, and event goal
    return await render_template(
        "event_search.html",
        keywords=cleaned_keywords,
        user_summary=user_summary,
        limited_mode=limited_mode,
        user_info=user_info,
        event_goal=event_goal
    )

@app.route("/api/get_user_info", methods=["GET"])
async def get_user_info_api():
    """API endpoint to get user information"""
    try:
        # Get user info from flow controller
        user_info = await flow_controller.get_user_info()
        return jsonify({"success": True, "user_info": user_info})
    except Exception as e:
        logger.error(f"Error getting user information: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/generate_user_report", methods=["GET"])
async def generate_user_report():
    """API endpoint to generate a report of interested users"""
    try:
        # Import the save_all_user_journeys function
        from save_all_user_journeys import save_all_user_journeys
        
        # Generate the report
        await save_all_user_journeys()
        
        return jsonify({
            "success": True, 
            "message": "User journey report generated successfully. Check the data/reports directory."
        })
    except Exception as e:
        logger.error(f"Error generating user report: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/test_mcp", methods=["POST"])
async def test_mcp():
    """Test the MCP server by calling a tool"""
    try:
        data = await request.get_json()
        server_name = data.get("server_name")
        tool_name = data.get("tool_name")
        arguments = data.get("arguments", {})
        
        if not server_name or not tool_name:
            return jsonify({"success": False, "error": "Missing server_name or tool_name"})
        
        logger.info(f"Testing MCP server: {server_name}, tool: {tool_name}, args: {arguments}")
        
        try:
            # Import the MCP client
            from modelcontextprotocol.client import use_mcp_tool
            
            # Call the MCP tool
            result = await use_mcp_tool(server_name, tool_name, arguments)
            
            # Parse the result if it's JSON
            try:
                parsed_result = json.loads(result)
                return jsonify({"success": True, "result": parsed_result})
            except:
                return jsonify({"success": True, "result": result})
                
        except ImportError:
            # If MCP client is not available, try using the direct method
            logger.warning("MCP client not available, trying direct method")
            try:
                # Use the test-direct.py script to call the MCP server directly
                import subprocess
                import sys
                
                # Create a temporary JSON file with the request
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                    temp_path = temp_file.name
                    json.dump({
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "mcp.call_tool",
                        "params": {
                            "name": tool_name,
                            "arguments": arguments
                        }
                    }, temp_file)
                
                # Call the MCP server directly using the test-direct.py script
                cmd = [
                    sys.executable,
                    "/Users/carol.zhu/Documents/Cline/MCP/website-analyzer/test-direct.py",
                    temp_path
                ]
                
                logger.info(f"Running direct MCP command: {' '.join(cmd)}")
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                stdout, stderr = process.communicate(timeout=30)
                
                if process.returncode != 0:
                    logger.error(f"Error running direct MCP command: {stderr}")
                    return jsonify({"success": False, "error": f"Direct MCP command failed: {stderr}"})
                
                # Parse the result
                try:
                    result_lines = stdout.strip().split('\n')
                    for line in result_lines:
                        if line.startswith('Response:'):
                            # Extract the JSON part
                            result_json = line[len('Response:'):].strip()
                            logger.info(f"Extracted JSON: {result_json}")
                            
                            # Parse the JSON
                            try:
                                parsed_result = json.loads(result_json)
                                if "result" in parsed_result:
                                    return jsonify({"success": True, "result": parsed_result["result"]})
                            except json.JSONDecodeError as json_err:
                                logger.error(f"JSON decode error: {str(json_err)}")
                                # Try to clean up the JSON string
                                cleaned_json = result_json.replace("'", '"')
                                try:
                                    parsed_result = json.loads(cleaned_json)
                                    if "result" in parsed_result:
                                        return jsonify({"success": True, "result": parsed_result["result"]})
                                except:
                                    pass
                    
                    # If we get here, we couldn't parse the response
                    logger.error(f"Full stdout: {stdout}")
                    return jsonify({"success": False, "error": "No valid response found in direct MCP output"})
                except Exception as e:
                    logger.error(f"Error parsing direct MCP output: {str(e)}")
                    logger.error(f"Full stdout: {stdout}")
                    return jsonify({"success": False, "error": f"Error parsing direct MCP output: {str(e)}"})
                
            except Exception as e:
                logger.error(f"Error using direct MCP method: {str(e)}")
                return jsonify({"success": False, "error": f"MCP client not available and direct method failed: {str(e)}"})
        except Exception as e:
            logger.error(f"Error calling MCP tool: {str(e)}")
            return jsonify({"success": False, "error": str(e)})
    
    except Exception as e:
        logger.error(f"Error in test_mcp: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

async def search_tradeshows_with_gemini(user_summary, keywords, target_events, product_url="", user_type="founder", location="sf"):
    """Search for tradeshows using Gemini-2.0-flash model with multiple parallel API calls
    
    Args:
        user_summary (str): The user's business profile summary
        keywords (list): List of keywords related to the user's business
        target_events (str): Target events recommendation text
        product_url (str, optional): The user's product/company website URL
        user_type (str, optional): The type of user (founder, sales, etc.)
        location (str, optional): The preferred location for events (default: sf)
        
    Returns:
        list: List of tradeshow events with details
    """
    try:
        # Extract goals from target events
        goals_pattern = r"(?:Goals|Objectives|Aims):[^\n]*(?:\n[^\n]+)*"
        goals_match = re.search(goals_pattern, target_events, re.IGNORECASE)
        goals = goals_match.group(0) if goals_match else ""
        
        # Make 3 parallel API calls with slightly different prompts to get diverse results
        all_tradeshows = []
        
        # Define the three different prompts
        prompts = [
            f"Search for most relevant **5** tradeshows leveraging websites such as 10times.com for this {user_type} at their company. The tradeshows MUST happen in the future, specifically from 2025 onwards (current year is 2025). DO NOT include any events from 2024 or earlier. Focus on TECHNOLOGY and AI events.",
            
            f"Search for most relevant **5** tradeshows leveraging websites such as 10times.com for this {user_type} at their company. The tradeshows MUST happen in the future, specifically from 2025 onwards (current year is 2025). DO NOT include any events from 2024 or earlier. Focus on INDUSTRY-SPECIFIC events relevant to their business.",
            
            f"Search for most relevant **5** tradeshows leveraging websites such as 10times.com for this {user_type} at their company. The tradeshows MUST happen in the future, specifically from 2025 onwards (current year is 2025). DO NOT include any events from 2024 or earlier. Focus on NETWORKING and BUSINESS DEVELOPMENT events."
        ]
        
        # Create tasks for parallel execution
        tasks = []
        for i, prompt_prefix in enumerate(prompts):
            # Create a complete prompt for each API call
            full_prompt = f"{prompt_prefix}\n\nUser profile: {user_summary}\n\nKeywords: {', '.join(keywords)}\n\nLocation preference: {location}\n\nFor each tradeshow, provide the following information in a structured format:\n- Event Title\n- Event Date (must be in 2025 or later)\n- Event Location\n- Event Description: Provide at least 3 detailed sentences - 1-2 sentences about the event itself (history, scope, importance) and 1-2 sentences about why it's specifically relevant to the user's product/business\n- Event Keywords\n- Conversion Path: Provide a detailed, actionable 3-4 sentence strategy for how this user can best leverage this event to achieve their goals (e.g. find future buyers/business partners etc.)\n- Event Official Website: MUST provide a valid website URL for each event. If you can't find the official website, provide the most relevant website related to the event or organization.\n- Conversion Score (0-100): How well this event aligns with the user's goals\n\nEnsure the Event Title is clear and properly formatted as it will be highlighted in the UI.\nMake sure the Event Description is insightful and specific to the user's business needs.\nEVERY event MUST have a website URL - this is critical for the application.\n\nReturn the results as a JSON array of objects, each with the above attributes."
            
            # Create a task for each API call
            task = asyncio.create_task(call_gemini_api(full_prompt, i+1))
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks)
        
        # Combine all tradeshows from the results
        for tradeshows in results:
            if tradeshows:
                all_tradeshows.extend(tradeshows)
        
        # Deduplicate tradeshows based on title and date
        deduplicated_tradeshows = []
        seen_events = set()
        
        # Debug the event structure
        if all_tradeshows:
            logger.info(f"Sample event keys: {list(all_tradeshows[0].keys())[:10]}")
        
        for event in all_tradeshows:
            # Debug each event
            logger.info(f"Processing event: {event}")
            
            # Try different field names that might contain the title
            title_fields = ['Event_Title', 'Event Title', 'title', 'name']
            event_title = ''
            for field in title_fields:
                if field in event and event[field]:
                    event_title = event[field].strip().lower()
                    break
            
            # Try different field names that might contain the website URL
            website_fields = ['Event_Official_Website', 'Event Official Website', 'website', 'url']
            event_website = ''
            for field in website_fields:
                if field in event and event[field]:
                    event_website = event[field].strip().lower()
                    break
            
            logger.info(f"Event title: '{event_title}', Event website: '{event_website}'")
            
            # Create a unique identifier based on website URL (primary) or title (fallback)
            event_key = event_website if event_website else event_title
            
            # Only add the event if we haven't seen it before
            if event_key not in seen_events and event_title:
                seen_events.add(event_key)
                deduplicated_tradeshows.append(event)
                logger.info(f"Added unique event: {event_title}")
            else:
                logger.info(f"Skipped duplicate event: {event_title}")
                
            # If we have no events yet, just add this one regardless
            if not deduplicated_tradeshows and event_title:
                logger.info(f"Adding first event as fallback: {event_title}")
                deduplicated_tradeshows.append(event)
                seen_events.add(event_key)
        
        logger.info(f"Combined {len(all_tradeshows)} tradeshows from {len(prompts)} parallel API calls")
        logger.info(f"After deduplication: {len(deduplicated_tradeshows)} unique tradeshows")
        
        all_tradeshows = deduplicated_tradeshows
        
        return all_tradeshows
    except Exception as e:
        logger.error(f"Error in search_tradeshows_with_gemini: {str(e)}")
        logger.error(traceback.format_exc())
        return []

async def call_gemini_api(prompt, call_id):
    """Make a single call to the Gemini API
    
    Args:
        prompt (str): The prompt to send to the API
        call_id (int): An identifier for this API call
        
    Returns:
        list: List of tradeshow events from this API call
    """
    try:
        # Call the Gemini API using the question engine with the correct model for tradeshow search
        logger.info(f"Calling Gemini-2.0-flash API for tradeshow search (call {call_id})...")
        # Use a direct API call to ensure we use the correct model for tradeshow search
        try:
            gemini_api_key = flow_controller.question_engine.gemini_api_key
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
                # Use the proper structured output format according to the Gemini API documentation
                "tools": [{
                    "functionDeclarations": [{
                        "name": "tradeshow_event",
                        "description": "Information about a tradeshow event",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "Event_Title": {
                                    "type": "string",
                                    "description": "The title of the event"
                                },
                                "Event_Date": {
                                    "type": "string",
                                    "description": "The date of the event (must be in 2025 or later)"
                                },
                                "Event_Location": {
                                    "type": "string",
                                    "description": "The location where the event will be held"
                                },
                                "Event_Description": {
                                    "type": "string",
                                    "description": "Detailed description of the event and why it's relevant to the user"
                                },
                                "Event_Keywords": {
                                    "type": "string",
                                    "description": "Keywords related to the event"
                                },
                                "Conversion_Path": {
                                    "type": "string",
                                    "description": "Strategy for how the user can leverage this event"
                                },
                                "Event_Official_Website": {
                                    "type": "string",
                                    "description": "URL of the official event website"
                                },
                                "Conversion_Score": {
                                    "type": "integer",
                                    "description": "Score from 0-100 indicating how well this event aligns with user's goals"
                                }
                            },
                            "required": ["Event_Title", "Event_Date", "Event_Location", "Event_Description", "Event_Keywords", "Conversion_Path", "Event_Official_Website", "Conversion_Score"]
                        }
                    }]
                }]
            }
            
            logger.info(f"Sending request to Gemini API with prompt length: {len(prompt)} (call {call_id})")
            logger.info(f"Prompt preview for call {call_id}: {prompt[:100]}...")
            logger.info(f"Using Gemini URL: {gemini_url[:70]}...")
            
            async with httpx.AsyncClient() as client:
                try:
                    logger.info(f"Sending POST request to Gemini API (call {call_id})...")
                    api_response = await client.post(
                        gemini_url,
                        json=data,
                        timeout=60.0  # Increased timeout for longer responses
                    )
                    logger.info(f"POST request completed with status code: {api_response.status_code} (call {call_id})")
                except Exception as e:
                    logger.error(f"Exception during HTTP request (call {call_id}): {str(e)}")
                    raise
                
            logger.info(f"Received response from Gemini API with status code: {api_response.status_code} (call {call_id})")
            
            if api_response.status_code == 200:
                result = api_response.json()
                if "candidates" in result and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    
                    # Check for function calls in the structured output format
                    if "functionCalls" in candidate["content"] and len(candidate["content"]["functionCalls"]) > 0:
                        logger.info(f"Found structured function call response (call {call_id})")
                        function_calls = candidate["content"]["functionCalls"]
                        
                        # Extract the tradeshow events from the function calls
                        tradeshows = []
                        for call in function_calls:
                            if call["name"] == "tradeshow_event":
                                try:
                                    # Parse the function arguments as JSON
                                    event_data = json.loads(call["args"])
                                    # Convert to our expected format
                                    event = {
                                        "Event Title": event_data.get("Event_Title", ""),
                                        "Event Date": event_data.get("Event_Date", ""),
                                        "Event Location": event_data.get("Event_Location", ""),
                                        "Event Description": event_data.get("Event_Description", ""),
                                        "Event Keywords": event_data.get("Event_Keywords", ""),
                                        "Conversion Path": event_data.get("Conversion_Path", ""),
                                        "Event Official Website": event_data.get("Event_Official_Website", ""),
                                        "Conversion Score": event_data.get("Conversion_Score", 0)
                                    }
                                    tradeshows.append(event)
                                except json.JSONDecodeError as e:
                                    logger.error(f"Error parsing function call args (call {call_id}): {e}")
                                except Exception as e:
                                    logger.error(f"Unexpected error parsing function call (call {call_id}): {str(e)}")
                                    logger.error(f"Function call: {call}")
                                    # Try to extract data directly from the function call if possible
                                    try:
                                        if isinstance(call.get("args"), str):
                                            # Log the raw args for debugging
                                            logger.info(f"Raw args (call {call_id}): {call['args'][:200]}...")
                                            
                                            # Try to clean up the args string
                                            args_str = call["args"].strip()
                                            if args_str.startswith('"') and args_str.endswith('"'):
                                                args_str = args_str[1:-1]  # Remove outer quotes
                                            
                                            # Try to parse as JSON again
                                            event_data = json.loads(args_str)
                                            event = {
                                                "Event Title": event_data.get("Event_Title", ""),
                                                "Event Date": event_data.get("Event_Date", ""),
                                                "Event Location": event_data.get("Event_Location", ""),
                                                "Event Description": event_data.get("Event_Description", ""),
                                                "Event Keywords": event_data.get("Event_Keywords", ""),
                                                "Conversion Path": event_data.get("Conversion_Path", ""),
                                                "Event Official Website": event_data.get("Event_Official_Website", ""),
                                                "Conversion Score": event_data.get("Conversion_Score", 0)
                                            }
                                            tradeshows.append(event)
                                    except Exception as inner_e:
                                        logger.error(f"Failed to extract data from function call (call {call_id}): {str(inner_e)}")
                                        # Continue to next function call
                        
                        if tradeshows:
                            logger.info(f"Successfully parsed {len(tradeshows)} events from structured output (call {call_id})")
                            return tradeshows
                    
                    # Fallback to the old text parsing if no function calls
                    if "parts" in candidate["content"] and len(candidate["content"]["parts"]) > 0:
                        response = candidate["content"]["parts"][0]["text"].strip()
                        logger.info(f"Successfully received response from gemini-2.0-flash, length: {len(response)} (call {call_id})")
                        logger.info(f"Response preview (call {call_id}): {response[:200]}...")
                    else:
                        logger.error(f"No text parts found in Gemini response (call {call_id})")
                        response = ""
                else:
                    logger.error(f"No candidates found in Gemini response (call {call_id}): {result}")
                    response = ""
            else:
                logger.error(f"Error calling Gemini API (call {call_id}): {api_response.status_code} - {api_response.text}")
                response = ""
        except Exception as e:
            logger.error(f"Exception calling Gemini API directly (call {call_id}): {str(e)}")
            logger.error(traceback.format_exc())
            response = ""
        logger.info(f"Gemini response received, length: {len(response) if response else 0} (call {call_id})")
        if response:
            logger.info(f"Gemini response preview (call {call_id}): {response[:200]}...")
        else:
            logger.warning(f"Empty response received from Gemini API (call {call_id})")
        
        # Parse the JSON response
        # First, try to find JSON in the response using regex
        logger.info(f"Attempting to parse JSON from Gemini response (call {call_id})...")
        
        # Remove markdown code block formatting if present
        cleaned_response = re.sub(r'```json|```', '', response).strip()
        
        # Try direct JSON parsing first
        try:
            logger.info(f"Attempting direct JSON parsing (call {call_id})...")
            tradeshows = json.loads(cleaned_response)
            logger.info(f"Direct JSON parsing successful, found {len(tradeshows)} tradeshows (call {call_id})")
            # Log the first tradeshow as an example
            if tradeshows:
                logger.info(f"Example tradeshow (call {call_id}): {json.dumps(tradeshows[0], indent=2)[:200]}...")
            return tradeshows
        except json.JSONDecodeError:
            logger.warning(f"Direct JSON parsing failed, trying regex extraction (call {call_id})...")
        
        # Try to find JSON array in the response using multiple patterns
        # First, look for standard JSON array pattern
        json_pattern = r'\[\s*\{[^\[\]]*\}(?:\s*,\s*\{[^\[\]]*\})*\s*\]'
        json_match = re.search(json_pattern, response, re.DOTALL)
        
        # If that fails, try a more lenient pattern that might catch malformed JSON
        if not json_match:
            json_pattern = r'\[\s*\{.*?\}(?:\s*,\s*\{.*?\})*\s*\]'
            json_match = re.search(json_pattern, response, re.DOTALL)
        
        tradeshows = []
        
        if json_match:
            logger.info(f"JSON pattern found in response (call {call_id})")
            json_str = json_match.group(0)
            logger.info(f"Extracted JSON string (call {call_id}, first 200 chars): {json_str[:200]}...")
            try:
                tradeshows = json.loads(json_str)
                logger.info(f"Successfully parsed JSON, found {len(tradeshows)} tradeshows (call {call_id})")
                # Log the first tradeshow as an example
                if tradeshows:
                    logger.info(f"Example tradeshow (call {call_id}): {json.dumps(tradeshows[0], indent=2)[:200]}...")
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON (call {call_id}): {str(e)}")
                logger.error(f"Problematic JSON string (call {call_id}): {json_str[:500]}...")
                # Will use fallback data below
        else:
            # If no JSON array found, try to extract structured data manually
            logger.warning(f"Could not find JSON array in Gemini response, attempting manual parsing (call {call_id})")
            event_blocks = re.split(r'\n\s*\d+\.\s*', response)
            logger.info(f"Manual parsing found {len(event_blocks)} potential event blocks (call {call_id})")
            
            for block in event_blocks:
                if not block.strip():
                    continue
                    
                event = {}
                title_match = re.search(r'Event Title:?\s*(.+)', block)
                event['Event Title'] = title_match.group(1).strip() if title_match else "Unknown Event"
                
                date_match = re.search(r'Event Date:?\s*(.+)', block)
                event['Event Date'] = date_match.group(1).strip() if date_match else ""
                
                location_match = re.search(r'Event Location:?\s*(.+)', block)
                event['Event Location'] = location_match.group(1).strip() if location_match else ""
                
                description_match = re.search(r'Event Description:?\s*([^\n]+(?:\n[^\n]+)*)', block)
                event['Event Description'] = description_match.group(1).strip() if description_match else ""
                
                keywords_match = re.search(r'Event Keywords:?\s*(.+)', block)
                event['Event Keywords'] = keywords_match.group(1).strip() if keywords_match else ""
                
                conversion_path_match = re.search(r'Conversion Path:?\s*([^\n]+(?:\n[^\n]+)*)', block)
                event['Conversion Path'] = conversion_path_match.group(1).strip() if conversion_path_match else ""
                
                website_match = re.search(r'Event Official Website:?\s*(.+)', block)
                event['Event Official Website'] = website_match.group(1).strip() if website_match else ""
                
                score_match = re.search(r'Conversion Score:?\s*(\d+)', block)
                event['Conversion Score'] = int(score_match.group(1)) if score_match else 0
                
                tradeshows.append(event)
        
        logger.info(f"Found {len(tradeshows)} tradeshows from Gemini API (call {call_id})")
        return tradeshows
        
    except Exception as e:
        logger.error(f"Error in call_gemini_api (call {call_id}): {str(e)}")
        logger.error(traceback.format_exc())
        return []


if __name__ == "__main__":
    # Use a dynamic port or default to 13306
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=13306, help='Port to run the server on')
    args = parser.parse_args()
    port = args.port
    print(f"Starting server on port {port}")
    app.run(debug=True, port=port)
