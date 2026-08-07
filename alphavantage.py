import requests
import os
from dotenv import load_dotenv
load_dotenv()

# TODO: THIS FILE IS UNUSED!!! CLEAN UP LATER.

POLYGON_API_KEY = os.getenv('POLYGON_KEY')

def quaterly_earnings(symbol):
    # replace the "demo" apikey below with your own key from https://www.alphavantage.co/support/#api-key
    url = 'https://www.alphavantage.co/query?function=EARNINGS&symbol=' + symbol + '&apikey=demo'
    r = requests.get(url)
    data = r.json()
    return data

def top_movers():
    pass