# Telegram Productivity Bot with DeepSeek AI

A Telegram bot that helps manage tasks and notes, powered by the DeepSeek language model for intelligent search and summarization. This bot runs on CUDOS Intercloud infrastructure and uses Ollama for local AI model deployment.

## Features

- **Note Management**: Save and organize notes
- **Task Tracking**: Add and manage tasks
- **AI-Powered Search**: Search through notes and tasks using DeepSeek AI
- **Smart Summaries**: Get AI-generated summaries of your content
- **Free Infrastructure**: Uses open-source components and free-tier services

## Technical Stack

- **Bot Framework**: Python Telegram Bot
- **AI Model**: DeepSeek-R1-Distill-Qwen-1.5B via Ollama
- **Database**: MongoDB
- **Deployment**: Docker & CUDOS Intercloud
- **Language**: Python 3.9+

## Project Structure

```
telegram-productivity-bot/
├── main.py                 # Main bot application
├── Dockerfile              # Bot container configuration
├── Dockerfile.ollama       # Ollama container configuration
├── docker-compose.yml      # Local development setup
├── docker-compose.prod.yml # Production deployment setup
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables
└── README.md              # This file
```

## Prerequisites

- Python 3.9 or higher
- Docker and Docker Compose
- CUDOS Intercloud account
- Telegram account (for bot creation)
- Docker Hub account (for image hosting)

## Local Development Setup

1. **Clone the Repository**
```bash
git clone <repository-url>
cd telegram-productivity-bot
```

2. **Set Up Environment**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

3. **Configure Environment Variables**
Create `.env` file:
```
TELEGRAM_BOT_TOKEN=your_bot_token
MONGO_URI=mongodb://localhost:27017
```

4. **Run Locally**
```bash
# Start services
docker compose up --build
```

## Production Deployment (CUDOS Intercloud)

1. **Prepare Docker Images**
```bash
# Build images
docker compose build

# Tag images
docker tag telegram-productivity-bot-bot your-username/telegram-productivity-bot:latest
docker tag telegram-productivity-bot-ollama your-username/ollama-deepseek:latest

# Push to Docker Hub
docker push your-username/telegram-productivity-bot:latest
docker push your-username/ollama-deepseek:latest
```

2. **CUDOS VM Setup**
```bash
# SSH into CUDOS VM
ssh user@your-cudos-vm-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get update
sudo apt-get install -y docker-compose
```

3. **Deploy on CUDOS**
```bash
mkdir ~/productivity-bot
cd ~/productivity-bot
# Copy docker-compose.prod.yml and .env to this directory
docker-compose -f docker-compose.prod.yml up -d
```

## Configuration Files

### Dockerfile
```dockerfile
FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY .env .

CMD ["python", "main.py"]
```

### Dockerfile.ollama
```dockerfile
FROM ollama/ollama:latest

COPY <<EOF /pull-model.sh
#!/bin/sh
ollama serve &
sleep 10
ollama pull deepseek-r1:1.5b
kill %1
EOF

RUN chmod +x /pull-model.sh
RUN /pull-model.sh

CMD ["ollama", "serve"]
```

### Requirements
```
python-telegram-bot==20.8
requests==2.31.0
python-dotenv==1.0.0
icalendar==5.0.11
aiohttp==3.9.1
motor==3.1.1
pymongo==4.6.1
```

## Bot Commands

- `/start` - Initialize the bot
- `/help` - Show help message
- `/note [text]` - Save a note
- `/task [text]` - Add a task
- `/list` - List all notes and tasks
- `/search [query]` - Search through content
- `/summary` - Get content summary
- `/query` [text] 🤖: Ask any general question and get a final answer
- `/summarize_meeting` 🗣️: Summarize a meeting transcript from a voice message (coming soon)
- `/delete_tasks` 🗑️: Delete all tasks
- `/delete_notes` 🗑️: Delete all notes


## Maintenance

### Monitoring
```bash
# Check container status
docker ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Check disk usage
df -h
```

### Updates
```bash
# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Restart services
docker-compose -f docker-compose.prod.yml up -d
```

### Backup
```bash
# Backup MongoDB data
docker exec mongodb mongodump --out /data/backup/
```

## Troubleshooting

1. **Ollama Container Issues**
```bash
# Check Ollama status
docker logs telegram-productivity-bot_ollama_1

# Verify model installation
docker exec telegram-productivity-bot_ollama_1 ollama list
```

2. **MongoDB Connection Issues**
```bash
# Check MongoDB status
docker logs telegram-productivity-bot_mongodb_1

# Test MongoDB connection
docker exec telegram-productivity-bot_mongodb_1 mongosh --eval "db.serverStatus()"
```

3. **Bot Container Issues**
```bash
# Check bot logs
docker logs telegram-productivity-bot_bot_1

# Restart bot container
docker-compose -f docker-compose.prod.yml restart bot
```

## Resource Requirements

- **CPU**: 4 cores minimum
- **RAM**: 8GB minimum
- **Storage**: 50GB minimum
- **Network**: Stable internet connection
