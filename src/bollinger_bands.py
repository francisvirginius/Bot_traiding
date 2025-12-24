"""
Module de calcul des Bandes de Bollinger
"""
import pandas as pd
import numpy as np
from typing import Tuple


class BollingerBands:
    """Calcule les Bandes de Bollinger et détecte les proximités"""

    def __init__(self, period: int = 20, multiplier: float = 2.0):
        """
        Initialise les paramètres des Bandes de Bollinger

        Args:
            period: Période pour la moyenne mobile
            multiplier: Multiplicateur pour l'écart-type
        """
        self.period = period
        self.multiplier = multiplier

    def calculate(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calcule les Bandes de Bollinger

        Args:
            prices: Série de prix de clôture

        Returns:
            Tuple (upper_band, basis, lower_band)
        """
        # Moyenne mobile (basis)
        basis = prices.rolling(window=self.period).mean()

        # Écart-type
        std = prices.rolling(window=self.period).std()

        # Bandes supérieure et inférieure
        upper_band = basis + (self.multiplier * std)
        lower_band = basis - (self.multiplier * std)

        return upper_band, basis, lower_band

    def calculate_distance(self, current_price: float, upper_band: float,
                          lower_band: float) -> Tuple[float, float]:
        """
        Calcule la distance en % du prix actuel aux bandes

        Args:
            current_price: Prix actuel
            upper_band: Bande supérieure
            lower_band: Bande inférieure

        Returns:
            Tuple (distance_upper_pct, distance_lower_pct)
        """
        # Distance à la bande haute en %
        distance_upper = abs(upper_band - current_price) / upper_band * 100

        # Distance à la bande basse en %
        distance_lower = abs(current_price - lower_band) / lower_band * 100

        return distance_upper, distance_lower

    def check_proximity(self, current_price: float, upper_band: float,
                       lower_band: float, proximity_threshold: float) -> dict:
        """
        Vérifie si le prix est proche d'une bande

        Args:
            current_price: Prix actuel
            upper_band: Bande supérieure
            lower_band: Bande inférieure
            proximity_threshold: Seuil de proximité en %

        Returns:
            Dict avec les informations de proximité
        """
        dist_upper, dist_lower = self.calculate_distance(
            current_price, upper_band, lower_band
        )

        return {
            'near_upper': dist_upper <= proximity_threshold,
            'near_lower': dist_lower <= proximity_threshold,
            'distance_upper_pct': round(dist_upper, 3),
            'distance_lower_pct': round(dist_lower, 3),
            'current_price': current_price,
            'upper_band': round(upper_band, 2),
            'lower_band': round(lower_band, 2)
        }
