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
                                _crawl_recursive(absolute_url, current_depth + 1)
                    except Exception as e:
                        logger.error(f"Error finding links on {current_url}: {str(e)}")
                            
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

# Function to create a download link for text content
def get_text_download_link(text, filename):
    """Generates a link to download the given text."""
    b64 = base64.b64encode(text.encode()).decode()
    return f'<a href="data:text/plain;base64,{b64}" download="{filename}">Download {filename}</a>'

# Function to create a download link for CSV content
def get_csv_download_link(results, filename):
    """Generates a link to download the given results as CSV."""
    csv_data = io.StringIO()
    writer = csv.writer(csv_data)
    
    # Write header
    writer.writerow(['Page Title', 'URL', 'Description', 'Section Title', 'Section Content', 'Link Text', 'Link URL'])
    
    # Write data
    for result in results:
        if not result['success']:
            continue
            
        page_title = result['metadata']['title']
        page_url = result['metadata']['url']
        description = result['metadata'].get('description', '')
        
        # Write sections
        for section in result['content_sections']:
            section_title = section['title']
            section_content = section['content'][:500]  # Truncate long content for CSV
            writer.writerow([page_title, page_url, description, section_title, section_content, '', ''])
        
        # Write important links
        for link in result['important_links']:
            link_text = link['text']
            link_url = link['url']
            writer.writerow([page_title, page_url, description, 'Important Links', '', link_text, link_url])
    
    csv_string = csv_data.getvalue()
    b64 = base64.b64encode(csv_string.encode()).decode()
    return f'<a href="data:text/csv;base64,{b64}" download="{filename}">Download {filename}</a>'

# Function to create a download link for CSV with Markdown content
def get_markdown_csv_download_link(results, filename):
    """Generates a link to download the markdown content as CSV."""
    csv_data = io.StringIO()
    writer = csv.writer(csv_data)
    
    # Write header
    writer.writerow(['Page Title', 'URL', 'Complete Markdown Content'])
    
    # Write data
    for result in results:
        if not result['success']:
            continue
            
        page_title = result['metadata']['title']
        page_url = result['metadata']['url']
        markdown_content = result['content']
        
        writer.writerow([page_title, page_url, markdown_content])
    
    csv_string = csv_data.getvalue()
    b64 = base64.b64encode(csv_string.encode()).decode()
    return f'<a href="data:text/csv;base64,{b64}" download="{filename}">Download {filename}</a>'

# Main app
def main():
    st.set_page_config(page_title="LLMStxt Generator", page_icon="📄", layout="wide")
    
    st.title("LLMStxt Generator")
    st.markdown("Extract content from websites in the LLMStxt format optimized for language models")
    
    # Add format explanation
    with st.expander("About LLMStxt Format"):
        st.markdown("""
        ## LLMStxt Format
        
        This tool generates content following the [LLMStxt guidelines](https://llmstxt.org/), which is a format designed to make web content more digestible for language models.
        
        Key features of the LLMStxt format:
        
        1. **Clean, structured content** - Removes navigation, ads, and other non-essential elements
        2. **Hierarchical structure** - Preserves heading levels and document organization
        3. **Metadata preservation** - Maintains title, description, author, and date information
        4. **Important links** - Collects and presents relevant links from the page
        5. **Plain text focus** - Eliminates complex formatting while keeping essential structure
        
        The tool creates a format that makes it easy for language models to understand the content's context and structure.
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
            combine_results = st.checkbox("Combine all pages into single file", value=True)
            extract_images = st.checkbox("Include image descriptions", value=False)
            col1, col2 = st.columns(2)
            with col1:
                output_format = st.radio("Output format:", ["Markdown (.md)", "CSV (.csv)", "Markdown in CSV (.csv)"])
        
        submitted = st.form_submit_button("Generate LLMStxt")
        
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
                
                domain = urlparse(url).netloc
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                
                # Handle standard CSV output format
                if output_format == "CSV (.csv)":
                    filename = f"{domain}_{timestamp}.csv"
                    st.markdown("### CSV Export")
                    
                    # Provide download link for CSV
                    st.markdown(get_csv_download_link(results, filename), unsafe_allow_html=True)
                    
                    # Show preview of CSV data
                    with st.expander("CSV Preview"):
                        preview_data = []
                        header = ['Page Title', 'Section Title', 'Section Content (truncated)']
                        preview_data.append(header)
                        
                        for result in results[:3]:  # Only show first 3 pages in preview
                            if not result['success']:
                                continue
                                
                            page_title = result['metadata']['title']
                            
                            for section in result['content_sections'][:2]:  # Only show first 2 sections per page
                                section_title = section['title']
                                section_content = section['content'][:100] + "..." if len(section['content']) > 100 else section['content']
                                preview_data.append([page_title, section_title, section_content])
                        
                        st.table(preview_data)
                
                # Handle Markdown in CSV format
                elif output_format == "Markdown in CSV (.csv)":
                    filename = f"{domain}_markdown_{timestamp}.csv"
                    st.markdown("### Markdown in CSV Export")
                    
                    # Provide download link for Markdown CSV
                    st.markdown(get_markdown_csv_download_link(results, filename), unsafe_allow_html=True)
                    
                    # Show preview of CSV data
                    with st.expander("Markdown CSV Preview"):
                        preview_data = []
                        header = ['Page Title', 'URL', 'Markdown Content (truncated)']
                        preview_data.append(header)
                        
                        for result in results[:3]:  # Only show first 3 pages in preview
                            if not result['success']:
                                continue
                                
                            page_title = result['metadata']['title']
                            page_url = result['metadata']['url']
                            markdown_content = result['content'][:150] + "..." if len(result['content']) > 150 else result['content']
                            
                            preview_data.append([page_title, page_url, markdown_content])
                        
                        st.table(preview_data)
                        
                        st.info("The complete markdown content for each page is included in the CSV file. This format is useful for importing into LLM tools that work with structured data.")
                
                # Handle Markdown output format
                else:
                    # Combine results if requested
                    if combine_results and len(results) > 1:
                        combined_content = f"# Website: {urlparse(url).netloc}\n\n"
                        combined_content += f"Date Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        combined_content += f"Total Pages: {len(results)}\n\n"
                        combined_content += "---\n\n"
                        
                        for i, result in enumerate(results, 1):
                            if not result['success']:
                                continue
                                
                            combined_content += f"# Page {i}: {result['metadata']['title']}\n"
                            combined_content += f"> URL: {result['metadata']['url']}\n\n"
                            
                            if result['metadata'].get('description'):
                                combined_content += f"{result['metadata']['description']}\n\n"
                            
                            # Add page content (skip the title which we already added)
                            content_lines = result['content'].split('\n')
                            if content_lines and content_lines[0].startswith('# '):
                                content_to_add = '\n'.join(content_lines[1:])
                            else:
                                content_to_add = result['content']
                                
                            combined_content += content_to_add + "\n\n---\n\n"
                        
                        # Display combined content
                        st.markdown("### Combined Results")
                        st.text_area("Combined LLMStxt Content:", combined_content, height=400)
                        
                        # Provide download link using HTML
                        filename = f"{domain}_combined_{timestamp}.md"
                        
                        # Use a workaround for the download button
                        st.markdown(get_text_download_link(combined_content, filename), unsafe_allow_html=True)
                        
                        # Also offer CSV with markdown option
                        st.markdown("### Alternative Download Options")
                        st.markdown("You can also download the combined markdown content as a CSV file:")
                        
                        # Create a special results object for the combined content
                        combined_results = [{
                            'success': True,
                            'metadata': {
                                'title': f"Combined pages from {domain}",
                                'url': url
                            },
                            'content': combined_content
                        }]
                        
                        csv_filename = f"{domain}_combined_{timestamp}.csv"
                        st.markdown(get_markdown_csv_download_link(combined_results, csv_filename), unsafe_allow_html=True)
                    
                    # Display individual results
                    st.markdown("### Individual Pages")
                    for i, result in enumerate(results, 1):
                        if not result['success']:
                            continue
                            
                        with st.expander(f"Page {i}: {result['metadata']['title']}"):
                            st.markdown(f"URL: {result['metadata']['url']}")
                            st.text_area(f"LLMStxt Content", result['content'], height=300)
                            
                            # Provide download options
                            st.markdown("#### Download Options")
                            
                            # Markdown download
                            page_filename = re.sub(r'[^\w]', '_', result['metadata']['url'])
                            page_filename = re.sub(r'_+', '_', page_filename)
                            page_filename = f"{page_filename[:50]}_{timestamp}.md"
                            
                            st.markdown(
                                get_text_download_link(result['content'], page_filename),
                                unsafe_allow_html=True
                            )
                            
                            # CSV with markdown download
                            csv_filename = f"{page_filename[:-3]}.csv"
                            
                            # Create a single-page result for CSV
                            single_result = [{
                                'success': True,
                                'metadata': result['metadata'],
                                'content': result['content']
                            }]
                            
                            st.markdown(
                                get_markdown_csv_download_link(single_result, csv_filename),
                                unsafe_allow_html=True
                            )
            else:
                st.error("Failed to crawl any pages. Check the URL and try again.")
                if results and 'error' in results[0]:
                    st.error(f"Error: {results[0]['error']}")
                    st.warning("If you're getting a 403 Forbidden error, try enabling 'Try to bypass 403 errors' in Advanced Options.")
    
    # Add best practices section
    with st.expander("LLMStxt Best Practices"):
        st.markdown("""
        ### Best Practices for LLMStxt
        
        1. **Focus on content, not form** - The LLMStxt format prioritizes the actual content rather than visual styling
        2. **Maintain structural hierarchy** - Preserve headings and document structure to help LLMs understand the content organization
        3. **Include metadata** - Title, author, date, and source URL provide important context
        4. **Clean unwanted elements** - Remove navigation menus, ads, footers, and other non-essential page elements
        5. **Simplify to plain text** - Eliminate complex HTML in favor of simple text with minimal formatting
        6. **Preserve semantic meaning** - Keep lists as lists, paragraphs as paragraphs
        
        This tool follows these guidelines to create LLM-friendly content extractions.
        """)
        
    # Add usage tips section
    with st.expander("Usage Tips for Different Export Formats"):
        st.markdown("""
        ### When to Use Each Export Format
        
        This tool offers three different export formats to suit various needs:
        
        1. **Markdown (.md)**
           - Best for reading the content directly
           - Ideal for importing into note-taking apps
           - Good for sharing with humans
           
        2. **CSV (.csv)**
           - Best for structured data analysis
           - Separates content into discrete fields (title, URL, sections, etc.)
           - Useful for filtering and sorting content
           
        3. **Markdown in CSV (.csv)**
           - Best for LLM processing pipelines
           - Keeps the full markdown content intact but in a structured CSV format
           - Ideal for batch processing with LLMs
           - Useful for creating training datasets
        
        Choose the format that best suits your workflow and how you plan to use the extracted content.
        """)

if __name__ == "__main__":
    main()
