"""
app.py - the web page for the backtester, built with Streamlit.

Start it with:   streamlit run app.py

This file only handles the user interface: the sidebar settings, the
results table and the charts. All the strategy math lives in backtest.py.

Streamlit runs this whole file from top to bottom every time you change a
setting, and redraws the page with the new results.
"""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import backtest

# Chart colors, kept in one place so they're easy to find and change.
STRATEGY_COLOR = "#1f77b4"  # blue: the crossover strategy's account value
HOLD_COLOR = "#7f7f7f"  # gray: buy and hold's account value
PRICE_COLOR = "#7f7f7f"  # gray too, because buy and hold just follows the price
SHORT_MA_COLOR = "#ff7f0e"  # orange
LONG_MA_COLOR = "#9467bd"  # purple
BUY_COLOR = "green"
SELL_COLOR = "red"


def as_percent(value):
    """Format a fraction as a percent, like 0.1234 -> '12.3%'.

    Shows 'n/a' when there is no value (for example, a win rate with no trades).
    """
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def metrics_for_table(metrics):
    """Turn one plan's metrics into nicely formatted text, labelled by row name."""
    return {
        "Final value": f"${metrics['final_value']:,.2f}",  # like $12,345.68
        "Total return": as_percent(metrics["total_return"]),
        "Annualized return": as_percent(metrics["annual_return"]),
        "Max drawdown": as_percent(metrics["max_drawdown"]),
        "Number of trades": str(metrics["num_trades"]),
        "Win rate": as_percent(metrics["win_rate"]),
    }


# The @ line is a "decorator": it tells Streamlit to save (cache) this
# function's answer. ttl means "time to live": after 1 hour the saved
# answer is thrown away and the next call downloads fresh prices.
@st.cache_data(ttl="1h", show_spinner="Downloading prices from Yahoo Finance...")
def load_prices(ticker, start_date, end_date, long_window):
    """Download prices, and remember the answer for one hour.

    Because Streamlit reruns this file after every change, caching stops us
    from downloading the same prices over and over again.
    """
    return backtest.download_prices(ticker, start_date, end_date, long_window)


# ---------------------------------------------------------------------------
# Page title
# ---------------------------------------------------------------------------
st.set_page_config(page_title="MA Crossover Backtester", page_icon="📈", layout="wide")
st.title("📈 Moving Average Crossover Backtester")
st.write(
    "**The strategy:** buy when the short moving average crosses above the long "
    "moving average, and sell when it crosses back below. Then compare that with "
    "simply buying and holding. *For learning only, not investment advice.*"
)

# ---------------------------------------------------------------------------
# Sidebar settings
# ---------------------------------------------------------------------------
today = date.today()
# pd.DateOffset(years=10) moves back exactly 10 calendar years (leap years included).
ten_years_ago = (pd.Timestamp(today) - pd.DateOffset(years=10)).date()
# Without a min_value, Streamlit's date picker only goes back 10 years from
# its starting date, so we give it a much earlier limit.
earliest_allowed = date(1970, 1, 1)

st.sidebar.header("Settings")
# strip() removes spaces at the ends and upper() makes capitals: " spy " -> "SPY"
ticker = st.sidebar.text_input("Ticker symbol", value="SPY").strip().upper()
start_date = st.sidebar.date_input(
    "Start date", value=ten_years_ago, min_value=earliest_allowed, max_value=today
)
end_date = st.sidebar.date_input(
    "End date", value=today, min_value=earliest_allowed, max_value=today
)
short_window = st.sidebar.number_input(
    "Short moving average (days)",
    min_value=1,
    max_value=backtest.MAX_WINDOW - 1,
    value=50,
    step=1,
)
long_window = st.sidebar.number_input(
    "Long moving average (days)",
    min_value=2,
    max_value=backtest.MAX_WINDOW,
    value=200,
    step=1,
)
starting_cash = st.sidebar.number_input(
    "Starting cash ($)", min_value=1.0, value=10_000.0, step=1_000.0
)

# An empty string counts as False in Python, so this means "nothing typed".
if not ticker:
    st.info("👈 Type a ticker symbol in the sidebar to get started.")
    st.stop()  # end this run here; nothing below gets drawn

# ---------------------------------------------------------------------------
# Run the backtest (the real work happens in backtest.py)
# ---------------------------------------------------------------------------
try:
    backtest.check_inputs(start_date, end_date, short_window, long_window, starting_cash)
    prices = load_prices(ticker, start_date, end_date, long_window)
    results = backtest.run_backtest(prices, start_date, short_window, long_window, starting_cash)
except backtest.BacktestError as problem:
    # Problems that backtest.py explains in plain words, like a misspelled ticker.
    st.error(str(problem))
    st.stop()
except Exception as problem:
    # Anything else, for example Yahoo limiting how often we can download
    # ("rate limiting"), some internet problems, or a bug in our own code.
    st.error(
        f"Something went wrong while getting data for '{ticker}'. If you're "
        f"offline, reconnect; otherwise wait a minute and try again.\n\n"
        f"Details: {problem}"
    )
    st.stop()

data = results["data"]
trades = results["strategy_trades"]
first_day = data.index[0].date()
last_day = data.index[-1].date()
st.caption(f"Backtest period: {first_day} to {last_day} ({len(data)} trading days)")

# If the ticker doesn't have enough history before the start date, the long
# moving average is missing (NaN) for the first part of the test.
# isna() is True on days it's missing, and .any() is True if ANY day is.
if data["Long MA"].isna().any():
    # first_valid_index() gives the first date that has a real value.
    ready_day = data["Long MA"].first_valid_index().date()
    st.warning(
        f"{ticker} doesn't have {long_window} trading days of history before the "
        f"start date, so the moving averages aren't ready until {ready_day}. "
        "The strategy can't trade before then."
    )

# If the short MA was already above the long MA on the first day (and that
# day wasn't itself a crossover), there was nothing to act on yet, so the
# strategy sits in cash until the next fresh crossover. Explain that.
first_row = data.iloc[0]  # .iloc[0] means "the first row, by position"
already_above = first_row["Short MA"] > first_row["Long MA"] and not first_row["Buy Signal"]
if already_above:
    if trades:  # a list with something in it counts as True
        wait_message = f"waited in cash until its first buy on {trades[0]['Buy Date'].date()}"
    else:
        wait_message = (
            "never saw the short MA cross above the long MA after that, "
            "so it never bought"
        )
    st.info(
        f"On {first_day} the {short_window}-day MA was already above the "
        f"{long_window}-day MA, so there was no crossover to act on yet. "
        f"The strategy {wait_message}."
    )

# ---------------------------------------------------------------------------
# Results table
# ---------------------------------------------------------------------------
st.subheader("Results")
strategy_metrics = results["strategy_metrics"]
hold_metrics = results["hold_metrics"]

# Each dictionary becomes one column, and its keys become the row labels.
results_table = pd.DataFrame(
    {
        "Crossover strategy": metrics_for_table(strategy_metrics),
        "Buy and hold": metrics_for_table(hold_metrics),
    }
)
st.table(results_table)

# A one-line summary. Subtracting two percentages gives "percentage points".
difference = strategy_metrics["total_return"] - hold_metrics["total_return"]
points = abs(difference) * 100  # abs() drops the minus sign
if points < 0.05:
    st.info("Both plans ended with about the same total return.")
elif difference > 0:
    st.success(f"The crossover strategy beat buy and hold by {points:.1f} percentage points.")
else:
    st.info(f"Buy and hold beat the crossover strategy by {points:.1f} percentage points.")

st.caption(
    "Each buy counts as one trade: the buy plus the sell after it, or a buy that "
    "is still open on the last day (scored at the last closing price). Buy and "
    "hold buys once and never sells, so it always shows 1 trade. Max drawdown is "
    "the biggest drop from a previous high. Annualized return is only shown for "
    "tests of about a year or longer."
)

# go.Scatter can draw lines or dots: mode="lines" joins the points into a
# line, and mode="markers" (used for the buy/sell triangles) draws only dots.

# ---------------------------------------------------------------------------
# Chart 1: account value over time (the "equity curve")
# ---------------------------------------------------------------------------
st.subheader("Account value over time")
equity_chart = go.Figure()
equity_chart.add_trace(
    go.Scatter(
        x=results["strategy_equity"].index,
        y=results["strategy_equity"],
        mode="lines",
        name="Crossover strategy",
        line=dict(color=STRATEGY_COLOR),
    )
)
equity_chart.add_trace(
    go.Scatter(
        x=results["hold_equity"].index,
        y=results["hold_equity"],
        mode="lines",
        name="Buy and hold",
        line=dict(color=HOLD_COLOR),
    )
)
equity_chart.update_layout(yaxis_title="Account value ($)", hovermode="x unified")
st.plotly_chart(equity_chart)

# ---------------------------------------------------------------------------
# Chart 2: price, both moving averages, and the buy/sell points
# ---------------------------------------------------------------------------
st.subheader(f"{ticker} price with moving averages and trades")

# Collect the dates and prices of every buy and every sell. Open trades
# have no real sell yet, so they get a buy marker only.
buy_dates = []
buy_prices = []
sell_dates = []
sell_prices = []
for trade in trades:
    buy_dates.append(trade["Buy Date"])
    buy_prices.append(trade["Buy Price"])
    if trade["Status"] == "Closed":
        sell_dates.append(trade["Sell Date"])
        sell_prices.append(trade["Sell Price"])

price_chart = go.Figure()
price_chart.add_trace(
    go.Scatter(
        x=data.index,
        y=data["Close"],
        mode="lines",
        name="Closing price",
        line=dict(color=PRICE_COLOR),
    )
)
price_chart.add_trace(
    go.Scatter(
        x=data.index,
        y=data["Short MA"],
        mode="lines",
        name=f"{short_window}-day MA",
        line=dict(color=SHORT_MA_COLOR),
    )
)
price_chart.add_trace(
    go.Scatter(
        x=data.index,
        y=data["Long MA"],
        mode="lines",
        name=f"{long_window}-day MA",
        line=dict(color=LONG_MA_COLOR),
    )
)
price_chart.add_trace(
    go.Scatter(
        x=buy_dates,
        y=buy_prices,
        mode="markers",
        name="Buy",
        marker=dict(symbol="triangle-up", size=13, color=BUY_COLOR),
    )
)
price_chart.add_trace(
    go.Scatter(
        x=sell_dates,
        y=sell_prices,
        mode="markers",
        name="Sell",
        marker=dict(symbol="triangle-down", size=13, color=SELL_COLOR),
    )
)
price_chart.update_layout(yaxis_title="Price ($)", hovermode="x unified")
st.plotly_chart(price_chart)

# ---------------------------------------------------------------------------
# Every trade, in a section you can open
# ---------------------------------------------------------------------------
# A "with" block puts everything indented under it inside the expander,
# a section the user can click to open or close.
with st.expander(f"See all {len(trades)} trades"):
    if not trades:
        st.write(
            "The short moving average never crossed above the long one in this "
            "period, so the strategy never bought. (A cross below only matters "
            "when we own shares.)"
        )
    else:
        rows = []
        for trade in trades:
            rows.append(
                {
                    "Bought": trade["Buy Date"].date(),
                    "Buy price": f"${trade['Buy Price']:,.2f}",
                    "Sold": trade["Sell Date"].date(),
                    "Sell price": f"${trade['Sell Price']:,.2f}",
                    "Return": as_percent(trade["Return"]),
                    "Status": trade["Status"],
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        st.caption(
            "\"Open\" means we still owned the shares on the last day, so the "
            "\"Sold\" date and price are just the last day's values."
        )
