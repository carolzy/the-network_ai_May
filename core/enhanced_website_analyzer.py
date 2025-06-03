import asyncio
from playwright.async_api import async_playwright
import httpx
import os
import json
import re
import logging
from typing import Dict, Any, Optional, List, Set
from dotenv import load_dotenv
from urllib.parse import urljoin, urlparse
import time

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
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Flag to determine which LLM to use
USE_GEMINI = True  # Set to False to use Claude instead

# Customer-related page keywords to look for
CUSTOMER_KEYWORDS = [
    'customers', 'client', 'case studies', 'case study', 'success stories', 
    'testimonials', 'use cases', 'portfolio', 'references', 'customer stories',
    'who we serve', 'industries', 'sectors', 'solutions', 'examples',
    'featured customers', 'customer spotlight', 'customer success',
    # Research/AI company specific terms
    'partners', 'collaborations', 'research partners', 'applications', 
    'implementations', 'deployments', 'users', 'adopters', 'organizations',
    'enterprise', 'business', 'commercial', 'companies', 'startups'
]

# Blog/content keywords
CONTENT_KEYWORDS = [
    'blog', 'news', 'insights', 'resources', 'content', 'articles',
    'publications', 'thought leadership', 'whitepapers', 'guides',
    # Research/AI company specific terms
    'research', 'papers', 'publications', 'journal', 'studies', 'findings',
    'experiments', 'reports', 'documentation', 'technical', 'academic',
    'announcements', 'updates', 'press', 'media'
]

async def find_relevant_pages(page, base_url: str) -> Dict[str, List[str]]:
    """Find customer-related and content pages from navigation and footer links."""
    try:
        logger.info("Scanning for customer-related and content pages...")
        
        # Extract all navigation and footer links
        links = await page.evaluate("""
            () => {
                const links = [];
                // Get all links from navigation areas
                const navSelectors = [
                    'nav a', 'header a', 'footer a', '.navigation a', '.nav a', 
                    '.menu a', '.header a', '.footer a', '[role="navigation"] a'
                ];
                
                const allLinks = new Set();
                navSelectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(link => {
                        if (link.href && link.textContent.trim()) {
                            allLinks.add(JSON.stringify({
                                href: link.href,
                                text: link.textContent.trim().toLowerCase()
                            }));
                        }
                    });
                });
                
                // Also check main content area for prominent links
                document.querySelectorAll('main a, .main a, .content a').forEach(link => {
                    if (link.href && link.textContent.trim()) {
                        allLinks.add(JSON.stringify({
                            href: link.href,
                            text: link.textContent.trim().toLowerCase()
                        }));
                    }
                });
                
                return Array.from(allLinks).map(linkStr => JSON.parse(linkStr));
            }
        """)
        
        customer_pages = []
        content_pages = []
        
        # Categorize links based on keywords
        for link in links:
            href = link['href']
            text = link['text']
            
            # Skip external links, fragments, and javascript
            if not href.startswith(base_url) and not href.startswith('/'):
                continue
            if href.startswith('#') or href.startswith('javascript:'):
                continue
                
            # Convert relative URLs to absolute
            if href.startswith('/'):
                href = urljoin(base_url, href)
            
            # Check for customer-related keywords
            if any(keyword in text for keyword in CUSTOMER_KEYWORDS):
                customer_pages.append(href)
                logger.info(f"Found customer page: {text} -> {href}")
            
            # Check for content-related keywords
            elif any(keyword in text for keyword in CONTENT_KEYWORDS):
                content_pages.append(href)
                logger.info(f"Found content page: {text} -> {href}")
        
        # Remove duplicates and limit results
        customer_pages = list(set(customer_pages))[:5]  # Limit to 5 customer pages
        content_pages = list(set(content_pages))[:3]    # Limit to 3 content pages
        
        return {
            "customer_pages": customer_pages,
            "content_pages": content_pages
        }
        
    except Exception as e:
        logger.error(f"Error finding relevant pages: {str(e)}")
        return {"customer_pages": [], "content_pages": []}

async def extract_customer_data(page, url: str) -> Dict[str, Any]:
    """Extract customer names, case studies, and industry information from a page."""
    try:
        logger.info(f"Extracting customer data from {url}")
        
        # Navigate to the page
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)  # Wait for dynamic content
        
        # Extract customer information
        customer_data = await page.evaluate("""
            () => {
                const customers = new Set();
                const industries = new Set();
                const caseStudies = [];
                
                // Look for company names in various contexts
                const companyPatterns = [
                    // Text patterns that often indicate company names
                    /([A-Z][a-z]+ (?:Inc|LLC|Corp|Corporation|Ltd|Limited|Company|Co\\.?))/g,
                    /([A-Z][a-zA-Z]+ (?:Technologies|Solutions|Systems|Software|Group|Partners))/g,
                    // Common company name patterns
                    /\\b([A-Z][a-zA-Z]{2,}(?:\\s+[A-Z][a-zA-Z]{2,}){0,2})\\s+(?:uses|chose|selected|implements|deployed)/gi
                ];
                
                // Get all text content
                const allText = document.body.textContent || '';
                
                // Extract potential company names using patterns
                companyPatterns.forEach(pattern => {
                    const matches = allText.match(pattern);
                    if (matches) {
                        matches.forEach(match => {
                            const cleaned = match.replace(/\\s+(uses|chose|selected|implements|deployed).*$/i, '').trim();
                            if (cleaned.length > 2 && cleaned.length < 50) {
                                customers.add(cleaned);
                            }
                        });
                    }
                });
                
                // Look for industry mentions
                const industryTerms = [
                    'healthcare', 'finance', 'banking', 'insurance', 'technology', 'manufacturing',
                    'retail', 'education', 'government', 'nonprofit', 'energy', 'utilities',
                    'telecommunications', 'media', 'entertainment', 'hospitality', 'travel',
                    'transportation', 'logistics', 'construction', 'real estate', 'legal',
                    'consulting', 'agriculture', 'food', 'automotive', 'aerospace', 'pharmaceutical'
                ];
                
                const lowerText = allText.toLowerCase();
                industryTerms.forEach(industry => {
                    if (lowerText.includes(industry)) {
                        industries.add(industry);
                    }
                });
                
                // Look for structured customer information (logos, cards, etc.)
                const customerElements = document.querySelectorAll([
                    '.customer', '.client', '.case-study', '.testimonial',
                    '[class*="customer"]', '[class*="client"]', '[class*="logo"]',
                    '[class*="case"]', '[class*="story"]'
                ].join(', '));
                
                customerElements.forEach(element => {
                    const text = element.textContent.trim();
                    const imgAlt = element.querySelector('img')?.alt || '';
                    
                    if (text && text.length < 100) {
                        customers.add(text);
                    }
                    if (imgAlt && imgAlt.length < 50) {
                        customers.add(imgAlt);
                    }
                });
                
                // Look for case study titles/descriptions
                const headings = document.querySelectorAll('h1, h2, h3, h4');
                headings.forEach(heading => {
                    const text = heading.textContent.trim();
                    if (text.length > 20 && text.length < 200 && 
                        (text.toLowerCase().includes('case') || 
                         text.toLowerCase().includes('story') ||
                         text.toLowerCase().includes('success'))) {
                        caseStudies.push(text);
                    }
                });
                
                return {
                    customers: Array.from(customers).slice(0, 20), // Limit to 20
                    industries: Array.from(industries),
                    caseStudies: caseStudies.slice(0, 10), // Limit to 10
                    textSample: allText.slice(0, 2000) // Sample for LLM analysis
                };
            }
        """)
        
        return customer_data
        
    except Exception as e:
        logger.error(f"Error extracting customer data from {url}: {str(e)}")
        return {"customers": [], "industries": [], "caseStudies": [], "textSample": ""}

async def analyze_with_customer_intelligence(website_data: Dict[str, Any], customer_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Use LLM to analyze website and customer data to generate strategic insights."""
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not found in environment variables")
        return {"error": "GEMINI_API_KEY not found in environment variables"}
    
    try:
        # Combine all customer data
        all_customers = []
        all_industries = []
        all_case_studies = []
        
        for data in customer_data:
            all_customers.extend(data.get("customers", []))
            all_industries.extend(data.get("industries", []))
            all_case_studies.extend(data.get("caseStudies", []))
        
        # Remove duplicates
        all_customers = list(set(all_customers))
        all_industries = list(set(all_industries))
        
        prompt = f"""
You are a strategic business intelligence analyst. Analyze this company's website and customer data to provide actionable insights.

COMPANY WEBSITE DATA:
Title: {website_data.get("title", "")}
Description: {website_data.get("description", "")}
Main Services: {website_data.get("main_features", [])}
Target Audience: {website_data.get("target_audience", "")}
Industries: {website_data.get("industries", [])}

CUSTOMER INTELLIGENCE:
Existing Customers Found: {all_customers[:15]}  # Limit for token efficiency
Industries Served: {all_industries}
Case Studies/Success Stories: {all_case_studies[:5]}

Based on this analysis, provide the following strategic insights:

1. **Customer Analysis**: Clean and validate the customer list - identify which are real companies vs noise
2. **Industry Focus**: Identify the top 3-5 industries this company primarily serves
3. **Target Recommendations**: Suggest 3-5 high-quality prospective target customers that would be excellent fits

For the target recommendations, create a detailed analysis with:
- Company Name
- Industry 
- Size (Enterprise/Mid-market/SMB)
- Company Website URL
- Why They're a Good Fit (be very insightful - consider their business model, growth stage, pain points, competitive landscape)

Format your response as a JSON object with these exact fields:
{{
    "validated_customers": ["list of real company names"],
    "primary_industries": ["top industries served"],
    "target_recommendations": [
        {{
            "company_name": "Company Name",
            "industry": "Industry",
            "size": "Company Size",
            "website": "https://company-website.com",
            "why_good_fit": "Detailed strategic reasoning"
        }}
    ]
}}

Make the "why_good_fit" explanations very strategic and insightful, considering:
- Industry trends and growth
- Technology adoption patterns
- Competitive positioning
- Business model alignment
- Scale and complexity needs
"""

        gemini_url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 2048
            }
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:  # Increased timeout to 60 seconds
            response = await client.post(gemini_url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    analysis_text = candidate["content"]["parts"][0]["text"]
                    
                    # Extract JSON from response
                    json_match = re.search(r'```json\s*(.*?)\s*```', analysis_text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        json_pattern = r'\{.*\}'
                        json_match = re.search(json_pattern, analysis_text, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                        else:
                            return {"error": "Could not extract JSON from response", "raw_response": analysis_text}
                    
                    try:
                        analysis = json.loads(json_str)
                        
                        # Validate the response structure
                        if not isinstance(analysis, dict):
                            logger.error(f"Invalid response format: {type(analysis)}")
                            return {"error": f"Invalid response format: expected dict, got {type(analysis)}"}
                            
                        # Check for required fields
                        required_fields = ["validated_customers", "primary_industries", "target_recommendations"]
                        missing_fields = [field for field in required_fields if field not in analysis]
                        if missing_fields:
                            logger.error(f"Missing required fields in response: {missing_fields}")
                            return {"error": f"Missing required fields in response: {missing_fields}"}
                            
                        # Validate target_recommendations structure
                        if not isinstance(analysis.get("target_recommendations", []), list):
                            logger.error("target_recommendations is not a list")
                            return {"error": "target_recommendations is not a list"}
                            
                        # Check each recommendation has required fields
                        for i, rec in enumerate(analysis.get("target_recommendations", [])):
                            if not isinstance(rec, dict):
                                logger.error(f"Recommendation {i} is not a dictionary")
                                return {"error": f"Recommendation {i} is not a dictionary"}
                                
                            rec_required_fields = ["company_name", "industry", "size", "why_good_fit"]
                            rec_missing_fields = [field for field in rec_required_fields if field not in rec]
                            if rec_missing_fields:
                                logger.error(f"Recommendation {i} missing fields: {rec_missing_fields}")
                                return {"error": f"Recommendation {i} missing fields: {rec_missing_fields}"}
                                
                            # Add website field if missing (backward compatibility)
                            if "website" not in rec:
                                company_name = rec.get("company_name", "")
                                if company_name:
                                    # Generate a simple domain name from company name
                                    domain = company_name.lower().replace(" ", "").replace("&", "and").replace("(", "").replace(")", "")
                                    rec["website"] = f"https://www.{domain}.com"
                                else:
                                    rec["website"] = ""
                        
                        return analysis
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON: {e}")
                        return {"error": f"Failed to parse JSON: {e}"}
                    except Exception as e:
                        logger.error(f"Error in customer intelligence analysis: {str(e)}")
                        import traceback
                        logger.error(traceback.format_exc())
                        return {"error": f"Error in analysis: {str(e)}"}
            
            return {"error": "Unexpected response format from Gemini API"}
    
    except Exception as e:
        logger.error(f"Error in customer intelligence analysis: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {"error": f"Error in analysis: {str(e)}"}
    try:
        logger.info(f"Starting enhanced analysis for: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
            )
            page = await context.new_page()
            
            # First, analyze the main page (existing functionality)
            logger.info("Analyzing main page...")
            await page.goto(url, wait_until="networkidle", timeout=90000)
            
            # Extract basic website data (simplified version of original function)
            title = await page.title()
            description = await page.evaluate("""
                () => {
                    const metaDescription = document.querySelector('meta[name="description"]');
                    return metaDescription ? metaDescription.getAttribute('content') : '';
                }
            """)
            
            # Find customer-related pages
            relevant_pages = await find_relevant_pages(page, url)
            
            # Extract customer data from relevant pages
            all_customer_data = []
            
            # Analyze customer pages
            for customer_page_url in relevant_pages["customer_pages"]:
                try:
                    logger.info(f"Analyzing customer page: {customer_page_url}")
                    customer_data = await extract_customer_data(page, customer_page_url)
                    if customer_data["customers"] or customer_data["industries"]:
                        all_customer_data.append(customer_data)
                    await asyncio.sleep(1)  # Be respectful with requests
                except Exception as e:
                    logger.warning(f"Failed to analyze customer page {customer_page_url}: {e}")
                    continue
            
            # Also check content pages for customer mentions
            for content_page_url in relevant_pages["content_pages"]:
                try:
                    logger.info(f"Analyzing content page: {content_page_url}")
                    customer_data = await extract_customer_data(page, content_page_url)
                    if customer_data["customers"] or customer_data["industries"]:
                        all_customer_data.append(customer_data)
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Failed to analyze content page {content_page_url}: {e}")
                    continue
                    
            # If no customer or content pages were found, analyze the main page
            if len(all_customer_data) == 0:
                logger.info("No customer or content pages found. Analyzing main page for customer information...")
                try:
                    # We're already on the main page, so extract data from it
                    customer_data = await extract_customer_data(page, url)
                    if customer_data["customers"] or customer_data["industries"]:
                        all_customer_data.append(customer_data)
                        
                    # Also try to find and analyze the "about" page if it exists
                    about_page_url = None
                    about_links = await page.evaluate("""
                        () => {
                            const aboutLinks = [];
                            document.querySelectorAll('a').forEach(link => {
                                const text = link.textContent.trim().toLowerCase();
                                const href = link.href;
                                if ((text.includes('about') || href.includes('about')) && 
                                    href && !href.startsWith('#') && !href.startsWith('javascript:')) {
                                    aboutLinks.push(href);
                                }
                            });
                            return aboutLinks;
                        }
                    """)
                    
                    if about_links and len(about_links) > 0:
                        about_page_url = about_links[0]
                        logger.info(f"Found about page: {about_page_url}")
                        await page.goto(about_page_url, wait_until="networkidle", timeout=60000)
                        about_data = await extract_customer_data(page, about_page_url)
                        if about_data["customers"] or about_data["industries"]:
                            all_customer_data.append(about_data)
                except Exception as e:
                    logger.warning(f"Failed to analyze main/about page: {e}")
                    
                # Even if we don't find customer data, create a minimal entry so we have something to analyze
                if len(all_customer_data) == 0:
                    logger.info("Creating minimal customer data from main page content")
                    all_customer_data.append({
                        "customers": [],
                        "industries": [],
                        "caseStudies": [],
                        "textSample": await page.evaluate('() => document.body.textContent')
                    })

            
            await browser.close()
            
            # Basic website data structure
            website_data = {
                "url": url,
                "title": title,
                "description": description,
                "main_features": [],  # Would be populated by full analysis
                "target_audience": "",  # Would be populated by full analysis
                "industries": []  # Would be populated by full analysis
            }
            
            # Generate strategic insights using LLM
            logger.info("Generating strategic insights...")
            strategic_analysis = await analyze_with_customer_intelligence(website_data, all_customer_data)
            
            # Combine everything into final result
            result = {
                "website_data": website_data,
                "customer_intelligence": {
                    "pages_analyzed": len(all_customer_data),
                    "customer_pages_found": relevant_pages["customer_pages"],
                    "content_pages_found": relevant_pages["content_pages"],
                    "raw_customer_data": all_customer_data
                },
                "strategic_analysis": strategic_analysis
            }
            
            logger.info("Enhanced analysis complete!")
            return result
            
    except Exception as e:
        logger.error(f"Error in enhanced website analysis: {str(e)}")
        return None

def format_target_recommendations(analysis_result: Dict[str, Any]) -> str:
    """Format the target recommendations into a nice table format."""
    if not analysis_result or "strategic_analysis" not in analysis_result:
        return "No analysis results available."
    
    strategic = analysis_result["strategic_analysis"]
    
    if "error" in strategic:
        return f"Analysis error: {strategic['error']}"
    
    output = []
    output.append("=== WEBSITE ANALYSIS WITH CUSTOMER INTELLIGENCE ===\n")
    
    # Website Summary
    website = analysis_result["website_data"]
    output.append(f"Company: {website['title']}")
    output.append(f"Website: {website['url']}")
    output.append(f"Description: {website['description']}\n")
    
    # Customer Intelligence Summary
    customer_intel = analysis_result["customer_intelligence"]
    output.append(f"Pages Analyzed: {customer_intel['pages_analyzed']}")
    output.append(f"Customer Pages Found: {len(customer_intel['customer_pages_found'])}")
    output.append(f"Content Pages Found: {len(customer_intel['content_pages_found'])}\n")
    
    # Validated Customers
    if "validated_customers" in strategic and strategic["validated_customers"]:
        output.append("EXISTING CUSTOMERS:")
        for customer in strategic["validated_customers"][:10]:  # Show top 10
            output.append(f"  • {customer}")
        output.append("")
    
    # Primary Industries
    if "primary_industries" in strategic and strategic["primary_industries"]:
        output.append("PRIMARY INDUSTRIES SERVED:")
        for industry in strategic["primary_industries"]:
            output.append(f"  • {industry.title()}")
        output.append("")
    
    # Target Recommendations Table
    if "target_recommendations" in strategic and strategic["target_recommendations"]:
        output.append("TARGET CUSTOMER RECOMMENDATIONS:")
        output.append("-" * 120)
        output.append(f"{'Industry':<15} {'Company Name':<25} {'Size':<12} {'Website':<32} {'Why They\'re a Good Fit':<60}")
        output.append("-" * 120)
        
        for rec in strategic["target_recommendations"]:
            industry = rec.get("industry", "")[:14]
            company = rec.get("company_name", "")[:24]
            size = rec.get("size", "")[:11]
            website = rec.get("website", "")[:31]
            reason = rec.get("why_good_fit", "")[:59]
            
            # Wrap long reasons
            if len(reason) > 59:
                reason = reason[:57] + "..."
            
            output.append(f"{industry:<15} {company:<25} {size:<12} {website:<32} {reason:<60}")
        
        output.append("-" * 120)
    
    return "\n".join(output)

# This is the main website analysis function that should be called from main()
async def analyze_website(url: str) -> Optional[Dict[str, Any]]:
    """Enhanced website analysis that includes customer intelligence gathering."""
    try:
        logger.info(f"Starting enhanced analysis for: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
            )
            page = await context.new_page()
            
            # First, analyze the main page (existing functionality)
            logger.info("Analyzing main page...")
            await page.goto(url, wait_until="networkidle", timeout=90000)
            
            # Extract basic website data (simplified version of original function)
            title = await page.title()
            description = await page.evaluate("""
                () => {
                    const metaDescription = document.querySelector('meta[name="description"]');
                    return metaDescription ? metaDescription.getAttribute('content') : '';
                }
            """)
            
            # Find customer-related pages
            logger.info("Scanning for customer-related and content pages...")
            relevant_pages = await find_relevant_pages(page, url)
            
            # Extract customer data from relevant pages
            all_customer_data = []
            
            # Analyze customer pages
            for customer_page_url in relevant_pages["customer_pages"]:
                try:
                    logger.info(f"Analyzing customer page: {customer_page_url}")
                    customer_data = await extract_customer_data(page, customer_page_url)
                    if customer_data["customers"] or customer_data["industries"]:
                        all_customer_data.append(customer_data)
                    await asyncio.sleep(1)  # Be respectful with requests
                except Exception as e:
                    logger.warning(f"Failed to analyze customer page {customer_page_url}: {e}")
                    continue
            
            # Also check content pages for customer mentions
            for content_page_url in relevant_pages["content_pages"]:
                try:
                    logger.info(f"Analyzing content page: {content_page_url}")
                    customer_data = await extract_customer_data(page, content_page_url)
                    if customer_data["customers"] or customer_data["industries"]:
                        all_customer_data.append(customer_data)
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Failed to analyze content page {content_page_url}: {e}")
                    continue
                    
            # If no customer or content pages were found, analyze the main page
            if len(all_customer_data) == 0:
                logger.info("No customer or content pages found. Analyzing main page for customer information...")
                try:
                    # We're already on the main page, so extract data from it
                    customer_data = await extract_customer_data(page, url)
                    if customer_data["customers"] or customer_data["industries"]:
                        all_customer_data.append(customer_data)
                        
                    # Also try to find and analyze the "about" page if it exists
                    about_links = await page.evaluate("""
                        () => {
                            const aboutLinks = [];
                            document.querySelectorAll('a').forEach(link => {
                                const text = link.textContent.trim().toLowerCase();
                                const href = link.href;
                                if ((text.includes('about') || href.includes('about')) && 
                                    href && !href.startsWith('#') && !href.startsWith('javascript:')) {
                                    aboutLinks.push(href);
                                }
                            });
                            return aboutLinks;
                        }
                    """)
                    
                    if about_links and len(about_links) > 0:
                        about_page_url = about_links[0]
                        logger.info(f"Found about page: {about_page_url}")
                        await page.goto(about_page_url, wait_until="networkidle", timeout=60000)
                        about_data = await extract_customer_data(page, about_page_url)
                        if about_data["customers"] or about_data["industries"]:
                            all_customer_data.append(about_data)
                except Exception as e:
                    logger.warning(f"Failed to analyze main/about page: {e}")
                    
                # Even if we don't find customer data, create a minimal entry so we have something to analyze
                if len(all_customer_data) == 0:
                    logger.info("Creating minimal customer data from main page content")
                    all_customer_data.append({
                        "customers": [],
                        "industries": [],
                        "caseStudies": [],
                        "textSample": await page.evaluate('() => document.body.textContent')
                    })
            
            await browser.close()
            
            # Basic website data structure
            website_data = {
                "url": url,
                "title": title,
                "description": description,
                "main_features": [],  # Would be populated by full analysis
                "target_audience": "",  # Would be populated by full analysis
                "industries": []  # Would be populated by full analysis
            }
            
            # Generate strategic insights using LLM
            logger.info("Generating strategic insights...")
            strategic_analysis = await analyze_with_customer_intelligence(website_data, all_customer_data)
            
            # Combine everything into final result
            result = {
                "website_data": website_data,
                "customer_intelligence": {
                    "pages_analyzed": len(all_customer_data),
                    "customer_pages_found": relevant_pages["customer_pages"],
                    "content_pages_found": relevant_pages["content_pages"],
                    "raw_customer_data": all_customer_data
                },
                "strategic_analysis": strategic_analysis
            }
            
            logger.info("Enhanced analysis complete!")
            return result
            
    except Exception as e:
        logger.error(f"Error in enhanced website analysis: {str(e)}")
        return None

async def generate_ui_data_from_analysis(website_analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate UI-specific data from the website analysis result.
    
    Args:
        website_analysis_result: The result from analyze_website() function
        
    Returns:
        Dictionary containing UI-ready data structure
    """
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not found in environment variables")
        return {"error": "GEMINI_API_KEY not found in environment variables"}
    
    try:
        # Import the prompt function
        from target_events_prompt import get_ui_generation_prompt
        
        # Generate the prompt with website analysis data
        prompt = get_ui_generation_prompt(website_analysis_result)
        
        gemini_url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 4096
            }
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:  # Increased timeout to 60 seconds
            response = await client.post(gemini_url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    analysis_text = candidate["content"]["parts"][0]["text"]
                    
                    # Extract JSON from response
                    json_match = re.search(r'```json\s*(.*?)\s*```', analysis_text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        # Try to find JSON object in the text
                        json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                        else:
                            return {"error": "Could not extract JSON from response", "raw_response": analysis_text}
                    
                    try:
                        # First attempt: direct JSON parsing
                        ui_data = json.loads(json_str)
                        return ui_data
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse UI data JSON: {e}")
                        try:
                            # Second attempt: fix common escape sequence issues
                            # Replace problematic escape sequences
                            fixed_json = re.sub(r'\\(?!["\\bfnrt/]|u[0-9a-fA-F]{4})', r'\\\\', json_str)
                            ui_data = json.loads(fixed_json)
                            return ui_data
                        except json.JSONDecodeError:
                            try:
                                # Third attempt: use ast.literal_eval as a fallback
                                import ast
                                # Convert JSON-like string to Python dict
                                ui_data = ast.literal_eval(json_str)
                                return ui_data
                            except (SyntaxError, ValueError):
                                # If all parsing attempts fail
                                return {"error": f"Failed to parse JSON: {e}", "raw_response": analysis_text}
            
            return {"error": "Unexpected response format from Gemini API"}
    
    except Exception as e:
        logger.error(f"Error generating UI data: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {"error": f"Error generating UI data: {str(e)}"}

# Modified main function that includes UI data generation
async def analyze_website_with_ui_data(url: str) -> Optional[Dict[str, Any]]:
    """
    Complete website analysis that generates both strategic analysis AND UI data.
    
    Args:
        url: The URL of the website to analyze
        
    Returns:
        A dictionary containing all analysis results plus UI-ready data
    """
    try:
        logger.info(f"Starting complete analysis for: {url}")
        
        # Step 1: Run the existing enhanced website analysis
        website_analysis_result = await analyze_website(url)  # Your existing function
        
        if not website_analysis_result:
            logger.error("Failed to get website analysis result")
            return None
        
        # Step 2: Generate UI-specific data from the analysis
        logger.info("Generating UI data from analysis...")
        ui_data = await generate_ui_data_from_analysis(website_analysis_result)
        
        # Step 3: Combine everything
        final_result = {
            **website_analysis_result,  # All original analysis
            "ui_data": ui_data          # UI-specific structured data
        }
        
        logger.info("Complete analysis with UI data finished!")
        return final_result
        
    except Exception as e:
        logger.error(f"Error in complete website analysis: {str(e)}")
        return None

# Usage example - replace your main() function call with this:
async def main_with_ui(url: str):
    """Main function that generates both analyses and UI data."""
    result = await analyze_website_with_ui_data(url)
    
    if result:
        # Print traditional analysis output  
        traditional_output = format_target_recommendations(result)
        print(traditional_output)
        print("\n" + "="*60 + "\n")
        
        # Save results
        with open("complete_analysis_report.json", "w") as f:
            json.dump(result, f, indent=2)
        
        # Save UI data separately for frontend
        if "ui_data" in result and "error" not in result["ui_data"]:
            with open("ui_data.json", "w") as f:
                json.dump(result["ui_data"], f, indent=2)
            print(" UI data ready! Saved to ui_data.json")
            print(" Complete analysis saved to complete_analysis_report.json")
        else:
            print(" UI data generation failed")
            if "ui_data" in result:
                print(f"Error: {result['ui_data'].get('error', 'Unknown error')}")
    else:
        print("Analysis failed. Check logs for details.")

async def main(url: str):
    """Main function to run the enhanced analysis."""
    result = await analyze_website(url)
    
    if result:
        formatted_output = format_target_recommendations(result)
        print(formatted_output)
        
        # Optionally save to file
        with open("website_analysis_report.json", "w") as f:
            json.dump(result, f, indent=2)
    else:
        print("Analysis failed. Check logs for details.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
        asyncio.run(main_with_ui(url))
    else:
        print("Usage: python enhanced_website_analyzer.py <url>")
        sys.exit(1)
