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
st.set_page_config(page_title="Genentech Product Data Crawler", layout="wide")
st.title("Genentech Product Data Crawler")

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Crawl Website", 
    "💊 Generate Drug Schema", 
    "🧪 Generate Clinical Trial Schema", 
    "🔗 Find Similar Sites"
])

# Tab 1: Crawl Website
with tab1:
    st.header("Website Crawler")
    st.write("Enter a URL to extract content from a webpage.")
    
    url_input = st.text_input("Enter URL:", placeholder="https://www.gene.com/...")
    
    # Suggest URLs for common Genentech products
    st.subheader("Suggested Product URLs")
    
    # Create columns for product category selection
    col1, col2 = st.columns(2)
    with col1:
        category = st.selectbox(
            "Select Product Category:",
            ["Oncology", "Neuroscience", "Ophthalmology", 
             "Immunology and Respiratory", "Hematology", "Infectious Disease"]
        )
    
    # Show products based on selected category
    with col2:
        # Filter products by category
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
    
    if st.button("Crawl Website", key="crawl_button"):
        if url_input:
            with st.spinner("Crawling website..."):
                # Call the crawl function
                result = crawl_website(url_input, format=output_format.lower(), respect_robots=respect_robots)
                
                if result['success']:
                    st.success("Website crawled successfully!")
                    
                    # Display tabs for different views of the content
                    content_tab1, content_tab2 = st.tabs(["Formatted Content", "Raw Data"])
                    
                    with content_tab1:
                        st.markdown(result['content'])
                    
                    with content_tab2:
                        st.json(result)
                    
                    # Provide download links
                    st.markdown(get_json_download_link(result, f"{urlparse(url_input).netloc}_content.json"), unsafe_allow_html=True)
                else:
                    st.error(f"Failed to crawl website: {result['error']}")
        else:
            st.warning("Please enter a URL")

# Tab 2: Generate Drug Schema
with tab2:
    st.header("Drug Schema Generator")
    st.write("Extract structured drug information from product websites.")
    
    # URL input for schema generation
    schema_url = st.text_input("Enter Product URL:", placeholder="https://www.gene.com/medical-professionals/medicines/...", key="schema_url")
    
    # Product selection for schema generation
    schema_col1, schema_col2 = st.columns(2)
    with schema_col1:
        schema_category = st.selectbox(
            "Select Product Category:",
            ["Oncology", "Neuroscience", "Ophthalmology", 
             "Immunology and Respiratory", "Hematology", "Infectious Disease"],
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
    
    if st.button("Generate Drug Schema", key="generate_schema"):
        if schema_url:
            with st.spinner("Generating schema... This may take a few minutes depending on the website size and crawl settings."):
                # Initialize the crawler and crawl the website
                crawler = WebCrawler()
                schema_result = crawler.crawl(schema_url, depth=crawl_depth, max_pages=max_pages, schema_type="pharma")
                
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
                    st.markdown(get_json_download_link(combined_schema, f"{schema_selected_product_info['brandName']}_schema.json"), unsafe_allow_html=True)
                    
                else:
                    st.error("Failed to generate schema. Please check the URL and try again.")
        else:
            st.warning("Please enter a product URL")

# Tab 3: Generate Clinical Trial Schema
with tab3:
    st.header("Clinical Trial Schema Generator")
    st.write("Extract structured clinical trial information for Genentech products.")
    
    # URL input for clinical trial schema
    ct_url = st.text_input("Enter Clinical Trial URL:", placeholder="https://clinicaltrials.gov/...", key="ct_url")
    
    # Product selection for clinical trials
    ct_col1, ct_col2 = st.columns(2)
    with ct_col1:
        ct_category = st.selectbox(
            "Select Product Category:",
            ["Oncology", "Neuroscience", "Ophthalmology", 
             "Immunology and Respiratory", "Hematology", "Infectious Disease"],
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
        "sponsor": "Genentech",
        "NCTId": None,
        "status": None
    }
    
    if st.button("Generate Clinical Trial Schema", key="generate_ct_schema"):
        if ct_url:
            with st.spinner("Generating clinical trial schema... This may take a few minutes."):
                # Here you would implement the clinical trial schema extraction
                # This is a placeholder that would need actual implementation
                st.info("This is a placeholder. Actual clinical trial schema extraction needs to be implemented.")
                
                # Example hardcoded result for demonstration
                example_ct_schema = CT_SCHEMA.copy()
                example_ct_schema["productName"] = ct_selected_product_info['brandName'] if ct_selected_product_info else "Unknown"
                example_ct_schema["genericName"] = ct_selected_product_info['genericName'] if ct_selected_product_info else "Unknown"
                example_ct_schema["studyType"] = "Interventional"
                example_ct_schema["phase"] = "Phase 3"
                example_ct_schema["conditions"] = ["Example Condition 1", "Example Condition 2"]
                example_ct_schema["NCTId"] = "NCT0000000"
                example_ct_schema["status"] = "Recruiting"
                
                # Display the schema
                st.subheader("Clinical Trial Schema")
                st.json(example_ct_schema)
                
                # Provide download link
                product_name = ct_selected_product_info['brandName'] if ct_selected_product_info else "product"
                st.markdown(get_json_download_link(example_ct_schema, f"{product_name}_clinical_trials.json"), unsafe_allow_html=True)
        else:
            st.warning("Please enter a clinical trial URL")

# Tab 4: Find Similar Sites
with tab4:
    st.header("Find Similar Sites")
    st.write("Discover related product websites and resources.")
    
    # Product selection for finding similar sites
    similar_col1, similar_col2 = st.columns(2)
    with similar_col1:
        similar_category = st.selectbox(
            "Select Product Category:",
            ["Oncology", "Neuroscience", "Ophthalmology", 
             "Immunology and Respiratory", "Hematology", "Infectious Disease"],
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
        st.write(f"**Selected Product:** {similar_selected_product_info['brandName']} ({similar_selected_product_info['genericName']})")
        
        # Options for finding similar sites
        search_options = st.multiselect(
            "Select search options:",
            [
                "Official product websites",
                "Genentech resources",
                "HCP resources",
                "Patient resources",
                "Clinical trial databases",
                "Prescribing information"
            ],
            default=["Official product websites", "Genentech resources"]
        )
        
        if st.button("Find Similar Sites", key="find_similar"):
            with st.spinner("Searching for similar sites..."):
                # Generate similar site results based on the selected product
                # This would need actual implementation
                st.subheader("Similar Sites")
                
                # Example results
                product_name = similar_selected_product_info['brandName']
                generic_name = similar_selected_product_info['genericName']
                
                results = {
                    "Official product websites": [
                        {"name": f"{product_name}.com", "url": f"https://www.{product_name.lower()}.com"},
                        {"name": f"{product_name} HCP", "url": f"https://www.{product_name.lower()}hcp.com"}
                    ],
                    "Genentech resources": [
                        {"name": f"{product_name} on Genentech.com", "url": f"https://www.gene.com/medical-professionals/medicines/{product_name.lower()}"},
                        {"name": "Genentech Patient Foundation", "url": "https://www.gene.com/patients/patient-foundation"}
                    ],
                    "HCP resources": [
                        {"name": f"{product_name} Prescribing Information", "url": f"https://www.gene.com/download/pdf/{product_name.lower()}_prescribing.pdf"},
                        {"name": "Dosing Calculator", "url": f"https://www.{product_name.lower()}hcp.com/dosing"}
                    ],
                    "Patient resources": [
                        {"name": f"{product_name} Patient Support", "url": f"https://www.{product_name.lower()}.com/patient-support"},
                        {"name": "Financial Assistance", "url": f"https://www.{product_name.lower()}.com/financial-support"}
                    ],
                    "Clinical trial databases": [
                        {"name": f"{product_name} on ClinicalTrials.gov", "url": f"https://clinicaltrials.gov/search?term={generic_name.replace(' ', '+')}"},
                        {"name": "Genentech Clinical Trials", "url": "https://www.gene.com/medical-professionals/clinical-trials"}
                    ],
                    "Prescribing information": [
                        {"name": f"{product_name} PI", "url": f"https://www.{product_name.lower()}.com/pi"},
                        {"name": "DailyMed", "url": f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={generic_name.replace(' ', '+')}"}
                    ]
                }
                
                # Display results based on selected options
                for option in search_options:
                    sites = results.get(option, [])
                    if sites:
                        st.write(f"**{option}:**")
                        for site in sites:
                            st.markdown(f"- [{site['name']}]({site['url']})")
                    else:
                        st.write(f"**{option}:** No sites found")
