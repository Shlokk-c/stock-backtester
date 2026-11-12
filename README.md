# Stock Strategy Backtester

A small web app that tests a classic trading strategy, the **moving average
crossover**, on real historical stock prices and compares it with simply
buying and holding.

*Built for learning purposes ONLY and nothing here is investment advice.*

## What it does

You pick a ticker (like `SPY`), a date range, two moving average lengths and
some starting cash. The app then:

1. Downloads daily prices from Yahoo Finance.
2. Calculates a **short** and a **long** simple moving average (SMA).
   A 50-day SMA is the average closing price over the last 50 trading days.
3. Runs the strategy:
   - **Buy** (with all your cash) when the short SMA crosses **above** the long SMA.
   - **Sell** (all your shares) when the short SMA crosses **below** the long SMA.
   - Long only (no short selling), all-in or all-out.
4. Runs **buy and hold** for comparison: buy on the first day, never sell.
5. Shows:
   - an **equity curve** (your account value over time) for both plans
   - a **price chart** with both moving averages and buy/sell markers
   - **metrics**: total return, annualized return, max drawdown, number of
     trades and win rate
   - a table of every trade

## Example result

Running `python backtest.py` tests SPY (a fund that tracks the S&P 500)
with 50-day and 200-day moving averages and $10,000 of starting cash, from
January 1, 2015 to January 1, 2025. It printed these numbers in November
2026:

| | Crossover strategy | Buy and hold |
|---|---|---|
| Final value | $23,859.14 | $33,957.38 |
| Total return | 138.6% | 239.6% |
| Annualized return | 9.1% | 13.0% |
| Max drawdown | -33.7% | -33.7% |
| Number of trades | 5 | 1 |
| Win rate | 60% | 100% |

Over those ten years, simply buying and holding SPY beat the crossover
strategy. If you run `python backtest.py` yourself (see [Run](#run)), your
numbers may differ slightly, because Yahoo sometimes updates its price data.
The web app starts with the last ten years instead, so it shows different
numbers. To see this same test in the app, set **Start date** to 2015/01/01
and **End date** to 2025/01/01 in the sidebar.

<details>
<summary><h2>Download</h2></summary>

Already have the project in `~/Projects/stock-backtester`? Skip to
[Install](#install).

Open the Terminal app (press `Cmd + Space`, type `Terminal`, and press
Return). Then type or paste these commands, pressing Return after each one.
They download the project into a `Projects` folder inside your home folder:

```bash
mkdir -p ~/Projects
cd ~/Projects
git clone https://github.com/Shlokk-c/stock-backtester.git
```

What those commands do:

- `mkdir -p ~/Projects` creates the `Projects` folder. `~` means your home
  folder: the folder with your username, which holds Desktop, Documents and
  Downloads. If `Projects` already exists, nothing happens.
- `cd ~/Projects` moves into that folder.
- `git clone` uses `git` (a tool for downloading code and tracking changes to
  it) to copy this project from GitHub into a new folder,
  `~/Projects/stock-backtester`.

The first time you use `git`, your Mac may open a window asking to install
its "command line developer tools". Click **Install** and follow the steps.
Terminal may also print a note about `xcode-select`; you can ignore it. The
download can take several minutes. When it's done, run all three commands
again. That's safe, and it works even if you closed Terminal while you
waited.

The rest of this README assumes the project is in
`~/Projects/stock-backtester`. If `git clone` says
`destination path 'stock-backtester' already exists`, you already have the
project, so go on to Install.

</details>

<details>
<summary><h2>Install</h2></summary>

You need **Python 3.11 or newer** (this project was built with 3.15). Check
yours by running this in Terminal:

```bash
python3 --version
```

The `python3` that comes with macOS is 3.9, which is too old. If that's what
you see, install a newer Python from [python.org](https://www.python.org/downloads/)
(or run `brew install python` if you use Homebrew), open a new Terminal
window, and check again.

Then, in Terminal, go to the project folder and set it up:

```bash
cd ~/Projects/stock-backtester
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

What those commands do:

- `cd ~/Projects/stock-backtester` moves into the project folder.
- `python3 -m venv .venv` creates a *virtual environment*: a private folder
  (`.venv`) where this project's packages get installed, so they don't mix
  with other projects.
- `source .venv/bin/activate` turns the virtual environment on for this
  terminal. Your prompt will start with `(.venv)`.
- `pip install -r requirements.txt` installs the packages listed in
  `requirements.txt`.

If you already made a `.venv` with an old Python, delete it first with
`rm -rf .venv` and run the commands again.

</details>

## Run

First time? Do the Download and Install steps above first (click each
heading to open it). You only need to do them once. After that, start the
app with:

```bash
cd ~/Projects/stock-backtester
source .venv/bin/activate
streamlit run app.py
```

Then open <http://localhost:8501> in your browser if it doesn't open by
itself. Change any setting in the sidebar and the results update.

To stop the app, click the terminal and press `Ctrl + C`.

> The first time you run Streamlit, it may ask for your email in the
> terminal. You can leave it blank and just press Return. Streamlit may also
> print a few tips when it starts; they're safe to ignore.

You can also run the backtest logic without the web page. If the app is
still running, open a new terminal tab (`Cmd + T`). A new tab starts with the
virtual environment turned off, so go to the project folder and turn it on
again first:

```bash
cd ~/Projects/stock-backtester
source .venv/bin/activate
python backtest.py
```

That runs a 50/200-day test on SPY from 2015 to 2025 and prints the results.

## How the code is organized

| File | What it's for |
|---|---|
| `backtest.py` | The strategy and the math: downloading prices, moving averages, crossover signals, the trading simulation and the metrics. No web page code. |
| `app.py` | The Streamlit web page: sidebar inputs, results table and Plotly charts. It calls functions from `backtest.py`. |
| `requirements.txt` | The Python packages the project needs, with exact versions. |
| `.gitignore` | Files git should ignore, like `.venv` and `.env`. |

## The metrics

| Metric | Meaning |
|---|---|
| Total return | How much the account grew overall. +50% means $10,000 became $15,000. |
| Annualized return | The steady yearly growth rate that would give the same total return (also called CAGR, short for compound annual growth rate). Only shown for tests of about a year or longer, because stretching a short test into a yearly rate gives silly numbers. |
| Max drawdown | The biggest drop from a previous high. -30% means at some point the account was 30% below its best value so far. |
| Number of trades | Each buy counts as one trade: either the buy plus the sell after it, or a buy still open on the last day. Buy and hold buys once and never sells, so it always shows 1. |
| Win rate | The percent of trades that made money. A trade still open on the last day is judged at the last closing price, so buy and hold shows either 100% or 0%. |

## Assumptions and limitations

Real trading is messier than this model. Things to keep in mind:

- **Trades happen at the closing price** on the day of the crossover.
- **Fractional shares** are allowed (like 12.34 shares), so each buy invests
  every dollar with no leftover change. When the strategy is out of the
  market (before its first buy and after each sell), all your money sits in
  cash.
- **No fees, taxes or slippage** (slippage is the difference between the
  price you expect and the price you actually get).
- **Prices are adjusted** for stock splits and dividends, so returns include
  dividends for both plans.
- **Warm-up period:** extra price history from before your start date is
  downloaded so the moving averages are ready on day one. If a stock is too
  new to have that history, the strategy waits until the averages are ready.
- **Only real crossovers count.** If the short average is already above the
  long one on your start date, the strategy waits for the next fresh cross
  above before buying. The app tells you when this happens.
- A trade that is still open on the last day is scored at the last closing
  price.
- **If the end date is today** and the market is still open, the last price
  is the live price and can change. (Crypto and futures trade almost around
  the clock.) The app remembers downloads for 1 hour.
- Past performance doesn't predict future results.

## Troubleshooting

- **"No price data found"**: check the ticker's spelling and the dates, and
  make sure you're online. Yahoo writes US share classes with a dash, so use
  `BRK-B`, not `BRK.B`.
- **Still failing after you got back online?** Stop the app with `Ctrl + C`
  and start it again with `streamlit run app.py`.
- **"Something went wrong"**: Yahoo sometimes limits how often you can
  download. Wait a minute and try again.
