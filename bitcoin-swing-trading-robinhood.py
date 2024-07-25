import base64
import datetime
import json
from typing import Any, Dict, Optional
import uuid
import requests
from cryptography.hazmat.primitives.asymmetric import ed25519
import time
from flask import Flask, render_template_string, jsonify

API_KEY = "YOUR-API-KEY"
BASE64_PRIVATE_KEY = "YOUR-PRIVATE-KEY"

app = Flask(__name__)

class CryptoAPITrading:
    def __init__(self):
        self.api_key = API_KEY
        private_bytes = base64.b64decode(BASE64_PRIVATE_KEY)
        # Note that the cryptography library used here only accepts a 32 byte ed25519 private key
        self.private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes[:32])
        self.base_url = "https://trading.robinhood.com"

    @staticmethod
    def _get_current_timestamp() -> int:
        return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())

    @staticmethod
    def get_query_params(key: str, *args: Optional[str]) -> str:
        if not args:
            return ""

        params = []
        for arg in args:
            params.append(f"{key}={arg}")

        return "?" + "&".join(params)

    def make_api_request(self, method: str, path: str, body: str = "") -> Any:
        timestamp = self._get_current_timestamp()
        headers = self.get_authorization_header(method, path, body, timestamp)
        url = self.base_url + path

        try:
            response = {}
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=json.loads(body), timeout=10)
            return response.json()
        except requests.RequestException as e:
            print(f"Error making API request: {e}")
            return None

    def get_authorization_header(
            self, method: str, path: str, body: str, timestamp: int
    ) -> Dict[str, str]:
        message_to_sign = f"{self.api_key}{timestamp}{path}{method}{body}"
        signature = self.private_key.sign(message_to_sign.encode("utf-8"))

        return {
            "x-api-key": self.api_key,
            "x-signature": base64.b64encode(signature).decode("utf-8"),
            "x-timestamp": str(timestamp),
        }

    def get_account(self) -> Any:
        path = "/api/v1/crypto/trading/accounts/"
        return self.make_api_request("GET", path)

    def get_trading_pairs(self, *symbols: Optional[str]) -> Any:
        query_params = self.get_query_params("symbol", *symbols)
        path = f"/api/v1/crypto/trading/trading_pairs/{query_params}"
        return self.make_api_request("GET", path)

    def get_holdings(self, *asset_codes: Optional[str]) -> Any:
        query_params = self.get_query_params("asset_code", *asset_codes)
        path = f"/api/v1/crypto/trading/holdings/{query_params}"
        return self.make_api_request("GET", path)

    def get_best_bid_ask(self, *symbols: Optional[str]) -> Any:
        query_params = self.get_query_params("symbol", *symbols)
        path = f"/api/v1/crypto/marketdata/best_bid_ask/{query_params}"
        return self.make_api_request("GET", path)

    def get_estimated_price(self, symbol: str, side: str, quantity: str) -> Any:
        path = f"/api/v1/crypto/marketdata/estimated_price/?symbol={symbol}&side={side}&quantity={quantity}"
        return self.make_api_request("GET", path)

    def place_order(
            self,
            client_order_id: str,
            side: str,
            order_type: str,
            symbol: str,
            order_config: Dict[str, str],
    ) -> Any:
        body = {
            "client_order_id": client_order_id,
            "side": side,
            "type": order_type,
            "symbol": symbol,
            f"{order_type}_order_config": order_config,
        }
        path = "/api/v1/crypto/trading/orders/"
        return self.make_api_request("POST", path, json.dumps(body))

    def cancel_order(self, order_id: str) -> Any:
        path = f"/api/v1/crypto/trading/orders/{order_id}/cancel/"
        return self.make_api_request("POST", path)

    def get_order(self, order_id: str) -> Any:
        path = f"/api/v1/crypto/trading/orders/{order_id}/"
        return self.make_api_request("GET", path)

    def get_orders(self) -> Any:
        path = "/api/v1/crypto/trading/orders/"
        return self.make_api_request("GET", path)

BUYING_POWER = 0
PRICE_DIP = 5
AMOUNT_TO_BUY = 0.001
PRICE_INCREASE_OFFSET = 7.5  # Increased to account for spreads and ensure profit
SLEEP_INTERVAL = 3.6  # 1000 requests per hour = 1 request every 3.6 seconds
NO_TRADE_RESET_INTERVAL = 30 * 60  # 30 minutes in seconds

# Shared state for the web UI
current_status = {
    "buying_power": 0.0,
    "current_price": 0.0,
    "ask_price": 0.0,
    "bid_price": 0.0,
    "baseline_price": 0.0,
    "last_action": "",
    "message": ""
}

def get_current_price(api_trading_client: CryptoAPITrading, symbol: str = "BTC-USD") -> Dict[str, float]:
    response = api_trading_client.get_best_bid_ask(symbol)
    if response and 'results' in response and len(response['results']) > 0:
        result = response['results'][0]
        return {
            'price': float(result['price']),
            'ask_inclusive_of_buy_spread': float(result['ask_inclusive_of_buy_spread']),
            'bid_inclusive_of_sell_spread': float(result['bid_inclusive_of_sell_spread'])
        }
    else:
        current_status["message"] = "Error: 'price' not found in response"
        return {'price': 0.0, 'ask_inclusive_of_buy_spread': 0.0, 'bid_inclusive_of_sell_spread': 0.0}

def update_buying_power(api_trading_client: CryptoAPITrading):
    global BUYING_POWER
    account_info = api_trading_client.get_account()
    if account_info and 'buying_power' in account_info:
        BUYING_POWER = float(account_info['buying_power'])
        current_status["buying_power"] = BUYING_POWER
    else:
        current_status["message"] = "Error: 'buying_power' not found in account info"

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Crypto Trading Bot</title>
    </head>
    <body>
        <h1>Bitcoin swing trading bot status</h1>
        <p>Buying Power: ${{ status.buying_power }}</p>
        <p>Current BTC Price: ${{ status.current_price }}</p>
        <p>Ask Price: ${{ status.ask_price }}</p>
        <p>Bid Price: ${{ status.bid_price }}</p>
        <p>Baseline Price: ${{ status.baseline_price }}</p>
        <p>Last Action: {{ status.last_action }}</p>
        <p>Message: {{ status.message }}</p>
        <script>
            setInterval(() => {
                fetch('/status')
                    .then(response => response.json())
                    .then(data => {
                        document.querySelector('p:nth-of-type(1)').textContent = `Buying Power: $${data.buying_power}`;
                        document.querySelector('p:nth-of-type(2)').textContent = `Current BTC Price: $${data.current_price}`;
                        document.querySelector('p:nth-of-type(3)').textContent = `Ask Price: $${data.ask_price}`;
                        document.querySelector('p:nth-of-type(4)').textContent = `Bid Price: $${data.bid_price}`;
                        document.querySelector('p:nth-of-type(5)').textContent = `Baseline Price: $${data.baseline_price}`;
                        document.querySelector('p:nth-of-type(6)').textContent = `Last Action: ${data.last_action}`;
                        document.querySelector('p:nth-of-type(7)').textContent = `Message: ${data.message}`;
                    });
            }, 5000);
        </script>
    </body>
    </html>
    """, status=current_status)

@app.route('/status')
def status():
    return jsonify(current_status)

def main():
    api_trading_client = CryptoAPITrading()
    
    # Get and update buying power
    update_buying_power(api_trading_client)
    initial_buying_power = BUYING_POWER
    current_status["buying_power"] = initial_buying_power
    current_status["message"] = f"Initial buying power: ${initial_buying_power}"
    
    # Get the current BTC price and set it as the baseline price
    current_prices = get_current_price(api_trading_client)
    baseline_price = current_prices['price']
    current_status["baseline_price"] = baseline_price
    
    last_trade_time = time.time()
    
    while True:
        update_buying_power(api_trading_client)
        current_prices = get_current_price(api_trading_client)
        current_price = current_prices['price']
        ask_price = current_prices['ask_inclusive_of_buy_spread']
        bid_price = current_prices['bid_inclusive_of_sell_spread']
        current_status["current_price"] = current_price
        current_status["ask_price"] = ask_price
        current_status["bid_price"] = bid_price
        
        current_time = time.time()
        
        # Reset baseline price if no trades have occurred in the specified interval
        if current_time - last_trade_time >= NO_TRADE_RESET_INTERVAL:
            baseline_price = current_price
            current_status["baseline_price"] = baseline_price
            current_status["message"] = f"Baseline price reset to current price: {baseline_price}"
            last_trade_time = current_time
        
        # Check for price dip
        if ask_price <= baseline_price - PRICE_DIP:
            current_status["last_action"] = f"Buy: ask_price ({ask_price}) <= baseline_price ({baseline_price}) - PRICE_DIP ({PRICE_DIP})"
            order = api_trading_client.place_order(
                str(uuid.uuid4()),
                "buy",
                "market",
                "BTC-USD",
                {"asset_quantity": str(AMOUNT_TO_BUY)}
            )
            current_status["message"] = f"Buy order placed: {order}"
            
            # Update the baseline price to the order filled price
            filled_price = ask_price # Assuming immediate fill for simplicity
            baseline_price = filled_price
            current_status["baseline_price"] = baseline_price
            last_trade_time = time.time()
            
            # Wait for price increase
            while bid_price < baseline_price + PRICE_INCREASE_OFFSET:
                update_buying_power(api_trading_client)
                current_prices = get_current_price(api_trading_client)
                current_price = current_prices['price']
                bid_price = current_prices['bid_inclusive_of_sell_spread']
                current_status["current_price"] = current_price
                current_status["bid_price"] = bid_price
                current_status["last_action"] = f"Sell: bid_price ({bid_price}) < baseline_price ({baseline_price}) + PRICE_INCREASE_OFFSET ({PRICE_INCREASE_OFFSET})"
                time.sleep(SLEEP_INTERVAL)  # Sleep to avoid hammering the API

            # Place sell order
            sell_order = api_trading_client.place_order(
                str(uuid.uuid4()),
                "sell",
                "market",
                "BTC-USD",
                {"asset_quantity": str(AMOUNT_TO_BUY)}
            )
            current_status["message"] = f"Sell order placed: {sell_order}"
            
            # Update baseline price again
            baseline_price = bid_price # Assuming immediate fill for simplicity
            current_status["baseline_price"] = baseline_price
            last_trade_time = time.time()
        
        time.sleep(SLEEP_INTERVAL)  # Sleep to avoid hammering the API

if __name__ == "__main__":
    import threading
    threading.Thread(target=main).start()
    app.run(host='0.0.0.0', port=5000, debug=True)
