#!/usr/bin/env python3
"""Test rapide du système"""
import sys
sys.path.insert(0, '/Applications/Cours/Python/AlerteTrade')

print("🧪 Test rapide du système AlerteTrade\n")

# Test 1: Imports
print("1. Test des imports...")
try:
    from src.config_loader import ConfigLoader
    from src.data_fetcher import DataFetcher
    from src.bollinger_bands import BollingerBands
    from src.alert_manager import AlertManager
    from src.notifiers import TelegramNotifier
    print("   ✅ Tous les modules importés avec succès\n")
except Exception as e:
    print(f"   ❌ Erreur d'import: {e}\n")
    sys.exit(1)

# Test 2: Configuration
print("2. Test de la configuration...")
try:
    config_loader = ConfigLoader()
    config = config_loader.load()
    print(f"   ✅ Configuration chargée")
    print(f"   - Symbole: {config['trading']['symbol']}")
    print(f"   - Intervalle: {config['trading']['interval']}")
    print(f"   - Telegram activé: {'telegram' in config['alerts']['methods']}\n")
except Exception as e:
    print(f"   ❌ Erreur de config: {e}\n")
    sys.exit(1)

# Test 3: Telegram
print("3. Test de Telegram...")
try:
    telegram_config = config.get('telegram', {})
    if telegram_config.get('bot_token') and telegram_config.get('chat_id'):
        notifier = TelegramNotifier(
            telegram_config['bot_token'],
            telegram_config['chat_id']
        )

        test_alert = {
            'timestamp': '2024-01-01T12:00:00',
            'message': '🧪 MESSAGE DE TEST',
            'type': 'upper',
            'price': 43500.0,
            'band_value': 43600.0,
            'distance_pct': 0.08
        }

        notifier.send(test_alert)
        print("   ✅ Message de test envoyé sur Telegram!\n")
    else:
        print("   ⚠️  Telegram non configuré\n")
except Exception as e:
    print(f"   ❌ Erreur Telegram: {e}\n")

# Test 4: Binance connection
print("4. Test de connexion Binance...")
try:
    fetcher = DataFetcher()
    price = fetcher.get_current_price('BTCUSDT')
    print(f"   ✅ Prix BTC actuel: ${price:,.2f}\n")
except Exception as e:
    print(f"   ❌ Erreur Binance: {e}\n")

# Test 5: Bollinger Bands
print("5. Test calcul Bollinger Bands...")
try:
    prices = fetcher.get_latest_close_prices('BTCUSDT', '1h', limit=50)
    bb = BollingerBands(20, 2.0)
    upper, basis, lower = bb.calculate(prices)

    print(f"   ✅ Bandes calculées:")
    print(f"   - Haute: ${upper.iloc[-1]:,.2f}")
    print(f"   - Moyenne: ${basis.iloc[-1]:,.2f}")
    print(f"   - Basse: ${lower.iloc[-1]:,.2f}\n")

    # Proximité
    proximity = bb.check_proximity(price, upper.iloc[-1], lower.iloc[-1], 0.1)
    print(f"   Distance bande haute: {proximity['distance_upper_pct']}%")
    print(f"   Distance bande basse: {proximity['distance_lower_pct']}%")

    if proximity['near_upper']:
        print("   🚨 PROCHE DE LA BANDE HAUTE!")
    if proximity['near_lower']:
        print("   🚨 PROCHE DE LA BANDE BASSE!")

    print()

except Exception as e:
    print(f"   ❌ Erreur BB: {e}\n")

print("=" * 60)
print("✅ Tests terminés ! Le système est prêt.")
print("=" * 60)
print("\nPour lancer le système complet:")
print("  python main.py")
