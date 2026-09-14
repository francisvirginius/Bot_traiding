"""
Analyse de la structure de marché :
  - Swing Highs / Swing Lows (N bougies de chaque côté)
  - Zones Supply / Demand (regroupement par proximité 0.3%)
  - BOS (Break of Structure) — confirmation de tendance
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SWING_N = 5                 # Nombre de bougies de chaque côté pour valider un swing
ZONE_TOLERANCE_PCT = 0.003  # 0.3% de tolérance pour regrouper les zones
BOS_LOOKBACK = 10           # Nombre de swings à regarder pour détecter un BOS


def detect_swing_highs(df: pd.DataFrame, n: int = SWING_N) -> list:
    """
    Détecte les swing highs : le high de la bougie i est le plus haut
    parmi les N bougies précédentes ET N bougies suivantes.

    Retourne une liste de dicts : {index, price, bar_index}
    """
    highs = df["high"].values
    result = []
    for i in range(n, len(highs) - n):
        window = highs[i - n : i + n + 1]
        if highs[i] == np.max(window):
            result.append({
                "bar_index": i,
                "price": float(highs[i]),
                "timestamp": df.index[i] if hasattr(df.index, "name") else i,
            })
    return result


def detect_swing_lows(df: pd.DataFrame, n: int = SWING_N) -> list:
    """
    Détecte les swing lows : le low de la bougie i est le plus bas
    parmi les N bougies précédentes ET N bougies suivantes.

    Retourne une liste de dicts : {index, price, bar_index}
    """
    lows = df["low"].values
    result = []
    for i in range(n, len(lows) - n):
        window = lows[i - n : i + n + 1]
        if lows[i] == np.min(window):
            result.append({
                "bar_index": i,
                "price": float(lows[i]),
                "timestamp": df.index[i] if hasattr(df.index, "name") else i,
            })
    return result


def _group_zones(swings: list, tolerance_pct: float = ZONE_TOLERANCE_PCT) -> list:
    """
    Regroupe des swings proches les uns des autres (tolérance en %) en zones.
    Chaque zone est représentée par son prix moyen + bornes.

    Retourne une liste de dicts : {price_center, price_low, price_high, count}
    """
    if not swings:
        return []

    prices = sorted([s["price"] for s in swings])
    zones = []
    current_group = [prices[0]]

    for price in prices[1:]:
        ref = current_group[-1]
        if abs(price - ref) / ref <= tolerance_pct:
            current_group.append(price)
        else:
            center = float(np.mean(current_group))
            zones.append({
                "price_center": center,
                "price_low": float(min(current_group)),
                "price_high": float(max(current_group)),
                "count": len(current_group),
            })
            current_group = [price]

    # Dernier groupe
    center = float(np.mean(current_group))
    zones.append({
        "price_center": center,
        "price_low": float(min(current_group)),
        "price_high": float(max(current_group)),
        "count": len(current_group),
    })

    return zones


def detect_bos(
    df: pd.DataFrame,
    swing_highs: list,
    swing_lows: list,
    lookback: int = BOS_LOOKBACK,
) -> Optional[str]:
    """
    Détecte le dernier Break of Structure (BOS).
      - BULLISH BOS : le close actuel dépasse le dernier swing high significatif
      - BEARISH BOS : le close actuel casse sous le dernier swing low significatif

    Retourne : 'BULLISH' | 'BEARISH' | None
    """
    if df.empty:
        return None

    current_close = float(df["close"].iloc[-1])

    # Prendre les N derniers swings avant la dernière bougie
    recent_highs = sorted(
        [sh for sh in swing_highs if sh["bar_index"] < len(df) - 1],
        key=lambda x: x["bar_index"],
    )[-lookback:]

    recent_lows = sorted(
        [sl for sl in swing_lows if sl["bar_index"] < len(df) - 1],
        key=lambda x: x["bar_index"],
    )[-lookback:]

    last_bos = None

    # BOS Bullish : close > dernier swing high récent
    if recent_highs:
        last_high_price = recent_highs[-1]["price"]
        # On cherche si la bougie actuelle a cassé le swing high
        if current_close > last_high_price:
            last_bos = "BULLISH"
            logger.debug(f"BOS BULLISH détecté : close {current_close:.2f} > swing high {last_high_price:.2f}")

    # BOS Bearish : close < dernier swing low récent (prioritaire sur bullish)
    if recent_lows:
        last_low_price = recent_lows[-1]["price"]
        if current_close < last_low_price:
            last_bos = "BEARISH"
            logger.debug(f"BOS BEARISH détecté : close {current_close:.2f} < swing low {last_low_price:.2f}")

    # Si les deux conditions sont remplies, le plus récent gagne
    if recent_highs and recent_lows:
        last_high = recent_highs[-1]
        last_low = recent_lows[-1]
        if current_close > last_high["price"] and current_close < last_low["price"]:
            # Impossible simultanément sauf données incohérentes
            last_bos = None
        elif (
            current_close > last_high["price"]
            and last_high["bar_index"] > (last_low["bar_index"] if recent_lows else -1)
        ):
            last_bos = "BULLISH"
        elif (
            current_close < last_low["price"]
            and (not recent_highs or last_low["bar_index"] > last_high["bar_index"])
        ):
            last_bos = "BEARISH"

    return last_bos


def analyze_structure(df: pd.DataFrame, swing_n: int = SWING_N) -> dict:
    """
    Analyse complète de la structure de marché.

    Args:
        df: DataFrame OHLCV (doit contenir high, low, close)
        swing_n: Nombre de bougies de chaque côté pour les swings

    Returns:
        dict avec clés :
            swing_highs: list
            swing_lows: list
            supply_zones: list
            demand_zones: list
            last_bos: 'BULLISH' | 'BEARISH' | None
    """
    if len(df) < 2 * swing_n + 1:
        logger.warning(
            f"DataFrame trop court ({len(df)} bougies) pour détecter les swings (min={2*swing_n+1})"
        )
        return {
            "swing_highs": [],
            "swing_lows": [],
            "supply_zones": [],
            "demand_zones": [],
            "last_bos": None,
        }

    swing_highs = detect_swing_highs(df, swing_n)
    swing_lows = detect_swing_lows(df, swing_n)
    supply_zones = _group_zones(swing_highs)
    demand_zones = _group_zones(swing_lows)
    last_bos = detect_bos(df, swing_highs, swing_lows)

    logger.info(
        f"Structure : {len(swing_highs)} swing highs, {len(swing_lows)} swing lows | "
        f"{len(supply_zones)} zones supply, {len(demand_zones)} zones demand | "
        f"BOS={last_bos}"
    )

    return {
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "supply_zones": supply_zones,
        "demand_zones": demand_zones,
        "last_bos": last_bos,
    }
