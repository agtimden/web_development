import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY', 'secret-key')

# Prefer DATABASE_URL if provided (e.g., mysql+mysqlconnector://user:pass@host/db)
DATABASE_URL = os.getenv('DATABASE_URL')

# Fallback to MySQL assembled from parts if DATABASE_URL is not set
if not DATABASE_URL:
    MYSQL_USER = os.getenv('MYSQL_USER')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_DB = os.getenv('MYSQL_DB')
    if MYSQL_USER and MYSQL_PASSWORD and MYSQL_DB:
        DATABASE_URL = f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"

# Final fallback to local sqlite for quick start
SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///project.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ECHO = True

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media', 'images')
