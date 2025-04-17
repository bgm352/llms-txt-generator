import streamlit as st
import os
import logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup, Comment
import re
import html2text
import json
import base64
import time
import random
import csv
import io
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define schema structure for pharmaceutical products
PHARMA_SCHEMA = {
    "brandName": None,
    "genericName": None,
    "manufacturer": "Genentech",
    "approvedIndications": [],
    "drugClass": None,
    "dosageForm": [],
    "administration": None,
    "prescribingInfo": None,
    "patientResources": [],
    "sideEffects": [],
    "warnings": [],
    "interactions": [],
    "mechanismOfAction": None,
    "clinicalTrials": [],
    "approvalDate": None,
    "packageInsertURL": None,
}

# Map of known Genentech products
GENENTECH_PRODUCTS = {
    "Oncology": [
        {"brandName": "Avastin", "genericName": "bevacizumab"},
        {"brandName": "Herceptin", "genericName": "trastuzumab"},
        {"brandName": "Rituxan", "genericName": "rituximab"},
        {"brandName": "Perjeta", "genericName": "pertuzumab"},
        {"brandName": "Kadcyla", "genericName": "ado-trastuzumab emtansine"},
        {"brandName": "Gazyva", "genericName": "obinutuzumab"},
        {"brandName": "Tarceva", "genericName": "erlotinib"},
        {"brandName": "Polivy", "genericName": "polatuzumab vedotin-piiq"},
        {"brandName": "Tecentriq", "genericName": "atezolizumab"},
        {"brandName": "Cotellic", "genericName": "cobimetinib"},
        {"brandName": "Alecensa", "genericName": "alectinib"},
        {"brandName": "Zelboraf", "genericName": "vemurafenib"},
        {"brandName": "Venclexta", "genericName": "venetoclax"},
        {"brandName": "Erivedge", "genericName": "vismodegib"},
        {"brandName": "Xeloda", "genericName": "capecitabine"}
    ],
    "Neuroscience": [
        {"brandName": "Ocrevus", "genericName": "ocrelizumab"}
    ],
    "Ophthalmology": [
        {"brandName": "Lucentis", "genericName": "ranibizumab"}
    ],
    "Immunology and Respiratory": [
        {"brandName": "Actemra", "genericName": "tocilizumab"},
        {"brandName": "Xolair", "genericName": "omalizumab"},
        {"brandName": "Esbriet", "genericName": "pirfenidone"},
        {"brandName": "Pulmozyme", "genericName": "dornase alfa"}
    ],
    "Hematology": [
        {"brandName": "Hemlibra", "genericName": "emicizumab"},
        {"brandName": "Activase", "genericName": "alteplase"},
        {"brandName": "Cathflo Activase", "genericName": "alteplase"},
        {"brandName": "TNKase", "genericName": "tenecteplase"}
    ],
    "Infectious Disease": [
        {"brandName": "Xofluza", "genericName": "baloxavir marboxil"},
        {"brandName": "Tamiflu", "genericName": "oseltamivir"},
        {"brandName": "Valcyte", "genericName": "valganciclovir"},
        {"brandName": "Cytovene", "genericName": "ganciclovir"},
        {"brandName": "Fuzeon", "genericName": "enfuvirtide"},
        {"brandName": "Invirase", "genericName": "saquinavir"},
        {"brandName": "Rocephin", "genericName": "ceftriaxone"}
    ],
    "Metabolic and Endocrinology": [
        {"brandName": "Nutropin", "genericName": "somatropin"},
        {"brandName": "Boniva", "genericName": "ibandronate"},
        {"brandName": "Xenical", "genericName": "orlistat"}
    ],
    "Other Medicines": [
        {"brandName": "CellCept", "genericName": "mycophenolate mofetil"},
        {"brandName": "Pegasys", "genericName": "peginterferon alfa-2a"},
        {"brandName": "Anaprox", "genericName": "naproxen sodium"},
        {"brandName": "EC-Naprosyn", "genericName": "naproxen"},
        {"brandName": "Naprosyn", "genericName": "naproxen"},
        {"brandName": "Klonopin", "genericName": "clonazepam"},
        {"brandName": "Kytril", "genericName": "granisetron"},
        {"brandName": "Roferon-A", "genericName": "interferon alfa-2a"},
        {"brandName": "Romazicon", "genericName": "flumazenil"},
        {"brandName": "Valium", "genericName": "diazepam"},
        {"brandName": "Zenapax", "genericName": "daclizumab"}
    ]
}

class WebCrawler:
    def __init__(self):
        # More realistic browser user agents
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.2 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
        ]
        self.visited_urls = set()
        
    def crawl(self, url, depth=1, max_pages=10, schema_type="pharma"):
        """
        Crawl a website up to a specified depth and number of pages,
        extracting schema information
        """
        results = []
        self.visited_urls = set()
        
        # First get the base schema
        base_schema = None
        if schema_type == "pharma":
            base_schema = self._extract_base_schema_from_url(url)
        
        def _crawl_recursive(current_url, current_depth):
            if current_depth > depth or len(self.visited_urls) >= max_pages or current_url in self.visited_urls:
                return
            
            self.visited_urls.add(current_url)
            
            # Extract content and schema
            content_result = crawl_website(current_url)
            schema_result = None
            
            if content_result['success']:
                # Extract schema from this page
                if schema_type == "pharma":
                    schema_result = self._extract_pharma_schema(
                        current_url, 
                        content_result, 
                        base_schema
                    )
                
                # Add results
                if schema_result:
                    results.append({
                        'url': current_url,
                        'content': content_result,
                        'schema': schema_result
                    })
                
                # Find more links to crawl if we haven't reached our depth or page limit
                if current_depth < depth and len(self.visited_urls) < max_pages:
                    try:
                        response = requests.get(current_url, headers={
                            'User-Agent': random.choice(self.user_agents)
                        }, timeout=10)
                        soup = BeautifulSoup(response.text, 'html.parser')
                        domain = urlparse(current_url).netloc
                        
                        # Find all links
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            absolute_url = urljoin(current_url, href)
                            
                            # Only follow links on the same domain
                            if urlparse(absolute_url).netloc == domain and absolute_url not in self.visited_urls:
                                # Prioritize important pages
                                priority_keywords = [
                                    'prescribing', 'information', 'patient', 'safety',
                                    'indication', 'dosage', 'administration', 'clinical',
                                    'trials', 'efficacy', 'side-effects', 'faq', 'about', 
                                    'isi', 'pi', 'medication-guide'
                                ]
                                
                                is_priority = any(keyword in absolute_url.lower() for keyword in priority_keywords)
                                
                                if is_priority:
                                    # Crawl priority pages first
                                    _crawl_recursive(absolute_url, current_depth + 1)
                                elif len(self.visited_urls) < max_pages:
                                    # Then crawl other pages
                                    _crawl_recursive(absolute_url, current_depth + 1)
                    except Exception as e:
                        logger.error(f"Error finding links on {current_url}: {str(e)}")
                            
        _crawl_recursive(url, 1)
        
        # Combine all schema results into a single comprehensive schema
        if results:
            combined_schema = self._combine_pharma_schemas([r['schema'] for r in results])
            return {
                'combined_schema': combined_schema,
                'page_results': results
            }
        return None
    
    def _extract_base_schema_from_url(self, url):
        """Extract initial schema information from URL and known product database"""
        schema = PHARMA_SCHEMA.copy()
        
        # Try to identify the product from the URL
        for category, products in GENENTECH_PRODUCTS.items():
            for product in products:
                brand_name = product['brandName'].lower()
                if brand_name in url.lower():
                    schema['brandName'] = product['brandName']
                    schema['genericName'] = product['genericName']
                    schema['drugClass'] = category
                    break
        
        return schema
    
    def _extract_pharma_schema(self, url, content_result, base_schema):
        """Extract pharmaceutical schema information from page content"""
        schema = base_schema.copy() if base_schema else PHARMA_SCHEMA.copy()
        
        # Extract information from metadata and content sections
        metadata = content_result.get('metadata', {})
        content_sections = content_result.get('content_sections', [])
        
        # Extract from title and description
        title = metadata.get('title', '')
        description = metadata.get('description', '')
        
        # If brand name not already set, try to extract it from title
        if not schema['brandName']:
            # Look for product name in title (assumed to be in format "Product Name - Description")
            if ' - ' in title:
                possible_brand = title.split(' - ')[0].strip()
                # Verify it's in our product list
                for category, products in GENENTECH_PRODUCTS.items():
                    for product in products:
                        if product['brandName'].lower() == possible_brand.lower():
                            schema['brandName'] = product['brandName']
                            schema['genericName'] = product['genericName']
                            schema['drugClass'] = category
                            break
        
        # Check for prescribing information URL
        important_links = content_result.get('important_links', [])
        for link in important_links:
            link_text = link.get('text', '').lower()
            link_url = link.get('url', '')
            
            if any(term in link_text for term in ['prescribing information', 'pi', 'package insert']):
                schema['packageInsertURL'] = link_url
        
        # Extract information from content sections
        for section in content_sections:
            section_title = section.get('title', '').lower()
            section_content = section.get('content', '')
            
            # Indications
            if any(term in section_title for term in ['indication', 'use', 'treat']):
                indications = self._extract_list_items(section_content)
                if indications:
                    schema['approvedIndications'].extend(indications)
            
            # Side effects
            if any(term in section_title for term in ['side effect', 'adverse', 'safety']):
                side_effects = self._extract_list_items(section_content)
                if side_effects:
                    schema['sideEffects'].extend(side_effects)
            
            # Warnings
            if any(term in section_title for term in ['warning', 'precaution', 'serious']):
                warnings = self._extract_list_items(section_content)
                if warnings:
                    schema['warnings'].extend(warnings)
            
            # Dosage
            if any(term in section_title for term in ['dosage', 'dose', 'administration']):
                if not schema['administration']:
                    schema['administration'] = section_content.strip()
                
                # Extract dosage forms
                dosage_forms = re.findall(r'(?:available|supplied)(?:\s+as)?(?:\s+an?)?\s+([^.]+(?:tablet|capsule|injection|solution|suspension|vial|infusion)[^.]*)', 
                                         section_content.lower())
                if dosage_forms:
                    schema['dosageForm'].extend([form.strip() for form in dosage_forms])
            
            # Mechanism of action
            if any(term in section_title for term in ['mechanism', 'how it works', 'action']):
                schema['mechanismOfAction'] = section_content.strip()
            
            # Clinical trials
            if any(term in section_title for term in ['clinical', 'trial', 'study', 'evidence']):
                trials = self._extract_list_items(section_content)
                if trials:
                    schema['clinicalTrials'].extend(trials)
            
            # Patient resources
            if any(term in section_title for term in ['patient', 'resource', 'support', 'assistance']):
                resources = self._extract_list_items(section_content)
                if resources:
                    schema['patientResources'].extend(resources)
        
        # Remove duplicates from lists
        for field in ['approvedIndications', 'sideEffects', 'warnings', 'clinicalTrials', 'patientResources', 'dosageForm']:
            if schema[field]:
                schema[field] = list(set(schema[field]))
        
        return schema
    
    def _extract_list_items(self, text):
        """Extract list items from text content"""
        # Look for bullet points or numbered lists
        bullet_items = re.findall(r'•\s*([^•\n]+)', text)
        if bullet_items:
            return [item.strip() for item in bullet_items if len(item.strip()) > 5]
        
        # Look for numbered lists
        numbered_items = re.findall(r'\d+\.\s*([^\d\n]+)', text)
        if numbered_items:
            return [item.strip() for item in numbered_items if len(item.strip()) > 5]
            
        # If no structured list is found, try splitting by sentences or line breaks
        if len(text) > 50:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            if sentences and len(sentences) > 1:
                return [s.strip() for s in sentences if len(s.strip()) > 15]
        
        # Return the whole text as a single item if it's not too long
        if text and len(text.strip()) > 10:
            return [text.strip()]
            
        return []
    
    def _combine_pharma_schemas(self, schemas):
        """Combine multiple schema results into one comprehensive schema"""
        if not schemas:
            return None
            
        combined = schemas[0].copy()
        
        # For subsequent schemas, merge their information
        for schema in schemas[1:]:
            # Merge list fields
            for field in ['approvedIndications', 'sideEffects', 'warnings', 'clinicalTrials', 'patientResources', 'dosageForm']:
                if schema[field]:
                    combined[field].extend(schema[field])
                    # Remove duplicates
                    combined[field] = list(set(combined[field]))
            
            # For text fields, use the most detailed information
            for field in ['mechanismOfAction', 'administration']:
                if schema[field] and (not combined[field] or len(schema[field]) > len(combined[field])):
                    combined[field] = schema[field]
            
            # For URL fields, use if not already set
            if schema['packageInsertURL'] and not combined['packageInsertURL']:
                combined['packageInsertURL'] = schema['packageInsertURL']
        
        return combined

def check_robots_txt(url):
    """Check if robots.txt allows crawling"""
    try:
        # Parse the domain from the URL
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        robots_url = f"{base_url}/robots.txt"
        
        # Get robots.txt content
        response = requests.get(robots_url, timeout=5)
        if response.status_code == 200:
            # Very basic check - see if there's a "Disallow: /" line
            if "Disallow: /" in response.text:
                path = parsed_url.path or "/"
                # Check if the specific path is disallowed
                for line in response.text.splitlines():
                    if line.startswith("Disallow:"):
                        disallow_path = line.split("Disallow:")[1].strip()
                        if path.startswith(disallow_path) and disallow_path:
                            return False, "This URL appears to be disallowed by the site's robots.txt"
        
        return True, None
        
    except Exception as e:
        # If we can't check robots.txt, proceed anyway
        return True, None

def clean_html(soup):
    """Remove unwanted elements from HTML according to LLMStxt guidelines"""
    # Remove scripts, styles, and other non-content elements
    for element in soup(["script", "style", "iframe", "nav", "footer", "aside"]):
        element.decompose()
    
    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Remove elements that are likely navigation or ads
    for element in soup.find_all(class_=lambda x: x and any(word in str(x).lower() for word in 
                                                        ["nav", "menu", "ad", "banner", "cookie", 
                                                         "popup", "sidebar", "footer", "header", 
                                                         "social", "share"])):
        element.decompose()
    
    # Try to identify and keep the main content area
    main_content = soup.find(["main", "article", "section", "div"], 
                             id=lambda x: x and "content" in x.lower(),
                             class_=lambda x: x and "content" in x.lower())
    
    # If we identified a main content area, return just that
    if main_content:
        # But ensure it has substantial content
        if len(main_content.get_text(strip=True)) > 200:
            return main_content
    
    return soup

def extract_main_content(soup):
    """
    Extract the main content from the page following LLMStxt format guidelines
    """
    # Clean the HTML to focus on main content
    content_soup = clean_html(soup)
    
    # Extract title
    title = soup.title.string.strip() if soup.title else "Unknown Title"
    
    # Extract metadata
    metadata = {
        'title': title,
        'description': '',
        'date_published': None,
        'author': None
    }
    
    # Try to get meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc:
        metadata['description'] = meta_desc.get('content', '')
    
    # Try to find author info
    author_meta = soup.find('meta', attrs={'name': 'author'})
    if author_meta:
        metadata['author'] = author_meta.get('content', '')
    
    # Try to find date published
    date_meta = soup.find('meta', attrs={'name': ['publishdate', 'date', 'pubdate']})
    if date_meta:
        metadata['date_published'] = date_meta.get('content', '')
    else:
        # Try to find a time element
        time_elem = soup.find('time')
        if time_elem and time_elem.get('datetime'):
            metadata['date_published'] = time_elem.get('datetime')
    
    # Extract content sections
    content_sections = []
    
    # Get all headings in the cleaned content
    headings = content_soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    
    # If no headings, try to create a single section from all content
    if not headings:
        main_content = content_soup.get_text(strip=True)
        if main_content:
            content_sections.append({
                'title': 'Main Content',
                'level': 2,
                'content': main_content
            })
    else:
        # Process each heading as a section
        for i, heading in enumerate(headings):
            level = int(heading.name[1])
            title = heading.get_text(strip=True)
            
            # Get the content for this section
            content = ""
            current = heading.next_sibling
            while current and (i == len(headings) - 1 or current != headings[i+1]):
                if current.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    if current.name == 'p':
                        content += current.get_text(strip=True) + "\n\n"
                    elif current.name == 'ul' or current.name == 'ol':
                        for li in current.find_all('li', recursive=False):
                            content += "- " + li.get_text(strip=True) + "\n"
                        content += "\n"
                    elif current.string and current.string.strip():
                        content += current.string.strip() + "\n"
                current = current.next_sibling
                
                # Break if we hit another heading
                if hasattr(current, 'name') and current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    break
                
            # Only add non-empty sections
            if content.strip():
                content_sections.append({
                    'title': title,
                    'level': level,
                    'content': content.strip()
                })
            
    # Extract important links
    important_links = []
    
    # Find all links in the main content
    links = content_soup.find_all('a', href=True)
    for link in links:
        # Skip empty links or javascript links
        href = link.get('href')
        if not href or href.startswith('javascript:') or href.startswith('#'):
            continue
        
        # Get the link text
        link_text = link.get_text(strip=True)
        if not link_text:
            continue
            
        # Skip very short or common navigation links
        if len(link_text) < 3 or link_text.lower() in ['home', 'next', 'prev', 'previous', 'back', 'more']:
            continue
            
        # Make URL absolute
        absolute_url = urljoin(metadata.get('url', ''), href)
        
        # Add to important links
        important_links.append({
            'text': link_text,
            'url': absolute_url
        })
    
    return metadata, content_sections, important_links

def format_llmstxt(metadata, content_sections, important_links):
    """
    Format content according to LLMStxt guidelines
    """
    # Start with the title as H1
    output = f"# {metadata['title']}\n\n"
    
    # Add metadata
    if metadata.get('description'):
        output += f"> {metadata['description']}\n\n"
    
    if metadata.get('author'):
        output += f"Author: {metadata['author']}\n"
        
    if metadata.get('date_published'):
        output += f"Date: {metadata['date_published']}\n"
        
    if metadata.get('url'):
        output += f"Source: {metadata['url']}\n"
        
    output += "\n"
    
    # Add content sections
    for section in content_sections:
        # Use the appropriate heading level
        output += f"{'#' * section['level']} {section['title']}\n\n"
        output += f"{section['content']}\n\n"
    
    # Add important links section if there are any
    if important_links:
        output += "## Important Links\n\n"
        for link in important_links:
            output += f"- [{link['text']}]({link['url']})\n"
        output += "\n"
    
    return output

def crawl_website(url, format="markdown", respect_robots=True):
    """
    Crawl a website and extract content according to LLMStxt guidelines.
    """
    try:
        # Check robots.txt if requested
        if respect_robots:
            allowed, reason = check_robots_txt(url)
            if not allowed:
                return {
                    'success': False,
                    'error': reason
                }
        
        # Choose a random user agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.2 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0'
        ]
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Add a slight delay to be gentle on the server
        time.sleep(1)
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Get content type and check if it's HTML
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            return {
                'success': False,
                'error': f"Unsupported content type: {content_type}"
            }
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract the main content according to LLMStxt format
        metadata, content_sections, important_links = extract_main_content(soup)
        
        # Update metadata with URL and timestamp
        metadata['url'] = url
        metadata['date_crawled'] = datetime.now().isoformat()
        
        # Format according to LLMStxt guidelines
        llms_content = format_llmstxt(metadata, content_sections, important_links)
        
        return {
            'success': True,
            'content': llms_content,
            'metadata': metadata,
            'content_sections': content_sections,
            'important_links': important_links
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': f"Request error: {str(e)}. The website may be blocking automated access."
        }
    except Exception as e:
        logger.error(f"Error crawling website: {str(e)}")
        return {
            'success': False,
            'error': f"Error: {str(e)}"
        }

# Function to create a download link for JSON content
def get_json_download_link(data, filename):
    """Generates a link to download the given data as JSON."""
    json_str = json.dumps(data, indent=2)
    b64 = base64.b64encode(json_str.encode()).decode()
    return f'<a href="data:application/json;base64,{b64}" download="{filename}">Download {filename}</a>'

# Function to create a download link for CSV content
def get_csv_download_link(results, filename):
    """Generates a link to download the given results as CSV."""
    csv_data = io.StringIO()
    writer = csv.writer(csv_data)
    
    # Write header
    writer.writerow(['Brand Name', 'Generic Name', 'Drug Class', 'Indications', 'Side Effects', 'Dosage Forms', 'Administration', 'Warnings', 'Mechanism of Action', 'Clinical Trials', 'Package Insert URL'])
    
    # Write data
    for result in results:
        if not result['success']:
            continue
            
        schema = result.get('schema', {})
        if not schema:
            continue
            
        writer.writerow([
            schema.get('brandName', ''),
            schema.get('genericName', ''),
            schema.get('drugClass', ''),
            '; '.join(schema.get('approvedIndications', [])),
            '; '.join(schema.get('sideEffects', [])),
            '; '.join(schema.get('dosageForm', [])),
            schema.get('administration', ''),
            '; '.join(schema.get('warnings', [])),
            schema.get('mechanismOfAction', ''),
            '; '.join(schema.get('clinicalTrials', [])),
            schema.get('packageInsertURL', '')
        ])
    
    csv_string = csv_data.getvalue()
    b64 = base64.b64encode(csv_string.encode()).decode()
    return f'<a href="data:text/csv;base64,{b64}" download="{filename}">Download {filename}</a>'

# Function to get a suggested product URL based on product name
def get_suggested_url(product_name):
    """Get a suggested URL for a given product name"""
    product_name_lower = product_name.lower()
    
    # Common
