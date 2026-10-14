# Save this file as ice_fetcher.py
import requests
import pandas as pd

class ICERedditClient:
    def __init__(self, api_key):
        # This saves your private ICE API key for authentication
        self.api_key = api_key
        self.base_url = "https://theice.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_sentiment(self, asset_ticker):
        """Fetches the latest Reddit sentiment for a specific ticker symbol"""
        params = {"ticker": asset_ticker}

        # Send a request over the internet to ICE
        response = requests.get(self.base_url, headers=self.headers, params=params)

        # Check if the connection worked (Status Code 200 means success)
        if response.status_code == 200:
            data = response.json().get("signals", [])
            # Turn the raw data into a neat table
            return pd.DataFrame(data)
        else:
            print(f"Error: Could not fetch data. Server said: {response.text}")
            return None
