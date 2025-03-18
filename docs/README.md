# LLMs.txt Generator Documentation

## Overview
The LLMs.txt Generator is a web application that creates LLM-friendly text files from websites. It follows the llms.txt specification and provides clean, structured content suitable for LLM consumption.

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/llms-txt-generator.git
cd llms-txt-generator
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
Create a `.env` file with the following options:
```
PROXY_URL=your_proxy_url  # Optional
RATE_LIMIT=2  # Requests per second
RESPECT_ROBOTS_TXT=True
USE_RANDOM_AGENTS=True
```

## Usage

1. Start the application:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://127.0.0.1:5000
```

3. Enter a website URL and select the crawl depth.

4. Click "Generate LLMs.txt" to create the file.

5. Preview the content and download the generated file.

## Features

### Content Cleaning
- Removes unwanted HTML elements (scripts, styles, ads)
- Preserves important content structure
- Maintains readability
- Handles code blocks and lists

### Crawling Options
- Configurable crawl depth
- Rate limiting
- Robots.txt compliance
- Proxy support
- Random user agents

### Output Format
The generated llms.txt files include:
- Source URL and crawl date
- User agent and proxy information
- Robots.txt compliance status
- HTTP status code
- Cleaned content

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the MIT License - see the LICENSE file for details. 