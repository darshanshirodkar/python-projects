#!/usr/bin/env python3
"""
Portfolio Evaluator - Calculates after-tax portfolio value
Fetches current stock prices and computes capital gains tax
Supports multiple currencies with automatic conversion
"""

import csv
import requests
import sys
from typing import List, Dict, Set


def fetch_stock_price(ticker: str) -> float:
    """
    Fetch the latest stock price for a given ticker using Yahoo Finance API

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'GOOGL')

    Returns:
        Current stock price as float (in USD)

    Raises:
        Exception if unable to fetch price
    """
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        price = data['chart']['result'][0]['meta']['regularMarketPrice']

        return float(price)

    except Exception as e:
        raise Exception(f"Failed to fetch price for {ticker}: {str(e)}")


def fetch_exchange_rates(currencies: Set[str]) -> Dict[str, float]:
    """
    Fetch exchange rates from USD to specified currencies

    Args:
        currencies: Set of currency codes (e.g., {'USD', 'EUR', 'GBP'})

    Returns:
        Dictionary mapping currency codes to exchange rates from USD

    Raises:
        Exception if unable to fetch exchange rates
    """
    try:
        # Use exchangerate-api.com free API (no key required for basic usage)
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        rates = data['rates']

        # Extract only the rates we need
        exchange_rates = {}
        for currency in currencies:
            currency_upper = currency.upper()
            if currency_upper in rates:
                exchange_rates[currency_upper] = rates[currency_upper]
            else:
                raise Exception(f"Currency '{currency}' not found in exchange rates")

        return exchange_rates

    except Exception as e:
        raise Exception(f"Failed to fetch exchange rates: {str(e)}")


def calculate_portfolio(csv_file: str) -> Dict:
    """
    Read portfolio from CSV and calculate after-tax values

    Args:
        csv_file: Path to CSV file with portfolio data

    Returns:
        Dictionary with portfolio statistics including currencies
    """
    portfolio_items = []
    total_current_value = 0
    total_cost_basis = 0
    total_capital_gains = 0
    total_tax = 0
    currencies = set()

    try:
        with open(csv_file, 'r') as file:
            reader = csv.DictReader(file)

            # Validate headers
            required_columns = ['company name', 'company ticker', 'number of shares',
                              'cost price', 'tax rate', 'currency']
            if not all(col in reader.fieldnames for col in required_columns):
                raise ValueError(f"CSV must contain columns: {', '.join(required_columns)}")

            print("\nFetching stock prices...\n")
            print("-" * 100)

            for row in reader:
                company_name = row['company name'].strip()
                ticker = row['company ticker'].strip().upper()
                num_shares = float(row['number of shares'])
                cost_price = float(row['cost price'])
                tax_rate = float(row['tax rate'])  # Expected as decimal (e.g., 0.20 for 20%)
                currency = row['currency'].strip().upper()

                # Track currencies
                currencies.add(currency)

                # Fetch current price (in USD)
                print(f"Fetching price for {ticker} ({company_name})...")
                current_price = fetch_stock_price(ticker)

                # Calculate values (all in USD)
                cost_basis = num_shares * cost_price
                current_value = num_shares * current_price
                capital_gain = current_value - cost_basis

                # Only tax positive gains
                tax_amount = max(0, capital_gain * tax_rate)
                after_tax_value = current_value - tax_amount

                # Store item details
                item = {
                    'company_name': company_name,
                    'ticker': ticker,
                    'shares': num_shares,
                    'cost_price': cost_price,
                    'current_price': current_price,
                    'cost_basis': cost_basis,
                    'current_value': current_value,
                    'capital_gain': capital_gain,
                    'tax_rate': tax_rate,
                    'tax_amount': tax_amount,
                    'after_tax_value': after_tax_value,
                    'currency': currency
                }
                portfolio_items.append(item)

                # Update totals
                total_cost_basis += cost_basis
                total_current_value += current_value
                total_capital_gains += capital_gain
                total_tax += tax_amount

            print("-" * 100)

    except FileNotFoundError:
        raise Exception(f"File not found: {csv_file}")
    except ValueError as e:
        raise Exception(f"Invalid data in CSV: {str(e)}")
    except KeyError as e:
        raise Exception(f"Missing required column: {str(e)}")

    total_after_tax_value = total_current_value - total_tax

    # Always include INR, USD, and CAD for output
    currencies.update(['INR', 'USD', 'CAD'])

    # Fetch exchange rates for all currencies
    print("\nFetching exchange rates...\n")
    exchange_rates = fetch_exchange_rates(currencies)

    return {
        'items': portfolio_items,
        'total_cost_basis': total_cost_basis,
        'total_current_value': total_current_value,
        'total_capital_gains': total_capital_gains,
        'total_tax': total_tax,
        'total_after_tax_value': total_after_tax_value,
        'currencies': currencies,
        'exchange_rates': exchange_rates
    }


def display_results(portfolio: Dict):
    """
    Display portfolio evaluation results in a formatted table

    Args:
        portfolio: Dictionary containing portfolio data and statistics
    """
    print("\n" + "=" * 100)
    print("PORTFOLIO EVALUATION REPORT")
    print("=" * 100)

    # Individual holdings
    print("\nINDIVIDUAL HOLDINGS:")
    print("-" * 100)
    header = f"{'Company':<20} {'Ticker':<8} {'Shares':<10} {'Cost':<10} {'Current':<10} " \
             f"{'Gain/Loss':<12} {'Tax':<10} {'After-Tax':<12}"
    print(header)
    print("-" * 100)

    for item in portfolio['items']:
        gain_loss_str = f"${item['capital_gain']:,.2f}"
        if item['capital_gain'] > 0:
            gain_loss_str = "+" + gain_loss_str

        print(f"{item['company_name']:<20} {item['ticker']:<8} {item['shares']:<10.2f} "
              f"${item['cost_price']:<9.2f} ${item['current_price']:<9.2f} "
              f"{gain_loss_str:<12} ${item['tax_amount']:<9.2f} ${item['after_tax_value']:<11,.2f}")

    # Summary in USD
    print("-" * 100)
    print("\nPORTFOLIO SUMMARY (USD):")
    print("-" * 100)
    print(f"Total Cost Basis:           ${portfolio['total_cost_basis']:>15,.2f}")
    print(f"Total Current Value:        ${portfolio['total_current_value']:>15,.2f}")
    print(f"Total Capital Gains:        ${portfolio['total_capital_gains']:>15,.2f}")
    print(f"Total Capital Gains Tax:    ${portfolio['total_tax']:>15,.2f}")
    print(f"Total After-Tax Value:      ${portfolio['total_after_tax_value']:>15,.2f}")

    # Performance metrics
    if portfolio['total_cost_basis'] > 0:
        pre_tax_return = (portfolio['total_current_value'] - portfolio['total_cost_basis']) / portfolio['total_cost_basis'] * 100
        after_tax_return = (portfolio['total_after_tax_value'] - portfolio['total_cost_basis']) / portfolio['total_cost_basis'] * 100

        print(f"\nPre-Tax Return:             {pre_tax_return:>15.2f}%")
        print(f"After-Tax Return:           {after_tax_return:>15.2f}%")

    # Currency conversions - Always show INR, USD, and CAD
    print("\n" + "=" * 100)
    print("PORTFOLIO VALUE (INR / USD / CAD)")
    print("=" * 100)
    print("\nAfter-Tax Portfolio Value:")
    print("-" * 100)

    exchange_rates = portfolio['exchange_rates']

    # Always display these three currencies in this order
    required_currencies = ['INR', 'USD', 'CAD']

    for currency in required_currencies:
        rate = exchange_rates[currency]
        converted_value = portfolio['total_after_tax_value'] * rate

        # Get currency symbol
        currency_symbol = get_currency_symbol(currency)
        print(f"{currency:<6} {currency_symbol}{converted_value:>18,.2f}  (Rate: 1 USD = {rate:.4f} {currency})")

    print("=" * 100)


def get_currency_symbol(currency_code: str) -> str:
    """
    Get the currency symbol for a given currency code

    Args:
        currency_code: ISO 4217 currency code (e.g., 'USD', 'EUR')

    Returns:
        Currency symbol as string
    """
    currency_symbols = {
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'CNY': '¥',
        'INR': '₹',
        'AUD': 'A$',
        'CAD': 'C$',
        'CHF': 'Fr',
        'SEK': 'kr',
        'NZD': 'NZ$',
        'KRW': '₩',
        'SGD': 'S$',
        'HKD': 'HK$',
        'NOK': 'kr',
        'MXN': '$',
        'BRL': 'R$',
        'RUB': '₽',
        'ZAR': 'R',
        'TRY': '₺'
    }
    return currency_symbols.get(currency_code, currency_code + ' ')


def main():
    """Main function to run the portfolio evaluator"""
    if len(sys.argv) != 2:
        print("Usage: python portfolio_evaluator.py <portfolio.csv>")
        print("\nCSV file should contain the following columns:")
        print("  - company name")
        print("  - company ticker")
        print("  - number of shares")
        print("  - cost price")
        print("  - tax rate (as decimal, e.g., 0.20 for 20%)")
        print("  - currency (ISO 4217 code, e.g., USD, EUR, GBP, INR)")
        sys.exit(1)

    csv_file = sys.argv[1]

    try:
        portfolio = calculate_portfolio(csv_file)
        display_results(portfolio)
    except Exception as e:
        print(f"\nError: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
