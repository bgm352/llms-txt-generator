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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebCrawler:
    def __init__(self):
        self.headers = {
            'User-Agent': 'LLMStxt-Crawler/1.0 (https://example.com/bot; bot@example.com)'
        }
    
    def crawl(self, url, depth=1, format="markdown"):
        return crawl_website(url, depth, format)

def crawl_website(url, depth=1, format="markdown"):
    """
    Crawl a website and extract content according to LLMStxt standards.
    
    Parameters:
    url (str): The URL to crawl
    depth (int): The crawling depth (currently only supports 1)
    format (str): Output format (markdown or plaintext)
    
    Returns:
    dict: Result of the crawling operation
    """
    try:
        headers = {
            'User-Agent': 'LLMStxt-Crawler/1.0 (https://example.com/bot; bot@example.com)'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
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
            'source_type': 'web'
        }
        
        # Try to find main content area
        main_content = None
        for tag in ['main', 'article', 'div[role="main"]', '.main-content', '#content', '#main']:
            if tag.startswith('.'):
                main_content = soup.select_one(tag)
            elif tag.startswith('#'):
                main_content = soup.find(id=tag[1:])
            elif '[' in tag:
                tag_name, attr = tag.split('[', 1)
                attr_name, attr_value = attr.rstrip(']').split('=')
                attr_value = attr_value.strip('"\'')
                main_content = soup.find(tag_name, {attr_name: attr_value})
            else:
                main_content = soup.find(tag)
                
            if main_content:
                break
        
        # If no main content found, use body
        if not main_content:
            main_content = soup.body or soup
        
        # Remove unwanted elements
        if main_content:
            for element in main_content.select('script, style, nav, footer, header, .sidebar, .ads, .comments, iframe, noscript, [role="complementary"]'):
                element.decompose()
        
        # Convert to desired format
        if format == "markdown":
            h2t = html2text.HTML2Text()
            h2t.ignore_links = False
            h2t.ignore_images = False
            h2t.ignore_tables = False
            content = h2t.handle(str(main_content))
        else:
            # Extract text content
            content = main_content.get_text(separator='\n\n')
            # Clean up whitespace
            content = re.sub(r'\n{3,}', '\n\n', content)
            content = re.sub(r'[ \t]+', ' ', content)
            content = content.strip()
        
        # Structure according to LLMStxt format
        llms_content = {
            "metadata": metadata,
            "content": content
        }
        
        return {
            'success': True,
            'content': content,
            'metadata': metadata,
            'llms_content': llms_content
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': f"Request error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Error crawling website: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


# Function to create a download link for text content
def get_download_link(text, filename):
    """Generates a link to download the given text."""
    b64 = base64.b64encode(text.encode()).decode()
    href = f'data:file/txt;base64,{b64}'
    return f'<a href="{href}" download="{filename}">Download {filename}</a>'


# Main app
def main():
    st.set_page_config(page_title="LLMStxt Generator", page_icon="📄", layout="wide")
    
    st.title("LLMStxt Generator")
    st.markdown("Extract content from websites in a format optimized for LLMs")
    
    # Creating crawler instance
    crawler = WebCrawler()
    
    # Form for URL input
    with st.form("url_form"):
        url = st.text_input("Enter website URL:")
        col1, col2 = st.columns(2)
        with col1:
            depth = st.number_input("Crawl depth:", min_value=1, max_value=3, value=1)
        with col2:
            format_option = st.selectbox("Output format:", ["markdown", "plaintext"])
        
        save_file = st.checkbox("Save to file", value=True)
        
        submitted = st.form_submit_button("Generate")
        
        if submitted:
            if not url:
                st.error("URL is required!")
                return
            
            with st.spinner("Crawling website..."):
                result = crawl_website(url, depth, format_option)
            
            if result['success']:
                # Format according to LLMStxt specifications
                llms_content = f"""# {result['metadata']['title']}

## Metadata
- URL: {result['metadata']['url']}
- Date Crawled: {result['metadata']['date_crawled']}
- Source Type: {result['metadata']['source_type']}

## Content
{result['content']}
"""
                
                # Display tabs for different views
                tab1, tab2, tab3 = st.tabs(["LLMStxt", "Raw Content", "JSON"])
                
                with tab1:
                    st.markdown(llms_content)
                
                with tab2:
                    st.text_area("Raw extracted content:", result['content'], height=400)
                
                with tab3:
                    json_format = {
                        "version": "1.0",
                        "metadata": result['metadata'],
                        "content": result['content']
                    }
                    st.json(json_format)
                
                # Save to file if requested
                if save_file:
                    # Create safe filename from URL
                    filename = re.sub(r'[^\w]', '_', url)
                    filename = re.sub(r'_+', '_', filename)
                    filename = f"{filename[:50]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.md"
                    
                    # Provide download button
                    st.download_button(
                        label="Download as Markdown",
                        data=llms_content,
                        file_name=filename,
                        mime="text/markdown",
                    )
                    
                    # Also provide JSON download
                    st.download_button(
                        label="Download as JSON",
                        data=json.dumps(json_format, indent=2),
                        file_name=f"{filename.replace('.md', '.json')}",
                        mime="application/json",
                    )
            else:
                st.error(f"Error: {result['error']}")

    # API Documentation
    with st.expander("API Documentation"):
        st.markdown("""
        ## API Usage
        
        You can also access this functionality via API:
        
        ### Endpoint
        
        ```
        POST /api/crawl
        ```
        
        ### Request Body
        
        ```json
        {
            "url": "https://example.com",
            "depth": 1,
            "format": "markdown"
        }
        ```
        
        ### Response
        
        ```json
        {
            "success": true,
            "version": "1.0",
            "metadata": {
                "title": "Example Domain",
                "url": "https://example.com",
                "date_crawled": "2025-03-19T12:34:56.789",
                "source_type": "web"
            },
            "content": "## Example Domain\\n\\nThis domain is for use in illustrative examples in documents..."
        }
        ```
        
        > Note: When using Streamlit, this API functionality is not directly accessible. This documentation is for reference if you deploy the Flask version separately.
        """)


if __name__ == "__main__":
    main()
