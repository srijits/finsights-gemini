"""
Gemini API client service for background job processing.
Uses google-genai SDK v1.x with Google Search grounding.
"""
import json
import re
import time
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from google import genai
from google.genai import types

from app.config import NEWS_SOURCES, TIMEZONE
from app.models.settings import Setting, ApiLog, NewsSource
from app.services.gemini import MARKET_SUMMARY_SCHEMA, SECTOR_NEWS_SCHEMA


class AsyncGeminiService:
    """Background Gemini API calls with grounding."""

    MODEL_NAME = "gemini-2.5-flash"

    def __init__(self, db: Session):
        self.db = db
        self._client = None

    def _get_api_key(self) -> Optional[str]:
        setting = self.db.query(Setting).filter(Setting.key == "gemini_api_key").first()
        return setting.value if setting and setting.value else None

    def _get_client(self):
        if self._client is None:
            api_key = self._get_api_key()
            if api_key:
                self._client = genai.Client(api_key=api_key)
        return self._client

    def is_configured(self) -> bool:
        return self._get_api_key() is not None

    def _get_news_sources(self) -> list[str]:
        sources = self.db.query(NewsSource).filter(NewsSource.is_active == True).all()
        return [s.domain for s in sources] if sources else NEWS_SOURCES

    def _build_domain_prompt(self, sources: list[str]) -> str:
        if not sources:
            return ""
        return f"\n\nPrefer information from: {', '.join(sources[:10])}."

    def _extract_citations(self, response) -> list[dict]:
        citations = []
        try:
            if response.candidates and response.candidates[0].grounding_metadata:
                grounding = response.candidates[0].grounding_metadata
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

    def _log_api_call(self, event_type: str, job_name: Optional[str], query: str,
                      status: str, response_time_ms: int = 0, news_count: int = 0,
                      error_message: Optional[str] = None, triggered_by: str = "manual"):
        log = ApiLog(
            timestamp=datetime.now(TIMEZONE), event_type=event_type, job_name=job_name,
            query=query, status=status, response_time_ms=response_time_ms,
            news_count=news_count, error_message=error_message, triggered_by=triggered_by,
        )
        self.db.add(log)
        self.db.commit()

    def fetch_summary(self, query: str, job_name: Optional[str] = None,
                      triggered_by: str = "scheduler", recency_filter: str = "day",
                      use_structured: bool = True) -> dict:
        """Fetch market summary with Google Search grounding."""
        client = self._get_client()
        if not client:
            return {"error": "API key not configured", "content": None, "citations": []}

        domain_prompt = self._build_domain_prompt(self._get_news_sources())
        start_time = time.time()

        try:
            recency = {"hour": "last hour", "day": "today", "week": "this week", "month": "this month"}.get(recency_filter, "recent")
            enhanced_query = f"{query}\n\nFocus on news from {recency}.{domain_prompt}"

            # Add JSON instruction to prompt (can't use response_mime_type with grounding)
            if use_structured:
                enhanced_query += "\n\nRespond with a JSON object containing: title, overview, key_points (array), sectors (array), market_sentiment, indices (array), sentiment_score (-10 to +10), sentiment_explanation."

            grounding_tool = types.Tool(google_search=types.GoogleSearch())
            config = types.GenerateContentConfig(tools=[grounding_tool])

            response = client.models.generate_content(model=self.MODEL_NAME, contents=enhanced_query, config=config)
            response_time = int((time.time() - start_time) * 1000)
            raw_content = response.text if response else ""

            if use_structured:
                try:
                    json_match = re.search(r'\{[\s\S]*\}', raw_content)
                    data = json.loads(json_match.group() if json_match else raw_content)
                    content = self._format_structured_summary(data)
                    title, sentiment_score, sentiment_explanation = data.get("title", ""), data.get("sentiment_score", 0), data.get("sentiment_explanation", "")
                except (json.JSONDecodeError, AttributeError):
                    content, title, sentiment_score, sentiment_explanation = raw_content, "", 0, ""
            else:
                content, title, sentiment_score, sentiment_explanation = raw_content, "", 0, ""

            self._log_api_call("api_call", job_name, query, "success", response_time, 1, triggered_by=triggered_by)
            return {
                "content": content, "title": title, "citations": self._extract_citations(response),
                "sentiment_score": sentiment_score, "sentiment_explanation": sentiment_explanation,
                "fetched_at": datetime.now(TIMEZONE).isoformat(),
            }
        except Exception as e:
            self._log_api_call("api_call", job_name, query, "failed", int((time.time() - start_time) * 1000), error_message=str(e), triggered_by=triggered_by)
            return {"error": str(e), "content": None, "citations": []}

    def fetch_news(self, query: str, job_name: Optional[str] = None,
                   triggered_by: str = "scheduler", recency_filter: str = "day",
                   max_articles: int = 5) -> dict:
        """Fetch news articles with Google Search grounding."""
        client = self._get_client()
        if not client:
            return {"error": "API key not configured", "articles": [], "citations": []}

        domain_prompt = self._build_domain_prompt(self._get_news_sources())
        start_time = time.time()

        try:
            recency = {"hour": "last hour", "day": "today", "week": "this week", "month": "this month"}.get(recency_filter, "recent")
            prompt = f"""Find {max_articles} news articles about: {query}
For each article provide: title, summary, content, stocks_mentioned (array), impact (positive/negative/neutral), sentiment_score (-10 to +10), sentiment_explanation.
Focus on {recency} news.{domain_prompt}

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

            self._log_api_call("api_call", job_name, query, "success", response_time, len(articles), triggered_by=triggered_by)
            return {"articles": articles, "citations": self._extract_citations(response), "fetched_at": datetime.now(TIMEZONE).isoformat()}
        except Exception as e:
            self._log_api_call("api_call", job_name, query, "failed", int((time.time() - start_time) * 1000), error_message=str(e), triggered_by=triggered_by)
            return {"error": str(e), "articles": [], "citations": []}

    def _format_structured_summary(self, data: dict) -> str:
        parts = []
        if data.get("overview"):
            parts.append(f"## Overview\n\n{data['overview']}")
        if data.get("indices"):
            parts.append("## Market Indices\n\n" + "\n".join(f"- **{i['name']}**: {i.get('value', '')} ({i.get('change', '')})" for i in data["indices"] if i.get("name")))
        if data.get("key_points"):
            parts.append("## Key Points\n\n" + "\n".join(f"- {p}" for p in data["key_points"]))
        if data.get("sectors"):
            parts.append("## Sector Performance\n\n" + "\n".join(f"- **{s['name']}**: {s.get('performance', '')}" + (f" - {s['reason']}" if s.get('reason') else "") for s in data["sectors"] if s.get("name")))
        if data.get("market_sentiment"):
            parts.append(f"## Market Sentiment\n\n**{data['market_sentiment'].capitalize()}**")
        return "\n\n".join(parts)

    def _clean_summary_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = " ".join(text.split())
        return text[:500] + "..." if len(text) > 500 else text
