import yfinance as yf
import pandas as pd
import datetime
import uuid

class PaperTrader:
    prices = pd.DataFrame()
    option_chains = {}
    FEE_RATE = 0.02

    def __init__(self, name, portfolio, initial, capital, id, has_options, has_fee):
        self.name = name
        self.portfolio = portfolio
        self.initial = initial
        self.capital = capital
        self.id = id
        self.has_options = has_options
        self.has_fee = has_fee
        # Check for any expired options.
        removed = False
        for trade in self.portfolio:
            if trade['type'] == 'call' or trade['type'] == 'put':
                if datetime.datetime.strptime(trade['expiry'], '%Y-%m-%d') < datetime.datetime.now():
                    self.portfolio.remove(trade)
                    removed = True
        if removed:
            # Update the portfolio in the database.
            from data.firebase_controller import updatePortfolio
            updatePortfolio(self.name, self)

        # Get the prices for all the tickers in the portfolio.
        self.get_prices()

    def get_url_from_name(self):
        return 'gid=' + self.name.replace(' ', '+')
    
    def get_sell_url(self, uid, ticker, quantity):
        return f'paper-trading/sell?{self.get_url_from_name()}&uid={uid}&t={ticker.upper()}&q={quantity}'
    
    def get_cover_url(self, uid, ticker, quantity):
        return f'paper-trading/cover?{self.get_url_from_name()}&uid={uid}&t={ticker.upper()}&q={quantity}'
    
    def get_option_exercise_url(self, uid):
        return f'paper-trading/exercise?{self.get_url_from_name()}&uid={uid}'

    def regular_bought(self):
        return any([trade['type'] == 'buy' or trade['type'] == 'short' for trade in self.portfolio])
    
    def option_bought(self):
        return any([trade['type'] == 'call' or trade['type'] == 'put' for trade in self.portfolio])

    @staticmethod
    def get_prices_for_tickers(ticker):
        # Look at the last 4 days of data for the ticker using datetime.
        startDate = str((datetime.datetime.now()-datetime.timedelta(days=4)).strftime('%Y-%m-%d'))
        endDate = str(datetime.datetime.now().strftime('%Y-%m-%d'))
        print('Ticker', ticker)
        data = yf.download(ticker, start=startDate, end=endDate)['Close']
        if data.empty:
            raise ValueError(f"No data found on ticker {ticker}.")
        return data
    
    @staticmethod
    def get_options(ticker):
        options =  yf.Ticker(ticker).options
        print('Options', options)
        if not options:
            raise ValueError(f"No options found on ticker {ticker}.")
        return options
    
    @staticmethod
    def get_option_chains(ticker, expiry):
        return yf.Ticker(ticker).option_chain(expiry)

    def get_prices(self): # Use this to get the prices for all the tickers in the portfolio. Initial Load
        tickers = list(set([trade['ticker'] for trade in self.portfolio]))
        # Use PaperTrader.get_prices_for_tickers() to get the price of a single ticker and combine the results.
        for ticker in tickers:
            if ticker not in PaperTrader.prices.columns:
                PaperTrader.prices[ticker] = PaperTrader.get_prices_for_tickers(ticker)
    
    def get_price(self, ticker):
        if ticker not in PaperTrader.prices.columns:
            PaperTrader.prices[ticker] = PaperTrader.get_prices_for_tickers(ticker)
        return PaperTrader.prices[ticker]
    
    def get_option_chain(self, ticker, expiry):
        if ticker not in PaperTrader.option_chains.keys():
            data = PaperTrader.get_option_chains(ticker, expiry)
            PaperTrader.option_chains[ticker] = {'calls': data[0], 'puts': data[1]}
        return PaperTrader.option_chains[ticker]
    
    def get_transaction_by_uuid(self, uuid):
        return [trade for trade in self.portfolio if trade['uid'] == uuid]

    def get_portfolio_value(self):
        portfolio_value = 0
        for trade in self.portfolio:
            if trade['type'] == 'call' or trade['type'] == 'put':
                continue
            ticker = trade['ticker']
            quantity = trade['quantity']
            price = PaperTrader.prices[ticker][-1]
            value = price * int(quantity)
            if trade['type'] == 'short':
                value *= -1
            portfolio_value += value
        return portfolio_value + self.capital
    
    def get_buying_power(self):
        long_stocks = sum([trade['price'] * trade['quantity'] for trade in self.portfolio if trade['type'] == 'buy'])
        short_stocks = sum([trade['price'] * trade['quantity'] for trade in self.portfolio if trade['type'] == 'short'])
        return self.capital + (0.5 * long_stocks) - (1.5 * short_stocks)
    
    def growth(self):
        return 100 * (self.get_portfolio_value() - self.initial) / self.initial

    def preview_buy(self, ticker, quantity):
        prices = self.get_price(ticker)
        price = prices[-1]
        cost = price * quantity
        fee = cost * PaperTrader.FEE_RATE if self.has_fee else 0
        if cost + fee > self.capital or cost + fee > self.get_buying_power():
            print("Insufficient funds to make this purchase.")
            raise ValueError("Insufficient funds to make this purchase.")
        else:
            print(f"Buying {quantity} shares of {ticker} at ${price} would cost ${cost:.2f}.")
        return price, cost, fee
    
    def preview_sell(self, uuid, quantity):
        trade = self.get_transaction_by_uuid(uuid)
        if not trade:
            print("You cannot sell a stock you don't own.")
            raise ValueError("You cannot sell a stock you don't own.")
        trade = trade[0]
        ticker = trade['ticker']
        prices = self.get_price(ticker)
        price = prices[-1]
        cost = price * quantity
        fee = cost * PaperTrader.FEE_RATE if self.has_fee else 0
        if quantity > trade['quantity']:
            print("You do not own enough shares to make this sale.")
            raise ValueError("You do not own enough shares to make this sale.")
        else:
            print(f"Selling {quantity} shares of {ticker} at ${price} would earn ${cost:.2f}.")
        return price, cost, fee
    
    def preview_short(self, ticker, quantity):
        prices = self.get_price(ticker)
        price = prices[-1]
        cost = price * quantity
        fee = cost * PaperTrader.FEE_RATE if self.has_fee else 0
        if cost + fee > self.capital or cost + fee > self.get_buying_power():
            print("Insufficient funds to make this purchase.")
            raise ValueError("Insufficient funds to make this purchase.")
        else:
            print(f"Shorting {quantity} shares of {ticker} at ${price} would cost ${cost:.2f}")
        return price, cost, fee
    
    def preview_cover(self, uuid, quantity):
        trade = self.get_transaction_by_uuid(uuid)
        if not trade:
            print("You cannot cover a stock you have not shorted.")
            raise ValueError("You cannot cover a stock you have not shorted.")
        trade = trade[0]
        ticker = trade['ticker']
        prices = self.get_price(ticker)
        price = prices[-1]
        cost = price * quantity
        fee = cost * PaperTrader.FEE_RATE if self.has_fee else 0
        if quantity > trade['quantity']:
            print("You have not shorted enough shares to make this sale.")
            raise ValueError("You have not shorted enough shares to make this sale.")
        else:
            print(f"Covering {quantity} shares of {ticker} at ${price} would cost ${cost:.2f}.")
        return price, cost, fee
    
    def preview_options(self, ticker, expiry, key):
        data = self.get_option_chain(ticker, expiry)[key]
        print(data)
        # Remove all options that have 0 premium.
        bid_ask = data[(data['bid'] + data['ask'])/2 > 0]
        if len(bid_ask) > 5: # If no results, default to using lastPrice.
            data = bid_ask
        return data.to_dict(), data.to_json()
    
    def preview_call(self, ticker, expiry, contractSymbol, contracts):
        call_data = self.get_option_chain(ticker, expiry)['calls']
        call_data = call_data[call_data['contractSymbol'] == contractSymbol]
        strikePrice = call_data['strike'].values[0]
        premium = (call_data['bid'].values[0] + call_data['ask'].values[0]) / 2
        if not premium:
            premium = call_data['lastPrice'].values[0]
        contractSize = call_data['contractSize'].values[0]
        inTheMoney = bool(call_data['inTheMoney'].values[0])
        cost = premium * contracts * 100 # Assuming 100 shares per contract.
        fee = cost * PaperTrader.FEE_RATE if self.has_fee else 0
        if cost + fee > self.capital or cost + fee > self.get_buying_power():
            print("Insufficient funds to make this purchase.")
            raise ValueError("Insufficient funds to make this purchase.")
        else:
            print(f"Calling {contracts} contracts of {ticker} at ${strikePrice} strike price and ${premium} premium would cost ${cost:.2f}")
        return strikePrice, premium, contractSize, inTheMoney, cost, fee
    
    def preview_put(self, ticker, expiry, contractSymbol, contracts):
        put_data = self.get_option_chain(ticker, expiry)['puts']
        put_data = put_data[put_data['contractSymbol'] == contractSymbol]
        strikePrice = put_data['strike'].values[0]
        premium = (put_data['bid'].values[0] + put_data['ask'].values[0]) / 2
        if not premium:
            premium = put_data['lastPrice'].values[0]
        contractSize = put_data['contractSize'].values[0]
        inTheMoney = bool(put_data['inTheMoney'].values[0])
        cost = premium * contracts * 100 # Assuming 100 shares per contract.
        fee = cost * PaperTrader.FEE_RATE if self.has_fee else 0
        if cost + fee > self.capital or cost + fee > self.get_buying_power():
            print("Insufficient funds to make this purchase.")
            raise ValueError("Insufficient funds to make this purchase.")
        else:
            print(f"Putting {contracts} contracts of {ticker} at ${strikePrice} strike price and ${premium} premium would cost ${cost:.2f}")
        return strikePrice, premium, contractSize, inTheMoney, cost, fee
    
    def preview_exercise(self, uid):
        option = self.get_option(uid)
        ticker = option['ticker']
        strike = option['strike']
        quantity = option['quantity']
        prices = self.get_price(ticker)
        price = float(prices[-1])
        gain = (price - strike) * quantity
        fee = gain * PaperTrader.FEE_RATE if self.has_fee else 0
        if option['type'] == 'put':
            gain = (strike - price) * quantity
        if self.capital + gain < 0 or self.get_buying_power() + gain < 0: # Check if the purchase can be made (enough free capital (not invested in stocks)).
            print("Insufficient funds to make this purchase.")
            raise ValueError("Insufficient funds to make this purchase.")
        return price, gain, fee

    def buy(self, ticker, quantity):
        prices = self.get_price(ticker)
        price = float(prices[-1])
        print('Price', price)
        print('Quantity', quantity)
        cost = price * int(quantity)
        fee = cost * PaperTrader.FEE_RATE if self.has_fee else 0
        if cost + fee > self.capital or cost + fee > self.get_buying_power(): # Check if the purchase can be made (enough free capital (not invested in stocks)).
            print("Insufficient funds to make this purchase.")
            raise ValueError("Insufficient funds to make this purchase.")
        else:
            self.portfolio.append({'ticker': ticker, 'quantity': int(quantity), 'price': price, 'datetime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'type': 'buy', 'uid': str(uuid.uuid4())})
            PaperTrader.prices[ticker] = prices
            self.capital -= cost + fee
            print(f"Bought {quantity} shares of {ticker} at ${price}")
            from data.firebase_controller import updatePortfolio
            updatePortfolio(self.name, self)

    def sell(self, uuid, quantity):
        trade = self.get_transaction_by_uuid(uuid)
        if not trade:
            print("You cannot sell a stock you don't own.")
            raise ValueError("You cannot sell a stock you don't own.")
        trade = trade[0]
        ticker = trade['ticker']
        if int(quantity) > trade['quantity']:
            print("You don't own enough shares to make this sale.")
            raise ValueError("You don't own enough shares to make this sale.")
        else:
            price = self.get_price(ticker)[-1]
            revenue = price * int(quantity)
            fee = revenue * PaperTrader.FEE_RATE if self.has_fee else 0
            self.capital += revenue - fee
            for trade in self.portfolio:
                if trade['uid'] == uuid:
                    trade['quantity'] -= int(quantity)
                    if trade['quantity'] == 0:
                        self.portfolio.remove(trade)
                        # Remove the ticker from the prices DataFrame
                        PaperTrader.prices.drop(ticker, axis=1, inplace=True)
                    break
            print(f"Sold {int(quantity)} shares of {ticker} at ${price}")
            from data.firebase_controller import updatePortfolio
            updatePortfolio(self.name, self)

    def short(self, ticker, quantity):
        prices = self.get_price(ticker)
        price = float(prices[-1])
        cost = price * int(quantity)
        fee = cost * PaperTrader.FEE_RATE if self.has_fee else 0
        if cost + fee > self.capital or cost + fee > self.get_buying_power():
            print("Insufficient funds to make this purchase.")
            raise ValueError("Insufficient funds to make this purchase.")
        else:
            self.portfolio.append({'ticker': ticker, 'quantity': int(quantity), 'price': price, 'datetime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'type': 'short', 'uid': str(uuid.uuid4())})
            PaperTrader.prices[ticker] = prices
            self.capital += cost - fee
            print(f"Shorted {quantity} shares of {ticker} at ${price}")
            from data.firebase_controller import updatePortfolio
            updatePortfolio(self.name, self)

    def cover(self, uuid, quantity):
        trade = self.get_transaction_by_uuid(uuid)
        if not trade:
            print("You cannot cover a stock you have not shorted.")
            raise ValueError("You cannot cover a stock you have not shorted.")
        trade = trade[0]
        ticker = trade['ticker']
        if int(quantity) > trade['quantity']:
            print("You have not shorted enough shares to make this sale.")
            raise ValueError("You have not shorted enough shares to make this sale.")
        else:
            price = self.get_price(ticker)[-1]
            cost = price * int(quantity)
            fee = cost * PaperTrader.FEE_RATE if self.has_fee else 0
            self.capital -= cost + fee
            for trade in self.portfolio:
                if trade['uid'] == uuid:
                    trade['quantity'] -= int(quantity)
                    if trade['quantity'] == 0:
                        self.portfolio.remove(trade)
                        # Remove the ticker from the prices DataFrame
                        PaperTrader.prices.drop(ticker, axis=1, inplace=True)
                    break
            print(f"Covered {int(quantity)} shares of {ticker} at ${price}")
            from data.firebase_controller import updatePortfolio
            updatePortfolio(self.name, self)

    def call(self, ticker, expiry, contractSymbol, contracts):
        call_data = self.get_option_chain(ticker, expiry)['calls']
        call_data = call_data[call_data['contractSymbol'] == contractSymbol]
        strikePrice = call_data['strike'].values[0]
        premium = float((call_data['bid'].values[0] + call_data['ask'].values[0]) / 2)
        if not premium:
            premium = call_data['lastPrice'].values[0]
        cost = premium * contracts * 100 # Assuming 100 shares per contract.
        fee = cost * PaperTrader.FEE_RATE if self.has_fee else 0
        if cost + fee > self.capital or cost + fee > self.get_buying_power():
            print("Insufficient funds to make this purchase.")
            raise ValueError("Insufficient funds to make this purchase.")
        else:
            self.portfolio.append({'ticker': ticker, 'symbol': contractSymbol, 'quantity': contracts * 100, 'strike': strikePrice, 'premium': premium, 'expiry': expiry, 'datetime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'type': 'call', 'uid': str(uuid.uuid4())})
            PaperTrader.prices[ticker] = self.get_price(ticker)
            self.capital -= cost + fee
            print(f"Called {contracts} contracts of {ticker} at ${strikePrice} strike price and ${premium} premium.")
            from data.firebase_controller import updatePortfolio
            updatePortfolio(self.name, self)

    def put(self, ticker, expiry, contractSymbol, contracts):
        put_data = self.get_option_chain(ticker, expiry)['puts']
        put_data = put_data[put_data['contractSymbol'] == contractSymbol]
        strikePrice = put_data['strike'].values[0]
        premium = float((put_data['bid'].values[0] + put_data['ask'].values[0]) / 2)
        if not premium:
            premium = put_data['lastPrice'].values[0]
        cost = premium * contracts * 100 # Assuming 100 shares per contract.
        fee = cost * PaperTrader.FEE_RATE if self.has_fee else 0
        if cost + fee > self.capital or cost + fee > self.get_buying_power():
            print("Insufficient funds to make this purchase.")
            raise ValueError("Insufficient funds to make this purchase.")
        else:
            self.portfolio.append({'ticker': ticker, 'symbol': contractSymbol, 'quantity': contracts * 100, 'strike': strikePrice, 'premium': premium, 'expiry': expiry, 'datetime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'type': 'put', 'uid': str(uuid.uuid4())})
            PaperTrader.prices[ticker] = self.get_price(ticker)
            self.capital -= cost + fee
            print(f"Put {contracts} contracts of {ticker} at ${strikePrice} strike price and ${premium} premium.")
            from data.firebase_controller import updatePortfolio
            updatePortfolio(self.name, self)

    def get_option(self, uid):
        option = [i for i in self.portfolio if i['uid'] == uid]
        if uid:
            if not option:
                raise ValueError(f"Call or Put Option UID {uid} does not exist.")
            else:
                return option[0]
        else:
            raise ValueError("Call or Put Option UID must be provided.")

    def exercise(self, uid):
        option = self.get_option(uid)
        ticker = option['ticker']
        strike = option['strike']
        quantity = option['quantity']
        prices = self.get_price(ticker)
        price = float(prices[-1])
        gain = (price - strike) * quantity
        if option['type'] == 'put':
            gain = (strike - price) * quantity
        if self.capital + gain < 0 or self.get_buying_power() + gain < 0: # Check if the purchase can be made (enough free capital (not invested in stocks)).
            print("Insufficient funds to make this purchase.")
            raise ValueError("Insufficient funds to make this purchase.")
        else:
            PaperTrader.prices[ticker] = prices
            self.capital += gain
            self.portfolio.remove(option)
            print(f"Exercised {option['type'].capitalize()} Option {option['symbol']} for {quantity} shares of {ticker} at ${strike}")
            from data.firebase_controller import updatePortfolio
            updatePortfolio(self.name, self)
        

    def print_portfolio(self):
        if not self.portfolio:
            print("You don't own any shares yet")
        else:
            for trade in self.portfolio:
                ticker = trade['ticker']
                quantity = trade['quantity']
                price = trade['price']
                uid = trade['uid']
                datetime = trade['datetime']
                print(f"{uid} at {datetime}: {quantity} shares of {ticker} at ${price}")
            portfolio_value = self.get_portfolio_value()
            print(f"\nTotal portfolio value: ${portfolio_value:.2f}")

    def to_dict(self):
        return {
            'name': self.name,
            'portfolio': self.portfolio,
            'initial': self.initial,
            'capital': self.capital,
            'id': self.id,
            'has_options': self.has_options,
            'has_fee': self.has_fee
        }

if __name__ == '__main__':
    # msft = yf.Ticker("MSFT")
    # msft_history = msft.history(start="2021-01-01", end="2023-04-16")
    # print(msft_history.head())

    # Create a portfolio with $10,000 to invest
    portfolio = {'AAPL': 10, 'AMZN': 5, 'TSLA': 3}
    initial = 5000
    capital = 10000
    trader = PaperTrader('hello', portfolio, initial, capital, 'saptak.das625@gmail.com', True, False)

    # Buy some shares of a stock
    trader.buy('MSFT', 2)

    # Sell some shares of a stock
    trader.sell('AAPL', 5)

    # Print the current portfolio and its total value
    trader.print_portfolio()
