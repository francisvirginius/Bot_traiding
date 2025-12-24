#!/usr/bin/env python3
"""
Script principal pour surveiller les Bandes de Bollinger et envoyer des alertes
"""
import time
import sys
from datetime import datetime
from src.config_loader import ConfigLoader
from src.data_fetcher import DataFetcher
from src.twelve_data_fetcher import TwelveDataFetcher
from src.bollinger_bands import BollingerBands
from src.alert_manager import AlertManager
from src.notifiers import (
    NotificationManager,
    ConsoleNotifier,
    TelegramNotifier,
    EmailNotifier
)


def setup_notifiers(config: dict) -> NotificationManager:
    """Configure les notifiers selon la configuration"""
    notification_manager = NotificationManager()

    if not config['alerts']['enabled']:
        return notification_manager

    methods = config['alerts']['methods']

    # Console
    if 'console' in methods:
        notification_manager.add_notifier(ConsoleNotifier())

    # Telegram
    if 'telegram' in methods:
        telegram_config = config.get('telegram', {})
        if telegram_config.get('bot_token') and telegram_config.get('chat_id'):
            notification_manager.add_notifier(
                TelegramNotifier(
                    telegram_config['bot_token'],
                    telegram_config['chat_id']
                )
            )
        else:
            print("⚠️ Telegram activé mais non configuré")

    # Email
    if 'email' in methods:
        email_config = config.get('email', {})
        if all([
            email_config.get('smtp_server'),
            email_config.get('sender_email'),
            email_config.get('sender_password'),
            email_config.get('receiver_email')
        ]):
            notification_manager.add_notifier(
                EmailNotifier(
                    email_config['smtp_server'],
                    email_config['smtp_port'],
                    email_config['sender_email'],
                    email_config['sender_password'],
                    email_config['receiver_email']
                )
            )
        else:
            print("⚠️ Email activé mais non configuré")

    return notification_manager


def main():
    """Fonction principale"""
    print("🚀 Démarrage du système d'alerte Bollinger Bands")
    print("=" * 60)

    # Chargement de la configuration
    try:
        config_loader = ConfigLoader()
        config = config_loader.load()
        print("✅ Configuration chargée")
    except Exception as e:
        print(f"❌ Erreur lors du chargement de la configuration: {e}")
        sys.exit(1)

    # Paramètres
    bb_config = config['bollinger_bands']
    trading_config = config['trading']
    symbol = trading_config['symbol']
    interval = trading_config['interval']
    check_interval = trading_config['check_interval']
    data_source = trading_config.get('data_source', 'binance')

    print(f"📊 Symbole: {symbol}")
    print(f"📡 Source: {data_source.upper()}")
    print(f"⏱️  Intervalle: {interval}")
    print(f"🔄 Vérification toutes les {check_interval}s")
    print(f"📏 Proximité: {bb_config['proximity_percent']}%")
    print("=" * 60 + "\n")

    # Initialisation des composants selon la source de données
    if data_source.lower() == 'twelvedata':
        api_key = config.get('twelvedata', {}).get('api_key')
        data_fetcher = TwelveDataFetcher(api_key if api_key else None)
        print("✅ Utilisation de Twelve Data API")
    else:
        data_fetcher = DataFetcher(
            config['binance']['api_key'],
            config['binance']['api_secret']
        )
        print("✅ Utilisation de Binance API")

    bb = BollingerBands(bb_config['period'], bb_config['multiplier'])
    alert_manager = AlertManager()
    notification_manager = setup_notifiers(config)

    print("✅ Système initialisé et en fonctionnement\n")

    # Boucle principale
    try:
        while True:
            try:
                # Récupération des données
                outputsize = bb_config['period'] + 50
                if data_source.lower() == 'twelvedata':
                    prices = data_fetcher.get_latest_close_prices(
                        symbol,
                        interval,
                        outputsize=outputsize
                    )
                else:
                    prices = data_fetcher.get_latest_close_prices(
                        symbol,
                        interval,
                        limit=outputsize
                    )

                # Calcul des bandes
                upper, basis, lower = bb.calculate(prices)

                # Prix actuel
                current_price = data_fetcher.get_current_price(symbol)

                # Vérification de la proximité
                proximity_data = bb.check_proximity(
                    current_price,
                    upper.iloc[-1],
                    lower.iloc[-1],
                    bb_config['proximity_percent']
                )

                # Affichage des infos
                now = datetime.now().strftime("%H:%M:%S")
                print(f"[{now}] Prix: {current_price} | "
                      f"Haute: {proximity_data['upper_band']} ({proximity_data['distance_upper_pct']}%) | "
                      f"Basse: {proximity_data['lower_band']} ({proximity_data['distance_lower_pct']}%)")

                # Vérification et envoi des alertes
                alerts = alert_manager.check_and_alert(proximity_data)

                for alert in alerts:
                    notification_manager.send_alert(alert)

                # Attente avant la prochaine vérification
                time.sleep(check_interval)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"❌ Erreur: {e}")
                time.sleep(check_interval)

    except KeyboardInterrupt:
        print("\n\n🛑 Arrêt du système")
        print(f"📊 Nombre total d'alertes: {len(alert_manager.alert_history)}")

        # Sauvegarde de l'historique
        try:
            alert_manager.save_history('alert_history.json')
            print("💾 Historique sauvegardé dans alert_history.json")
        except Exception as e:
            print(f"⚠️ Erreur lors de la sauvegarde: {e}")


if __name__ == "__main__":
    main()
