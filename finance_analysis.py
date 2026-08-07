import yfinance as yf
import os
import requests

ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEYS')
ALPHA_VANTAGE_KEY_TWO = os.getenv('ALPHA_VANTAGE_KEYS_TWO')
ALPHA_VANTAGE_KEY_THREE = os.getenv('ALPHA_VANTAGE_KEYS_THREE')
ALPHA_VANTAGE_KEY_FOUR = os.getenv('ALPHA_VANTAGE_KEYS_FOUR')
ALPHA_VANTAGE_KEY_FIVE = os.getenv('ALPHA_VANTAGE_KEYS_FIVE')
ALPHA_VANTAGE_KEY_SIX = os.getenv('ALPHA_VANTAGE_KEYS_SIX')
ALPHA_VANTAGE_KEY_SEVEN = os.getenv('ALPHA_VANTAGE_KEYS_SEVEN')
ALPHA_VANTAGE_KEY_EIGHT = os.getenv('ALPHA_VANTAGE_KEYS_EIGHT')
ALPHA_VANTAGE_KEY_NINE = os.getenv('ALPHA_VANTAGE_KEYS_NINE')

ALPHA_VANTAGE_KEYS = [ALPHA_VANTAGE_KEY, ALPHA_VANTAGE_KEY_TWO, ALPHA_VANTAGE_KEY_THREE, ALPHA_VANTAGE_KEY_FOUR, ALPHA_VANTAGE_KEY_FIVE, ALPHA_VANTAGE_KEY_SIX, ALPHA_VANTAGE_KEY_SEVEN, ALPHA_VANTAGE_KEY_EIGHT, ALPHA_VANTAGE_KEY_NINE]

def get_composite_score(ticker_name):
    # Get the financials of the stock
    url = f'https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={ticker_name}&apikey={ALPHA_VANTAGE_KEY}'
    latest_income_statement = requests.get(url).json()['quarterlyReports'][0]
    url = f'https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol={ticker_name}&apikey={ALPHA_VANTAGE_KEY_TWO}'
    latest_balance_sheet = requests.get(url).json()['quarterlyReports'][0]

    # income_statement_dict = latest_income_statement[list(latest_income_statement.keys())[0]]
    # balance_sheet_dict = latest_balance_sheet[list(latest_balance_sheet.keys())[0]]

    stock_potential = stock_potential_general(latest_income_statement, latest_balance_sheet)

    return stock_potential

# The numbers we need to retrieve from the API
# From Income statement orbalance sheet(get from polygon i think because yahoo finance is slow)
### current quarter's earnings
### previous quarter's earnings
### current quarter's revenue
### previous quarter's revenue
# Earning Yield = EPS / Price
# Dividend Yield = Dividend / Price
# Price Momentum = RSI from alpha vantage
# Volume Trend = OBV from alpha vantage
# Sentiment Score = from news/tweets API
# Price Action = MACD from alpha vantage
# Volatility we calculate from our prices. standard deviation multiplied by the square root of the number of periods of time, 
    
def calculate_growth_potential(current_earnings, previous_earnings, current_revenue, previous_revenue):
    """
    Transform the growth potential into a score from 0 to 1.
    Original Range is -100 to infinity.
    The new range is 0 to 1.
    """

    earnings_growth = (current_earnings - previous_earnings) / previous_earnings
    revenue_growth = (current_revenue - previous_revenue) / previous_revenue
    growth_potential = (earnings_growth + revenue_growth)/2
    return 1 - (-100 * (1 / growth_potential))

def calculate_value_potential(earnings_yield, dividend_yield):
    """
    Transform the value potential into a score from 0 to 1.
    Original Range is 0 to 100.
    The new range is 0 to 1.
    """
    value_potential = (earnings_yield + dividend_yield) / 2
    return value_potential / 100

def calculate_long_stock_score(growth_potential, value_potential, sentiment_score):
    stock_score = (growth_potential + value_potential + sentiment_score) / 3
    return stock_score

def calculate_earnings_surprise(actual_earnings, estimated_earnings):
    """
    Transform the earnings surprise into a score from 0 to 1.
    Original Range is -infinity to infinity.
    The practical range is -0.02 to 0.02.
    """
    earnings_surprise = (actual_earnings - estimated_earnings) / estimated_earnings
    return earnings_surprise

def calculate_short_stock_score(earnings_surprise, price_momentum, volume_trend):
    stock_score = (earnings_surprise + price_momentum + volume_trend) / 3
    return stock_score

def calculate_obv(previous_obv, current_volume, price_change):
    sign = 1 if price_change > 0 else -1
    obv = previous_obv + (current_volume * sign)
    return obv

def stock_potential_general(income, balance_sheet):
    """
    Calculates the stock potential of a stock based on the general formula.
    Bad: <0.01
    Ok: 0.01 - 0.05
    Great: >0.05
    """
    ebit = float(income['ebit'])
    net_fixed_assets = float(balance_sheet['totalNonCurrentAssets'])
    working_capital = float(balance_sheet['totalAssets'])
    print(ebit, net_fixed_assets, working_capital)
    return round(ebit / (net_fixed_assets + working_capital), 4)

def stock_potential_precise(income, balance_sheet):
    pass

def get_news(ticker_name):
    ticker = yf.Ticker(ticker_name)
    return ticker.news

if __name__ == '__main__':
    # print('Composite Indicator: ', get_composite_score('MSFT'))
    # print('PE and EPS Ratios: ', get_pe_and_eps('MSFT'))
    print(get_news('GOOG'))

    # # Day Stock Score
    # price_action = 8.0  # Example price action score
    # volume = 7.5  # Example volume score
    # volatility = 9.2  # Example volatility score

    # stock_score = calculate_day_stock_score(price_action, volume, volatility)
    # print("Day Trading Stock Score:", stock_score)

    # # On-Balance Volume (OBV)
    # previous_obv = 100000  # Example previous OBV
    # current_volume = 5000  # Example current volume
    # price_change = 1.5  # Example price change

    # obv = calculate_obv(previous_obv, current_volume, price_change)
    # print("On-Balance Volume (OBV):", obv)

    # # Short-Term Stock Score
    # earnings_surprise = 8.0  # Example earnings surprise score
    # price_momentum = 7.5  # Example price momentum score
    # volume_trend = 9.2  # Example volume trend score

    # stock_score = calculate_short_stock_score(earnings_surprise, price_momentum, volume_trend)
    # print("Short-Term Stock Score:", stock_score)

    # # Earnings Surprise
    # actual_earnings = 1500000  # Example actual earnings
    # estimated_earnings = 1200000  # Example estimated earnings

    # earnings_surprise = calculate_earnings_surprise(actual_earnings, estimated_earnings)
    # print("Earnings Surprise:", earnings_surprise)

    # # Long-term Stock Potential
    # growth_potential = 8.5  # Example growth potential score
    # value_potential = 7.2  # Example value potential score
    # sentiment_score = 9.0  # Example sentiment score
    # stock_score = calculate_long_stock_score(growth_potential, value_potential, sentiment_score)
    # print("Long-Term Stock Score:", stock_score)

    # # Value Potential
    # earnings_yield = 0.08  # Example earnings yield
    # dividend_yield = 0.04  # Example dividend yield

    # value_potential = calculate_value_potential(earnings_yield, dividend_yield)
    # print("Value Potential:", value_potential)

    # # Growth Potential
    # current_earnings= 5000000 # Example of earnings
    # previous_earnings= 69696969696969696969 #Example of previos earnings
    # current_revenue = 10000000  # Example current year's revenue
    # previous_revenue = 8000000  # Example previous year's revenue

    # growth_potential = calculate_growth_potential(current_earnings, previous_earnings, current_revenue, previous_revenue)
    # print("Growth Potential:", growth_potential)