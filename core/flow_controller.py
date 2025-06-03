from typing import Dict, List, Optional, Any
import logging
import os
import random
import json
import httpx
import re
from pathlib import Path
from dotenv import load_dotenv
import sys
from datetime import datetime
# from voice_integration.question_engine import QuestionEngine
from core.question_engine import QuestionEngine
import traceback

# Import the website analyzer
from core.website_analyzer import analyze_website_with_browser as browser_analyze_website

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class FlowController:
    """Controls the multi-step B2B sales flow with enhanced personalization and signal interpretation"""

    _instance = None

    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = FlowController()
        return cls._instance

    def __init__(self):
        """Initialize the flow controller with enhanced personalization capabilities."""
        # Load API keys
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        logger.info(f"Loaded Gemini API key: {self.gemini_api_key[:10] if self.gemini_api_key else 'Not found'}")

        # User data
        self.current_product_line = ""
        self.current_sector = ""
        self.current_segment = ""
        self.keywords = []
        self.linkedin_consent = False
        self.zip_code = ""
        self.user_summary = ""  # Added user summary attribute
        self.selected_goals = []
        self.primary_goal = ""
        self.user_type = "founder"  # Default user type (founder or vc)
        self.website = ""
        self.current_image_data = None
        self.target_events_text = ""  # Store target events recommendation text
        
        # User information
        self.user_name = ""
        self.email = ""
        self.company_name = ""
        self.has_provided_user_info = False

        # VC-specific data
        self.vc_sector_focus = ""
        self.vc_investment_stage = ""
        self.vc_team_preferences = ""
        self.vc_traction_requirements = ""

        # Conversation memory with enhanced signal tracking
        self.conversation_memory = []
        self.context_summary = ""
        self.user_signals = {
            "interest_level": 0,  # 0-10 scale
            "pain_points": [],
            "objections": [],
            "positive_reactions": [],
            "engagement_metrics": {
                "questions_asked": 0,
                "detailed_responses": 0,
                "short_responses": 0,
                "skipped_questions": 0
            }
        }

        # Website analysis results for each step with improved categorization
        self.website_analysis_results = {}
        self.website_analysis_summary = {}

        # Demo/template mode flag: if True, always use ui_data.json as UI data
        self.demo_mode_use_ui_data_json = False  # Set to True for demo/template mode
        # Use latest timestamped data/ui_data_*.json as UI data
        self.use_latest_data_ui_json = False  # Allow backend to generate and save new UI data files

        # Optimized flow state with streamlined steps
        self.founder_steps = [
            'product',
            'event_interests',
            'market',
            'unique_value',
            'team_differentiation',
            'use_case',  # Removed pitch_strategy as it's often redundant with unique_value
            'company_size',
            'linkedin',
            'location',
            'complete'
        ]
        
        # Recruitment-focused flow with specialized questions
        self.recruitment_steps = [
            'product',
            'event_interests',
            'recruitment_roles',  # Specific roles they're trying to recruit
            'recruitment_details',  # More details about the roles (e.g., type of engineers)
            'company_culture',  # What makes their company attractive to candidates
            'recruitment_challenges',  # Specific challenges they face in recruiting
            'linkedin',
            'location',
            'complete'
        ]
        
        # Combined flow for users interested in both finding buyers and recruiting
        self.combined_steps = [
            'product',
            'event_interests',
            # Buyer-focused steps
            'market',
            'unique_value',
            'team_differentiation',
            # Recruitment-focused steps
            'recruitment_roles',
            'recruitment_details',
            'company_culture',
            # Common steps
            'company_size',
            'linkedin',
            'location',
            'complete'
        ]
        
        self.vc_steps = [
            'vc_sector_focus',
            'vc_investment_stage',
            'vc_team_preferences',
            'vc_traction_requirements',
            'linkedin',
            'location',
            'complete'
        ]
        
        # Use the appropriate step sequence based on user type
        self.steps = self.founder_steps
        
        # Flags for tracking user interests
        self.buyer_focus = False
        self.recruitment_focus = False

        # Initialize the question engine
        self.question_engine = QuestionEngine()

    async def is_url(self, text: str) -> bool:
        """Check if the given text is a URL."""
        # Check if it starts with http:// or https://
        if text.strip().startswith(("http://", "https://")):
            return True
        
        # Check if it looks like a domain name (contains a dot and no spaces)
        if "." in text and " " not in text.strip() and len(text.strip()) > 5:
            return True
            
        return False

    async def analyze_url_if_present(self, step: str, text: str) -> Optional[Dict[str, Any]]:
        """
        Check if the text is a URL and analyze it using the website analyzer.
        
        Args:
            step: The current step
            text: The text to check
            
        Returns:
            The website analysis results if the text is a URL, None otherwise
        """
        if not await self.is_url(text):
            return None
            
        # If it's a URL but doesn't start with http:// or https://, add https://
        url = text.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
            
        try:
            logger.info(f"{step} step contains URL: {url}. Analyzing website...")
            website_data = await browser_analyze_website(url)
            if website_data:
                logger.info(f"Website analysis successful for {url}")
                # Store the website analysis results for this step
                self.website_analysis_results[step] = website_data
                return website_data
            else:
                logger.warning(f"Website analysis failed for {url}")
                return None
        except Exception as e:
            logger.error(f"Error analyzing website in {step} step: {str(e)}")
            return None

    async def determine_next_step(self, current_step: str) -> str:
        """Determine the next step in the flow with enhanced personalization."""
        # If we're at the end of the flow, return 'complete'
        if current_step == 'complete':
            return 'complete'
            
        # Use the appropriate step sequence based on user type
        if self.user_type == "vc":
            steps_to_use = self.vc_steps
        else:
            steps_to_use = self.founder_steps
            
        # Update the current steps list
        self.steps = steps_to_use

        # Find the current step in the steps list
        try:
            current_index = steps_to_use.index(current_step)
        except ValueError:
            # If the current step is not in the list, start from the beginning
            return steps_to_use[0]

        # Temporarily disable skipping steps based on interest level
        # if self.user_signals["interest_level"] < 3 and current_index < len(steps_to_use) - 3:
        #     # If user shows low interest, skip to the essential steps (linkedin, location)
        #     return steps_to_use[-3]  # Return the third-to-last step
            
        # Return the next step
        if current_index < len(steps_to_use) - 1:
            return steps_to_use[current_index + 1]
        else:
            return 'complete'

    async def get_next_step(self, current_step: str) -> str:
        """Get the next step in the flow."""
        return await self.determine_next_step(current_step)

    async def get_question(self, step: str, previous_message: str = "") -> str:
        """Get the question for the current step."""
        try:
            # Get the context
            context = await self.get_context()

            # Generate the question using the question engine
            question = await self.question_engine.get_question(step, context, previous_message)
            return question
        except Exception as e:
            logger.error(f"Error generating question: {str(e)}")
            return f"Could you tell me more about your {step}?"

    async def get_follow_up_question(self, step: str, previous_answer: str, follow_up_count: int = 0, suggest_next: bool = False) -> str:
        """Get a follow-up question for the current step."""
        try:
            # Check if we should suggest moving to the next step
            if suggest_next:
                next_step = await self.get_next_step(step)
                next_step_name = {
                    'product': 'your target market',
                    'market': 'what makes your product unique',
                    'differentiation': 'your target company size',
                    'company_size': 'LinkedIn integration',
                    'linkedin': 'your location',
                    'location': 'completing your setup'
                }.get(next_step, 'the next step')

                return f"Thanks for that information. Would you like to add anything else or shall we move on to {next_step_name}?"

            # Check for signs of user impatience in the previous answer
            impatience_indicators = [
                "next", "continue", "move on", "skip", "enough", "done", "finish", "complete", "proceed"
            ]
            if any(indicator in previous_answer.lower() for indicator in impatience_indicators):
                return "Let's move on to the next step."

            # Get the context
            context = await self.get_context()

            # Generate the follow-up question using the question engine
            question = await self.question_engine.generate_follow_up_question(step, context, previous_answer, follow_up_count)
            return question
        except Exception as e:
            logger.error(f"Error generating follow-up question: {str(e)}")
            return "Can you tell me more about that?"

    async def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text.
        
        Args:
            text: The text to extract URLs from
            
        Returns:
            A list of URLs found in the text
        """
        # Common URL patterns
        url_patterns = [
            r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)',  # Standard URLs
            r'(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)'  # URLs without protocol
        ]
        
        urls = []
        for pattern in url_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Add https:// if missing
                url = match
                if not url.startswith(('http://', 'https://')):
                    url = f"https://{url}"
                urls.append(url)
        
        return urls

    async def store_answer(self, step: str, answer: str, image_data=None):
        """Store the user's answer with enhanced signal interpretation.

        Args:
            step: The current onboarding step
            answer: The user's text answer
            image_data: Optional image data uploaded by the user
        """
        logger.info(f"Storing answer for step {step}: text={bool(answer.strip())}, image={image_data is not None}")

        # Store the answer in the conversation memory
        memory_entry = {
            "step": step,
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        }

        # If image was provided, store that it was included (but not the actual data)
        has_image = False
        if image_data is not None and len(image_data) > 0:
            has_image = True
            memory_entry["image_included"] = True
            # Store the image data in a separate attribute
            self.current_image_data = image_data
            logger.info(f"Stored image data of {len(image_data)} bytes")

        self.conversation_memory.append(memory_entry)
        logger.info(f"Added memory entry for step {step}")

        # Analyze user signals from the answer
        await self._analyze_user_signals(step, answer)

        # Store the answer in the appropriate attribute based on the step
        # If answer is empty but image is provided, use a placeholder
        effective_answer = answer
        if answer.strip() == "" and image_data is not None:
            effective_answer = "[Image provided]"

        # Check if the answer is only a URL
        is_only_url = False
        if answer.strip().startswith(('http://', 'https://')) and ' ' not in answer.strip():
            is_only_url = True
            
        # Extract URLs from the answer and analyze them with improved website analysis
        urls = await self._extract_urls(effective_answer)
        website_data = None
        
        # Analyze the first URL found
        if urls:
            url = urls[0]
            logger.info(f"Found URL in {step} step: {url}. Analyzing website...")
            website_data = await browser_analyze_website(url)
            if website_data:
                logger.info(f"Website analysis successful for {url}")
                # Store the website analysis results for this step
                self.website_analysis_results[step] = website_data
                
                # If the answer is only a URL, store that information
                if is_only_url:
                    self.website_analysis_results[f"{step}_is_only_url"] = True
                    
                # Generate a summary of the website analysis for easier access
                await self._summarize_website_analysis(step, website_data)
            else:
                logger.warning(f"Website analysis failed for {url}")

        # Store the answer in the appropriate attribute based on the step with enhanced data extraction
        if step == "product":
            if website_data and website_data.get('title'):
                self.current_product_line = website_data.get('title')
            else:
                self.current_product_line = effective_answer
            self.user_type = "founder"  # Set user type to founder when product is provided
            # Update steps based on user type
            self.steps = self.founder_steps
        elif step == "event_interests":
            # Skip processing if the user skipped this question
            if effective_answer == "skipped":
                logger.info("User skipped event interests question")
                return
                
            # Parse the answer as JSON to get selected goals
            self.selected_goals = []
            try:
                # Try to parse as JSON
                import json
                self.selected_goals = json.loads(effective_answer)
                logger.info(f"Parsed selected goals from JSON: {self.selected_goals}")
            except json.JSONDecodeError:
                # Fall back to old format parsing
                logger.info(f"Failed to parse as JSON, trying old format: {effective_answer}")
                # Split by semicolon to separate goals and primary indicator
                parts = effective_answer.split(';')
                
                # Get selected goals
                if parts and parts[0]:
                    self.selected_goals = [goal.strip() for goal in parts[0].split(',')]
                    
                # Get primary goal if specified
                if len(parts) > 1 and parts[1].startswith('primary='):
                    self.primary_goal = parts[1].replace('primary=', '').strip()
                
            logger.info(f"Selected goals: {self.selected_goals}")
            logger.info(f"Primary goal: {self.primary_goal}")
            
            # Set focus flags based on selected goals
            self.buyer_focus = 'find_buyers' in self.selected_goals
            self.recruitment_focus = 'recruit_talent' in self.selected_goals
            
            # Store in user signals
            self.user_signals["selected_goals"] = self.selected_goals
            self.user_signals["primary_goal"] = self.primary_goal
            self.user_signals["buyer_focus"] = self.buyer_focus
            self.user_signals["recruitment_focus"] = self.recruitment_focus
            
            # Determine which flow to use based on selected options
            if self.buyer_focus and self.recruitment_focus:
                # If both buyer and recruitment focus, use the combined flow
                self.steps = self.combined_steps
                logger.info("Using combined flow for both buyer and recruitment focus")
            elif self.recruitment_focus:
                # If only recruitment focus, use the recruitment flow
                self.steps = self.recruitment_steps
                logger.info("Using recruitment-focused flow")
            else:
                # Default to founder flow
                self.steps = self.founder_steps
                logger.info("Using standard founder flow")
        elif step == "recruitment_roles":
            # Store the specific roles they're trying to recruit
            self.user_signals["recruitment_roles"] = effective_answer
        elif step == "recruitment_details":
            # Store the details about the roles
            self.user_signals["recruitment_details"] = effective_answer
        elif step == "company_culture":
            # Store information about company culture for recruitment
            self.user_signals["company_culture"] = effective_answer
        elif step == "recruitment_challenges":
            # Store recruitment challenges
            self.user_signals["recruitment_challenges"] = effective_answer
        elif step == "market":
            if website_data and website_data.get('industries') and len(website_data.get('industries')) > 0:
                # Use the first industry from website analysis
                self.current_sector = website_data.get('industries')[0]
            elif website_data and website_data.get('title'):
                self.current_sector = website_data.get('title')
            else:
                self.current_sector = effective_answer
        elif step == "company_size":
            if website_data and website_data.get('company_size'):
                self.current_segment = website_data.get('company_size')
            else:
                self.current_segment = effective_answer
        elif step == "linkedin":
            self.linkedin_consent = effective_answer.lower() in ["yes", "sure", "ok", "okay", "y", "yep", "yeah", "definitely", "absolutely"]
        elif step == "location":
            # Extract zip code if present in the answer
            zip_match = re.search(r'\b\d{5}(?:-\d{4})?\b', effective_answer)
            if zip_match:
                self.zip_code = zip_match.group(0)
            else:
                self.zip_code = effective_answer
        elif step == "website":
            self.website = effective_answer
        elif step == "vc_sector_focus":
            self.vc_sector_focus = effective_answer
            self.user_type = "vc"  # Set user type to VC when sector focus is provided
            # Update steps based on user type
            self.steps = self.vc_steps
        elif step == "vc_investment_stage":
            self.vc_investment_stage = effective_answer
        elif step == "vc_team_preferences":
            self.vc_team_preferences = effective_answer
        elif step == "vc_traction_requirements":
            self.vc_traction_requirements = effective_answer
        elif step == "unique_value":
            # Extract unique value from website data if available
            if website_data and website_data.get('unique_value'):
                self.context_summary = website_data.get('unique_value')
            else:
                self.context_summary = effective_answer
        elif step == "team_differentiation":
            self.context_summary += f" {effective_answer}"
        elif step == "use_case":
            self.context_summary += f" {effective_answer}"

        # Update the context summary with enhanced information
        await self.update_context_summary()

        # Update the keywords based on the new information with improved relevance
        await self.update_keywords()

    async def process_answer(self, step: str, answer: str) -> Dict[str, Any]:
        """Process the user's answer for the current step."""
        try:
            # Store the answer
            await self.store_answer(step, answer)

            # Get the next step
            next_step = await self.determine_next_step(step)

            # Generate the next question, passing the user's current answer as previous_message
            next_question = await self.get_question(next_step, answer)

            # Generate keywords if we have enough context
            keywords = []
            if len(self.conversation_memory) >= 2:  # At least product and market
                keywords = await self.clean_keywords()

            # Return the response
            return {
                'current_step': step,
                'next_step': next_step,
                'next_question': next_question,
                'keywords': keywords
            }

        except Exception as e:
            logger.error(f"Error processing answer: {str(e)}")
            return {
                'current_step': step,
                'next_step': 'error',
                'next_question': "I'm sorry, there was an error processing your answer. Could you try again?",
                'keywords': []
            }

    async def update_context_summary(self):
        """Update the context summary based on the conversation memory."""
        # Reset the context summary
        self.context_summary = ""

        # Add each memory entry to the context summary
        for item in self.conversation_memory:
            # Skip entries without a step or answer
            if 'step' not in item or 'answer' not in item:
                continue

            # Append the step and answer to the context summary
            self.context_summary += f"{item['step']}: {item['answer']}\n"

        logger.info(f"Updated context summary: {self.context_summary}")

    async def update_keywords(self):
        """Update the keywords based on the new information."""
        # Get the current context
        context = await self.get_context()

        # Collect all website analysis results
        website_data = {}
        
        # First check if we have any website analysis results from any step
        for step, data in self.website_analysis_results.items():
            if data:
                website_data = data
                break
                
        # If no website data from steps, check if there's a website URL in the context
        if not website_data:
            website_url = context.get('website', '')
            
            if website_url and len(website_url) > 5:
                # If we have a website URL, analyze it using the browser-based website analyzer
                logger.info(f"Analyzing website for keywords: {website_url}")

                # Use the browser-based website analyzer if available
                use_browser = True

                if use_browser:
                    logger.info(f"Using browser-based website analyzer for keywords: {website_url}")
                    website_data = await browser_analyze_website(website_url)

                    if not website_data:
                        logger.warning(f"Browser-based website analysis failed for keywords, falling back to curl-based analyzer")
                        # Fall back to the question engine's analyze_website_with_browser method
                        website_data = await self.question_engine.analyze_website_with_browser(website_url)
                else:
                    # Use the question engine's analyze_website_with_browser method
                    website_data = await self.question_engine.analyze_website_with_browser(website_url)

        # Use different prompts based on user type
        if self.user_type == "founder":
            # Founder prompt
            prompt = f"""
            You are a B2B sales assistant helping to generate relevant keywords for targeting.

            Current context:
            - Product/Service: {context.get('product', '')}
            - Target Market: {context.get('market', '')}
            - Company Size: {context.get('company_size', '')}
            - Differentiation: {context.get('differentiation', '')}
            """

            # Add website data if available
            if website_data:
                prompt += f"""
                Website Title: {website_data.get('title', '')}
                Website Description: {website_data.get('description', '')}
                Website Headings: {', '.join(website_data.get('headings', []))}
                """

                # If this is an industries page, include the industries
                if 'industries' in website_data and website_data['industries']:
                    prompt += f"Industries: {', '.join(website_data['industries'])}\n"

            prompt += """
            Based on this information, generate a list of 15 keywords that would be most relevant for this company's B2B sales targeting. These should be specific phrases that potential customers might search for.

            Format your response as a JSON array of strings, like this:
            [
              "keyword 1",
              "keyword 2",
              ...
            ]
            """
        else:  # VC prompt
            prompt = f"""
            You are a B2B sales assistant helping to generate relevant keywords for targeting.

            Current context:
            - Sector Focus: {context.get('sector_focus', '')}
            - Investment Stage: {context.get('investment_stage', '')}
            - Team Preferences: {context.get('team_preferences', '')}
            - Traction Requirements: {context.get('traction_requirements', '')}
            """

            prompt += """
            Based on this information, generate a list of 15 keywords that would be most relevant for this VC's investment interests. These should be specific phrases that startups or entrepreneurs might search for.

            Format your response as a JSON array of strings, like this:
            [
              "keyword 1",
              "keyword 2",
              ...
            ]
            """

        try:
            # Use the Gemini API to generate keywords
            if self.gemini_api_key:
                logger.info(f"Generating keywords with prompt for {self.user_type} user type")
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"

                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.2,
                        "topP": 0.8,
                        "topK": 40,
                        "maxOutputTokens": 1024
                    }
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(gemini_url, json=payload)
                    response.raise_for_status()
                    data = response.json()

                    if "candidates" in data and len(data["candidates"]) > 0:
                        candidate = data["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            keywords_text = candidate["content"]["parts"][0]["text"]
                            logger.info(f"Original API response: {keywords_text}")

                            # Clean up the response for JSON parsing
                            cleaned_text = keywords_text.strip()
                            
                            # Method 1: Try to extract a JSON array
                            # Find the first [ and last ] to extract the JSON array
                            json_start = cleaned_text.find("[")
                            json_end = cleaned_text.rfind("]")
                            
                            if json_start != -1 and json_end != -1 and json_end > json_start:
                                json_text = cleaned_text[json_start:json_end + 1]
                                logger.info(f"Extracted JSON array: {json_text}")
                                
                                try:
                                    # Try to parse the JSON array
                                    keywords = json.loads(json_text)
                                    if isinstance(keywords, list) and len(keywords) > 0:
                                        logger.info(f"Successfully parsed keywords from JSON: {keywords}")
                                        # Shuffle the keywords to randomize the order
                                        random.shuffle(keywords)
                                        self.keywords = keywords
                                        logger.info(f"Updated keywords: {self.keywords}")
                                    else:
                                        raise ValueError("Parsed JSON is not a non-empty list")
                                except (json.JSONDecodeError, ValueError) as e:
                                    logger.error(f"Error parsing JSON array: {str(e)}")
                                    # Continue to fallback methods
                            else:
                                logger.warning("Could not find JSON array markers [ and ] in response")
                            
                            # Method 2: If JSON parsing failed, try regex to extract quoted strings
                            if not self.keywords:
                                # Try to extract keywords using regex as a fallback
                                keyword_matches = re.findall(r'"([^"]+)"', cleaned_text)
                                if keyword_matches and len(keyword_matches) > 0:
                                    logger.info(f"Extracted {len(keyword_matches)} keywords using regex: {keyword_matches}")
                                    random.shuffle(keyword_matches)
                                    self.keywords = keyword_matches
                                    logger.info(f"Updated keywords using regex: {self.keywords}")
                                else:
                                    logger.warning("Failed to extract keywords using regex")
                            
                            # Method 3: If both methods failed, extract keywords from the text directly
                            if not self.keywords:
                                # Split the text by newlines and look for lines that might be keywords
                                lines = cleaned_text.split('\n')
                                potential_keywords = []
                                
                                for line in lines:
                                    # Remove common list markers and whitespace
                                    cleaned_line = re.sub(r'^[\s\d\-\*\•\.\)]+', '', line).strip()
                                    
                                    # Skip empty lines or very short words
                                    if len(cleaned_line) > 3 and not cleaned_line.startswith(('```', '###', '##', '#')):
                                        # Remove any trailing punctuation
                                        cleaned_line = re.sub(r'[,.;:!?]+$', '', cleaned_line)
                                        
                                        # If the line contains a colon, take only the part before the colon
                                        if ':' in cleaned_line and not cleaned_line.startswith('http'):
                                            cleaned_line = cleaned_line.split(':', 1)[0].strip()
                                        
                                        if cleaned_line and len(cleaned_line) <= 50:  # Reasonable keyword length
                                            potential_keywords.append(cleaned_line)
                                
                                if potential_keywords:
                                    logger.info(f"Extracted {len(potential_keywords)} keywords from text: {potential_keywords}")
                                    random.shuffle(potential_keywords)
                                    self.keywords = potential_keywords[:15]  # Limit to 15 keywords
                                    logger.info(f"Updated keywords from text: {self.keywords}")
                                else:
                                    logger.warning("Failed to extract keywords from text")
                            
                            # Method 4: Last resort - generate some default keywords based on context
                            if not self.keywords:
                                logger.warning("All keyword extraction methods failed, using default keywords")
                                default_keywords = []
                                
                                # Extract words from context to use as keywords
                                context_text = ""
                                if self.user_type == "founder":
                                    context_text = f"{context.get('product', '')} {context.get('market', '')}"
                                else:  # VC
                                    context_text = f"{context.get('sector_focus', '')} {context.get('investment_stage', '')}"
                                
                                # Extract words that might be good keywords
                                words = re.findall(r'\b[A-Za-z][A-Za-z\-]{2,}\b', context_text)
                                unique_words = list(set([w.lower() for w in words if len(w) > 3]))
                                
                                if unique_words:
                                    default_keywords = unique_words[:10]  # Limit to 10 keywords
                                
                                # Add some generic keywords based on user type
                                if self.user_type == "founder":
                                    default_keywords.extend(["startup", "innovation", "technology", "software", "business"])
                                else:  # VC
                                    default_keywords.extend(["investment", "venture capital", "startup", "funding", "technology"])
                                
                                self.keywords = default_keywords
                                logger.info(f"Using default keywords: {self.keywords}")
                    else:
                        logger.error("Unexpected response format from Gemini API")
            else:
                logger.warning("Gemini API key not found, skipping keyword generation")

            logger.info(f"Updated keywords: {self.keywords}")
            return self.keywords
        except Exception as e:
            logger.error(f"Error updating keywords: {str(e)}")
            return self.keywords

    async def clean_keywords(self, max_keywords=25):
        """Clean and return the keywords."""
        # If we don't have any keywords, generate them
        if not self.keywords:
            await self.update_keywords()

        # Return the keywords, limited to max_keywords
        return self.keywords[:max_keywords]

    async def generate_user_summary(self, max_words=None):
        """Generate a concise summary about the user and their product."""
        try:
            context = await self.get_context()
            
            # Add website analysis results to the context
            for step, data in self.website_analysis_results.items():
                if data:
                    context[f"website_analysis_{step}"] = data
            
            # Add the previous user summary to the context if it exists
            if self.user_summary:
                context['previous_user_summary'] = self.user_summary
                
            # Generate a new summary using the question engine
            summary = await self.question_engine.generate_user_summary(context, max_words=None)

            # Only update user_summary if we got a non-empty response
            if summary:
                self.user_summary = summary
                logger.info(f"Generated user summary: {summary}")
            else:
                logger.warning("Received empty user summary from question engine")
                # Keep the existing summary if we have one
                if not self.user_summary:
                    # Create a basic summary from context if we don't have one
                    product = context.get('product', '')
                    market = context.get('market', '')
                    if product and market:
                        self.user_summary = f"A company building {product} for the {market} market."
                        logger.info(f"Created basic user summary: {self.user_summary}")
            return self.user_summary
        except Exception as e:
            logger.error(f"Error generating user summary: {str(e)}")
            return self.user_summary

    async def get_context(self):
        """Get the current context as a dictionary."""
        context = {}

        if self.user_type == "founder":
            # Founder-specific context
            context = {
                'product': self.current_product_line,
                'market': self.current_sector,
                'company_size': self.current_segment,
                'differentiation': self.context_summary,
                'linkedin': 'Yes' if self.linkedin_consent else 'No',
                'location': self.zip_code,
                'website': self.website
            }

            # Include image data if available
            if self.current_image_data is not None:
                context['image_data'] = self.current_image_data
        else:  # VC context
            context = {
                'sector_focus': self.vc_sector_focus,
                'investment_stage': self.vc_investment_stage,
                'team_preferences': self.vc_team_preferences,
                'traction_requirements': self.vc_traction_requirements,
                'linkedin': 'Yes' if self.linkedin_consent else 'No',
                'location': self.zip_code
            }

        # Add website analysis results to the context
        for step, data in self.website_analysis_results.items():
            if data:
                context[f"website_analysis_{step}"] = data

        return context

    async def get_completeness_score(self):
        """Calculate a completeness score for the onboarding process."""
        # Define critical and optional fields based on user type
        critical_fields = {}
        optional_fields = {}

        if self.user_type == "vc":
            critical_fields = {
                'vc_sector_focus': self.vc_sector_focus,
                'vc_investment_stage': self.vc_investment_stage
            }
            optional_fields = {
                'vc_team_preferences': self.vc_team_preferences,
                'vc_traction_requirements': self.vc_traction_requirements
            }
        else:  # founder
            critical_fields = {
                'product': self.current_product_line,
                'market': self.current_sector
            }
            optional_fields = {
                'differentiation': self.context_summary,
                'company_size': self.current_segment
            }

        # Calculate completeness score
        critical_score = sum(1 for value in critical_fields.values() if value) / len(critical_fields)
        optional_score = sum(0.5 for value in optional_fields.values() if value) / max(1, len(optional_fields))

        # Combine scores (critical fields are weighted more heavily)
        total_score = (critical_score * 0.7) + (optional_score * 0.3)
        return min(1.0, total_score)  # Cap at 1.0

    async def get_flow_status(self):
        """Get the current status of the flow."""
        return {
            'user_type': self.user_type,
            'completeness': await self.get_completeness_score(),
            'keywords': await self.clean_keywords(),
            'user_summary': self.user_summary
        }

    async def reset(self):
        """Reset the flow controller to its initial state."""
        self.__init__()
        return {"success": True, "message": "Flow controller reset successfully"}
        
    async def save_user_info(self, user_name: str, email: str, company_name: str = ""):
        """Save user information.
        
        Args:
            user_name: User's name
            email: User's email address
            company_name: User's company name (optional)
            
        Returns:
            Dictionary with success status and message
        """
        self.user_name = user_name
        self.email = email
        self.company_name = company_name
        self.has_provided_user_info = True
        
        logger.info(f"Saved user information: {user_name}, {email}, {company_name}")
        
        return {
            "success": True,
            "message": "User information saved successfully"
        }
        
    async def get_user_info(self):
        """Get user information.
        
        Returns:
            Dictionary with user information
        """
        return {
            "user_name": self.user_name,
            "email": self.email,
            "company_name": self.company_name,
            "has_provided_user_info": self.has_provided_user_info
        }
        
    async def _analyze_user_signals(self, step: str, answer: str):
        """
        Analyze user signals from their answer to better personalize the experience.
        
        Args:
            step: The current step
            answer: The user's answer
        """
        try:
            # Update engagement metrics
            if len(answer.strip()) < 10:
                self.user_signals["engagement_metrics"]["short_responses"] += 1
            elif len(answer.strip()) > 100:
                self.user_signals["engagement_metrics"]["detailed_responses"] += 1
                
            # Check for questions in the answer
            if "?" in answer:
                self.user_signals["engagement_metrics"]["questions_asked"] += 1
                
            # Check for skip indicators
            skip_indicators = ["skip", "next", "move on", "don't know", "not sure", "later"]
            if any(indicator in answer.lower() for indicator in skip_indicators):
                self.user_signals["engagement_metrics"]["skipped_questions"] += 1
                
            # Analyze sentiment and extract signals using Gemini if available
            if self.gemini_api_key and len(answer.strip()) > 20:
                await self._analyze_sentiment_with_llm(step, answer)
            else:
                # Simple rule-based signal extraction
                self._extract_signals_rule_based(answer)
                
            # Calculate interest level based on engagement metrics
            engagement_score = (
                self.user_signals["engagement_metrics"]["detailed_responses"] * 2 +
                self.user_signals["engagement_metrics"]["questions_asked"] * 1.5 -
                self.user_signals["engagement_metrics"]["short_responses"] * 0.5 -
                self.user_signals["engagement_metrics"]["skipped_questions"] * 1
            )
            
            # Normalize to 0-10 scale
            self.user_signals["interest_level"] = min(10, max(0, engagement_score))
            
            logger.info(f"Updated user signals: interest_level={self.user_signals['interest_level']}")
            
        except Exception as e:
            logger.error(f"Error analyzing user signals: {str(e)}")
    
    async def _analyze_sentiment_with_llm(self, step: str, answer: str):
        """
        Use Gemini to analyze sentiment and extract signals from user's answer.
        
        Args:
            step: The current step
            answer: The user's answer
        """
        try:
            prompt = f"""
            Analyze the following user response to a question about their {step}:
            
            "{answer}"
            
            Extract the following information:
            1. Overall sentiment (positive, neutral, negative)
            2. Any pain points or challenges mentioned
            3. Any objections or hesitations
            4. Any positive reactions or enthusiasm
            
            Format your response as a JSON object with these fields.
            """
            
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "topP": 0.8,
                    "topK": 40,
                    "maxOutputTokens": 1024
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(gemini_url, json=payload)
                response.raise_for_status()
                data = response.json()
                
                if "candidates" in data and len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        analysis_text = candidate["content"]["parts"][0]["text"]
                        
                        # Try to extract JSON from the response
                        json_match = re.search(r'```json\s*(.*?)\s*```', analysis_text, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(1)
                        else:
                            # If no JSON code block, try to use the whole response
                            json_str = analysis_text
                        
                        try:
                            analysis = json.loads(json_str)
                            
                            # Update user signals based on analysis
                            if "pain_points" in analysis and analysis["pain_points"]:
                                for pain_point in analysis["pain_points"]:
                                    if pain_point and pain_point not in self.user_signals["pain_points"]:
                                        self.user_signals["pain_points"].append(pain_point)
                                        
                            if "objections" in analysis and analysis["objections"]:
                                for objection in analysis["objections"]:
                                    if objection and objection not in self.user_signals["objections"]:
                                        self.user_signals["objections"].append(objection)
                                        
                            if "positive_reactions" in analysis and analysis["positive_reactions"]:
                                for reaction in analysis["positive_reactions"]:
                                    if reaction and reaction not in self.user_signals["positive_reactions"]:
                                        self.user_signals["positive_reactions"].append(reaction)
                                        
                            # Adjust interest level based on sentiment
                            if "sentiment" in analysis:
                                if analysis["sentiment"] == "positive":
                                    self.user_signals["interest_level"] += 1
                                elif analysis["sentiment"] == "negative":
                                    self.user_signals["interest_level"] -= 1
                                    
                            logger.info(f"Updated user signals from LLM analysis: {self.user_signals}")
                            
                        except json.JSONDecodeError:
                            logger.error("Failed to parse JSON from Gemini's response")
                
        except Exception as e:
            logger.error(f"Error analyzing sentiment with LLM: {str(e)}")
    
    def _extract_signals_rule_based(self, answer: str):
        """
        Extract signals from user's answer using simple rule-based approach.
        
        Args:
            answer: The user's answer
        """
        try:
            # Convert to lowercase for easier matching
            lower_answer = answer.lower()
            
            # Check for pain points
            pain_indicators = ["challenge", "problem", "difficult", "struggle", "pain", "issue", "worry", "concerned"]
            for indicator in pain_indicators:
                if indicator in lower_answer:
                    # Extract the sentence containing the pain point
                    sentences = re.split(r'[.!?]+', answer)
                    for sentence in sentences:
                        if indicator in sentence.lower():
                            pain_point = sentence.strip()
                            if pain_point and pain_point not in self.user_signals["pain_points"]:
                                self.user_signals["pain_points"].append(pain_point)
            
            # Check for objections
            objection_indicators = ["but ", "however", "not sure", "expensive", "costly", "not convinced", "doubt"]
            for indicator in objection_indicators:
                if indicator in lower_answer:
                    # Extract the sentence containing the objection
                    sentences = re.split(r'[.!?]+', answer)
                    for sentence in sentences:
                        if indicator in sentence.lower():
                            objection = sentence.strip()
                            if objection and objection not in self.user_signals["objections"]:
                                self.user_signals["objections"].append(objection)
            
            # Check for positive reactions
            positive_indicators = ["great", "excellent", "amazing", "love", "excited", "interested", "perfect", "awesome"]
            for indicator in positive_indicators:
                if indicator in lower_answer:
                    # Extract the sentence containing the positive reaction
                    sentences = re.split(r'[.!?]+', answer)
                    for sentence in sentences:
                        if indicator in sentence.lower():
                            reaction = sentence.strip()
                            if reaction and reaction not in self.user_signals["positive_reactions"]:
                                self.user_signals["positive_reactions"].append(reaction)
                                
            logger.info(f"Extracted signals using rule-based approach: {self.user_signals}")
            
        except Exception as e:
            logger.error(f"Error extracting signals with rule-based approach: {str(e)}")
    
    async def _summarize_website_analysis(self, step: str, website_data: Dict[str, Any]):
        """
        Generate a summary of website analysis results for easier access.
        
        Args:
            step: The current step
            website_data: The website analysis results
        """
        try:
            # Create a summary of the most important information
            summary = {
                "title": website_data.get("title", ""),
                "description": website_data.get("description", ""),
                "industries": website_data.get("industries", []),
                "target_audience": website_data.get("target_audience", ""),
                "unique_value": website_data.get("unique_value", ""),
                "company_size": website_data.get("company_size", "")
            }
            
            # Store the summary
            self.website_analysis_summary[step] = summary
            
            logger.info(f"Generated website analysis summary for {step}: {summary}")
            
        except Exception as e:
            logger.error(f"Error summarizing website analysis: {str(e)}")
    
    async def record_user_journey(self, action: str, details: dict = None):
        """Record a step in the user journey with enhanced tracking.
        
        Args:
            action: The action being recorded (e.g., 'question_answered', 'event_bookmarked')
            details: Additional details about the action
            
        Returns:
            Dictionary with success status
        """
        if not self.email:
            logger.warning("Attempted to record user journey without email")
            return {"success": False, "error": "No email associated with this session"}
            
        # Create journey entry with enhanced data
        journey_entry = {
            "timestamp": datetime.now().isoformat(),
            "email": self.email,
            "user_name": self.user_name,
            "action": action,
            "user_signals": self.user_signals,
            "completeness_score": await self.get_completeness_score()
        }
        
        # Log the journey entry
        logger.info(f"User journey recorded: {journey_entry}")
        
        # Save to a JSON file in the data/user_journey directory
        try:
            # Create the user_journey directory if it doesn't exist
            # Use hardcoded path to ensure data is saved to the correct location
            user_journey_dir = Path("/Users/carol.zhu/Documents/network_ai_0425_updated/data/user_journey")
            user_journey_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a filename based on email
            email_filename = self.email.replace("@", "_at_").replace(".", "_dot_")
            file_path = user_journey_dir / f"{email_filename}.json"
            
            # Check if file already exists
            if file_path.exists():
                # Load existing data
                try:
                    with open(file_path, 'r') as f:
                        user_data = json.load(f)
                except json.JSONDecodeError:
                    # If file is corrupted, create new data
                    user_data = {
                        "user_info": {},
                        "journey_data": {},
                        "interest_level": "low"
                    }
            else:
                # Create new data structure
                user_data = {
                    "user_info": {},
                    "journey_data": {},
                    "interest_level": "low"
                }
            
            # Update user info
            user_data["user_info"] = {
                "user_name": self.user_name,
                "email": self.email,
                "company_name": self.company_name,
                "has_provided_user_info": self.has_provided_user_info
            }
            
            # Update journey data (only essential fields)
            user_data["journey_data"] = {
                "user_type": self.user_type,
                "product": self.current_product_line,
                "market": self.current_sector,
                "company_size": self.current_segment,
                "last_action": action,
                "last_action_details": details or {},
                "timestamp": datetime.now().isoformat()
            }
            
            # Quick interest level calculation
            interest_score = (2 if self.has_provided_user_info else 0) + \
                            (1 if self.current_product_line else 0) + \
                            (1 if self.current_sector else 0) + \
                            (1 if self.website_analysis_results else 0) + \
                            (1 if len(self.conversation_memory) > 3 else 0)
            
            if interest_score >= 5:
                user_data["interest_level"] = "high"
            elif interest_score >= 3:
                user_data["interest_level"] = "medium"
            else:
                user_data["interest_level"] = "low"
            
            # Save the data to a JSON file (without pretty printing)
            with open(file_path, 'w') as f:
                json.dump(user_data, f)
                
            return {"success": True, "message": "User data saved successfully"}
        except Exception as e:
            logger.error(f"Error saving user data: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def generate_target_events_recommendation(self):
        import traceback
        logger.info(f"website_analysis_results: {getattr(self, 'website_analysis_results', None)}")
        if hasattr(self, 'website_analysis_results'):
            logger.info(f"website_analysis_results['ui_data']: {self.website_analysis_results.get('ui_data', None)}")
        """Generate a recommendation for target events based on business profile and goals."""
        try:
            # FE DEMO: If use_latest_data_ui_json is True, load the most recent data/ui_data_*.json
            if getattr(self, 'use_latest_data_ui_json', False):
                import glob, os, re
                data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
                # Try to get company name from self.company_name, self.current_product_line, or self.website_analysis_results
                company = getattr(self, 'company_name', None)
                if not company:
                    company = getattr(self, 'current_product_line', None)
                if not company and hasattr(self, 'website_analysis_results') and self.website_analysis_results:
                    company = self.website_analysis_results.get('company_name') or self.website_analysis_results.get('title')
                if not company:
                    company = 'unknown'
                company_safe = re.sub(r'[^a-zA-Z0-9_-]', '_', str(company))[:32]
                # Find files matching this company
                pattern = os.path.join(data_dir, f'ui_data_{company_safe}_*.json')
                files = sorted(glob.glob(pattern), reverse=True)
                if not files:
                    # Fallback to any file
                    files = sorted(glob.glob(os.path.join(data_dir, 'ui_data_*.json')), reverse=True)
                if files:
                    latest_file = files[0]
                    try:
                        with open(latest_file, 'r') as f:
                            ui_data = json.load(f)
                        logger.info(f"Loaded UI data from {latest_file} (FE demo mode)")
                        # Merge with minimal fallback structure and hardcoded visibility_notice
                        fallback = {
                            "multi_factor_analysis": {"customer_analysis": "", "market_growth": ""},
                            "key_differentiators": [],
                            "target_customers": [],
                            "who_to_target": [],
                            "event_strategies": {},
                            "specific_events": [],
                            "keywords": [],
                            "business_profile": {
                                "description": ""
                            }
                        }
                        # Merge generated ui_data with fallback
                        def merge(d, f):
                            for k, v in f.items():
                                if k not in d or d[k] in (None, ""):
                                    d[k] = v
                                elif isinstance(v, dict) and isinstance(d[k], dict):
                                    merge(d[k], v)
                            return d
                        merged_ui_data = merge(dict(ui_data), fallback)
                        self.website_analysis_results['ui_data'] = merged_ui_data
                        return merged_ui_data
                    except Exception as e:
                        logger.error(f"Failed to load {latest_file} in FE demo mode: {e}")
                else:
                    logger.warning("No ui_data_*.json files found in data/ directory for FE demo mode")
            # DEMO MODE: If demo_mode_use_ui_data_json is True, always load from ui_data.json
            if getattr(self, 'demo_mode_use_ui_data_json', False):
                try:
                    with open('core/ui_data.json', 'r') as f:
                        ui_data = json.load(f)
                    logger.info("Loaded UI data from ui_data.json (demo mode)")
                    self.website_analysis_results['ui_data'] = ui_data
                    return ui_data
                except Exception as e:
                    logger.error(f"Failed to load ui_data.json in demo mode: {e}")

            # If we have website analysis results with UI data, use that
            if (hasattr(self, 'website_analysis_results') and 
                self.website_analysis_results and 
                'ui_data' in self.website_analysis_results and 
                self.website_analysis_results['ui_data']):
                ui_data = self.website_analysis_results['ui_data']
                # Extract event strategies from UI data
                if 'event_strategies' in ui_data:
                    strategies = ui_data['event_strategies']
                    # Build formatted response from structured data
                    response_parts = []
                    # Add who to target section
                    if 'who_to_target' in ui_data:
                        response_parts.append("WHO TO TARGET:")
                        for target in ui_data['who_to_target']:
                            response_parts.append(f"• {target.get('group_title', '')}: {target.get('group_detail', '')}")
                        response_parts.append("")
                    # Add goal-specific strategies
                    for goal_key, strategy in strategies.items():
                        if isinstance(strategy, dict) and 'goal_title' in strategy:
                            response_parts.append(f"{strategy['goal_title']}:")
                            # Handle the new simplified format with 'strategy' field
                            if 'strategy' in strategy:
                                response_parts.append(f"• {strategy['strategy']}")
                            # Fallback to old format with 'event_types' if present
                            elif 'event_types' in strategy:
                                for event_type in strategy['event_types']:
                                    if isinstance(event_type, dict):
                                        response_parts.append(f"• {event_type.get('type_title', '')}")
                                        response_parts.append(f"  {event_type.get('why_works', '')}")
                            response_parts.append("")
                    # Store the formatted text for backward compatibility
                    self.target_events_text = "\n".join(response_parts)
                    # Return the full UI data structure
                    return ui_data

            # If ui_data is missing, try to generate it using enhanced analyzer
            website_url = getattr(self, 'website', None)
            if website_url:
                try:
                    from core.optimized_analyzer import analyze_website_with_ui_data_parallel
                    result = await analyze_website_with_ui_data_parallel(website_url)
                    if result and 'ui_data' in result and result['ui_data']:
                        self.website_analysis_results['ui_data'] = result['ui_data']
                        logger.info("Generated UI data using enhanced analyzer and assigned to website_analysis_results['ui_data']")
                        return result['ui_data']
                except Exception as e:
                    logger.error(f"Failed to generate UI data using enhanced analyzer: {e}")

            # Fallback to loading ui_data.json if still no UI data
            try:
                with open('core/ui_data.json', 'r') as f:
                    ui_data = json.load(f)
                logger.info("Loaded UI data from ui_data.json as fallback")
                self.website_analysis_results['ui_data'] = ui_data
                return ui_data
            except Exception as e:
                logger.error(f"Failed to load ui_data.json as fallback: {e}")

            # Fallback to basic recommendation if no structured data
            primary_goal = self.primary_goal if hasattr(self, 'primary_goal') else ""
            if not primary_goal and hasattr(self, 'selected_goals') and self.selected_goals:
                primary_goal = self.selected_goals[0]
            # Create fallback UI data structure based on primary goal
            fallback_text = ""
            if primary_goal == "find_buyers":
                fallback_text = "Based on your goal of finding buyers, we recommend focusing on industry-specific trade shows and conferences where potential customers gather."
            elif primary_goal == "recruit_talent": 
                fallback_text = "For recruiting talent, we recommend targeting tech job fairs, university career events, and industry-specific networking meetups."
            elif primary_goal == "business_partners":
                fallback_text = "To find business partners, focus on industry conferences, partnership-focused events, and ecosystem gatherings."
            elif primary_goal == "investors":
                fallback_text = "For connecting with investors, target startup pitch events, investor showcases, and industry-specific venture capital gatherings."
            else:
                fallback_text = "We recommend focusing on industry-specific events where you can connect with potential customers, partners, and talent."
            
            # Store the fallback text for backward compatibility
            self.target_events_text = fallback_text
            
            # Create a minimal UI data structure with the fallback text
            fallback_ui_data = {
                "target_events_text": fallback_text,
                "who_to_target": [
                    {"group_title": "Industry Professionals", "group_detail": "Focus on decision-makers in your target market"},
                    {"group_title": "Potential Customers", "group_detail": "Connect with individuals who have a need for your product or service"}
                ],
                "event_strategies": {
                    "find_buyers": {
                        "goal_title": "For Finding Buyers/Users",
                        "goal_icon": "💰",
                        "strategy": "Attend industry-specific trade shows and conferences where potential customers gather."
                    },
                    "business_partners": {
                        "goal_title": "For Meeting Business Partners",
                        "goal_icon": "🤝",
                        "strategy": "Participate in conferences and integration events to connect with potential partners."
                    },
                    "recruit_talent": {
                        "goal_title": "For Recruiting Talent",
                        "goal_icon": "👥",
                        "strategy": "Attend university career fairs and industry meetups to connect with professionals."
                    },
                    "investors": {
                        "goal_title": "For Connecting with Investors",
                        "goal_icon": "💼",
                        "strategy": "Participate in venture capital conferences and pitch events."
                    },
                    "networking": {
                        "goal_title": "For General Networking",
                        "goal_icon": "🌐",
                        "strategy": "Join industry mixers and professional meetups to build relationships."
                    }
                },
                "specific_events": [
                    {
                        "title": "Industry Conference 2025",
                        "meta": "April 2025 • San Francisco, CA • Conference",
                        "description": "A major gathering of industry professionals where you can showcase your products and services.",
                        "primary_goal": "find_buyers"
                    },
                    {
                        "title": "Tech Expo 2025",
                        "meta": "June 2025 • New York, NY • Expo",
                        "description": "A large technology exhibition with opportunities for networking and partnership building.",
                        "primary_goal": "business_partners"
                    },
                    {
                        "title": "Industry Summit 2025",
                        "meta": "September 2025 • Chicago, IL • Summit",
                        "description": "A focused gathering of industry leaders and decision-makers.",
                        "primary_goal": "networking"
                    }
                ],
                "multi_factor_analysis": {
                    "customer_analysis": "Analysis based on available information about your target market.",
                    "market_growth": "General market trends and growth opportunities in your industry."
                },
                "key_differentiators": [
                    {"icon": "💡", "text": "Your unique value proposition"},
                    {"icon": "⚡", "text": "Your technological advantages"},
                    {"icon": "🌍", "text": "Your market reach"},
                    {"icon": "🎭", "text": "Your innovation capabilities"}
                ]
            }
            
            return fallback_ui_data
                    
        except Exception as e:
            logger.error(f"Error generating target events recommendation: {str(e)}")
            fallback_text = "We recommend focusing on industry-specific events where you can connect with potential customers, partners, and talent."
            self.target_events_text = fallback_text
            
            # Create a minimal UI data structure with the error fallback text
            error_fallback_ui_data = {
                "target_events_text": fallback_text,
                "who_to_target": [
                    {"group_title": "Industry Professionals", "group_detail": "Focus on decision-makers in your target market"},
                    {"group_title": "Potential Customers", "group_detail": "Connect with individuals who have a need for your product or service"}
                ],
                "event_strategies": {
                    "find_buyers": {
                        "goal_title": "For Finding Buyers/Users",
                        "goal_icon": "💰",
                        "strategy": "Attend industry-specific trade shows and conferences where potential customers gather."
                    },
                    "business_partners": {
                        "goal_title": "For Meeting Business Partners",
                        "goal_icon": "🤝",
                        "strategy": "Participate in conferences and integration events to connect with potential partners."
                    },
                    "recruit_talent": {
                        "goal_title": "For Recruiting Talent",
                        "goal_icon": "👥",
                        "strategy": "Attend university career fairs and industry meetups to connect with professionals."
                    },
                    "investors": {
                        "goal_title": "For Connecting with Investors",
                        "goal_icon": "💼",
                        "strategy": "Participate in venture capital conferences and pitch events."
                    },
                    "networking": {
                        "goal_title": "For General Networking",
                        "goal_icon": "🌐",
                        "strategy": "Join industry mixers and professional meetups to build relationships."
                    }
                },
                "specific_events": [
                    {
                        "title": "Industry Conference 2025",
                        "meta": "April 2025 • San Francisco, CA • Conference",
                        "description": "A major gathering of industry professionals where you can showcase your products and services.",
                        "primary_goal": "find_buyers"
                    },
                    {
                        "title": "Tech Expo 2025",
                        "meta": "June 2025 • New York, NY • Expo",
                        "description": "A large technology exhibition with opportunities for networking and partnership building.",
                        "primary_goal": "business_partners"
                    },
                    {
                        "title": "Industry Summit 2025",
                        "meta": "September 2025 • Chicago, IL • Summit",
                        "description": "A focused gathering of industry leaders and decision-makers.",
                        "primary_goal": "networking"
                    }
                ],
                "multi_factor_analysis": {
                    "customer_analysis": "Analysis based on available information about your target market.",
                    "market_growth": "General market trends and growth opportunities in your industry."
                },
                "key_differentiators": [
                    {"icon": "💡", "text": "Your unique value proposition"},
                    {"icon": "⚡", "text": "Your technological advantages"},
                    {"icon": "🌍", "text": "Your market reach"},
                    {"icon": "🎭", "text": "Your innovation capabilities"}
                ]
            }
            
            return error_fallback_ui_data

        """Determine the appropriate follow-up question based on selected goals."""
        try:
            # If no goals are selected, default to market question
            if not self.selected_goals:
                return "market"
                
            # If the primary goal is finding buyers, ask about target market
            if self.primary_goal == "find_buyers" or "find_buyers" in self.selected_goals:
                return "market"
                
            # If the primary goal is recruiting talent, ask about recruitment roles
            elif self.primary_goal == "recruit_talent" or "recruit_talent" in self.selected_goals:
                return "recruitment_roles"
                
            # If the primary goal is meeting business partners, ask about unique value
            elif self.primary_goal == "business_partners" or "business_partners" in self.selected_goals:
                return "unique_value"
                
            # If the primary goal is connecting with investors, ask about company size/stage
            elif self.primary_goal == "investors" or "investors" in self.selected_goals:
                return "company_size"
                
            # Default to market question
            else:
                return "market"
                
        except Exception as e:
            logger.error(f"Error determining follow-up question: {str(e)}")
            return "market"  # Default to market question if there's an error
            
