"""
Module pour les différents types de notifications
"""
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
from datetime import datetime


class ConsoleNotifier:
    """Affiche les alertes dans la console"""

    def send(self, alert: Dict):
        """Affiche l'alerte"""
        print("\n" + "=" * 60)
        print(f"{alert['message']}")
        print(f"Timestamp: {alert['timestamp']}")
        print(f"Prix actuel: {alert['price']}")
        print(f"Bande {alert['type']}: {alert['band_value']}")
        print(f"Distance: {alert['distance_pct']}%")
        print("=" * 60 + "\n")


class TelegramNotifier:
    """Envoie des alertes via Telegram"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send(self, alert: Dict):
        """Envoie l'alerte via Telegram"""
        message = f"""
{alert['message']}

📊 Prix: {alert['price']}
📈 Bande {alert['type']}: {alert['band_value']}
📏 Distance: {alert['distance_pct']}%
🕐 {datetime.fromisoformat(alert['timestamp']).strftime('%H:%M:%S')}
        """

        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }

        try:
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
        except Exception as e:
            print(f"Erreur lors de l'envoi Telegram: {e}")


class EmailNotifier:
    """Envoie des alertes par email"""

    def __init__(self, smtp_server: str, smtp_port: int, sender_email: str,
                 sender_password: str, receiver_email: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.receiver_email = receiver_email

    def send(self, alert: Dict):
        """Envoie l'alerte par email"""
        message = MIMEMultipart()
        message['From'] = self.sender_email
        message['To'] = self.receiver_email
        message['Subject'] = f"Trading Alert - Bande {alert['type'].upper()}"

        body = f"""
        Alerte de Trading - Bandes de Bollinger

        {alert['message']}

        Prix actuel: {alert['price']}
        Bande {alert['type']}: {alert['band_value']}
        Distance: {alert['distance_pct']}%

        Heure: {alert['timestamp']}
        """

        message.attach(MIMEText(body, 'plain'))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
        except Exception as e:
            print(f"Erreur lors de l'envoi email: {e}")


class NotificationManager:
    """Gère tous les types de notifications"""

    def __init__(self):
        self.notifiers = []

    def add_notifier(self, notifier):
        """Ajoute un type de notification"""
        self.notifiers.append(notifier)

    def send_alert(self, alert: Dict):
        """Envoie l'alerte à tous les notifiers configurés"""
        for notifier in self.notifiers:
            try:
                notifier.send(alert)
            except Exception as e:
                print(f"Erreur avec notifier {type(notifier).__name__}: {e}")
