'''
Simple linkedin wangler (created after DC meetup) 
(Travis Hoppe, code released CC(3.0))

EXAMPLE USAGE:
> python linkedin_simple.py logik google arpc

OUTPUT (truncated):
[
  "logik", 
  {
    "Company Size": "11-50 employees", 
    "Website": "http://logikcull.com", 
    "Industry": "Internet", 
    "Type": "Privately Held", 
    "Founded": "2004"
  }
]
{
    "Company Size": "10,001+ employees", 
    ...
'''

from bs4 import BeautifulSoup
import sys, urllib2, random, time, json

# Get a list of company names from the command line
CO_NAMES = sys.argv[1:]

# Loop over the list of companies
for company in CO_NAMES:

  # Get the html data
  url = "http://www.linkedin.com/company/{}".format(company)
  raw = urllib2.urlopen(url).read()
  
  # Create the soup so we can parse it with BS4
  soup = BeautifulSoup(raw)

   # Work with a smaller subset
  node = soup.find(attrs = {"class" : "grid-f"})

  # If we are able to find the company info go ahead
  if node!=None:

    # Find the part we are interested in
    info   = node.find(attrs = {"class" : "basic-info"})
    titles = [item.get_text(strip=True) for item in info.findAll("dt")]
    data   = [item.get_text(strip=True) for item in info.findAll("dd")]
    
    output = [company,dict(zip(titles,data))]
  
  # If not leave a dummy output
  else:
    output = [company,{}]

  # Output the info in a nice JSON format
  print json.dumps(output, indent=2)

  # Sleep randomly 5-10 seconds to be nice
  sleep_time = random.uniform(5,10)
  time.sleep(sleep_time)
