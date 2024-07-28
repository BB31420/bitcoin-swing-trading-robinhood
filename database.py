import sqlite3
from typing import Any, Dict

class Database:
    def __init__(self, db_name: str = 'trading_logs.db'):
        self.db_conn = sqlite3.connect(db_name)
        self.db_cursor = self.db_conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.db_cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT,
            trade_type TEXT,
            amount REAL,
            price REAL
        )
        ''')
        
        self.db_cursor.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            current_price REAL,
            ask_price REAL,
            bid_price REAL
        )
        ''')

        self.db_cursor.execute('''
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            error_message TEXT
        )
        ''')

        self.db_conn.commit()

    def log_trade(self, trade_date: str, trade_type: str, amount: float, price: float):
        self.db_cursor.execute('''
        INSERT INTO trades (trade_date, trade_type, amount, price)
        VALUES (?, ?, ?, ?)
        ''', (trade_date, trade_type, amount, price))
        self.db_conn.commit()

    def log_price(self, timestamp: str, symbol: str, current_price: float, ask_price: float, bid_price: float):
        self.db_cursor.execute('''
        INSERT INTO prices (timestamp, symbol, current_price, ask_price, bid_price)
        VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, symbol, current_price, ask_price, bid_price))
        self.db_conn.commit()

    def log_error(self, timestamp: str, error_message: str):
        self.db_cursor.execute('''
        INSERT INTO errors (timestamp, error_message)
        VALUES (?, ?)
        ''', (timestamp, error_message))
        self.db_conn.commit()
