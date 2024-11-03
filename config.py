import os

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev_key_123')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENROUTE_API_KEY = os.environ.get('OPENROUTE_API_KEY', 'YOUR_API_KEY')  # Should be set in environment
