"""sitemap employer của cv chuẩn XML nên có thể dùng thư viện xml.etree.ElementTree
"""
import multiprocessing.pool
import os
import sys 
module_path = os.path.abspath(os.getcwd())
if module_path not in sys.path:
    sys.path.append(module_path)
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from utils.mongodb_connection import MongoDB
from utils import config as cfg
from datetime import date
import re
import time
import multiprocessing

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept-Encoding": "*",
    "Connection": "keep-alive"
}
mongodb = None

# Get current date in YYYY-MM-DD format
today = date.today().strftime("%Y-%m-%d")  
conn = cfg.mongodb['CRAWLING']

def connect_mongodb():   
    """
    Return a connection to mongodb
    Args: None
    Returns: mongodb
    """      
    mongodb = MongoDB(  dbname = conn['dbname'], 
                        collection_name = conn['cv_employer_sitemap'],
                        host = conn['host'], 
                        port = conn['port'], 
                        username = conn['username'], 
                        password = conn['password']
                    )
    mongodb.connect()
    
    return mongodb

def crawl_employer_sitemap(url):
    """
    Reads an XML URL containing URLs and saves them to a JSON file.
    Args:
        url (str): The URL of the XML file containing URLs.
    Raises:
        Exception: If the request fails or the XML parsing fails.           
    Return:
        List
    """    
    list_url = []
    pattern = r'\.([A-Z0-9]+)\.html'
    try:
        response = requests.get(url = url, 
                                headers = headers)
        
        if response.status_code == 410:
            print(f"Warning: XML resource might be unavailable (410 Gone).")
            return  # Exit the function if it's a 410 error
        elif response.status_code != 200:
            raise Exception(f"Failed to fetch XML: {response.status_code}")
        elif response.status_code == 200:
            """ Solution 1 - Using BeautifulSoup
            """
            # # Crawl sitemap
            # soup = BeautifulSoup(response.content, "xml")
            # list_item = soup.find_all('url')
        
            # for item in list_item:
            #     employer_url = item.find('loc').get_text() if item.find('loc') else None
            #     employer_id = re.search(pattern, employer_url).group(1) if employer_url else None
            #     changefreq = item.find('changefreq').get_text() if item.find('changefreq') else None
            #     lastmod = item.find('lastmod').get_text() if item.find('lastmod') else None
                
            #     list_url.append(
            #         {
            #             "employer_id": employer_id,
            #             "employer_url": employer_url,
            #             "changefreq": changefreq,
            #             "lastmod": lastmod,
            #             "created_date": today
            #         }
            #     ) 
            """
            Solution 2: Using ElementTree + BeautifulSoup
            """
            root = ET.fromstring(response.content)
            namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}  # Namespace for the sitemap
            for url in root.findall('ns:url', namespaces):
                employer_url = url.find('ns:loc', namespaces).text.strip()
                employer_id = re.search(pattern, employer_url).group(1) if employer_url else None
                changefreq = url.find('ns:changefreq', namespaces)
                lastmod = url.find('ns:lastmod', namespaces)
                
                list_url.append({
                    "employer_id": employer_id,
                    'employer_url': employer_url,
                    'changefreq': changefreq.text.strip() if changefreq is not None else None,
                    'lastmod': lastmod.text.strip() if lastmod is not None else None,
                    "created_date": today
                })
            
        return list_url    
    except requests.exceptions.RequestException as e:
        print( f"Error occurred: {str(e)}")         
    
def employer_sitemap_process():
    """
    Process the pipeline to crawl and store data of sitemap url into mongodb
    Args: 
        mongodb: connection to mongodb
    Returns: 
    """ 
    mongodb = connect_mongodb()
    # Crawling sitemap
    sitemap_url = "https://careerviet.vn/sitemap/employer.xml"
    list_url = crawl_employer_sitemap(sitemap_url)
    
     # Delete current data
    delete_filter = {"created_date": today}
    mongodb.delete_many(delete_filter)
    
    # Load current data
    mongodb.insert_many(list_url)
    
    # Close the connection    
    mongodb.close()
 
def crawl_employer_worker(url):
    """
    Crawl a employer
    Args: 
        url (string): employer url
    Returns: 
    """ 
    time.sleep(1) 
    employer_id = employer_name = location = company_size = industry = website = about_us = None
    pattern = r'\.([A-Z0-9]+)\.html'
    match = re.search(pattern, url)
    if match:
        employer_id = match.group(1)
        
    try:
        response = requests.get(    url = url, 
                                    headers=headers)
        parser = 'html.parser'
        if response.status_code == 410:
            print(f"Warning: XML resource might be unavailable (410 Gone).")
            return  # Exit the function if it's a 410 error
        elif response.status_code != 200:
            raise Exception(f"Failed to fetch XML: {response.status_code}")
        elif response.status_code == 200:
            # Crawl job
            soup = BeautifulSoup(response.content, parser) 
            company_info = soup.find('div', class_='company-info')
            employer = {}  
            
            if company_info:
                employer_name = company_info.find('h1', class_='name').text.strip() if company_info.find('h1', class_='name') else None
                location = soup.find('div', class_='content').find('p').text.strip() if soup.find('p').text.strip() else None
                li_tags = soup.find_all('li')
                for li in li_tags:
                    if li.find('span', class_='mdi-account-supervisor'):
                        company_size = li.find('span', class_='mdi-account-supervisor').text.strip()
                    if li.find('span', class_='mdi-gavel'):
                        industry = li.find('span', class_='mdi-gavel').text.strip()
                    if li.find('span', class_='mdi-link'):
                        website = li.find('span', class_='mdi-link').text.strip()
                if  soup.find('div', class_='intro-section'):
                    about_us = soup.find('div', class_='intro-section').find('div', class_='box-text').text.strip()
                           
            employer ={
                "employer_id": employer_id,
                "employer_name": employer_name,
                "location" : location,
                "company_size" : company_size,
                "industry" : industry,
                "website" : website,
                "about_us" : about_us,                
                "employer_url": url,
                "created_date": today,
                "worker": check_url_worker(url)
            }
            
            mongodb = connect_mongodb()    
            mongodb.set_collection(conn['cv_employer_detail'])
            mongodb.insert_one(employer)
            # Close the connection    
            mongodb.close()            
            # time.sleep(1) 
    except requests.exceptions.RequestException as e:
        print( f"Error occurred: {str(e)}")
           
def employer_url_generator():    
    """
    Crawl all jobs in sitemap data and store into mongodb
    Args: 
        mongodb
    Returns: employer url
    """  
    mongodb = connect_mongodb()
    mongodb.set_collection(conn['cv_employer_sitemap'])
    # Filter
    filter = {"created_date": today}
    # Projecttion: select only the "job_url" field
    projection = {"_id": False, "employer_url": True}
    cursor = mongodb.select(filter, projection)
    
    # Extract job_url
    for document in cursor: 
        print(document["employer_url"])
        yield document["employer_url"]
    
    # Close the connection    
    mongodb.close()

  
def current_employer_process():
    """
    Process the pipeline to crawl and store data of employer url into mongodb
    Args: 
        mongodb: connection to mongodb
    Returns: 
    """ 
    mongodb = connect_mongodb()
    mongodb.set_collection(conn['cv_employer_detail'])    
     # Delete current data
    delete_filter = {"created_date": today}
    mongodb.delete_many(delete_filter)
    # Close the connection    
    mongodb.close()
    
    print('Start to crawl')
    with multiprocessing.Pool(2) as pool:
        # parallel the scapring process
        pool.map(crawl_employer_worker, employer_url_generator())
 
def check_url_worker(url):
    url_name = url[len('https://careerviet.vn/vi/nha-tuyen-dung/') -1 : len('https://careerviet.vn/vi/nha-tuyen-dung/')]
    print(url_name)
    if url_name in 'c':
        return 1
    return 2
       
if __name__ == "__main__":  
    # Process site map process
    employer_sitemap_process()
    
    # Current employer process
    current_employer_process()
    

    


