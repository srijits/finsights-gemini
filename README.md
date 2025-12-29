# FinSights (Gemini Edition)

AI-powered financial news platform for Indian stock market traders. Built with FastAPI and **Google Gemini 2.5 Flash** with real-time Google Search grounding.

> **Fork Note**: This is a fork of the original [FinSights](https://github.com/marketcalls/FinSights) project, migrated from Perplexity AI to Google Gemini for better rate limits and cost efficiency.

## Features

- **AI Market Summaries**: Pre-market and post-market summaries with sentiment analysis
- **Real-time Grounding**: Google Search integration for up-to-date news
- **Sector Coverage**: Banking, IT, Pharma, Auto, Energy, FMCG, Metals, Realty
- **Stock Search**: Search news by NSE/BSE stock symbols
- **Admin Panel**: Full control over news, scheduler, and API settings
- **Scheduled Jobs**: Automated news fetching via APScheduler
- **Citation Support**: Sources linked from grounding metadata

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI, SQLAlchemy, SQLite |
| Frontend | Jinja2, Tailwind CSS, DaisyUI |
| AI | Google Gemini 2.5 Flash + Google Search |
| Package Manager | uv (fast Python package manager) |
| Scheduler | APScheduler |

## Quick Start

### Local Development

```bash
# Clone
git clone https://github.com/srijits/finsights-gemini.git
cd finsights-gemini

# Install with uv (recommended)
uv sync

# Or with pip
pip install -r requirements.txt

# Build CSS
npm install && npm run build:css

# Run
uv run uvicorn app.main:app --reload
```

### Server Deployment (Ubuntu)

```bash
# Copy code to server
scp -r ./finsights-gemini ubuntu@server:/home/ubuntu/finsights

# Run install script
sudo bash /home/ubuntu/finsights/install_finsights.sh
```

The install script:
- Installs uv package manager
- Sets up Python environment
- Creates systemd service
- Configures nginx with SSL

## Configuration

### Gemini API Key

1. Get a free API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Go to Admin → Settings
3. Enter and validate your API key

**Free tier limits**: 15 RPM, 1M TPM, 1500 RPD

### Admin Login

Default credentials (change after first login):
- Username: `admin`
- Password: `admin123`

## Project Structure

```
finsights/
├── app/
│   ├── services/
│   │   ├── gemini.py        # Gemini API client
│   │   ├── gemini_async.py  # Background job client
│   │   └── news_fetcher.py  # News storage logic
│   ├── routers/             # FastAPI routes
│   ├── templates/           # Jinja2 templates
│   └── main.py              # Application entry
├── install_finsights.sh     # Server deployment script
└── requirements.txt         # Python dependencies
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Home page with all news |
| `GET /category/{name}` | News by category |
| `GET /search?q=SYMBOL` | Search by stock symbol |
| `GET /admin/dashboard` | Admin dashboard |
| `GET /admin/settings` | API key configuration |
| `GET /health` | Health check |

## Changes from Original

| Feature | Original | This Fork |
|---------|----------|-----------|
| AI Provider | Perplexity API | Google Gemini 2.5 Flash |
| Search | Perplexity's built-in | Google Search grounding |
| Rate Limits | Paid/Limited | Generous free tier |
| Package Manager | pip | uv (10-100x faster) |

## License

MIT License - see [LICENSE](LICENSE) file.

## Disclaimer

For informational purposes only. Not financial advice. Always do your own research.
