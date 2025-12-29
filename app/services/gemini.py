"""
Gemini API client service.
Uses the official google-genai SDK v1.x with Google Search grounding.
Replaces Perplexity for fetching news and market summaries.
"""
import json
import time
import re
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from google import genai
from google.genai import types

from app.config import NEWS_SOURCES, TIMEZONE
from app.models.settings import Setting, ApiLog, NewsSource


# JSON Schema for structured market summary response
MARKET_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Concise headline (max 100 chars)"},
        "overview": {"type": "string", "description": "2-3 sentence overview"},
        "key_points": {"type": "array", "items": {"type": "string"}, "description": "3-5 bullet points"},
        "sectors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "performance": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["name", "performance"]
            }
        },
        "market_sentiment": {"type": "string", "enum": ["bullish", "bearish", "neutral", "mixed"]},
        "indices": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "value": {"type": "string"}, "change": {"type": "string"}},
                "required": ["name"]
            }
        },
        "sentiment_score": {"type": "integer", "description": "-10 to +10"},
        "sentiment_explanation": {"type": "string"}
    },
    "required": ["title", "overview", "key_points", "market_sentiment", "sentiment_score", "sentiment_explanation"]
}

SECTOR_NEWS_SCHEMA = {
    "type": "object",
    "properties": {
        "articles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "content": {"type": "string"},
                    "stocks_mentioned": {"type": "array", "items": {"type": "string"}},
                    "impact": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                    "sentiment_score": {"type": "integer"},
                    "sentiment_explanation": {"type": "string"}
                },
                "required": ["title", "summary", "content", "sentiment_score", "sentiment_explanation"]
            }
        }
    },
    "required": ["articles"]
}


class GeminiService:
    """Service for Gemini API with Google Search grounding."""

    MODEL_NAME = "gemini-2.5-flash"

    def __init__(self, db: Session):
        self.db = db
        self._client = None

    def _get_api_key(self) -> Optional[str]:
        """Get API key from database settings."""
        setting = self.db.query(Setting).filter(Setting.key == "gemini_api_key").first()
        if setting and setting.value:
            return setting.value
        return None

    def _get_client(self):
        """Get or create Gemini client."""
        if self._client is None:
            api_key = self._get_api_key()
            if api_key:
                self._client = genai.Client(api_key=api_key)
        return self._client

    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return self._get_api_key() is not None

    def _get_news_sources(self) -> list[str]:
        """Get active news sources from database."""
        sources = self.db.query(NewsSource).filter(NewsSource.is_active == True).all()
        if sources:
            return [s.domain for s in sources]
        return NEWS_SOURCES

    def _build_domain_prompt(self, sources: list[str]) -> str:
        """Build prompt instruction for preferring specific domains."""
        if not sources:
            return ""
        domains_list = ", ".join(sources[:10])
        return f"\n\nPrefer information from these trusted Indian financial news sources: {domains_list}."

    def validate_api_key(self, api_key: str) -> tuple[bool, str]:
        """Validate an API key by making a test call."""
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=self.MODEL_NAME,
                contents="Say hello in one word",
            )
            if response and response.text:
                return True, "API key is valid!"
            return False, "API returned empty response"
        except Exception as e:
            error_msg = str(e)
            if "API_KEY_INVALID" in error_msg or "401" in error_msg:
                return False, "Invalid API key"
            elif "429" in error_msg:
                return False, "Rate limit exceeded - key appears valid"
            return False, f"Validation error: {error_msg[:100]}"

    def set_api_key(self, api_key: str, user_id: Optional[int] = None) -> bool:
        """Set or update the API key."""
        setting = self.db.query(Setting).filter(Setting.key == "gemini_api_key").first()
        if setting:
            setting.value = api_key
            setting.updated_by = user_id
            setting.updated_at = datetime.now(TIMEZONE)
        else:
            setting = Setting(
                key="gemini_api_key",
                value=api_key,
                encrypted=False,
                updated_by=user_id,
                updated_at=datetime.now(TIMEZONE),
            )
            self.db.add(setting)
        self.db.commit()
        self.db.refresh(setting)
        self._client = None
        return True

    def _log_api_call(self, event_type: str, job_name: Optional[str], query: str,
                      status: str, response_time_ms: int, news_count: int = 0,
                      error_message: Optional[str] = None, triggered_by: str = "manual"):
        """Log an API call to the database."""
        log = ApiLog(
            timestamp=datetime.now(TIMEZONE),
            event_type=event_type,
            job_name=job_name,
            query=query,
            status=status,
            response_time_ms=response_time_ms,
            news_count=news_count,
            error_message=error_message,
            triggered_by=triggered_by,
        )
        self.db.add(log)
        self.db.commit()

    def _extract_citations(self, response) -> list[dict]:
        """Extract citations from Gemini grounding metadata."""
        citations = []
        try:
            if not response.candidates:
                return citations
            candidate = response.candidates[0]
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                grounding = candidate.grounding_metadata
                if hasattr(grounding, 'grounding_chunks') and grounding.grounding_chunks:
                    for i, chunk in enumerate(grounding.grounding_chunks, 1):
                        if hasattr(chunk, 'web') and chunk.web:
                            citations.append({
                                "index": i,
                                "url": getattr(chunk.web, 'uri', ''),
                                "title": getattr(chunk.web, 'title', None)
                            })
        except Exception:
            pass
        return citations

    def fetch_summary(self, query: str, job_name: Optional[str] = None,
                      triggered_by: str = "manual", recency_filter: str = "day",
                      use_structured: bool = True) -> dict:
        """Fetch AI summary with Google Search grounding."""
        client = self._get_client()
        if not client:
            return {"error": "API key not configured", "content": None, "citations": []}

        news_sources = self._get_news_sources()
        domain_prompt = self._build_domain_prompt(news_sources)
        start_time = time.time()

        try:
            recency_hint = {"hour": "from the last hour", "day": "from today",
                           "week": "from this week", "month": "from this month"}.get(recency_filter, "recent")

            enhanced_query = f"{query}\n\nFocus on news {recency_hint}.{domain_prompt}"

            # Add JSON instruction to prompt (can't use response_mime_type with grounding)
            if use_structured:
                enhanced_query += "\n\nRespond with a JSON object containing: title, overview, key_points (array), sectors (array), market_sentiment, indices (array), sentiment_score (-10 to +10), sentiment_explanation."

            # Google Search grounding tool
            grounding_tool = types.Tool(google_search=types.GoogleSearch())
            config = types.GenerateContentConfig(tools=[grounding_tool])

            response = client.models.generate_content(
                model=self.MODEL_NAME,
                contents=enhanced_query,
                config=config,
            )

            response_time = int((time.time() - start_time) * 1000)
            raw_content = response.text if response else ""

            if use_structured:
                try:
                    json_match = re.search(r'\{[\s\S]*\}', raw_content)
                    data = json.loads(json_match.group() if json_match else raw_content)
                    content = self._format_structured_summary(data)
                    title = data.get("title", "")
                    sentiment_score = data.get("sentiment_score", 0)
                    sentiment_explanation = data.get("sentiment_explanation", "")
                except (json.JSONDecodeError, AttributeError):
                    content, title, sentiment_score, sentiment_explanation = raw_content, "", 0, ""
            else:
                content, title, sentiment_score, sentiment_explanation = raw_content, "", 0, ""

            citations = self._extract_citations(response)

            self._log_api_call("api_call", job_name, query, "success", response_time, 1, triggered_by=triggered_by)

            return {
                "content": content, "title": title, "citations": citations,
                "sentiment_score": sentiment_score, "sentiment_explanation": sentiment_explanation,
                "fetched_at": datetime.now(TIMEZONE).isoformat(),
            }

        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            self._log_api_call("api_call", job_name, query, "failed", response_time, error_message=str(e), triggered_by=triggered_by)
            return {"error": str(e), "content": None, "citations": []}

    def _format_structured_summary(self, data: dict) -> str:
        """Convert structured JSON to markdown."""
        parts = []
        if data.get("overview"):
            parts.append(f"## Overview\n\n{data['overview']}")
        if data.get("indices"):
            indices_text = "## Market Indices\n\n"
            for idx in data["indices"]:
                if idx.get("name"):
                    indices_text += f"- **{idx['name']}**: {idx.get('value', '')} ({idx.get('change', '')})\n"
            parts.append(indices_text.strip())
        if data.get("key_points"):
            parts.append("## Key Points\n\n" + "\n".join(f"- {p}" for p in data["key_points"]))
        if data.get("sectors"):
            sectors_text = "## Sector Performance\n\n"
            for s in data["sectors"]:
                if s.get("name"):
                    sectors_text += f"- **{s['name']}**: {s.get('performance', '')}"
                    if s.get("reason"):
                        sectors_text += f" - {s['reason']}"
                    sectors_text += "\n"
            parts.append(sectors_text.strip())
        if data.get("market_sentiment"):
            parts.append(f"## Market Sentiment\n\n**{data['market_sentiment'].capitalize()}**")
        return "\n\n".join(parts)

    def fetch_structured_news(self, query: str, job_name: Optional[str] = None,
                              triggered_by: str = "manual", recency_filter: str = "day",
                              max_articles: int = 5) -> list[dict]:
        """Fetch news articles with Google Search grounding."""
        client = self._get_client()
        if not client:
            return []

        news_sources = self._get_news_sources()
        domain_prompt = self._build_domain_prompt(news_sources)
        start_time = time.time()

        try:
            recency_hint = {"hour": "from the last hour", "day": "from today",
                           "week": "from this week", "month": "from this month"}.get(recency_filter, "recent")

            prompt = f"""Find {max_articles} news articles about: {query}
For each article provide: title, summary, content, stocks_mentioned (array), impact (positive/negative/neutral), sentiment_score (-10 to +10), sentiment_explanation.
Focus on news {recency_hint}.{domain_prompt}

Respond with a JSON object containing an "articles" array."""

            # Google Search grounding (can't use response_mime_type with grounding)
            grounding_tool = types.Tool(google_search=types.GoogleSearch())
            config = types.GenerateContentConfig(tools=[grounding_tool])

            response = client.models.generate_content(model=self.MODEL_NAME, contents=prompt, config=config)
            response_time = int((time.time() - start_time) * 1000)
            raw_content = response.text if response else ""

            try:
                json_match = re.search(r'\{[\s\S]*\}', raw_content)
                data = json.loads(json_match.group() if json_match else raw_content)
                articles = data.get("articles", [])
            except (json.JSONDecodeError, AttributeError):
                articles = []

            citations = self._extract_citations(response)
            for article in articles:
                article["citations"] = citations

            self._log_api_call("api_call", job_name, query, "success", response_time, len(articles), triggered_by=triggered_by)
            return articles

        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            self._log_api_call("api_call", job_name, query, "failed", response_time, error_message=str(e), triggered_by=triggered_by)
            return []

    def _clean_summary_text(self, text: str) -> str:
        """Clean markdown formatting."""
        if not text:
            return ""
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
        text = " ".join(text.split())
        return text[:500] + "..." if len(text) > 500 else text
