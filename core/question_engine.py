import random
import logging
import re
import os
import requests
import json
import base64
from dotenv import load_dotenv
import httpx
from pathlib import Path
from typing import Dict, List, Optional, Any
import urllib.parse

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class QuestionEngine:
    """Generates dynamic questions for the onboarding flow based on context"""

    def __init__(self):
        """Initialize the QuestionEngine with prompt templates"""
        self.logger = logging.getLogger(__name__)

        # Check if Gemini API key is available
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        if self.gemini_api_key:
            self.logger.info("Gemini API key found. Using dynamic LLM-based questions.")
        else:
            self.logger.warning("No Gemini API key found. Will use basic dynamic question generation.")

        # Steps in the onboarding flow
        self.steps = ['product', 'event_interests', 'market', 'unique_value', 'team_differentiation', 'pitch_strategy', 'use_case', 'differentiation', 'company_size', 'website', 'linkedin', 'location', 'complete']
        
        # Steps in the VC onboarding flow
        self.vc_steps = ['vc_sector_focus', 'vc_investment_stage', 'vc_team_preferences', 'vc_traction_requirements', 'website', 'linkedin', 'location', 'complete']

        # Centralized prompt templates for all LLM-based generation
        self.prompt_templates = {
            # Question generation prompts
            'question': {
                'product': """
                Use this exact question: "What product or service does your business offer?"
                
                IMPORTANT: Do not include any additional explanatory text. Just use the exact question above.
                The UI will include a text field with placeholder: "Paste your business URL (e.g. your website) or describe your product."
                """,
                'market': """
                The user sells: {product}

                Use this exact question: "What industry or market sector are you targeting with your product?"
                
                IMPORTANT: Do not include any additional explanatory text. Just use the exact question above.
                """,
                
                'target_events': """
                Based on the business profile and the selected event goals, provide a detailed recommendation for:

                1. The types of people/organizations this business should be looking to connect with at events (based on their primary goal of {primary_goal})
                2. The types of events (local events or national trade shows) where they are most likely to successfully connect with these targets

                Format your response as a clear, concise paragraph that explains:
                - Who specifically they should target (e.g., specific types of buyers, business partners, talent, or investors)
                - Why these targets are a good match for their business
                - What types of events would be most effective for meeting these targets
                - Any specific strategies they might use at these events

                Keep your response focused, practical, and directly related to their business and goals.
                """,
                'differentiation': """
                The user sells: {product}
                They target the {market} industry.

                Generate a friendly, conversational question asking what makes their product unique compared to competitors.
                Reference their product/service in your question.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.
                
                IMPORTANT: Make sure to phrase this as a clear question about what makes their product different from competitors.
                Focus on specific differentiation factors like features, pricing, technology, or approach.
                
                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their product differentiation. Keep the entire response concise and conversational.
                """,
                'company_size': """
                The user sells: {product}
                They target the {market} industry.
                Their differentiator: {differentiation}
                
                Generate a friendly, conversational question asking about their target company size or customer segment.
                Reference their product/service in your question.
                
                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their target company size or customer segment. Keep the entire response concise and conversational.
                """,
                'website': """
                The user sells: {product}
                They target the {market} industry.
                Their differentiator: {differentiation}
                Their target company size: {company_size}
                
                Generate a friendly, conversational question asking if they have a company or product website URL they'd like to share.
                Explain that this will help generate more accurate recommendations and insights about networking opportunities.
                Mention that this is optional and they can skip this step.
                
                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their website. Keep the entire response concise and conversational.
                """,
                'linkedin': """
                The user sells: {product}
                They target the {market} industry.
                Their differentiator: {differentiation}
                Their target company size: {company_size}
                Their website: {website}

                Generate a friendly, conversational question asking if they would like to connect their LinkedIn account
                to improve recommendations. Explain briefly why this would be helpful.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about LinkedIn integration. Keep the entire response concise and conversational.
                """,
                'location': """
                The user sells: {product}
                They target the {market} industry.
                Their differentiator: {differentiation}
                Their target company size: {company_size}

                Generate a friendly, conversational question asking for their zip code to help find local events.
                Mention that this is optional and they can skip this step.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their location. Keep the entire response concise and conversational.
                """,
                'complete': """
                Generate a friendly, conversational message thanking the user for providing all the information.
                Let them know that you've gathered everything needed to find great companies for them.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then provide the completion message. Keep the entire response concise and conversational.
                """,
                'default': """
                Generate a friendly, conversational question for the step: {step}
                Context: {context}
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask your question. Keep the entire response concise and conversational.
                """,
                'vc_sector_focus': """
                Generate a friendly, conversational question asking what sector the VC firm focuses on.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their sector focus. Keep the entire response concise and conversational.
                """,
                'vc_investment_stage': """
                Generate a friendly, conversational question asking what investment stage the VC firm typically invests in.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their investment stage. Keep the entire response concise and conversational.
                """,
                'vc_team_preferences': """
                Generate a friendly, conversational question asking what kind of team the VC firm prefers to invest in.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their team preferences. Keep the entire response concise and conversational.
                """,
                'vc_traction_requirements': """
                Generate a friendly, conversational question asking what traction requirements the VC firm has for investments.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their traction requirements. Keep the entire response concise and conversational.
                """,
                'unique_value': """
                The user sells: {product}
                They target the {market} industry.

                Generate a friendly, conversational question asking what makes their product truly unique.
                Focus on getting them to articulate their core value proposition and key differentiators.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about what makes their product truly unique. Keep the entire response concise and conversational.
                """,
                'team_differentiation': """
                The user sells: {product}
                They target the {market} industry.

                Generate a friendly, conversational question asking why their team is uniquely positioned to deliver on their differentiation.
                Focus on team strengths, expertise, and competitive advantages.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.
                
                IMPORTANT: Make sure to phrase this as a clear question about why their specific team can make this differentiation happen.
                Ask about team background, expertise, or unique skills that enable them to deliver on their promises.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their team's competitive advantages. Keep the entire response concise and conversational.
                """,
                'pitch_strategy': """
                The user sells: {product}
                They target the {market} industry.

                Generate a friendly, conversational question asking how they plan to pitch their differentiation to potential customers.
                Focus on their messaging strategy and how they communicate their value proposition.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.
                
                IMPORTANT: Make sure to phrase this as a clear question about their pitch strategy.
                Ask specifically about how they plan to communicate their value proposition to customers.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their pitch strategy. Keep the entire response concise and conversational.
                """,
                'use_case': """
                The user sells: {product}
                They target the {market} industry.

                Generate a friendly, conversational question asking for a specific example or use case that demonstrates their value.
                Focus on getting them to share a specific example or customer story that demonstrates their value.
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential customers.
                
                IMPORTANT: Make sure to phrase this as a clear question asking for a concrete example use case.
                Ask them to describe a specific scenario where their product solves a real problem for a customer.

                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about a specific use case. Keep the entire response concise and conversational.
                """,
                'event_interests': """
                The user sells: {product}

                Use this EXACT question with the numbered options on separate lines:

                "What is your main goal of networking? (You can select multiple options and put a star next to your most important goal)
                1. Find more buyers/users of your product/service
                2. Recruit talent for your team
                3. Meet meaningful business partners
                4. Connect with strategic investors
                5. Just meet interesting people, learning new things"
                
                IMPORTANT: You MUST include all five numbered options exactly as shown above.
                If you want to personalize the question based on their product, do so before asking the question, but keep the question and options exactly as written.
                """,
                'recruitment_roles': """
                The user sells: {product}
                Their networking goal is recruitment.

                Use this exact question: "What specific roles are you trying to recruit?"
                
                IMPORTANT: Do not include any additional explanatory text like "Okay, I understand!" or "If you asked a question previously..."
                Just use the exact question above, or if responding to a user question, answer it briefly first and then use the exact question.
                """,
                'recruitment_details': """
                The user sells: {product}
                Their networking goal is recruitment.
                They are recruiting for: {recruitment_roles}

                Generate a follow-up question asking for more specific details about the roles they're trying to recruit.
                For example, if they mentioned "engineers", ask about specific types (full-stack, back-end, ML, AI, FE/UI/UX, etc.).
                If they mentioned "sales", ask about specific types (SDR, AE, sales manager, etc.).
                
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential candidates.
                
                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about the specific role details. Keep the entire response concise and conversational.
                """,
                'company_culture': """
                The user sells: {product}
                Their networking goal is recruitment.
                They are recruiting for: {recruitment_roles}
                
                Generate a friendly, conversational question asking what makes their company an attractive place for candidates to work.
                Focus on company culture, benefits, work environment, growth opportunities, etc.
                
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential candidates.
                
                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their company culture. Keep the entire response concise and conversational.
                """,
                'recruitment_challenges': """
                The user sells: {product}
                Their networking goal is recruitment.
                They are recruiting for: {recruitment_roles}
                
                Generate a friendly, conversational question asking about specific challenges they face in recruiting for these roles.
                Focus on understanding pain points like competition for talent, specific skill requirements, etc.
                
                Keep it short and engaging. This is for NetworkAI, a tool that helps founders find potential candidates.
                
                IMPORTANT: If the user's previous message contains a question, first briefly answer their question,
                then ask about their recruitment challenges. Keep the entire response concise and conversational.
                """,
            },
            # Keyword generation prompt
            'keywords': """
            Based on the following context about a business and its product/service:
            {context}

            Generate keywords that describe the product offering, target customer, and industries served.
            Pay special attention to any industries or sectors mentioned in the website data.
            If the website mentions specific industries they serve (like healthcare, finance, legal, etc.), 
            be sure to include those industries in your keywords.
            
            Generate only the most relevant keywords that would help find ideal target companies.
            Format your response as a comma-separated list of keywords only, without any additional text or explanations.
            Limit to 15 keywords maximum.
            """,

        }

        # Load workflow patterns if available
        self.patterns_path = Path("workflows/patterns_v1.json")
        self.workflow_patterns = self._load_patterns()

    def _load_patterns(self) -> Dict[str, Any]:
        """Load workflow patterns from JSON file."""
        try:
            if self.patterns_path.exists():
                with open(self.patterns_path) as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load workflow patterns: {str(e)}")
            return {}

    async def get_question(self, step, context=None, previous_message=None):
        """
        Generate a personalized question based on the current step and context

        Args:
            step (str): The current step in the onboarding flow
            context (dict): Context from previous answers
            previous_message (str): The user's previous message, to check if it contains a question

        Returns:
            str: A dynamically generated question tailored to the user's context
        """
        if context is None:
            context = {}

        if step is None or step == 'complete':
            step = 'complete'

        # Check if we have website analysis data to enhance the question
        website_data = None
        for key, value in context.items():
            if key.startswith('website_analysis_') and value:
                website_data = value
                break

        # Try to use the LLM first if we have an API key
        if self.gemini_api_key:
            try:
                # Pass website data to enhance the question generation
                llm_response = await self._generate_with_llm(step, context, previous_message, website_data)
                if llm_response:
                    return llm_response
            except Exception as e:
                logger.error(f"Error using LLM for question generation: {str(e)}")
                # Fall through to basic question generation if LLM fails

        # Generate a basic question if LLM fails or is not available
        return self._generate_basic_question(step, context, website_data)

    async def generate_with_gemini(self, prompt, context=None, max_tokens=1024):
        """
        Generate text using the Gemini API with a custom prompt
        
        Args:
            prompt (str): The prompt to send to Gemini
            context (str, optional): Additional context to add to the prompt
            max_tokens (int, optional): Maximum number of tokens to generate
            
        Returns:
            str: The generated text
        """
        try:
            if not self.gemini_api_key:
                logger.error("No Gemini API key found. Cannot generate text with Gemini.")
                return None
                
            # Add context to the prompt if provided
            if context:
                prompt = f"{prompt}\n\n{context}"
                
            # Call the Gemini API
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
            
            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.3,
                    "topP": 0.9,
                    "topK": 40,
                    "maxOutputTokens": max_tokens
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=data,
                    timeout=10.0
                )
                
            if response.status_code == 200:
                result = response.json()
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0]["content"]
                    if "parts" in content and len(content["parts"]) > 0:
                        generated_text = content["parts"][0]["text"]
                        
                        # Clean up the response
                        generated_text = generated_text.strip()
                        
                        logger.info(f"Generated text with Gemini API: {generated_text[:100]}...")
                        return generated_text
                        
                logger.error(f"Unexpected response format from Gemini API: {result}")
                return None
            else:
                logger.error(f"Error calling Gemini API: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating text with Gemini: {str(e)}")
            return None
            
    async def _generate_with_llm(self, step, context, previous_message=None, website_data=None):
        """Generate a personalized question using the Gemini API with enhanced context"""
        try:
            # Construct a prompt based on the current step and context
            prompt = self._construct_prompt(step, context, previous_message, website_data)

            # Call the Gemini API with improved parameters
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"

            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.3,  # Slightly higher temperature for more creative questions
                    "topP": 0.9,
                    "topK": 40,
                    "maxOutputTokens": 1024
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=data,
                    timeout=10.0  # Increased timeout for more reliable responses
                )

            if response.status_code == 200:
                result = response.json()
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0]["content"]
                    if "parts" in content and len(content["parts"]) > 0:
                        question = content["parts"][0]["text"]

                        # Clean up the response to ensure it's a single question
                        question = self._clean_llm_response(question)

                        logger.info(f"Generated enhanced question with Gemini API: {question}")
                        return question

                logger.error(f"Unexpected response format from Gemini API: {result}")
                return self._generate_basic_question(step, context, website_data)
            else:
                logger.error(f"Error calling Gemini API: {response.status_code} - {response.text}")
                # Fall back to basic question generation
                return self._generate_basic_question(step, context, website_data)

        except Exception as e:
            logger.error(f"Error generating question with LLM: {str(e)}")
            # Fall back to basic question generation
            return self._generate_basic_question(step, context, website_data)

    def _construct_prompt(self, step, context, previous_message=None, website_data=None):
        """Construct an enhanced prompt for the LLM based on the current step and context"""
        # Get the appropriate prompt template for the step
        if step in self.prompt_templates['question']:
            prompt_template = self.prompt_templates['question'][step]
        else:
            prompt_template = self.prompt_templates['question']['default']

        # Add the previous message to the context if provided
        previous_message_context = ""
        if previous_message:
            previous_message_context = f"\nUser's previous message: \"{previous_message}\"\n"

        # Add website data to enhance the prompt if available
        website_context = ""
        if website_data:
            website_context = f"""
\nWebsite Analysis Data:
- Title: {website_data.get('title', '')}
- Description: {website_data.get('description', '')}
- Target Audience: {website_data.get('target_audience', '')}
- Industries: {', '.join(website_data.get('industries', []))}
- Unique Value: {website_data.get('unique_value', '')}
- Company Size: {website_data.get('company_size', '')}
"""

        # Format the prompt with context values
        formatted_prompt = prompt_template.format(
            step=step,
            context=context,
            product=context.get('product', ''),
            market=context.get('market', ''),
            differentiation=context.get('differentiation', ''),
            company_size=context.get('company_size', '')
        )

        # Insert the previous message context and website context after the first line
        if previous_message_context or website_context:
            lines = formatted_prompt.split('\n', 1)
            if len(lines) > 1:
                formatted_prompt = lines[0] + previous_message_context + website_context + lines[1]
            else:
                formatted_prompt = formatted_prompt + previous_message_context + website_context

        # Add instructions for more personalized questions
        formatted_prompt += """
\nIMPORTANT: Make your question conversational, engaging, and personalized to the user's context. 
If you have website data, reference specific details from it to show understanding of their business.
Avoid generic questions when you have specific information available.
"""

        return formatted_prompt

    def _clean_llm_response(self, response):
        """Clean up the LLM response to ensure it's a single question"""
        # Remove any "AI:" or "Assistant:" prefixes
        response = re.sub(r'^(AI:|Assistant:)\s*', '', response)

        # Remove any thinking process or explanations in brackets or parentheses
        response = re.sub(r'\[.*?\]|\(.*?\)', '', response)
        
        # Special handling for event_interests to preserve the numbered options
        if "What's your main goal for networking?" in response and "Please select one of the following options:" in response:
            # Extract the question and options
            pattern = r"(What's your main goal for networking\?.*?Please select one of the following options:.*?)(?:\n\n|\Z)"
            match = re.search(pattern, response, re.DOTALL)
            if match:
                question_with_options = match.group(1).strip()
                
                # Make sure it includes the numbered options
                if "1." in question_with_options and "2." in question_with_options:
                    return question_with_options
                else:
                    # If options are missing, append them
                    return """What's your main goal for networking? Please select one of the following options:
1. Find more buyers/users of your product/service
2. Recruit talent for your team
3. Meet meaningful business partners
4. Connect with strategic investors"""
        
        # For other questions, use the standard cleaning
        lines = response.split('\n')
        question_lines = []
        for line in lines:
            line = line.strip()
            if line and (line.endswith('?') or re.search(r'what|how|why|when|where|which|can|could|would|will|do|does|is|are', line.lower())):
                question_lines.append(line)

        if question_lines:
            return question_lines[0]  # Return the first question

        # If no question was found, return the original response
        return response.strip()

    def _generate_basic_question(self, step, context, website_data=None):
        """Generate a basic question based on the step without using LLM, but with enhanced personalization"""
        # Basic questions for each step
        basic_questions = {
            'product': "What product or service does your company offer?",
            'market': "What market or industry are you targeting?",
            'differentiation': "What makes your product unique compared to competitors?",
            'company_size': "What size of companies are you targeting?",
            'website': "Do you have a company or product website URL you'd like to share? If you don't have one yet, just let us know! This will help generate more accurate recommendations.",
            'linkedin': "Would you like to connect your LinkedIn account to enhance recommendations?",
            'location': "What's your zip code for finding local events? (You can skip this)",
            'complete': "Thanks for providing all the information! We'll find great companies for you.",
            'vc_sector_focus': "What sector does your VC firm focus on?",
            'vc_investment_stage': "What investment stage does your VC firm typically invest in?",
            'vc_team_preferences': "What kind of team does your VC firm prefer to invest in?",
            'vc_traction_requirements': "What traction requirements does your VC firm have for investments?",
            'unique_value': "What makes your solution truly unique in the market?",
            'team_differentiation': "How is your team uniquely positioned to deliver on your value proposition?",
            'use_case': "Can you share a specific example or use case that demonstrates your value?",
            'event_interests': "What's your main goal for networking? Please select one of the following options:\n1. Find more buyers/users of your product/service\n2. Recruit talent for your team\n3. Meet meaningful business partners\n4. Connect with strategic investors"
        }

        # Add context to make the question more personalized
        if step == 'market' and 'product' in context:
            return f"What market or industry are you targeting with your {context['product']}?"
        elif step == 'differentiation' and 'product' in context:
            return f"What makes your {context['product']} unique compared to competitors?"
        elif step == 'company_size' and 'product' in context:
            return f"What size of companies are you targeting with your {context['product']}?"
        elif step == 'unique_value' and 'product' in context and 'market' in context:
            return f"What makes your {context['product']} truly unique in the {context['market']} market?"
        elif step == 'team_differentiation' and 'product' in context:
            return f"How is your team uniquely positioned to deliver {context['product']} successfully?"
        elif step == 'use_case' and 'product' in context and 'market' in context:
            return f"Can you share a specific example of how {context['product']} delivers value in the {context['market']} market?"

        # Add website data to make the question more personalized
        if website_data:
            if step == 'market' and website_data.get('industries'):
                industries = ', '.join(website_data.get('industries')[:3])
                return f"I see your website mentions {industries}. Are these the main industries you're targeting, or are there others?"
            elif step == 'differentiation' and website_data.get('unique_value'):
                return f"Your website suggests your unique value is related to {website_data.get('unique_value')}. Could you elaborate on what makes this truly unique compared to competitors?"
            elif step == 'company_size' and website_data.get('target_audience'):
                return f"Based on your website, it seems you might be targeting {website_data.get('target_audience')}. What specific company sizes are you focusing on?"

        # For event_interests, always use the multiple-choice format
        if step == 'event_interests':
            return basic_questions['event_interests']
            
        # Return the basic question or a generic one if step not found
        return basic_questions.get(step, "Tell me more about your needs.")

    def get_next_step(self, current_step):
        """
        Determine the next step based on the current step

        Args:
            current_step (str): The current step in the onboarding flow

        Returns:
            str: The next step in the onboarding flow
        """
        try:
            current_index = self.steps.index(current_step)
            if current_index < len(self.steps) - 1:
                return self.steps[current_index + 1]
            else:
                return 'complete'
        except ValueError:
            return 'product'  # Default to the first step if current_step is not found

    async def generate_keywords(self, context):
        """
        Generate keywords based on user input and website analysis

        Args:
            context (dict): Context from previous answers

        Returns:
            list: List of generated keywords
        """
        try:
            # Extract relevant information from context
            product = context.get('product', '')
            market = context.get('market', '')
            differentiation = context.get('differentiation', '')
            company_size = context.get('company_size', '')
            
            # Check if there's a website URL in the product or context
            website_url = context.get('website', '')
            website_data = {}
            
            # If no website URL is explicitly provided, try to extract it from the product description
            if (not website_url or len(website_url) < 5) and product:
                extracted_url = self._extract_website_url(product)
                if extracted_url:
                    logger.info(f"Extracted website URL from product description for keywords: {extracted_url}")
                    website_url = extracted_url
            
            # Prepare the context for keyword generation
            if website_url and len(website_url) > 5:
                # If we have a website URL, analyze it using curl
                browser_data = await self.analyze_website_with_browser(website_url)
                if browser_data:
                    logger.info(f"Successfully analyzed website with browser for keywords: {website_url}")
                    website_data = browser_data
                    
                    # Add website data to the context for keyword generation
                    combined_context = f"""
                    Product/Service: {product}
                    Target Market/Industry: {market}
                    Unique Value Proposition: {differentiation}
                    Target Company Size: {company_size}
                    
                    Website Title: {website_data.get('title', '')}
                    Website Description: {website_data.get('description', '')}
                    Website Headings: {', '.join(website_data.get('headings', []))}
                    Website Paragraphs: {' '.join(website_data.get('paragraphs', []))[:500]}
                    """
                    
                    # If this is an industries page, include the industries
                    if "industries" in website_data:
                        combined_context += f"\nIndustries: {', '.join(website_data.get('industries', []))}"
                else:
                    # If website analysis failed, use regular context
                    combined_context = f"""
                    Product/Service: {product}
                    Target Market/Industry: {market}
                    Unique Value Proposition: {differentiation}
                    Target Company Size: {company_size}
                    Website URL: {website_url}
                    """
            else:
                # No website URL available, use regular context
                combined_context = f"""
                Product/Service: {product}
                Target Market/Industry: {market}
                Unique Value Proposition: {differentiation}
                Target Company Size: {company_size}
                """

            # Generate keywords using Gemini API
            if not self.gemini_api_key:
                logger.error("No Gemini API key found. Cannot generate keywords.")
                return []
                
            keywords = await self._generate_keywords_with_llm(combined_context)
            if keywords:
                # Optimize the keywords
                optimized_keywords = self._optimize_keywords(keywords)
                return optimized_keywords
            else:
                logger.error("Failed to generate keywords with LLM.")
                return []

        except Exception as e:
            logger.error(f"Error generating keywords: {str(e)}")
            return []

    def _optimize_keywords(self, keywords):
        """
        Optimize keywords by deduplicating and ranking by significance

        Args:
            keywords (list): List of keywords to optimize

        Returns:
            list: List of optimized keywords (max 15)
        """
        try:
            # Remove duplicates and empty strings
            unique_keywords = list(set([kw.strip() for kw in keywords if kw.strip()]))

            # Rank keywords by significance
            ranked_keywords = self._rank_keywords_by_significance(unique_keywords)

            # Limit to 15 keywords
            optimized_keywords = ranked_keywords[:15]

            logger.info(f"Optimized keywords: {optimized_keywords}")
            return optimized_keywords
        except Exception as e:
            logger.error(f"Error optimizing keywords: {str(e)}")
            return keywords[:15] if len(keywords) > 15 else keywords

    def _rank_keywords_by_significance(self, keywords):
        """
        Rank keywords by their significance

        Args:
            keywords (list): List of unique keywords

        Returns:
            list: List of keywords ranked by significance
        """
        try:
            # Score each keyword based on multiple factors
            keyword_scores = {}

            for keyword in keywords:
                # Initialize score
                score = 0

                # Factor 1: Length (longer keywords are often more specific)
                # But not too long
                length = len(keyword)
                if 3 <= length <= 20:
                    score += min(length / 5, 3)  # Cap at 3 points

                # Factor 2: Multi-word phrases are more specific
                word_count = len(keyword.split())
                if word_count > 1:
                    score += min(word_count, 3)  # Cap at 3 points

                # Factor 3: Industry-specific terms
                industry_terms = ["b2b", "saas", "enterprise", "platform", "solution", "technology", "ai", "ml", "data", "analytics", "cloud", "software", "service", "automation", "integration", "management"]
                if keyword.lower() in industry_terms or any(term in keyword.lower() for term in industry_terms):
                    score += 2

                keyword_scores[keyword] = score

            # Sort keywords by score (descending)
            sorted_words = sorted(keywords, key=lambda k: keyword_scores.get(k, 0), reverse=True)

            return sorted_words
        except Exception as e:
            logger.error(f"Error ranking keywords: {str(e)}")
            return keywords

    def _extract_website_url(self, text):
        """Extract a website URL from text if present."""
        # Common URL patterns
        url_patterns = [
            r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)',  # Standard URLs
            r'(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)'  # URLs without protocol
        ]
        
        for pattern in url_patterns:
            matches = re.findall(pattern, text)
            if matches:
                url = matches[0]
                # Add https:// if missing
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                return url
        
        return None

    async def _generate_keywords_with_llm(self, context):
        """Generate keywords using the Gemini API"""
        try:
            # Prepare the prompt for keyword generation using the centralized template
            prompt = self.prompt_templates['keywords'].format(context=context)

            # Call the Gemini API
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"

            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=data,
                    timeout=5.0
                )

            if response.status_code == 200:
                result = response.json()
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0]["content"]
                    if "parts" in content and len(content["parts"]) > 0:
                        keywords_text = content["parts"][0]["text"]

                        # Parse the keywords from the response
                        keywords_list = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]

                        # Limit to 15 keywords
                        keywords_list = keywords_list[:15]

                        logger.info(f"Generated keywords with LLM: {keywords_list}")
                        return keywords_list

            logger.error(f"Error or unexpected response from Gemini API")
            return None

        except Exception as e:
            logger.error(f"Error generating keywords with LLM: {str(e)}")
            return None

    def _extract_basic_keywords(self, text):
        """Extract basic keywords from text using simple rules"""
        # Convert to lowercase and split by common separators
        words = re.findall(r'\b\w+\b', text.lower())

        # Remove common stop words
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about', 'as', 'of', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall', 'should', 'can', 'could', 'may', 'might', 'must', 'that', 'which', 'who', 'whom', 'this', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had', 'does', 'did', 'doing', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]

        # Count word frequency
        word_counts = {}
        for word in filtered_words:
            word_counts[word] = word_counts.get(word, 0) + 1

        # Get the most frequent words as keywords
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        keywords = [word for word, count in sorted_words[:15]]

        # Add some common business keywords if we don't have enough
        if len(keywords) < 5:
            common_keywords = ["B2B", "enterprise", "software", "technology", "solution", "platform", "service", "analytics", "automation", "AI", "cloud", "data", "security", "integration", "management"]
            keywords.extend(common_keywords[:10 - len(keywords)])

        return keywords

    async def analyze_website_with_browser(self, url):
        """Use the website_analyzer.py implementation to analyze a website."""
        try:
            # Import the website_analyzer.py implementation
            from website_analyzer import analyze_website_with_browser as browser_analyze_website
            
            logger.info(f"Using website_analyzer.py to analyze website: {url}")
            
            # Call the website_analyzer.py implementation
            website_data = await browser_analyze_website(url)
            
            if website_data:
                logger.info(f"Website analysis successful for {url}")
                
                # Convert the website_data format to match what the question_engine expects
                converted_data = {
                    "title": website_data.get("title", ""),
                    "description": website_data.get("description", ""),
                    "keywords": website_data.get("keywords", []),
                    "headings": website_data.get("headings", []),
                    "paragraphs": [],  # Not provided by website_analyzer.py
                    "all_text": [website_data.get("raw_text", "")],
                    "url": url,
                    "homepage_url": "",
                    "homepage_title": "",
                    "homepage_description": ""
                }
                
                # Add industries if available
                if "industries" in website_data:
                    converted_data["industries"] = website_data.get("industries", [])
                
                return converted_data
            else:
                logger.warning(f"Website analysis failed for {url}")
                return None
        except Exception as e:
            logger.error(f"Error analyzing website with browser: {str(e)}")
            return None
            
    async def generate_follow_up_question(self, step, context, previous_answer, follow_up_count=0):
        """
        Generate a personalized follow-up question based on the user's previous answer

        Args:
            step (str): The current step in the onboarding flow
            context (dict): Context from previous answers
            previous_answer (str): The user's previous answer
            follow_up_count (int): The number of follow-up questions already asked

        Returns:
            str: A dynamically generated follow-up question
        """
        try:
            # Check if we have website analysis data to enhance the question
            website_data = None
            for key, value in context.items():
                if key.startswith('website_analysis_') and value:
                    website_data = value
                    break
                    
            # If we've already asked 2 follow-up questions, suggest moving on
            if follow_up_count >= 2:
                return "Thanks for that information. Would you like to add anything else or shall we move on to the next step?"

            # Check if the answer is very short or lacks detail
            is_short_answer = len(previous_answer.split()) < 10
            
            # Check for signs of user impatience in the previous answer
            impatience_indicators = [
                "next", "continue", "move on", "skip", "enough", "done", "finish", "complete", "proceed"
            ]
            if any(indicator in previous_answer.lower() for indicator in impatience_indicators):
                return "Let's move on to the next step."

            # Try to use the LLM first if we have an API key
            if self.gemini_api_key:
                # Construct a prompt for follow-up question generation
                prompt = f"""
                You are a B2B sales assistant helping to gather information from a user.

                Current step: {step}
                User's previous answer: "{previous_answer}"
                Follow-up count: {follow_up_count}
                """
                
                # Add context to the prompt
                if context:
                    prompt += "\nContext:\n"
                    for key, value in context.items():
                        if isinstance(value, str) and not key.startswith('website_analysis_'):
                            prompt += f"- {key}: {value}\n"
                
                # Add website data to the prompt if available
                if website_data:
                    prompt += "\nWebsite Analysis Data:\n"
                    for key, value in website_data.items():
                        if key in ['title', 'description', 'unique_value', 'target_audience', 'company_size'] and value:
                            prompt += f"- {key}: {value}\n"
                    if 'industries' in website_data and website_data['industries']:
                        prompt += f"- industries: {', '.join(website_data['industries'])}\n"
                
                prompt += """
                Generate a follow-up question that digs deeper into the user's answer. The question should be:
                1. Conversational and friendly
                2. Specific to what they just shared
                3. Designed to get more detailed information
                4. Not repetitive of what they've already told you
                5. Personalized based on any website data available

                If their answer was already detailed (more than 50 words), or if this would be the 2nd follow-up question,
                instead ask if they want to add anything else or move on to the next step.

                If the user's answer mentions specific challenges, pain points, or unique aspects, focus your follow-up
                question on those areas to get more details.

                Return only the follow-up question, without any additional text.
                """

                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"

                data = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.3,
                        "topP": 0.9,
                        "topK": 40,
                        "maxOutputTokens": 1024
                    }
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        json=data,
                        timeout=10.0
                    )

                if response.status_code == 200:
                    result = response.json()
                    if "candidates" in result and len(result["candidates"]) > 0:
                        content = result["candidates"][0]["content"]
                        if "parts" in content and len(content["parts"]) > 0:
                            question = content["parts"][0]["text"]
                            
                            # Clean up the response
                            question = self._clean_llm_response(question)
                            
                            logger.info(f"Generated enhanced follow-up question with Gemini API: {question}")
                            return question

            # Fall back to basic follow-up questions if LLM fails or is not available
            if is_short_answer:
                # For short answers, ask for more details based on the step
                if step == 'product':
                    return "Could you tell me a bit more about your product's key features or capabilities?"
                elif step == 'market':
                    return "Are there specific segments within that market that you're particularly focused on?"
                elif step == 'differentiation':
                    return "How does that differentiation translate to tangible benefits for your customers?"
                elif step == 'unique_value':
                    return "How does that unique value position you against your main competitors?"
                elif step == 'team_differentiation':
                    return "What specific expertise or background does your team have that enables this?"
                elif step == 'use_case':
                    return "Can you share a specific example of how a customer has benefited from this?"
                else:
                    return "Could you tell me a bit more about that?"
            else:
                # For longer answers, suggest moving on
                return "Thanks for that information. Would you like to add anything else or shall we move on to the next step?"

        except Exception as e:
            logger.error(f"Error generating follow-up question: {str(e)}")
            return "Can you tell me more about that?"
            
    async def generate_user_summary(self, context, max_words=None):
        """Generate a concise summary about the user and their product."""
        try:
            # Extract relevant information from context
            product = context.get('product', '')
            market = context.get('market', '')
            differentiation = context.get('differentiation', '')
            company_size = context.get('company_size', '')
            website_url = context.get('website', '')
            previous_summary = context.get('previous_user_summary', '')
            
            # Check for website analysis results in the context
            website_data = {}
            is_only_url = False
            
            # Check if any step has website analysis results
            for key, value in context.items():
                if key.startswith('website_analysis_') and not key.endswith('_is_only_url') and value:
                    website_data = value
                    # Check if this step's answer was only a URL
                    step_name = key.replace('website_analysis_', '')
                    if f"{step_name}_is_only_url" in context:
                        is_only_url = True
                    break
            
            # If no website data found in context but we have a URL, analyze it
            if not website_data and website_url and len(website_url) > 5:
                logger.info(f"Analyzing website for user summary: {website_url}")
                website_data = await self.analyze_website_with_browser(website_url)
            
            # Prepare the prompt based on whether the answer was only a URL or not
            if website_data:
                if is_only_url:
                    # If the answer was only a URL, use ONLY the website data
                    prompt = """
                    You are a B2B sales assistant helping to generate an insightful summary about a business.
                    
                    Based ONLY on the following website data:
                    """
                    
                    # Add ALL website data fields
                    prompt += f"""
                    Website Title: {website_data.get('title', '')}
                    Website Description: {website_data.get('description', '')}
                    Website Headings: {', '.join(website_data.get('headings', []))}
                    """
                    
                    # Include ALL additional fields from website_analyzer.py
                    if website_data.get('target_audience'):
                        prompt += f"Target Audience: {website_data.get('target_audience')}\n"
                    
                    if website_data.get('main_features'):
                        features = website_data.get('main_features')
                        if isinstance(features, list):
                            prompt += f"Main Features: {', '.join(features)}\n"
                        else:
                            prompt += f"Main Features: {features}\n"
                    
                    if website_data.get('unique_value'):
                        prompt += f"Unique Value: {website_data.get('unique_value')}\n"
                        
                    if website_data.get('industries'):
                        prompt += f"Industries: {', '.join(website_data.get('industries'))}\n"
                        
                    if website_data.get('company_size'):
                        prompt += f"Company Size: {website_data.get('company_size')}\n"
                        
                    if website_data.get('raw_text'):
                        prompt += f"Raw Text Sample: {website_data.get('raw_text')[:500]}\n"
                    
                    # Add previous summary if available
                    if previous_summary:
                        prompt += f"\nPrevious Summary: {previous_summary}\n"
                    
                    prompt += """
                    Generate an insightful, professional summary (3-9 sentences) about what this company does, who they serve, and their key offerings.
                    Focus ONLY on the information provided in the website data.
                    """
                else:
                    # If the answer wasn't only a URL, use both website data and user input
                    prompt = f"""
                    You are a B2B sales assistant helping to generate an insightful summary about a business.

                    Current context:
                    - Product/Service: {product}
                    - Target Market: {market}
                    - Company Size: {company_size}
                    - Differentiation: {differentiation}
                    """

                    # Add ALL website data fields
                    prompt += f"""
                    Website Title: {website_data.get('title', '')}
                    Website Description: {website_data.get('description', '')}
                    Website Headings: {', '.join(website_data.get('headings', []))}
                    """
                    
                    # Include ALL additional fields from website_analyzer.py
                    if website_data.get('target_audience'):
                        prompt += f"Target Audience: {website_data.get('target_audience')}\n"
                    
                    if website_data.get('main_features'):
                        features = website_data.get('main_features')
                        if isinstance(features, list):
                            prompt += f"Main Features: {', '.join(features)}\n"
                        else:
                            prompt += f"Main Features: {features}\n"
                    
                    if website_data.get('unique_value'):
                        prompt += f"Unique Value: {website_data.get('unique_value')}\n"
                        
                    if website_data.get('industries'):
                        prompt += f"Industries: {', '.join(website_data.get('industries'))}\n"
                        
                    if website_data.get('company_size'):
                        prompt += f"Company Size: {website_data.get('company_size')}\n"
                        
                    if website_data.get('raw_text'):
                        prompt += f"Raw Text Sample: {website_data.get('raw_text')[:500]}\n"
                    
                    # Add previous summary if available
                    if previous_summary:
                        prompt += f"\nPrevious Summary: {previous_summary}\n"
                    
                    prompt += """
                    Based on this information, generate an insightful, professional summary (3-9 sentences) about what this company does, who they serve, and their key offerings.
                    """
            else:
                # No website data available
                prompt = f"""
                You are a B2B sales assistant helping to generate an insightful summary about a business.

                Current context:
                - Product/Service: {product}
                - Target Market: {market}
                - Company Size: {company_size}
                - Differentiation: {differentiation}
                """
                
                # Add previous summary if available
                if previous_summary:
                    prompt += f"\nPrevious Summary: {previous_summary}\n"
                
                prompt += """
                Based on this information, generate an insightful, professional summary (3-9 sentences) about what this company does, who they serve, and their key offerings.
                """

            # Call the Gemini API
            if not self.gemini_api_key:
                logger.warning("No Gemini API key found. Using basic user summary generation.")
                # Create a basic summary from the available context
                product_info = context.get('product', '')
                market_info = context.get('market', '')
                company_size = context.get('company_size', '')
                
                # Use website data if available
                if website_data:
                    if website_data.get('title'):
                        product_info = website_data.get('title', product_info)
                    if website_data.get('description'):
                        product_info += ": " + website_data.get('description', '')
                    if website_data.get('industries') and len(website_data.get('industries')) > 0:
                        market_info = ", ".join(website_data.get('industries', []))
                    if website_data.get('company_size'):
                        company_size = website_data.get('company_size', company_size)
                
                # Create a basic summary
                if product_info and market_info:
                    summary = f"A company building {product_info} for the {market_info} market."
                    if company_size:
                        summary += f" They are a {company_size} company."
                    return summary
                elif product_info:
                    return f"A company building {product_info}."
                else:
                    return "A company looking for networking opportunities."
                
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"

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
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                if "candidates" in data and len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        summary = candidate["content"]["parts"][0]["text"]
                        
                        # Clean up the summary
                        summary = summary.strip()
                        
                        # Limit the summary length if requested
                        if max_words:
                            words = summary.split()
                            if len(words) > max_words:
                                summary = ' '.join(words[:max_words]) + '...'
                        
                        logger.info(f"Generated user summary: {summary}")
                        return summary

            logger.error("Unexpected response format from Gemini API")
            return ""
        except Exception as e:
            logger.error(f"Error generating user summary: {str(e)}")
            return ""
