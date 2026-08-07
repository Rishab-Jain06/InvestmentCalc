# import time
# from selenium import webdriver
import requests
from bs4 import BeautifulSoup
import datetime
import traceback
import os
from dotenv import load_dotenv
import finnhub

def parse_date(date_str):
    # return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %dth, %Y")
    pass

def scrape_insider_data(stock_symbol):
    try:
        # Access the URL using Chrome selenium driver.
        url = f'https://fintel.io/insiders?sticker={stock_symbol.lower()}&sinsider=&smin=&smax=&scode=P&scode=S&sfiledate=7&stradedate=7&Search=Search'
        print('URL', url)
        # options = Options()
        # options.add_argument("--headless")
        # options.add_argument("--disable-gpu")
        # options.add_argument("--enable-cookies") # Enable cookies
        # options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36") # Set user agent string
        # userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        # options = webdriver.ChromeOptions()
        # options.add_argument('--headless')
        # options.add_argument("--incognito")
        # options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
        # options.add_argument("--nogpu")
        # options.add_argument("--disable-gpu")
        # options.add_argument("--window-size=1280,1280")
        # options.add_argument("--no-sandbox")
        # options.add_argument("--enable-javascript")
        # options.add_argument("--enable-cookies")
        # options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # options.add_experimental_option('useAutomationExtension', False)
        # options.add_argument('--disable-blink-features=AutomationControlled')


        # driver = webdriver.Chrome(executable_path=os.environ.get("CHROMEDRIVER_PATH"), options=options) # type: ignore
        # driver = webdriver.Chrome(options=options)
        # driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        # driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": userAgent})
        # driver.get(url)
        # time.sleep(1.5)
        # html = driver.page_source

        # Make a genuine-looking request to the URL.
        headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
            'Accept': 'text/html,application/json,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        html = requests.get(url, headers=headers).content

        # print('HTML', html)
        soup = BeautifulSoup(html, 'html.parser')
        # response = requests.get(url)

        # response.raise_for_status()

        # soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table', {'class': 'table'})
        # print('Table', table)

        insider_data = []
        if table:
            for row in table.find_all('tr')[1:]: # type: ignore
                cells = row.find_all('td')
                file_date = parse_date(cells[0].text.strip())
                trade_date = parse_date(cells[1].text.strip())
                form = cells[2].text.strip()
                ticker = cells[3].text.strip()
                security_title = cells[4].text.strip().split(", ")[0]
                insider = cells[5].text.strip().split("\n", 1)
                insider_name = insider[0].strip()
                print('Insider Name', insider_name)
                insider_role = insider[1].strip().replace("\n", " ")
                print('Insider Role', insider_role)
                transaction_type = cells[6].text.strip().split("-", 1)[1].strip()
                print('Transaction Type', transaction_type)
                code = "Bought" if transaction_type == "Purchase" else "Sold"
                print('Code', code)
                shares = cells[8].text.strip('- ')
                print('Shares', shares)
                share_price = cells[9].text.strip('- ')
                print('Share Price', share_price)
                value = cells[10].text.strip('- ')
                print('Value', value)
                remaining_shares = cells[11].text.strip('- ')
                print('Remaining Shares', remaining_shares)
                current_value = float(share_price) * int(remaining_shares.replace(',', ''))
                print('Current Value', current_value)

                sentence = f"On {trade_date}, {insider_name} {code.lower()} {shares} {security_title.lower()} in {ticker} for ${value} for ${share_price}/share. {insider_name} is a {insider_role} of {ticker}, filed the trade on {file_date}, and now owns {remaining_shares} {security_title.lower()}, at a current value of about ${current_value:,.2f}"
                print('Sentence', sentence)

                raw_data = {
                    "trade_date": trade_date,
                    "file_date": file_date,
                    "name": insider_name,
                    "role": insider_role,
                    "action": code,
                    "quantity": shares,
                    "stock_type": security_title,
                    "price": share_price,
                    "total": value,
                    "remaining": remaining_shares,
                    "current_value": current_value
                }

                insider_data.append(raw_data)
        else:
            print('Issue with HTML. No table found.')
            insider_data = html
        return insider_data
    except Exception as e:
        print(e)
        raise Exception('Data could not be found')
load_dotenv()
FINNHUB_KEY = 'cifijkhr01qhvakk47b0cifijkhr01qhvakk47bg'
FINNHUB_KEY_TWO = 'cifijvhr01qhvakk47ggcifijvhr01qhvakk47h0'

finnhub_client = finnhub.Client(api_key=FINNHUB_KEY)
finnhub_client_two = finnhub.Client(api_key=FINNHUB_KEY_TWO)

start_date = '2023-01-01'
end_date = datetime.date.today().strftime('%Y-%m-%d')

def get_insider_data(stock_symbol):
    data = finnhub_client.stock_insider_transactions(stock_symbol, start_date, end_date)
    # raw_data = {
    #                 "trade_date": trade_date,
    #                 "file_date": file_date,
    #                 "name": insider_name,
    #                 "role": insider_role,
    #                 "action": code,
    #                 "quantity": shares,
    #                 "stock_type": security_title,
    #                 "price": share_price,
    #                 "total": value,
    #                 "remaining": remaining_shares,
    #                 "current_value": current_value
    #             }
    all_data = []
    dict_data = {}
    for i in data:
        dict_data['trade_date'] = i['transactionDate']
        dict_data['file_date'] = i['filingDate']
        dict_data['name'] = i['name']
        dict_data['action'] = 'Bought' if i['change'] >= 0 else 'Sold'
        dict_data['quantity'] = i['share']
        dict_data['total'] = i['share'] * i['transactionPrice']
        dict_data['price'] = i['transactionPrice']
        all_data.append(dict_data)
    return all_data
    

if __name__ == '__main__':
    print(get_insider_data('OESX'))