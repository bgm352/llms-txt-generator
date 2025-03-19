from flask import Flask, render_template, request, jsonify, send_file
import os
import logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import markdown
import re
import html2text
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Implement WebCrawler class since it was imported but not defined
class WebCrawler:
    def __init__(self):
        self.headers = {
            'User-Agent': 'LLMStxt-Crawler/1.0 (https://example.com/bot; bot@example.com)'
        }
    
    def crawl(self, url, depth=1, format="markdown"):
        return crawl_website(url, depth, format)

crawler = WebCrawler()

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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    url = request.form.get('url')
    depth = int(request.form.get('depth', 1))
    format = request.form.get('format', 'markdown')
    
    if not url:
        return jsonify({'success': False, 'error': 'URL is required'})
    
    result = crawl_website(url, depth, format)
    
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
        
        # Save to file if requested
        if request.form.get('save', False):
            save_dir = os.path.join(os.getcwd(), 'crawled_content')
            os.makedirs(save_dir, exist_ok=True)
            
            # Create safe filename from URL
            filename = re.sub(r'[^\w]', '_', url)
            filename = re.sub(r'_+', '_', filename)
            filename = f"{filename[:50]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.md"
            
            file_path = os.path.join(save_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(llms_content)
        
        # Provide JSON format for API consumers
        json_format = {
            "version": "1.0",
            "metadata": result['metadata'],
            "content": result['content']
        }
        
        return jsonify({
            'success': True,
            'data': {
                'llmsText': llms_content,
                'json': json_format,
                'metadata': result['metadata']
            }
        })
    else:
        return jsonify({
            'success': False,
            'error': result['error']
        })

@app.route('/api/crawl', methods=['POST'])
def api_crawl():
    """API endpoint that accepts JSON input"""
    data = request.json
    
    if not data or 'url' not in data:
        return jsonify({'success': False, 'error': 'URL is required in JSON body'})
    
    url = data['url']
    depth = data.get('depth', 1)
    format = data.get('format', 'markdown')
    
    result = crawl_website(url, depth, format)
    
    if result['success']:
        return jsonify({
            'success': True,
            'version': '1.0',
            'metadata': result['metadata'],
            'content': result['content']
        })
    else:
        return jsonify({
            'success': False,
            'error': result['error']
        })

@app.route('/download/<filename>')
def download(filename):
    try:
        # Make sure the output directory exists
        output_dir = os.path.join(os.getcwd(), 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        file_path = os.path.join(output_dir, filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {filename}")
            
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'File not found'
        }), 404

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        'success': False,
        'error': 'Not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs(os.path.join(os.getcwd(), 'output'), exist_ok=True)
    os.makedirs(os.path.join(os.getcwd(), 'crawled_content'), exist_ok=True)
    
    app.run(debug=False, host='127.0.0.1', port=5000)  # Set debug to False in production
