# This code takes in a search query and returns the first result from Investopedia. It then extracts the text from the article and returns it as a string.

import requests
from bs4 import BeautifulSoup as bs
from selenium import webdriver
from selenium.webdriver.common.by import By


def investopedia_search(searchquery):
    searchList = str(searchquery).split()
    searchquery = ''
    for i in searchList:
        searchquery = searchquery + i + '+'

    url = f'https://investopedia.com/search?q={searchquery}'
    soup = bs(requests.get(url).content, 'html.parser')

    anchor = soup.find(id='search-results__link_1-0')
    return anchor['href'] # type: ignore

def investopedia_web_scrape(link):
    article = ''

    soup = bs(requests.get(link).content, 'html.parser')
    for o in soup.find(id='mntl-sc-page_1-0').find_all('p', recursive=False): # type: ignore
        if len(o.text) > 20:
            article += o.text + ' '
    
    return article

if __name__ == '__main__':
    print(investopedia_web_scrape(investopedia_search('Aroon')).strip().replace("\n", ""))