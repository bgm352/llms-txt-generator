import streamlit as st
import os
import logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re
import html2text
import json
import base64
import time
import random
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        
    def crawl(self, url, depth=1, format="markdown", max_pages=10):
        """
        Crawl a website up to a specified depth and number of pages
        """
        results = []
        self.visited_urls = set()
        
        def _crawl_recursive(current_url, current_depth):
            if current_depth > depth or len(self.visited_urls) >= max_pages or current_url in self.visited_urls:
                return
            
            self.visited_urls.add(current_url)
            result = crawl_website(current_url, format=format)
            
            if result['success']:
                results.append(result)
                
                # Find more links to crawl if we haven't reached our depth or page limit
                if current_depth < depth and len(self.visited_urls) < max_pages:
                    soup = BeautifulSoup(requests.get(current_url).text, 'html.parser')
                    domain = urlparse(current_url).netloc
                    
                    # Find all links
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        absolute_url = urljoin(current_url, href)
                        
                        # Only follow links on the same domain
                        if urlparse(absolute_url).netloc == domain and absolute_url not in self.visited_urls:
                            _crawl_recursive(absolute_url, current_depth + 1)
                            
        _crawl_recursive(url, 1)
        return results

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

def extract_sections_and_links(soup):
    """
    Extract sections and links from the page in a structured way
    """
    sections = []
    current_section = {"title": "Main Content", "links": []}
    
    # Find all headings (h1-h6)
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    
    # Process each heading as a potential section
    for heading in headings:
        # Save previous section if it exists
        if current_section["links"] or len(sections) == 0:
            sections.append(current_section)
            
        # Start new section
        current_section = {
            "title": heading.get_text().strip(),
            "links": []
        }
        
        # Find all links following this heading until the next heading
        next_element = heading.find_next()
        while next_element and next_element.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            if next_element.name == 'a' and next_element.get('href'):
                link_text = next_element.get_text().strip()
                link_url = next_element.get('href')
                
                # Get optional details from title attribute or surrounding text
                link_details = next_element.get('title', '')
                
                # If no title attribute, try to get details from parent paragraph
                if not link_details and next_element.parent.name == 'p':
                    paragraph_text = next_element.parent.get_text().strip()
                    link_text_pos = paragraph_text.find(link_text)
                    if link_text_pos >= 0:
                        context_text = paragraph_text[link_text_pos + len(link_text):].strip()
                        if context_text:
                            link_details = context_text[:100] + ('...' if len(context_text) > 100 else '')
                
                current_section["links"].append({
                    "title": link_text,
                    "url": link_url,
                    "details": link_details
                })
            
            next_element = next_element.find_next()
    
    # Add the last section if it has links
    if current_section["links"]:
        sections.append(current_section)
    
    return sections

def format_llmstxt(metadata, sections):
    """
    Format content according to requested LLMStxt format
    """
    content = f"# {metadata['title']}\n"
    
    # Add optional description if available
    if metadata.get('description'):
        content += f"> {metadata['description']}\n\n"
    
    # Add each section with its links
    for section in sections:
        content += f"## {section['title']}\n"
        
        for link in section['links']:
            content += f"- [{link['title']}]({link['url']})"
            if link.get('details'):
                content += f": {link['details']}"
            content += "\n"
        
        content += "\n"
    
    return content

def crawl_website(url, format="markdown", respect_robots=True):
    """
    Crawl a website and extract content according to the custom LLMStxt format.
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
        
        # Extract metadata
        metadata = {
            'title': soup.title.string if soup.title else 'Unknown Title',
            'url': url,
            'date_crawled': datetime.now().isoformat(),
            'source_type': 'web',
            'description': ''
        }
        
        # Try to get meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            metadata['description'] = meta_desc.get('content', '')
        
        # Extract sections and links in the requested format
        sections = extract_sections_and_links(soup)
        
        # Format according to the requested LLMStxt structure
        llms_content = format_llmstxt(metadata, sections)
        
        return {
            'success': True,
            'content': llms_content,
            'metadata': metadata,
            'sections': sections,
            'raw_html': response.text  # Store for debugging or further processing
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

# Function to create a download link for text content
def get_download_link(text, filename):
    """Generates a link to download the given text."""
    b64 = base64.b64encode(text.encode()).decode()
    href = f'data:file/txt;base64,{b64}'
    return f'<a href="{href}" download="{filename}">Download {filename}</a>'

# Main app
def main():
    st.set_page_config(page_title="Custom LLMStxt Generator", page_icon="📄", layout="wide")
    
    st.title("Custom LLMStxt Generator")
    st.markdown("Extract structured content from websites in a format optimized for LLMs")
    
    # Add format explanation
    with st.expander("Format Explanation"):
        st.markdown("""
        ## Custom LLMStxt Format
        
        This tool generates content in the following format:
        
        ```
        # Title
        > Optional description goes here
        Optional details go here
        
        ## Section name
        - [Link title](https://link_url): Optional link details
        
        ## Optional Section
        - [Link title](https://link_url): Optional link details
        ```
        
        This format:
        1. Clearly identifies the page title
        2. Provides context through the optional description
        3. Organizes content into logical sections
        4. Preserves important links with their context
        """)
    
    # Creating crawler instance
    crawler = WebCrawler()
    
    # Form for URL input
    with st.form("url_form"):
        url = st.text_input("Enter website URL:")
        col1, col2, col3 = st.columns(3)
        with col1:
            depth = st.number_input("Crawl depth:", min_value=1, max_value=3, value=1)
        with col2:
            max_pages = st.number_input("Maximum pages to crawl:", min_value=1, max_value=50, value=10)
        with col3:
            respect_robots = st.checkbox("Respect robots.txt", value=True)
        
        advanced_options = st.expander("Advanced Options")
        with advanced_options:
            bypass_403 = st.checkbox("Try to bypass 403 errors", value=False)
            save_file = st.checkbox("Save to file", value=True)
            combine_results = st.checkbox("Combine all pages into single file", value=True)
        
        submitted = st.form_submit_button("Generate")
        
        if submitted:
            if not url:
                st.error("URL is required!")
                return
                
            # Add http:// if missing
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                st.info(f"Added https:// to URL: {url}")
            
            with st.spinner(f"Crawling website (up to {max_pages} pages)..."):
                if depth > 1:
                    # Multi-page crawl
                    results = crawler.crawl(url, depth=depth, max_pages=max_pages)
                else:
                    # Single page crawl
                    result = crawl_website(url)
                    results = [result] if result['success'] else []
            
            if results:
                # Display results
                st.success(f"Successfully crawled {len(results)} pages")
                
                # Combine results if requested
                if combine_results:
                    combined_content = f"# Website: {urlparse(url).netloc}\n\n"
                    for i, result in enumerate(results, 1):
                        combined_content += f"# Page {i}: {result['metadata']['title']}\n"
                        # Add URL as subtitle
                        combined_content += f"> URL: {result['metadata']['url']}\n\n"
                        # Add the content without the title (which we just added)
                        page_content = result['content']
                        # Remove the first line (title) as we've already added it
                        page_content_lines = page_content.split('\n')
                        if page_content_lines and page_content_lines[0].startswith('# '):
                            page_content = '\n'.join(page_content_lines[1:])
                        combined_content += page_content + "\n\n---\n\n"
                    
                    # Display combined content
                    st.markdown("### Combined Results")
                    st.text_area("Combined LLMStxt Content:", combined_content, height=400)
                    
                    # Download combined content
                    if save_file:
                        domain = urlparse(url).netloc
                        filename = f"{domain}_combined_{datetime.now().strftime('%Y%m%d%H%M%S')}.md"
                        
                        st.download_button(
                            label="Download Combined Results",
                            data=combined_content,
                            file_name=filename,
                            mime="text/markdown"
                        )
                
                # Display individual results
                st.markdown("### Individual Pages")
                for i, result in enumerate(results, 1):
                    with st.expander(f"Page {i}: {result['metadata']['title']}"):
                        st.markdown(f"URL: {result['metadata']['url']}")
                        st.text_area(f"Content for {result['metadata']['title']}", result['content'], height=300)
                        
                        # Download individual result
                        if save_file:
                            page_filename = re.sub(r'[^\w]', '_', result['metadata']['url'])
                            page_filename = re.sub(r'_+', '_', page_filename)
                            page_filename = f"{page_filename[:50]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.md"
                            
                            st.download_button(
                                label=f"Download {result['metadata']['title']}",
                                data=result['content'],
                                file_name=page_filename,
                                mime="text/markdown",
                                key=f"download_{i}"
                            )
            else:
                st.error("Failed to crawl any pages. Check the URL and try again.")
                if results and 'error' in results[0]:
                    st.error(f"Error: {results[0]['error']}")
                    st.warning("If you're getting a 403 Forbidden error, try enabling 'Try to bypass 403 errors' in Advanced Options.")
    
    # Add best practices section
    with st.expander("Best Practices"):
        st.markdown("""
        ### Best Practices for Web Crawling
        
        1. **Respect website terms of service** - Some websites explicitly forbid crawling
        2. **Use reasonable crawl rates** - Be gentle on servers by limiting requests
        3. **Check robots.txt** - Honor the website's crawling preferences
        4. **Focus on relevant content** - Avoid crawling login pages, privacy policies, etc.
        5. **Be careful with depth** - Higher depth values can lead to crawling many irrelevant pages
        
        This tool implements these best practices by default, but you can adjust settings in Advanced Options.
        """)

if __name__ == "__main__":
    main()
