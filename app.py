from flask import Flask, render_template, request, jsonify # type: ignore
import requests
from bs4 import BeautifulSoup
import markdown
from datetime import datetime
import os

app = Flask(__name__)

def crawl_website(url, depth=1):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer']):
            element.decompose()
            
        # Extract text content
        content = soup.get_text(separator='\n\n')
        
        # Basic formatting
        content = content.replace('\n\n\n', '\n\n')
        content = content.strip()
        
        return {
            'success': True,
            'content': content,
            'url': url,
            'date': datetime.now().isoformat()
        }
    except Exception as e:
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
    
    if not url:
        return jsonify({'success': False, 'error': 'URL is required'})
    
    result = crawl_website(url, depth)
    
    if result['success']:
        llms_content = f"""# Website Content for LLMs
URL: {result['url']}
Date Crawled: {result['date']}

## Content:

{result['content']}
"""
        return jsonify({
            'success': True,
            'data': {
                'llmsText': llms_content,
                'metadata': {
                    'crawlDate': result['date'],
                    'sourceUrl': result['url']
                }
            }
        })
    else:
        return jsonify({
            'success': False,
            'error': result['error']
        })

if __name__ == '__main__':
    app.run(debug=True)