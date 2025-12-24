"""
Module pour récupérer les données depuis Twelve Data API (Forex/Gold)
"""
import pandas as pd
from twelvedata import TDClient
from typing import Optional
from datetime import datetime


class TwelveDataFetcher:
    """Récupère les données Forex/Gold depuis Twelve Data"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le client Twelve Data

        Args:
            api_key: Clé API Twelve Data (requis - gratuit sur twelvedata.com)
        """
        if not api_key or api_key == "":
            # Utiliser une clé démo pour les tests
            api_key = "demo"
        self.client = TDClient(apikey=api_key)

    def get_historical_data(self, symbol: str, interval: str, outputsize: int = 100) -> pd.DataFrame:
        """
        Récupère les données historiques

        Args:
            symbol: Symbole (ex: XAU/USD, EUR/USD, BTC/USD)
            interval: Intervalle (1min, 5min, 15min, 30min, 1h, 4h, 1day)
            outputsize: Nombre de chandeliers à récupérer

        Returns:
            DataFrame avec les données OHLCV
        """
        # Convertir le format Binance vers Twelve Data
        interval_map = {
            '1m': '1min',
            '5m': '5min',
            '15m': '15min',
            '30m': '30min',
            '1h': '1h',
            '4h': '4h',
            '1d': '1day'
        }

        td_interval = interval_map.get(interval, interval)

        # Récupération des données
        ts = self.client.time_series(
            symbol=symbol,
            interval=td_interval,
            outputsize=outputsize
        )

        df = ts.as_pandas()

        # Renommer les colonnes pour correspondre au format attendu
        df = df.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        })

        # Inverser l'ordre (du plus ancien au plus récent)
        df = df.iloc[::-1].reset_index()
        df = df.rename(columns={'datetime': 'timestamp'})

        # S'assurer que les colonnes sont en float
        df['close'] = df['close'].astype(float)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)

        return df

    def get_current_price(self, symbol: str) -> float:
        """
        Récupère le prix actuel

        Args:
            symbol: Symbole (ex: XAU/USD)

        Returns:
            Prix actuel
        """
        quote = self.client.quote(symbol=symbol)
        data = quote.as_json()
        return float(data['close'])

    def get_latest_close_prices(self, symbol: str, interval: str, outputsize: int = 100) -> pd.Series:
        """
        Récupère uniquement les prix de clôture

        Args:
            symbol: Symbole
            interval: Intervalle
            outputsize: Nombre de prix à récupérer

        Returns:
            Série de prix de clôture
        """
        df = self.get_historical_data(symbol, interval, outputsize)
        return df['close']
