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

# Set up page config and title
st.set_page_config(page_title="Pharmaceutical Website Data Extractor", layout="wide")
st.title("Pharmaceutical Website Data Extractor")

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Crawl Website", 
    "💊 Generate Drug Schema", 
    "🧪 Generate Clinical Trial Schema", 
    "🔗 Find Similar Sites"
])

# Helper function for URL validation
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

# Tab 1: Crawl Website
with tab1:
    st.header("Website Crawler")
    st.write("Enter a URL to extract content from any pharmaceutical webpage.")
    
    url_input = st.text_input("Enter URL:", placeholder="https://www.example.com/product-page")
    
    # Suggest URLs for common Genentech products
    with st.expander("Suggested Genentech Product URLs"):
        # Create columns for product category selection
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox(
                "Select Product Category:",
                list(GENENTECH_PRODUCTS.keys())
            )
        
        # Show products based on selected category
        with col2:
            filtered_products = [product for product in GENENTECH_PRODUCTS.get(category, [])]
            product_names = [product["brandName"] for product in filtered_products]
            
            selected_product = st.selectbox("Select Product:", product_names)
            
            # Get product details
            selected_product_info = next(
                (product for product in filtered_products if product["brandName"] == selected_product), 
                None
            )
        
        # Display product info and URL suggestion
        if selected_product_info:
            st.write(f"**Brand Name:** {selected_product_info['brandName']}")
            st.write(f"**Generic Name:** {selected_product_info['genericName']}")
            
            # Generate suggested URLs
            suggested_urls = [
                f"https://www.gene.com/medical-professionals/medicines/{selected_product_info['brandName'].lower()}",
                f"https://www.{selected_product_info['brandName'].lower()}.com",
                f"https://www.gene.com/patients/medicines/{selected_product_info['brandName'].lower()}"
            ]
            
            for suggested_url in suggested_urls:
                if st.button(f"Use URL: {suggested_url}", key=f"url_{suggested_url}"):
                    url_input = suggested_url
                    st.session_state.url = suggested_url
    
    # Crawl options
    respect_robots = st.checkbox("Respect robots.txt", value=True)
    output_format = st.radio("Output Format:", ["Markdown", "HTML", "Text"])
    
    if st.button("Crawl Website", key="crawl_button") or ('url' in st.session_state and st.session_state.url):
        if url_input or ('url' in st.session_state and st.session_state.url):
            url_to_crawl = url_input or st.session_state.url
            
            # Store URL in session state for other tabs to use
            st.session_state.last_crawled_url = url_to_crawl
            st.session_state.last_crawled_data = None
            
            with st.spinner("Crawling website..."):
                # Call the crawl function
                result = crawl_website(url_to_crawl, format=output_format.lower(), respect_robots=respect_robots)
                
                # Store result in session state for other tabs to use
                if result['success']:
                    st.session_state.last_crawled_data = result
                
                if result['success']:
                    st.success("Website crawled successfully!")
                    
                    # Display tabs for different views of the content
                    content_tab1, content_tab2 = st.tabs(["Formatted Content", "Raw Data"])
                    
                    with content_tab1:
                        st.markdown(result['content'])
                    
                    with content_tab2:
                        st.json(result)
                    
                    # Provide download links
                    hostname = urlparse(url_to_crawl).netloc
                    st.markdown(get_json_download_link(result, f"{hostname}_content.json"), unsafe_allow_html=True)
                else:
                    st.error(f"Failed to crawl website: {result['error']}")
        else:
            st.warning("Please enter a URL")

# Tab 2: Generate Drug Schema
with tab2:
    st.header("Drug Schema Generator")
    st.write("Extract structured drug information from any pharmaceutical website.")
    
    # URL input for schema generation
    schema_url = st.text_input("Enter Product URL:", placeholder="https://www.example.com/drug-page", key="schema_url")
    
    # Option to use the last crawled URL from Tab 1
    if 'last_crawled_url' in st.session_state:
        if st.button(f"Use Last Crawled URL: {st.session_state.last_crawled_url}", key="use_last_url_schema"):
            schema_url = st.session_state.last_crawled_url
    
    # Suggested products section
    with st.expander("Suggested Genentech Product URLs"):
        # Product selection for schema generation
        schema_col1, schema_col2 = st.columns(2)
        with schema_col1:
            schema_category = st.selectbox(
                "Select Product Category:",
                list(GENENTECH_PRODUCTS.keys()),
                key="schema_category"
            )
        
        with schema_col2:
            # Filter products
            schema_filtered_products = [product for product in GENENTECH_PRODUCTS.get(schema_category, [])]
            schema_product_names = [product["brandName"] for product in schema_filtered_products]
            
            schema_selected_product = st.selectbox("Select Product:", schema_product_names, key="schema_product")
            
            # Get product details
            schema_selected_product_info = next(
                (product for product in schema_filtered_products if product["brandName"] == schema_selected_product), 
                None
            )
        
        # Display product info and URL suggestions for schema generation
        if schema_selected_product_info:
            # Generate suggested URLs
            schema_suggested_urls = [
                f"https://www.gene.com/medical-professionals/medicines/{schema_selected_product_info['brandName'].lower()}",
                f"https://www.{schema_selected_product_info['brandName'].lower()}.com",
                f"https://www.gene.com/patients/medicines/{schema_selected_product_info['brandName'].lower()}"
            ]
            
            for suggested_url in schema_suggested_urls:
                if st.button(f"Use URL: {suggested_url}", key=f"schema_url_{suggested_url}"):
                    schema_url = suggested_url
                    st.session_state.schema_url = suggested_url
    
    # Crawl depth and page limit
    schema_col3, schema_col4 = st.columns(2)
    with schema_col3:
        crawl_depth = st.slider("Crawl Depth:", min_value=1, max_value=5, value=2)
    with schema_col4:
        max_pages = st.slider("Max Pages:", min_value=1, max_value=20, value=10)
    
    if st.button("Generate Drug Schema", key="generate_schema") or ('schema_url' in st.session_state and st.session_state.schema_url):
        url_to_use = schema_url or (st.session_state.schema_url if 'schema_url' in st.session_state else None)
        
        if url_to_use:
            with st.spinner("Generating schema... This may take a few minutes depending on the website size and crawl settings."):
                # Initialize the crawler and crawl the website
                crawler = WebCrawler()
                schema_result = crawler.crawl(url_to_use, depth=crawl_depth, max_pages=max_pages, schema_type="pharma")
                
                # Store for other tabs
                st.session_state.last_schema_result = schema_result
                
                if schema_result:
                    st.success("Schema generated successfully!")
                    
                    # Display the combined schema
                    st.subheader("Combined Drug Schema")
                    combined_schema = schema_result['combined_schema']
                    
                    # Create a more user-friendly display
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Basic Information:**")
                        st.write(f"Brand Name: {combined_schema.get('brandName', 'Not found')}")
                        st.write(f"Generic Name: {combined_schema.get('genericName', 'Not found')}")
                        st.write(f"Manufacturer: {combined_schema.get('manufacturer', 'Not found')}")
                        st.write(f"Drug Class: {combined_schema.get('drugClass', 'Not found')}")
                        
                        st.write("**Dosage & Administration:**")
                        st.write(f"Dosage Forms: {', '.join(combined_schema.get('dosageForm', ['Not found']))}")
                        st.write("Administration:")
                        st.write(combined_schema.get('administration', 'Not found'))
                    
                    with col2:
                        st.write("**Mechanism & Approval:**")
                        st.write("Mechanism of Action:")
                        st.write(combined_schema.get('mechanismOfAction', 'Not found'))
                        st.write(f"Approval Date: {combined_schema.get('approvalDate', 'Not found')}")
                        
                        st.write("**Resources:**")
                        st.write(f"Package Insert URL: {combined_schema.get('packageInsertURL', 'Not found')}")
                    
                    # Expandable sections for longer lists
                    with st.expander("Approved Indications", expanded=False):
                        indications = combined_schema.get('approvedIndications', [])
                        if indications:
                            for idx, indication in enumerate(indications, 1):
                                st.write(f"{idx}. {indication}")
                        else:
                            st.write("No indications found")
                    
                    with st.expander("Side Effects", expanded=False):
                        side_effects = combined_schema.get('sideEffects', [])
                        if side_effects:
                            for idx, effect in enumerate(side_effects, 1):
                                st.write(f"{idx}. {effect}")
                        else:
                            st.write("No side effects found")
                    
                    with st.expander("Warnings", expanded=False):
                        warnings = combined_schema.get('warnings', [])
                        if warnings:
                            for idx, warning in enumerate(warnings, 1):
                                st.write(f"{idx}. {warning}")
                        else:
                            st.write("No warnings found")
                    
                    with st.expander("Clinical Trials", expanded=False):
                        trials = combined_schema.get('clinicalTrials', [])
                        if trials:
                            for idx, trial in enumerate(trials, 1):
                                st.write(f"{idx}. {trial}")
                        else:
                            st.write("No clinical trials found")
                    
                    with st.expander("Patient Resources", expanded=False):
                        resources = combined_schema.get('patientResources', [])
                        if resources:
                            for idx, resource in enumerate(resources, 1):
                                st.write(f"{idx}. {resource}")
                        else:
                            st.write("No patient resources found")
                    
                    # Raw data view
                    with st.expander("Raw Schema Data", expanded=False):
                        st.json(combined_schema)
                    
                    # Provide download links
                    product_name = combined_schema.get('brandName', 'product')
                    st.markdown(get_json_download_link(combined_schema, f"{product_name}_schema.json"), unsafe_allow_html=True)
                    
                else:
                    st.error("Failed to generate schema. Please check the URL and try again.")
        else:
            st.warning("Please enter a product URL")

# Tab 3: Generate Clinical Trial Schema
with tab3:
    st.header("Clinical Trial Schema Generator")
    st.write("Extract structured clinical trial information from any pharmaceutical clinical trial page.")
    
    # URL input for clinical trial schema
    ct_url = st.text_input("Enter Clinical Trial URL:", placeholder="https://clinicaltrials.gov/study/...", key="ct_url")
    
    # Option to use the last crawled URL
    if 'last_crawled_url' in st.session_state:
        if st.button(f"Use Last Crawled URL: {st.session_state.last_crawled_url}", key="use_last_url_ct"):
            ct_url = st.session_state.last_crawled_url
    
    # Suggested clinical trial URLs
    with st.expander("Find Clinical Trial URLs"):
        # Product selection for clinical trials
        ct_col1, ct_col2 = st.columns(2)
        with ct_col1:
            ct_category = st.selectbox(
                "Select Product Category:",
                list(GENENTECH_PRODUCTS.keys()),
                key="ct_category"
            )
        
        with ct_col2:
            # Filter products
            ct_filtered_products = [product for product in GENENTECH_PRODUCTS.get(ct_category, [])]
            ct_product_names = [product["brandName"] for product in ct_filtered_products]
            
            ct_selected_product = st.selectbox("Select Product:", ct_product_names, key="ct_product")
            
            # Get product details
            ct_selected_product_info = next(
                (product for product in ct_filtered_products if product["brandName"] == ct_selected_product), 
                None
            )
        
        # Display clinical trial search options
        if ct_selected_product_info:
            st.write(f"**Selected Product:** {ct_selected_product_info['brandName']} ({ct_selected_product_info['genericName']})")
            
            # Generate suggested URLs for clinical trials
            ct_suggested_urls = [
                f"https://clinicaltrials.gov/search?cond=&term={ct_selected_product_info['genericName'].replace(' ', '+')}&type=&rslt=&recrs=&age_v=&gndr=&intr=&titles=&outc=&spons=Genentech&lead=&id=&cntry=&state=&city=&dist=&locn=&phase=&rsub=&strd_s=&strd_e=&prcd_s=&prcd_e=&sfpd_s=&sfpd_e=&rfpd_s=&rfpd_e=&lupd_s=&lupd_e=&sort=",
                f"https://www.gene.com/medical-professionals/clinical-trials?Medicine={ct_selected_product_info['brandName'].lower()}"
            ]
            
            for suggested_url in ct_suggested_urls:
                if st.button(f"Use URL: {suggested_url}", key=f"ct_url_{suggested_url}"):
                    ct_url = suggested_url
                    st.session_state.ct_url = suggested_url
    
    # Clinical trial schema options
    ct_col3, ct_col4 = st.columns(2)
    with ct_col3:
        ct_crawl_depth = st.slider("Crawl Depth:", min_value=1, max_value=3, value=2, key="ct_depth")
    with ct_col4:
        ct_max_pages = st.slider("Max Pages:", min_value=1, max_value=10, value=5, key="ct_max_pages")
    
    # Define a clinical trial schema structure
    CT_SCHEMA = {
        "productName": None,
        "genericName": None,
        "studyType": None,
        "phase": None,
        "conditions": [],
        "interventions": [],
        "primaryOutcomes": [],
        "secondaryOutcomes": [],
        "eligibilityCriteria": {
            "inclusion": [],
            "exclusion": []
        },
        "enrollmentCount": None,
        "studyStart": None,
        "studyCompletion": None,
        "locations": [],
        "sponsor": None,
        "NCTId": None,
        "status": None
    }
    
    # Function to extract clinical trial data
    def extract_clinical_trial_data(url, depth=2, max_pages=5):
        try:
            # First do a basic crawl of the URL
            result = crawl_website(url)
            
            if not result['success']:
                return None
                
            # Initialize a CT schema
            ct_schema = CT_SCHEMA.copy()
            
            # Extract basic information from the crawled content
            content = result.get('content', '')
            
            # Extract NCT ID (clinical trials ID format)
            nct_match = re.search(r'NCT\d{8}', content)
            if nct_match:
                ct_schema['NCTId'] = nct_match.group(0)
            
            # Extract phase information
            phase_match = re.search(r'Phase (?:I{1,3}|[1-4]|I{1,3}/I{1,3}|[1-4]/[1-4])', content)
            if phase_match:
                ct_schema['phase'] = phase_match.group(0)
            
            # Extract status
            for status in ['Recruiting', 'Active, not recruiting', 'Completed', 'Withdrawn', 'Terminated', 'Not yet recruiting']:
                if status in content:
                    ct_schema['status'] = status
                    break
            
            # Extract enrollment count
            enrollment_match = re.search(r'(?:Enrollment|Participants):\s*(\d+)', content)
            if enrollment_match:
                ct_schema['enrollmentCount'] = enrollment_match.group(1)
            
            # Extract study dates
            start_match = re.search(r'(?:Start Date|Study Start):\s*([A-Za-z]+ \d{1,2}, \d{4}|\d{1,2} [A-Za-z]+ \d{4}|\d{4}-\d{2}-\d{2})', content)
            if start_match:
                ct_schema['studyStart'] = start_match.group(1)
                
            completion_match = re.search(r'(?:Completion Date|Study Completion):\s*([A-Za-z]+ \d{1,2}, \d{4}|\d{1,2} [A-Za-z]+ \d{4}|\d{4}-\d{2}-\d{2})', content)
            if completion_match:
                ct_schema['studyCompletion'] = completion_match.group(1)
            
            # Extract sponsor
            sponsor_match = re.search(r'(?:Sponsor|Responsible Party):\s*([^,;\n\r]+)', content)
            if sponsor_match:
                ct_schema['sponsor'] = sponsor_match.group(1).strip()
                
            # Extract conditions
            conditions_section = re.search(r'(?:Condition|Disease)s?:([^:]+?)(?:Intervention|Sponsor|Outcome)', content)
            if conditions_section:
                condition_text = conditions_section.group(1)
                conditions = [c.strip() for c in re.split(r',|\n', condition_text) if c.strip()]
                ct_schema['conditions'] = conditions
            
            # For ClinicalTrials.gov URLs, try to extract if a Genentech product is being studied
            if 'clinicaltrials.gov' in url.lower():
                # Check all Genentech products
                for category, products in GENENTECH_PRODUCTS.items():
                    for product in products:
                        if product['brandName'].lower() in content.lower() or product['genericName'].lower() in content.lower():
                            ct_schema['productName'] = product['brandName']
                            ct_schema['genericName'] = product['genericName']
                            break
            
            # Extract primary outcomes
            outcomes_section = re.search(r'Primary (?:Outcome|Endpoint|Measure)[^:]*:([^:]+?)(?:Secondary|Sponsor|Eligibility)', content)
            if outcomes_section:
                outcome_text = outcomes_section.group(1)
                outcomes = [o.strip() for o in re.split(r'\n\s*-|\n\d+\.|\n\s*•', outcome_text) if o.strip()]
                ct_schema['primaryOutcomes'] = outcomes
            
            return ct_schema
            
        except Exception as e:
            st.error(f"Error extracting clinical trial data: {str(e)}")
            return None
    
    if st.button("Generate Clinical Trial Schema", key="generate_ct_schema") or ('ct_url' in st.session_state and st.session_state.ct_url):
        url_to_use = ct_url or (st.session_state.ct_url if 'ct_url' in st.session_state else None)
        
        if url_to_use:
            with st.spinner("Extracting clinical trial data..."):
                # Extract clinical trial information
                ct_schema = extract_clinical_trial_data(url_to_use, depth=ct_crawl_depth, max_pages=ct_max_pages)
                
                if ct_schema:
                    st.success("Clinical trial information extracted!")
                    
                    # Display the schema in a readable format
                    st.subheader("Clinical Trial Information")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Basic Information:**")
                        st.write(f"NCT ID: {ct_schema.get('NCTId', 'Not found')}")
                        st.write(f"Product: {ct_schema.get('productName', 'Not specified')}")
                        st.write(f"Generic Name: {ct_schema.get('genericName', 'Not specified')}")
                        st.write(f"Phase: {ct_schema.get('phase', 'Not specified')}")
                        st.write(f"Status: {ct_schema.get('status', 'Not specified')}")
                    
                    with col2:
                        st.write("**Timeline Information:**")
                        st.write(f"Enrollment: {ct_schema.get('enrollmentCount', 'Not specified')} participants")
                        st.write(f"Study Start: {ct_schema.get('studyStart', 'Not specified')}")
                        st.write(f"Study Completion: {ct_schema.get('studyCompletion', 'Not specified')}")
                        st.write(f"Sponsor: {ct_schema.get('sponsor', 'Not specified')}")
                    
                    # Expandable sections
                    with st.expander("Conditions", expanded=False):
                        conditions = ct_schema.get('conditions', [])
                        if conditions:
                            for idx, condition in enumerate(conditions, 1):
                                st.write(f"{idx}. {condition}")
                        else:
                            st.write("No conditions specified")
                    
                    with st.expander("Primary Outcomes", expanded=False):
                        outcomes = ct_schema.get('primaryOutcomes', [])
                        if outcomes:
                            for idx, outcome in enumerate(outcomes, 1):
                                st.write(f"{idx}. {outcome}")
                        else:
                            st.write("No primary outcomes specified")
                    
                    # Raw data view
                    with st.expander("Raw Clinical Trial Data", expanded=False):
                        st.json(ct_schema)
                    
                    # Provide download link
                    filename = f"clinical_trial_{ct_schema.get('NCTId', 'data')}.json"
                    st.markdown(get_json_download_link(ct_schema, filename), unsafe_allow_html=True)
                else:
                    st.error("Failed to extract clinical trial data. Please check the URL and try again.")
        else:
            st.warning("Please enter a clinical trial URL")

# Tab 4: Find Similar Sites
with tab4:
    st.header("Find Similar Sites")
    st.write("Discover related websites and resources based on a URL.")
    
    # URL input
    similar_url = st.text_input("Enter URL to find similar sites:", placeholder="https://www.example.com/product-page", key="similar_url")
    
    # Option to use the last crawled URL
    if 'last_crawled_url' in st.session_state:
        if st.button(f"Use Last Crawled URL: {st.session_state.last_crawled_url}", key="use_last_url_similar"):
            similar_url = st.session_state.last_crawled_url
    
    # Option to use last schema product
    if 'last_schema_result' in st.session_state:
        combined_schema = st.session_state.last_schema_result.get('combined_schema', {})
        product_name = combined_schema.get('brandName')
        if product_name:
            if st.button(f"Find sites similar to {product_name}", key="use_last_schema_product"):
                st.session_state.similar_product_name = product_name
                st.session_state.similar_product_generic = combined_schema.get('genericName', '')
    
    # Or manually select a product
    with st.expander("Select a Specific Product"):
        # Product selection
        similar_col1, similar_col2 = st.columns(2)
        with similar_col1:
            similar_category = st.selectbox(
                "Select Product Category:",
                list(GENENTECH_PRODUCTS.keys()),
                key="similar_category"
            )
        
        with similar_col2:
            # Filter products
            similar_filtered_products = [product for product in GENENTECH_PRODUCTS.get(similar_category, [])]
            similar_product_names = [product["brandName"] for product in similar_filtered_products]
            
            similar_selected_product = st.selectbox("Select Product:", similar_product_names, key="similar_product")
            
            # Get product details
            similar_selected_product_info = next(
                (product for product in similar_filtered_products if product["brandName"] == similar_selected_product), 
                None
            )
        
        # Display product info
        if similar_selected_product_info:
            if st.button(f"Find sites similar to {similar_selected_product_info['brandName']}", key="use_selected_product"):
                st.session_state.similar_product_name = similar_selected_product_info['brandName']
                st.session_state.similar_product_generic = similar_selected_product_info['genericName']
    
    # Search options
    search_types = st.multiselect(
        "Types of sites to find:",
        [
            "Official product websites",
            "Manufacturer resources",
            "Healthcare professional resources",
            "Patient resources",
            "Clinical trial databases",
            "Prescribing information",
            "Mechanism of action",
            "Competitive products",
            "Scientific publications"
        ],
        default=["Official product websites", "Healthcare professional resources", "Patient resources"]
    )
    
    # Function to find similar sites based on URL or product info
    def find_similar_sites(url=None, product_name=None, generic_name=None, search_types=None):
        similar_sites = {}
        
        # Case 1: We have a URL but no product info
        if url and not product_name:
            # Try to extract product name from URL or content
            try:
                # Basic crawl to get content
                result = crawl_website(url)
                
                if result['success']:
                    content = result.get('content', '').lower()
                    domain = urlparse(url).netloc
                    
                    # Try to identify product from content or URL
                    for category, products in GENENTECH_PRODUCTS.items():
                        for product in products:
                            brand_lower = product['brandName'].lower()
                            generic_lower = product['genericName'].lower()
                            
                            if brand_lower in domain or brand_lower in content or generic_lower in content:
                                product_name = product['brandName']
                                generic_name = product['genericName']
                                break
                        if product_name:
                            break
            except:
                pass
        
        # Generate recommendations based on product name if available
        if product_name:
            product_lower = product_name.lower()
            generic_lower = generic_name.lower() if generic_name else ""
            
            # Official product websites
            if "Official product websites" in search_types:
                similar_sites["Official product websites"] = [
                    {"name": f"{product_name}.com", "url": f"https://www.{product_lower}.com"},
                    {"name": f"{product_name} HCP", "url": f"https://www.{product_lower}hcp.com"}
                ]
            
            # Manufacturer resources
            if "Manufacturer resources" in search_types:
                similar_sites["Manufacturer resources"] = [
                    {"name": f"{product_name} on Genentech.com", "url": f"https://www.gene.com/medical-professionals/medicines/{product_lower}"},
                    {"name": "Genentech Patient Foundation", "url": "https://www.gene.com/patients/patient-foundation"}
                ]
            
            # Healthcare professional resources
            if "Healthcare professional resources" in search_types:
                similar_sites["Healthcare professional resources"] = [
                    {"name": f"{product_name} Prescribing Information", "url": f"https://www.gene.com/download/pdf/{product_lower}_prescribing.pdf"},
                    {"name": "Dosing Calculator", "url": f"https://www.{product_lower}hcp.com/dosing"},
                    {"name": f"{product_name} on Medscape", "url": f"https://reference.medscape.com/drug/{product_lower}-{generic_lower}-999999"}
                ]
            
            # Patient resources
            if "Patient resources" in search_types:
                similar_sites["Patient resources"] = [
                    {"name": f"{product_name} Patient Support", "url": f"https://www.{product_lower}.com/patient-support"},
                    {"name": "Financial Assistance", "url": f"https://www.{product_lower}.com/financial-support"},
                    {"name": f"{product_name} on RxList", "url": f"https://www.rxlist.com/search/rxl.htm?q={product_lower}"}
                ]
            
            # Clinical trial databases 
            if "Clinical trial databases" in search_types:
                similar_sites["Clinical trial databases"] = [
