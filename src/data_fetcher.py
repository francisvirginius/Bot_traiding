"""
Module pour récupérer les données de prix depuis Binance
"""
import pandas as pd
from binance.client import Client
from typing import Optional
from datetime import datetime


class DataFetcher:
    """Récupère les données de prix depuis Binance"""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialise le client Binance

        Args:
            api_key: Clé API Binance (optionnel pour données publiques)
            api_secret: Secret API Binance (optionnel pour données publiques)
        """
        self.client = Client(api_key, api_secret)

    def get_historical_klines(self, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
        """
        Récupère les chandeliers historiques

        Args:
            symbol: Symbole de trading (ex: BTCUSDT)
            interval: Intervalle de temps (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Nombre de chandeliers à récupérer

        Returns:
            DataFrame avec les données OHLCV
        """
        klines = self.client.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit
        )

        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        # Conversion des types
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['close'] = df['close'].astype(float)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['volume'] = df['volume'].astype(float)

        return df

    def get_current_price(self, symbol: str) -> float:
        """
        Récupère le prix actuel

        Args:
            symbol: Symbole de trading

        Returns:
            Prix actuel
        """
        ticker = self.client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])

    def get_latest_close_prices(self, symbol: str, interval: str, limit: int = 100) -> pd.Series:
        """
        Récupère uniquement les prix de clôture

        Args:
            symbol: Symbole de trading
            interval: Intervalle de temps
            limit: Nombre de prix à récupérer

        Returns:
            Série de prix de clôture
        """
        df = self.get_historical_klines(symbol, interval, limit)
        return df['close']
