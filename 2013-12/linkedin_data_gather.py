#!/usr/bin/env python
# -*- coding: utf-8 -*-

###
#
# Input: linkedin_url
#
# Requirements: BeautifulSoup4, unicodecsv
#
# Given a linkedin company profile URL, scrape the company information and export it to a CSV
#
# Usage: python linkedin_data_gather.py [linkedin_url]
#
###

import sys
import urllib2
from bs4 import BeautifulSoup
import unicodecsv
import random
import time

if __name__ == '__main__':
      
  # Get the linkedin url provided at the command line
  url_to_get = sys.argv[1]
  
  print "Current URL: " + url_to_get
  
  # Get the HTML contents of the page and put it into BeautifulSoup
  opener = urllib2.build_opener()

  # Create a user agent
  opener.addheaders = [('User-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36')]
  
  # Open the page and read the contents into a variable we can use
  li_company_page = opener.open(url_to_get).read()

  # Create the soup so we can parse it with BS4
  soup = BeautifulSoup(li_company_page.decode('utf-8', 'ignore'))
  
  # Get the company description & specialties from the soup
  basic_li_data = soup.find(attrs = { "class" : "text-logo"})
  
  if basic_li_data:
    # Get the description
    description = basic_li_data.contents[1].text if basic_li_data.contents else "N/A"
  
    # Get the specialities
    specialties = basic_li_data.contents[5].text.strip().replace("\n", "") if basic_li_data.contents and len(basic_li_data.contents) >= 5 else "N/A"
  
  # Potential data to get: website, type, founded, industry, company size
  # Not all companies have complete profiles.
  # If the information doesn't exist, we use "N/A" rather than a blank or null. These can later be handled during analysis or in later wrangling.
  
  # Look through the soup for the dt and dd elements. This is where the information is
  raw_li_data = soup.find_all(["dt", "dd"])

  # If we have something, clean it up by removing white space
  if raw_li_data:
    clean_li_data = []
    for x in range(len(raw_li_data)):
      clean_li_data.append(raw_li_data[x].text.strip())
  
    # Create a python dict so we can get the company's information by title (company size) as opposed to using a number
    all_li_data = dict(clean_li_data[i:i+2] for i in range(0, len(clean_li_data), 2))
  
    # The .get() method on a dict let's you write this a little more nicely.
    # Thanks to Aaron for cleaning this up!
    company_size = all_li_data.get('Company Size', 'N/A')
    website_url = all_li_data.get('Website', 'N/A')
    industry = all_li_data.get('Industry', 'N/A')
    company_type = all_li_data.get('Type', 'N/A')
    year_founded = all_li_data.get('Founded', 'N/A')
  
  # Let's export the data to CSV
  try:
    # TODO: Change this path in your code!!!
    csv_file_to_create = "/Users/robertdempsey/Documents/linkedin_data.csv"
  
    with open(csv_file_to_create, 'wb') as csvfile:
      li_writer = unicodecsv.writer(csvfile, encoding='utf-8')
      li_writer.writerow([description, specialties, company_size, website_url, industry, company_type, year_founded])
      print "The file has been successfully created! Read it and weep!"
  except:
    print "Sorry, I couldn't create the file because: ", sys.exc_info()[0]
    raise
  
  # Uncomment this code if you're going to be pulling multiple pages from the same website. It will help keep you from being banned.
  # For each page you pull, it will pause between 15 and 23 seconds
  # Also, this code will need to go above the CSV code. I leave that, and other updates to the code, to you my fellow wrangler.
  # sleep_time = 15 * random.random() + 8
  # print "Sleeping for: " + str(sleep_time) + " seconds"
  # time.sleep(sleep_time)  