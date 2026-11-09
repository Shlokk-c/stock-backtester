"""
backtest.py - the strategy and the math behind the app.

There is no Streamlit (web page) code in this file. Keeping the logic
separate from the user interface means you can test it on its own,
reuse it in a notebook, or put a different interface on top of it.

How a backtest runs, step by step:
  1. check_inputs()         make sure the settings make sense
  2. download_prices()      get daily closing prices from Yahoo Finance
  3. add_moving_averages()  add the short and long moving averages
  4. find_crossovers()      mark the days where the two averages cross
  5. run_strategy()         pretend to trade on those days, one day at a time
  6. run_buy_and_hold()     the simple plan: buy on day one, never sell
  7. calculate_metrics()    score each plan (returns, drawdown, win rate)

run_backtest() calls steps 3 to 7 in order and returns all the results.
"""

from datetime import timedelta

import pandas as pd
import yfinance as yf

# The longest moving average we allow (about 8 years of trading days).
MAX_WINDOW = 2000


class BacktestError(Exception):
    """A problem we can explain to the user in plain words, like a bad ticker.

    Making our own kind of error lets app.py tell OUR friendly messages apart
    from unexpected errors that come from inside other libraries.
    """


def check_inputs(start_date, end_date, short_window, long_window, starting_cash):
    """Make sure the settings make sense before doing any work.

    Raises a BacktestError with a friendly message if something is wrong.
    The app catches that error and shows the message on the page.
    """
    if start_date >= end_date:
        raise BacktestError("The start date must be before the end date.")
    if short_window < 1:
        raise BacktestError("The moving averages must be at least 1 day long.")
    if short_window >= long_window:
        raise BacktestError(
            "The short moving average must be shorter than the long moving average."
        )
    if long_window > MAX_WINDOW:
        raise BacktestError(f"The long moving average can be at most {MAX_WINDOW:,} days.")
    if starting_cash <= 0:
        raise BacktestError("Starting cash must be more than $0.")


def download_prices(ticker, start_date, end_date, long_window):
    """Download daily closing prices for one ticker from Yahoo Finance.

    We also download some extra days BEFORE start_date, called a "warm-up".
    A 200-day moving average needs 200 days of prices before it has a value.
    Without the warm-up, the strategy couldn't trade for the first ~10 months.

    Returns a DataFrame (a table) with one column, "Close", and one row per
    trading day. Raises a BacktestError if Yahoo sends back no usable data.
    That happens when the ticker is misspelled, and usually also when there
    is no internet connection, because yfinance often reports both problems
    the same way: with an empty table.
    """
    # A year has about 252 trading days but 365 calendar days (because of
    # weekends), so going back 2 calendar days for every trading day we need
    # is a safe buffer. The extra 14 days cover holidays when markets close.
    warmup_start = start_date - timedelta(days=long_window * 2 + 14)

    # yfinance stops the day BEFORE the `end` date, so add one day to make
    # sure end_date itself is included.
    day_after_end = end_date + timedelta(days=1)

    history = yf.Ticker(ticker).history(
        start=warmup_start,
        end=day_after_end,
        auto_adjust=True,  # adjust old prices for stock splits and dividends
    )

    if history.empty:
        message = (
            f"No price data found for '{ticker}'. Check that the ticker symbol is "
            "spelled correctly, that it traded during the dates you picked, and "
            "that you're connected to the internet."
        )
        if "." in ticker:
            message += (
                " Tip: for US share classes Yahoo uses a dash, "
                "for example BRK-B instead of BRK.B."
            )
        raise BacktestError(message)

    # Double brackets [["Close"]] keep a table (DataFrame) with one column.
    # Single brackets ["Close"] would give a bare column (a Series) instead.
    # dropna() then removes any days with a missing price.
    prices = history[["Close"]].dropna()

    # This simple backtester can't handle prices of zero or below. (They do
    # happen: US oil futures closed below $0 in April 2020.) The comparison
    # gives True/False for each day, and .any() is True if ANY day is True.
    if (prices["Close"] <= 0).any():
        raise BacktestError(
            f"Yahoo's prices for '{ticker}' include zero or negative values, "
            "and this simple backtester only works with positive prices."
        )

    # Each row is labelled with its date; pandas calls these row labels the
    # "index". Yahoo's dates include a time zone (New York time for US
    # stocks). We only care about the date, so remove the time zone.
    prices.index = prices.index.tz_localize(None)
    return prices


def add_moving_averages(prices, short_window, long_window):
    """Add the short and long simple moving averages as two new columns.

    A simple moving average (SMA) is the average of the last N closing prices.
    For example, the 50-day SMA on a given day is the average of that day's
    close and the 49 closes before it. Until there are N days of prices, the
    average is NaN ("not a number"), which here just means "not ready yet".
    """
    data = prices.copy()  # work on a copy so we never change the original table
    data["Short MA"] = data["Close"].rolling(window=short_window).mean()
    data["Long MA"] = data["Close"].rolling(window=long_window).mean()
    return data


def find_crossovers(data):
    """Mark the days when the short moving average crosses the long one.

    Adds two True/False columns:
      "Buy Signal":  yesterday the short MA was at or below the long MA,
                     and today it is above it (it crossed UP).
      "Sell Signal": yesterday the short MA was above the long MA,
                     and today it is at or below it (it crossed DOWN).

    In pandas, for True/False columns:  &  means AND,  ~  means NOT.
    """
    data = data.copy()

    # True on days when the short MA is above the long MA.
    short_above = data["Short MA"] > data["Long MA"]

    # The same True/False values moved down one row, so each row can see
    # what the answer was on the previous trading day. The first row has
    # no "yesterday", so we fill it with False.
    short_above_yesterday = short_above.shift(1, fill_value=False)

    # A crossover only counts if both averages had values yesterday AND
    # today. The long MA is always the last one to become ready, so we
    # only need to check that one. notna() is True where there is a number
    # and False where the value is missing (NaN).
    ready_today = data["Long MA"].notna()
    ready_yesterday = ready_today.shift(1, fill_value=False)
    both_ready = ready_today & ready_yesterday

    data["Buy Signal"] = both_ready & short_above & ~short_above_yesterday
    data["Sell Signal"] = both_ready & ~short_above & short_above_yesterday
    return data


def make_trade(buy_date, buy_price, sell_date, sell_price, status):
    """Package one trade (a buy and the sell that closed it) as a dictionary."""
    return {
        "Buy Date": buy_date,
        "Buy Price": buy_price,
        "Sell Date": sell_date,
        "Sell Price": sell_price,
        "Return": sell_price / buy_price - 1,  # 0.10 means the trade made +10%
        "Status": status,  # "Closed", or "Open" if we still owned it at the end
    }


def run_strategy(data, starting_cash):
    """Pretend to trade the crossover strategy, one day at a time.

    Rules:
      - Start with all cash and no shares.
      - Buy Signal while we own no shares -> spend ALL our cash on shares.
      - Sell Signal while we own shares   -> sell ALL our shares.
      - Every trade happens at that day's closing price.
      - Fractional shares are allowed (like 12.34 shares), so every dollar
        gets invested. This simple model has no fees or taxes.

    Returns two things:
      equity: a pandas Series with our total account value on each day
      trades: a list of trades, each one made by make_trade()
    """
    cash = starting_cash
    shares = 0.0
    buy_date = None  # when we bought our current shares
    buy_price = None  # the price we paid for them
    equity = []  # account value at the end of each day
    trades = []

    # data.iterrows() hands us one row (one trading day) at a time:
    # `day` is that row's date and `row` holds that day's values.
    for day, row in data.iterrows():
        price = row["Close"]

        if row["Buy Signal"] and shares == 0:
            shares = cash / price  # all-in: spend all our cash
            cash = 0.0
            buy_date = day
            buy_price = price

        elif row["Sell Signal"] and shares > 0:
            cash = shares * price  # all-out: sell every share
            shares = 0.0
            trades.append(make_trade(buy_date, buy_price, day, price, "Closed"))

        # Account value today = cash + what our shares are worth.
        equity.append(cash + shares * price)

    # Still holding shares on the last day? Score that trade using the last
    # closing price, as if we sold it then, but label it "Open".
    # .iloc[-1] means "the last row, by position" (-1 counts from the end).
    if shares > 0:
        last_day = data.index[-1]
        last_price = data["Close"].iloc[-1]
        trades.append(make_trade(buy_date, buy_price, last_day, last_price, "Open"))

    # Turn the plain list into a pandas Series labelled by date.
    equity = pd.Series(equity, index=data.index)
    return equity, trades


def run_buy_and_hold(data, starting_cash):
    """The simplest plan: buy on the first day with all our cash, never sell.

    Returns the same two things as run_strategy(), so both plans can be
    scored by the same calculate_metrics() function.
    """
    first_price = data["Close"].iloc[0]  # .iloc[0] is the first row by position
    last_price = data["Close"].iloc[-1]
    shares = starting_cash / first_price

    # Account value every day = number of shares x that day's price.
    equity = shares * data["Close"]

    # Buy and hold makes exactly one trade, still open on the last day.
    trades = [make_trade(data.index[0], first_price, data.index[-1], last_price, "Open")]
    return equity, trades


def calculate_metrics(equity, trades, starting_cash):
    """Score a plan using its equity curve and its list of trades.

    Returns a dictionary with:
      final_value   - account value on the last day, in dollars
      total_return  - how much we gained overall (0.50 means +50%)
      annual_return - the steady yearly growth rate that would give the same
                      total return (also called CAGR: compound annual growth
                      rate). None for tests shorter than about a year.
      max_drawdown  - the biggest drop from a previous high (-0.30 means -30%)
      num_trades    - how many trades: each buy counts as one, whether it was
                      later sold or was still open on the last day
      win_rate      - the fraction of trades that made money (None if no trades)
    """
    final_value = equity.iloc[-1]
    total_return = final_value / starting_cash - 1

    # How many years the test covers. 365.25 days per year accounts for leap years.
    years = (equity.index[-1] - equity.index[0]).days / 365.25

    # Stretching a short test into a yearly rate gives silly numbers (+7% in
    # one week works out to about +3,300% a year), so we only annualize tests
    # of about a year or more. We use 0.95 instead of 1 because weekends and
    # holidays mean even a full calendar year spans only 360-364 days from
    # its first trading day to its last.
    if years >= 0.95:
        # If money grows by the same percent each year for `years` years,
        # this is the yearly percent that ends at final_value.
        annual_return = (final_value / starting_cash) ** (1 / years) - 1
    else:
        annual_return = None

    # Drawdown: on each day, how far are we below the highest value so far?
    # cummax() gives the running maximum, e.g. [1, 3, 2, 5] -> [1, 3, 3, 5].
    highest_so_far = equity.cummax()
    drawdown = equity / highest_so_far - 1
    max_drawdown = drawdown.min()  # the most negative day is the worst drop

    # Win rate: what fraction of trades made money?
    num_trades = len(trades)
    wins = 0
    for trade in trades:
        if trade["Return"] > 0:
            wins += 1
    if num_trades > 0:
        win_rate = wins / num_trades
    else:
        win_rate = None  # no trades means there is no win rate to report

    return {
        "final_value": final_value,
        "total_return": total_return,
        "annual_return": annual_return,
        "max_drawdown": max_drawdown,
        "num_trades": num_trades,
        "win_rate": win_rate,
    }


def run_backtest(prices, start_date, short_window, long_window, starting_cash):
    """Run the whole backtest and return everything the app needs to display.

    `prices` should come from download_prices(), warm-up days included.
    Returns a dictionary with the price data (plus moving averages and
    signals), both equity curves, the strategy's trades, and both sets of
    metrics.
    """
    data = add_moving_averages(prices, short_window, long_window)
    data = find_crossovers(data)

    # The warm-up days were only needed to get the averages started.
    # From here on, keep just the dates the user asked for. The comparison
    # gives True/False for each row, and data[...] keeps only the True rows.
    data = data[data.index >= pd.Timestamp(start_date)]
    if data.empty:
        raise BacktestError(
            "There are no trading days in the dates you picked. "
            "Try a wider date range."
        )

    # If the stock has fewer days of prices than the long MA needs, the long
    # MA never gets a value and the strategy could never trade. Say so,
    # instead of showing a comparison that means nothing.
    # isna() is True where a value is missing; .all() is True if EVERY one is.
    if data["Long MA"].isna().all():
        raise BacktestError(
            f"Not enough price history for a {long_window}-day moving average: "
            f"only {len(prices)} trading days of prices were found. "
            "Try a shorter long moving average."
        )

    strategy_equity, strategy_trades = run_strategy(data, starting_cash)
    hold_equity, hold_trades = run_buy_and_hold(data, starting_cash)

    return {
        "data": data,
        "strategy_equity": strategy_equity,
        "strategy_trades": strategy_trades,
        "strategy_metrics": calculate_metrics(strategy_equity, strategy_trades, starting_cash),
        "hold_equity": hold_equity,
        "hold_metrics": calculate_metrics(hold_equity, hold_trades, starting_cash),
    }


# This block only runs when you start this file directly with:
#     python backtest.py
# It does NOT run when app.py imports this file. It's a quick way to try the
# logic without the web page.
if __name__ == "__main__":
    from datetime import date

    ticker = "SPY"
    start = date(2015, 1, 1)
    end = date(2025, 1, 1)
    prices = download_prices(ticker, start, end, long_window=200)
    # 10_000 is just 10000; the underscore makes big numbers easier to read.
    results = run_backtest(prices, start, short_window=50, long_window=200, starting_cash=10_000)

    for plan_name, key in [("crossover strategy", "strategy_metrics"), ("buy and hold", "hold_metrics")]:
        metrics = results[key]
        print(f"\n{ticker} {plan_name}:")
        print(f"  final value:   ${metrics['final_value']:,.2f}")
        print(f"  total return:  {metrics['total_return']:.1%}")
        if metrics["annual_return"] is not None:
            print(f"  annual return: {metrics['annual_return']:.1%}")
        print(f"  max drawdown:  {metrics['max_drawdown']:.1%}")
        print(f"  trades:        {metrics['num_trades']}")
        if metrics["win_rate"] is not None:
            print(f"  win rate:      {metrics['win_rate']:.0%}")
