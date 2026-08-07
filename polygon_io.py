import numpy as np
import pandas as pd
import matplotlib
import json
import matplotlib.pyplot as plt
import requests
from dotenv import load_dotenv
load_dotenv()

import os
import datetime

POLYGON_API_KEY = os.getenv('POLYGON_KEY')
POLYGON_API_KEY_2 = os.getenv('POLYGON_KEY_TWO')
POLYGON_API_KEY_3 = os.getenv('POLYGON_KEY_THREE')
POLYGON_API_KEY_4 = os.getenv('POLYGON_KEY_FOUR')
POLYGON_API_KEY_5 = os.getenv('POLYGON_KEY_FIVE')
POLYGON_API_KEY_6 = os.getenv('POLYGON_KEY_SIX')
POLYGON_API_KEY_7 = os.getenv('POLYGON_KEY_SEVEN')
POLYGON_API_KEY_8 = os.getenv('POLYGON_KEY_EIGHT')
POLYGON_API_KEY_9 = os.getenv('POLYGON_KEY_NINE')
POLYGON_API_KEY_10 = os.getenv('POLYGON_KEY_TEN')
polygon_keys = [POLYGON_API_KEY, POLYGON_API_KEY_2, POLYGON_API_KEY_3, POLYGON_API_KEY_4, POLYGON_API_KEY_5, POLYGON_API_KEY_6, POLYGON_API_KEY_7, POLYGON_API_KEY_8, POLYGON_API_KEY_9, POLYGON_API_KEY_10]

polygon_index = 0
def getPolygonKey():
    global polygon_index
    polygon_key = polygon_keys[polygon_index]
    polygon_index += 1
    if polygon_index == len(polygon_keys):
        polygon_index = 0
    return polygon_key

matplotlib.use('Agg')

def getStockData(ticker):
    plt.style.use('dark_background')

    # start_date and end_date are strings in the format 'YYYY-MM-DD'. Dates must be within the last 10 years.
    end_date = datetime.datetime.now()
    start_date = (end_date - datetime.timedelta(days=365.25*2)).strftime('%Y-%m-%d')
    end_date = end_date.strftime('%Y-%m-%d')
    
    # Send GET request to https://api.polygon.io/v2/aggs/ticker/AAPL/range/30/minute/2021-01-09/2023-01-09?adjusted=true&sort=asc&limit=50000&apiKey=Eu58Vwvimp7zHkrIuypgLiLpwg5uGjN5
    url = f'https://api.polygon.io/v2/aggs/ticker/{ticker.upper()}/range/1/day/{start_date}/{end_date}?'
    polygon_key = getPolygonKey()
    params = f'adjusted=true&sort=asc&limit=50000&apiKey={polygon_key}'
    print(polygon_key)
    resp = requests.get(url+params)
    past = resp.json()
    print(past)
    past = past['results']

    stock_prices = pd.DataFrame({'date': np.array([datetime.datetime.fromtimestamp(i['t']/1000).strftime('%Y-%m-%d') for i in past]), # type: ignore
                             'open': [i['o'] for i in past],  # type: ignore
                             'close': [i['c'] for i in past],  # type: ignore
                             'high': [i['h'] for i in past], # type: ignore
                             'low': [i['l'] for i in past], # type: ignore
                             'volume': [i['v'] for i in past],  # type: ignore
                             'vwap': [i['vw'] for i in past]})  # type: ignore
    ohlc = stock_prices.loc[:, ['open', 'high', 'low', 'close', 'volume', 'vwap']]
    stock_prices['date'] = pd.to_datetime(stock_prices['date'])
    ohlc.set_index(stock_prices['date'], inplace=True)

    # Plot
    # mc = mplfinance.make_marketcolors(up='#1EB854',down='#ff0000', edge='inherit', wick={'up':'#1EB854','down':'#ff0000'}, volume='#1EB854')
    # customstyle = mplfinance.make_mpf_style(base_mpf_style='nightclouds',
    #                              facecolor='#171212', marketcolors=mc)
    # mplfinance.plot(ohlc, type='candle', style=customstyle,
    #         title=f'{ticker}, {start_date} - {end_date}',
    #         ylabel='Price ($)',
    #         ylabel_lower='Shares \nTraded',
    #         volume=True)
    # plt.savefig('static/candle-bars.png', facecolor='#171212')
    dates = stock_prices['date'].dt.strftime('%Y-%m-%d').tolist()
    return (start_date, end_date), dates, ohlc

if __name__ == '__main__':
    data = getStockData('AAPL')
    ohlc = data[2]
    ohlc.drop("vwap", axis=1)
    ohlc = ohlc.reset_index()
    ohlc_formatted = []
    for i in ohlc.index:
        ohlc_formatted.append([int(ohlc['date'][i].to_pydatetime().timestamp())*1000, ohlc['open'][i], ohlc['high'][i], ohlc['low'][i], ohlc['close'][i], ohlc['volume'][i]])
    ohlc_json = json.dumps(ohlc_formatted)