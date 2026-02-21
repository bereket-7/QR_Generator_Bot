#!/bin/bash
set -e

# Docker entrypoint script for QR Bot
# Handles database initialization, migrations, and service startup

echo "🚀 Starting QR Bot Container..."

# Function to check if Redis is available
check_redis() {
    echo "🔍 Checking Redis connection..."
    python -c "
import redis
import os
import time

redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = int(os.environ.get('REDIS_PORT', 6379))

for i in range(30):  # Try for 30 seconds
    try:
        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        r.ping()
        print('✅ Redis is ready!')
        break
    except Exception as e:
        print(f'⏳ Waiting for Redis... ({i+1}/30)')
        time.sleep(1)
else:
    print('❌ Redis connection failed!')
    exit(1)
"
}

# Function to initialize database
init_database() {
    echo "🗄️ Initializing database..."
    
    # Check if database exists
    if [ ! -f "/app/qr_bot.db" ]; then
        echo "📝 Creating new database..."
        python -c "
from database import init_db
init_db()
print('✅ Database initialized successfully!')
"
    else:
        echo "📝 Database exists, checking for updates..."
        python -c "
import sqlite3
import os

db_path = '/app/qr_bot.db'

# Check if we need to run updates
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if dynamic_qr_codes table exists
    cursor.execute(\"\"\"
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='dynamic_qr_codes'
    \"\"\")
    
    if not cursor.fetchone():
        print('🔄 Running database updates...')
        with open('/app/database_updates.sql', 'r') as f:
            sql_script = f.read()
        cursor.executescript(sql_script)
        conn.commit()
        print('✅ Database updated successfully!')
    else:
        print('✅ Database is up to date!')
    
    conn.close()
except Exception as e:
    print(f'❌ Database update failed: {e}')
    exit(1)
"
}

# Function to create directories
create_directories() {
    echo "📁 Creating necessary directories..."
    mkdir -p /app/logs /app/qr_codes /app/temp
    chmod 755 /app/logs /app/qr_codes /app/temp
    echo "✅ Directories created!"
}

# Function to validate configuration
validate_config() {
    echo "⚙️ Validating configuration..."
    
    # Check required environment variables
    required_vars=("BOT_TOKEN" "JWT_SECRET")
    missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        echo "❌ Missing required environment variables:"
        printf '%s\n' "${missing_vars[@]}"
        exit 1
    fi
    
    echo "✅ Configuration validated!"
}

# Function to start the appropriate service
start_service() {
    echo "🎯 Starting service: $1"
    
    case "$1" in
        "bot")
            echo "🤖 Starting Telegram Bot..."
            exec python bot.py
            ;;
        "admin")
            echo "🖥️ Starting Admin Panel..."
            exec python admin_panel/app.py
            ;;
        "api")
            echo "🌐 Starting REST API..."
            exec python api/main.py
            ;;
        "worker")
            echo "⚙️ Starting Background Worker..."
            exec python -m celery worker -A tasks
            ;;
        *)
            echo "❌ Unknown service: $1"
            echo "Available services: bot, admin, api, worker"
            exit 1
            ;;
    esac
}

# Main execution flow
main() {
    # Determine service to start
    SERVICE=${1:-bot}
    
    echo "=========================================="
    echo "🤖 QR Bot Docker Container"
    echo "📅 $(date)"
    echo "🔧 Service: $SERVICE"
    echo "=========================================="
    
    # Run initialization steps
    validate_config
    create_directories
    check_redis
    init_database
    
    # Start the service
    start_service "$SERVICE"
}

# Handle signals gracefully
trap 'echo "🛑 Shutting down..."; exit 0' SIGTERM SIGINT

# Run main function with all arguments
main "$@"
