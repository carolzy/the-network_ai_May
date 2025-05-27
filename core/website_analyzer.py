import asyncio
from playwright.async_api import async_playwright
import httpx
import os
import json
import re
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL_NAME = "claude-3-7-sonnet-20250219"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"

# Flag to determine which LLM to use
USE_GEMINI = True  # Set to False to use Claude instead

async def extract_visible_text(url: str) -> Dict[str, Any]:
    """Launch Chromium browser and extract visible text and metadata from a webpage with enhanced extraction."""
    try:
        logger.info(f"Extracting content from {url} using Playwright...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
            )
            page = await context.new_page()

            logger.info(f"Navigating to {url}...")
            try:
                # Try to navigate with a longer timeout
                await page.goto(url, wait_until="networkidle", timeout=90000)
            except Exception as e:
                logger.warning(f"Navigation timeout, continuing with partial page load: {str(e)}")
                # Continue with what we have

            logger.info("Extracting page metadata...")
            # Extract title
            title = await page.title()
            
            # Extract meta description
            description = await page.evaluate("""
                () => {
                    const metaDescription = document.querySelector('meta[name="description"]');
                    if (metaDescription) return metaDescription.getAttribute('content');
                    
                    // Try Open Graph description as fallback
                    const ogDescription = document.querySelector('meta[property="og:description"]');
                    if (ogDescription) return ogDescription.getAttribute('content');
                    
                    // Try Twitter description as fallback
                    const twitterDescription = document.querySelector('meta[name="twitter:description"]');
                    if (twitterDescription) return twitterDescription.getAttribute('content');
                    
                    return '';
                }
            """)
            
            # Extract meta keywords
            meta_keywords = await page.evaluate("""
                () => {
                    const metaKeywords = document.querySelector('meta[name="keywords"]');
                    return metaKeywords ? metaKeywords.getAttribute('content') : '';
                }
            """)
            
            # Extract headings with hierarchy
            headings = await page.evaluate("""
                () => {
                    const headings = [];
                    const elements = document.querySelectorAll('h1, h2, h3, h4');
                    elements.forEach(el => {
                        const text = el.textContent.trim();
                        if (text) {
                            headings.push({
                                level: parseInt(el.tagName.substring(1)),
                                text: text
                            });
                        }
                    });
                    return headings;
                }
            """)
            
            # Extract flat list of headings for backward compatibility
            flat_headings = [h['text'] for h in headings]

            # Extract links
            links = await page.evaluate("""
                () => {
                    const links = [];
                    const elements = document.querySelectorAll('a[href]');
                    elements.forEach(el => {
                        const href = el.getAttribute('href');
                        const text = el.textContent.trim();
                        if (href && text && !href.startsWith('#') && !href.startsWith('javascript:')) {
                            links.push({
                                href: href,
                                text: text
                            });
                        }
                    });
                    return links;
                }
            """)

            # Extract paragraphs
            paragraphs = await page.evaluate("""
                () => {
                    const paragraphs = [];
                    const elements = document.querySelectorAll('p');
                    elements.forEach(el => {
                        const text = el.textContent.trim();
                        if (text && text.length > 20) {  // Only include substantial paragraphs
                            paragraphs.push(text);
                        }
                    });
                    return paragraphs;
                }
            """)
            
            # Extract lists (bullet points)
            lists = await page.evaluate("""
                () => {
                    const lists = [];
                    const elements = document.querySelectorAll('ul, ol');
                    elements.forEach(listEl => {
                        const items = [];
                        listEl.querySelectorAll('li').forEach(li => {
                            const text = li.textContent.trim();
                            if (text) items.push(text);
                        });
                        if (items.length > 0) {
                            lists.push({
                                type: listEl.tagName.toLowerCase(),
                                items: items
                            });
                        }
                    });
                    return lists;
                }
            """)

            logger.info("Extracting page content...")
            content = await page.evaluate("""
                () => {
                    function getVisibleText(element) {
                        const style = window.getComputedStyle(element);
                        if (style && (style.visibility === 'hidden' || style.display === 'none')) {
                            return '';
                        }
                        let text = '';
                        for (const child of element.childNodes) {
                            if (child.nodeType === Node.TEXT_NODE) {
                                text += child.textContent.trim() + ' ';
                            } else if (child.nodeType === Node.ELEMENT_NODE) {
                                text += getVisibleText(child);
                            }
                        }
                        return text;
                    }
                    return getVisibleText(document.body);
                }
            """)
            
            # Check for common industry pages
            industries = await page.evaluate("""
                () => {
                    // Common industry-related terms to look for
                    const industryTerms = [
                        'healthcare', 'finance', 'banking', 'insurance', 'technology', 'manufacturing',
                        'retail', 'education', 'government', 'nonprofit', 'energy', 'utilities',
                        'telecommunications', 'media', 'entertainment', 'hospitality', 'travel',
                        'transportation', 'logistics', 'construction', 'real estate', 'legal',
                        'professional services', 'consulting', 'agriculture', 'food', 'beverage',
                        'pharmaceutical', 'biotech', 'automotive', 'aerospace', 'defense'
                    ];
                    
                    // Look for industry terms in headings, paragraphs, and list items
                    const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4')).map(el => el.textContent.toLowerCase());
                    const paragraphs = Array.from(document.querySelectorAll('p')).map(el => el.textContent.toLowerCase());
                    const listItems = Array.from(document.querySelectorAll('li')).map(el => el.textContent.toLowerCase());
                    
                    // Combine all text elements
                    const allText = [...headings, ...paragraphs, ...listItems].join(' ');
                    
                    // Find matching industries
                    const foundIndustries = [];
                    for (const industry of industryTerms) {
                        if (allText.includes(industry)) {
                            foundIndustries.push(industry);
                        }
                    }
                    
                    // Check for "Industries" or "Sectors" sections
                    const industryHeadings = Array.from(document.querySelectorAll('h1, h2, h3, h4')).filter(
                        el => el.textContent.toLowerCase().includes('industr') || 
                             el.textContent.toLowerCase().includes('sector')
                    );
                    
                    // If we found industry headings, look at the list items that follow
                    for (const heading of industryHeadings) {
                        let element = heading.nextElementSibling;
                        while (element && !['H1', 'H2', 'H3', 'H4'].includes(element.tagName)) {
                            if (element.tagName === 'UL' || element.tagName === 'OL') {
                                const items = Array.from(element.querySelectorAll('li')).map(li => li.textContent.trim());
                                foundIndustries.push(...items);
                            }
                            element = element.nextElementSibling;
                        }
                    }
                    
                    return [...new Set(foundIndustries)]; // Remove duplicates
                }
            """)

            # Take a screenshot
            screenshot_path = "temp_screenshot.png"
            await page.screenshot(path=screenshot_path)
            
            # Read the screenshot as base64
            import base64
            with open(screenshot_path, "rb") as f:
                screenshot_base64 = base64.b64encode(f.read()).decode("utf-8")
            
            # Clean up the screenshot file
            import os
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)

            await browser.close()
            
            return {
                "url": url,
                "title": title,
                "description": description,
                "meta_keywords": meta_keywords,
                "headings": flat_headings,
                "headings_hierarchy": headings,
                "links": links,
                "paragraphs": paragraphs,
                "lists": lists,
                "content": content.strip(),
                "screenshot": screenshot_base64,
                "industries": industries
            }
    except Exception as e:
        logger.error(f"Error extracting content from {url}: {str(e)}")
        return {
            "url": url,
            "title": f"Error: {str(e)}",
            "description": "",
            "headings": [],
            "content": "",
            "screenshot": ""
        }

async def ask_claude(text: str, url: str) -> Dict[str, Any]:
    """Send extracted text to Claude for analysis."""
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not found in environment variables")
        return {"error": "ANTHROPIC_API_KEY not found in environment variables"}
    
    try:
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        prompt = f"""
You are a website analysis assistant.
Here is the extracted text content from the website {url}:

---
{text[:10000]}  # Limit text to avoid token limits
---

Please analyze and provide the following information in a structured format:

1. Title: The main title or name of the website/company
2. Description: A brief description of what the website/company does
3. Keywords: 10-15 keywords that best represent this website's content and purpose
4. Target Audience: Who this website is primarily targeting
5. Main Features/Services: The main offerings or services
6. Unique Value Proposition: What makes this website/company unique
7. Industries: Any specific industries this website targets
8. Company Size: If detectable, what size of companies this targets (SMB, enterprise, etc.)

Format your response as a structured JSON object with these fields. Do not include any explanatory text outside the JSON structure.
"""

        payload = {
            "model": MODEL_NAME,
            "max_tokens": 2000,
            "temperature": 0,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            analysis_text = data["content"][0]["text"]
            
            # Try to extract JSON from the response
            json_match = re.search(r'```json\s*(.*?)\s*```', analysis_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # If no JSON code block, try to use the whole response
                json_str = analysis_text
            
            try:
                analysis = json.loads(json_str)
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON from Claude's response")
                # Create a basic structure with the raw text
                analysis = {
                    "Title": "Parsing Error",
                    "Description": "Failed to parse structured data from analysis",
                    "raw_analysis": analysis_text
                }
            
            return analysis
    
    except Exception as e:
        logger.error(f"Error calling Claude API: {str(e)}")
        return {"error": f"Error calling Claude API: {str(e)}"}

async def ask_gemini(text: str, url: str, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send extracted text to Gemini for enhanced analysis."""
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not found in environment variables")
        return {"error": "GEMINI_API_KEY not found in environment variables"}
    
    try:
        # Extract key information to provide as context
        title = extracted_data.get("title", "")
        description = extracted_data.get("description", "")
        meta_keywords = extracted_data.get("meta_keywords", "")
        headings = extracted_data.get("headings", [])
        paragraphs = extracted_data.get("paragraphs", [])
        industries = extracted_data.get("industries", [])
        
        # Create a more structured prompt with the extracted data
        prompt = f"""
You are a website analysis assistant specializing in B2B company analysis.
Here is the extracted information from the website {url}:

TITLE: {title}
DESCRIPTION: {description}
META KEYWORDS: {meta_keywords}
HEADINGS: {', '.join(headings[:10])}  # Limit to first 10 headings
DETECTED INDUSTRIES: {', '.join(industries)}

SAMPLE PARAGRAPHS:
{' '.join(paragraphs[:5])}  # Limit to first 5 paragraphs

FULL TEXT SAMPLE:
{text[:8000]}  # Limit text to avoid token limits

Please analyze this information and provide the following in a structured format:

1. Title: The main title or name of the website/company (use the most accurate representation)
2. Description: A concise description of what the website/company does (2-3 sentences)
3. Keywords: 10-15 keywords that best represent this website's content and purpose
4. Target Audience: Who this website is primarily targeting (be specific about industries, roles, company types)
5. Main Features/Services: The main offerings or services (list format)
6. Unique Value Proposition: What makes this website/company unique compared to competitors
7. Industries: Any specific industries this website targets (list format)
8. Company Size: If detectable, what size of companies this targets (SMB, mid-market, enterprise, etc.)
9. B2B Focus: Rate on a scale of 1-10 how focused this company is on B2B vs B2C
10. Pricing Model: If detectable, what pricing model they use (subscription, one-time, freemium, etc.)

Format your response as a structured JSON object with these fields. Do not include any explanatory text outside the JSON structure.
"""

        gemini_url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        
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
                    except json.JSONDecodeError:
                        logger.error("Failed to parse JSON from Gemini's response")
                        # Try to extract JSON with a more lenient approach
                        try:
                            # Find anything that looks like JSON
                            json_pattern = r'\{.*\}'
                            json_match = re.search(json_pattern, analysis_text, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(0)
                                analysis = json.loads(json_str)
                            else:
                                # Create a basic structure with the raw text
                                analysis = {
                                    "Title": title or "Parsing Error",
                                    "Description": description or "Failed to parse structured data from analysis",
                                    "raw_analysis": analysis_text
                                }
                        except Exception:
                            # Create a basic structure with the raw text
                            analysis = {
                                "Title": title or "Parsing Error",
                                "Description": description or "Failed to parse structured data from analysis",
                                "raw_analysis": analysis_text
                            }
                    
                    return analysis
            
            return {"error": "Unexpected response format from Gemini API"}
    
    except Exception as e:
        logger.error(f"Error calling Gemini API: {str(e)}")
        return {"error": f"Error calling Gemini API: {str(e)}"}

async def analyze_website(url: str) -> Optional[Dict[str, Any]]:
    """
    Enhanced logic to fetch website, extract text, and analyze via LLM.
    
    Args:
        url: The URL of the website to analyze
        
    Returns:
        A dictionary containing the extracted website data and analysis
    """
    try:
        logger.info(f"Analyzing website: {url}")
        website_data = await extract_visible_text(url)
        
        if not website_data["content"]:
            logger.error(f"Failed to extract content from {url}")
            return None

        # Use Gemini for analysis with enhanced extracted data
        logger.info("Using Gemini for enhanced analysis...")
        analysis = await ask_gemini(website_data["content"], url, website_data)
        
        # If no industries were detected in the extraction, use the ones from the LLM analysis
        if not website_data.get("industries") and analysis.get("Industries"):
            if isinstance(analysis["Industries"], list):
                website_data["industries"] = analysis["Industries"]
            elif isinstance(analysis["Industries"], str):
                website_data["industries"] = [industry.strip() for industry in analysis["Industries"].split(',')]
        
        # Combine everything into a result dictionary with enhanced fields
        result = {
            "url": url,
            "title": analysis.get("Title", website_data["title"]),
            "description": analysis.get("Description", website_data["description"]),
            "keywords": analysis.get("Keywords", []),
            "target_audience": analysis.get("Target Audience", ""),
            "main_features": analysis.get("Main Features/Services", []),
            "unique_value": analysis.get("Unique Value Proposition", ""),
            "industries": website_data.get("industries", analysis.get("Industries", [])),
            "company_size": analysis.get("Company Size", ""),
            "b2b_focus": analysis.get("B2B Focus", 5),  # Default to middle of scale if not provided
            "pricing_model": analysis.get("Pricing Model", ""),
            "headings": website_data["headings"],
            "paragraphs": website_data.get("paragraphs", [])[:5],  # Store a sample of paragraphs
            "links": website_data.get("links", [])[:10],  # Store a sample of links
            "raw_text": website_data["content"][:1000],  # Store a sample of the raw text
            "screenshot": website_data["screenshot"],
            "meta_keywords": website_data.get("meta_keywords", ""),
            "raw_analysis": analysis
        }
        
        logger.info(f"Enhanced analysis complete for {url}")
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing website: {str(e)}")
        return None

# Function to be called from flow_controller.py
async def analyze_website_with_browser(url: str) -> Optional[Dict[str, Any]]:
    """
    Analyze a website using Playwright and LLM.
    This function name matches what's expected in flow_controller.py
    
    Args:
        url: The URL of the website to analyze
        
    Returns:
        A dictionary containing the extracted website data
    """
    return await analyze_website(url)

async def main(url: str):
    """Full flow: fetch website content, send to LLM, print summary."""
    result = await analyze_website(url)
    
    if result:
        print("\n=== Website Analysis ===\n")
        print(f"Title: {result['title']}")
        print(f"Description: {result['description']}")
        print(f"Keywords: {', '.join(result['keywords']) if isinstance(result['keywords'], list) else result['keywords']}")
        print(f"Target Audience: {result['target_audience']}")
        print(f"Unique Value: {result['unique_value']}")
        print(f"Industries: {', '.join(result['industries']) if isinstance(result['industries'], list) else result['industries']}")
    else:
        print("Analysis failed. Check logs for details.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python website_analyzer.py <URL>")
        sys.exit(1)

    url = sys.argv[1]
    asyncio.run(main(url))
