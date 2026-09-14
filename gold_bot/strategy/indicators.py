"""
Calcul des indicateurs techniques : EMA 50/200, MACD (12,26,9), ADX (14)
Utilise pandas-ta si disponible, sinon calcul manuel pur pandas/numpy.
"""
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Helpers manuels ──────────────────────────────────────────────────────────

def _ema_manual(series: pd.Series, span: int) -> pd.Series:
    """EMA via pandas ewm (identique à pandas-ta)."""
    return series.ewm(span=span, adjust=False).mean()


def _macd_manual(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Retourne (macd_line, signal_line, histogram)."""
    ema_fast = _ema_manual(close, fast)
    ema_slow = _ema_manual(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema_manual(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _adx_manual(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calcule ADX, +DI et -DI selon la méthode Wilder.
    Retourne (adx, plus_di, minus_di).
    """
    # True Range
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    # Directional Movement
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm = pd.Series(plus_dm, index=close.index)
    minus_dm = pd.Series(minus_dm, index=close.index)

    # Smoothing Wilder (RMA = EMA avec alpha=1/period)
    def wilder_smooth(s: pd.Series, n: int) -> pd.Series:
        result = s.copy().astype(float)
        # Initialisation à la première somme de `n` valeurs
        first_valid = s.first_valid_index()
        if first_valid is None:
            return result
        idx = s.index.get_loc(first_valid)
        if idx + n > len(s):
            return result
        result.iloc[idx + n - 1] = s.iloc[idx : idx + n].sum()
        for i in range(idx + n, len(s)):
            result.iloc[i] = result.iloc[i - 1] - result.iloc[i - 1] / n + s.iloc[i]
        result.iloc[idx : idx + n - 1] = np.nan
        return result

    atr = wilder_smooth(tr, period)
    plus_dm_s = wilder_smooth(plus_dm, period)
    minus_dm_s = wilder_smooth(minus_dm, period)

    plus_di = 100 * plus_dm_s / atr
    minus_di = 100 * minus_dm_s / atr

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = wilder_smooth(dx, period)

    return adx, plus_di, minus_di


# ─── Interface publique ────────────────────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule EMA 50/200, MACD (12,26,9), ADX (14) sur un DataFrame OHLCV.

    Colonnes attendues en entrée : open, high, low, close, volume (minuscules)
    Colonnes ajoutées : ema50, ema200, macd, macd_signal, macd_hist, adx, plus_di, minus_di

    Returns:
        DataFrame enrichi (copie)
    """
    df = df.copy()

    # Vérification des colonnes
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes OHLCV manquantes dans le DataFrame : {missing}")

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # Tentative pandas-ta
    pandas_ta_ok = False
    try:
        import pandas_ta as ta  # type: ignore

        # EMA
        df["ema50"] = ta.ema(close, length=50)
        df["ema200"] = ta.ema(close, length=200)

        # MACD
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            df["macd"] = macd_df.iloc[:, 0]        # MACD_12_26_9
            df["macd_signal"] = macd_df.iloc[:, 2]  # MACDs_12_26_9
            df["macd_hist"] = macd_df.iloc[:, 1]    # MACDh_12_26_9
        else:
            raise ValueError("pandas_ta MACD returned empty")

        # ADX
        adx_df = ta.adx(high, low, close, length=14)
        if adx_df is not None and not adx_df.empty:
            df["adx"] = adx_df.iloc[:, 0]       # ADX_14
            df["plus_di"] = adx_df.iloc[:, 1]   # DMP_14
            df["minus_di"] = adx_df.iloc[:, 2]  # DMN_14
        else:
            raise ValueError("pandas_ta ADX returned empty")

        pandas_ta_ok = True
        logger.debug("Indicateurs calculés avec pandas-ta")

    except Exception as e:
        logger.info(f"pandas-ta non disponible ou erreur ({e}) — calcul manuel")

    if not pandas_ta_ok:
        # Calcul manuel
        df["ema50"] = _ema_manual(close, 50)
        df["ema200"] = _ema_manual(close, 200)

        macd_line, macd_sig, macd_hist = _macd_manual(close, 12, 26, 9)
        df["macd"] = macd_line
        df["macd_signal"] = macd_sig
        df["macd_hist"] = macd_hist

        adx, plus_di, minus_di = _adx_manual(high, low, close, 14)
        df["adx"] = adx
        df["plus_di"] = plus_di
        df["minus_di"] = minus_di

        logger.debug("Indicateurs calculés manuellement (numpy/pandas)")

    return df
