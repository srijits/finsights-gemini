"""
RSS Feed routes for FinSights news.
Provides RSS 2.0 feeds for all news categories.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.config import CATEGORY_NAMES, SUBCATEGORY_NAMES, TIMEZONE
from app.services.cache import cache_manager


router = APIRouter(prefix="/feed", tags=["RSS Feeds"])


def escape_xml(text: str) -> str:
    """Escape special XML characters."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def format_rfc822_date(dt: datetime) -> str:
    """Format datetime as RFC 822 for RSS pubDate."""
    if not dt:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return ""
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0530")


def strip_html(text: str) -> str:
    """Remove HTML tags from text for RSS description."""
    if not text:
        return ""
    import re
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Collapse whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def get_sentiment_label(score: int) -> str:
    """Convert sentiment score to human-readable label."""
    if score is None:
        return "Neutral"
    if score >= 7:
        return "Very Bullish"
    elif score >= 4:
        return "Bullish"
    elif score >= 1:
        return "Slightly Bullish"
    elif score == 0:
        return "Neutral"
    elif score >= -3:
        return "Slightly Bearish"
    elif score >= -6:
        return "Bearish"
    else:
        return "Very Bearish"


def build_rss_feed(
    title: str,
    description: str,
    link: str,
    news_items: list,
    base_url: str
) -> str:
    """Build RSS 2.0 XML feed from news items."""
    now = format_rfc822_date(datetime.now(TIMEZONE))
    
    items_xml = []
    for news in news_items:
        news_id = news.get("id", "")
        news_title = escape_xml(news.get("title", "No Title"))
        news_summary = escape_xml(strip_html(news.get("summary", "")))
        news_link = f"{base_url}/news/{news_id}"
        
        # Get publish date
        pub_date = news.get("published_at") or news.get("fetched_at")
        pub_date_str = format_rfc822_date(pub_date) if pub_date else now
        
        # Category info
        category = news.get("category", "")
        subcategory = news.get("subcategory", "")
        category_name = CATEGORY_NAMES.get(category, category)
        if subcategory:
            category_name = f"{category_name} - {SUBCATEGORY_NAMES.get(subcategory, subcategory)}"
        
        # Sentiment info
        sentiment_score = news.get("sentiment_score")
        sentiment_explanation = news.get("sentiment_explanation", "")
        sentiment_label = get_sentiment_label(sentiment_score)
        
        # Build sentiment XML elements
        sentiment_xml = ""
        if sentiment_score is not None:
            sentiment_xml = f"""
      <finsights:sentimentScore>{sentiment_score}</finsights:sentimentScore>
      <finsights:sentimentLabel>{escape_xml(sentiment_label)}</finsights:sentimentLabel>"""
            if sentiment_explanation:
                sentiment_xml += f"""
      <finsights:sentimentExplanation>{escape_xml(sentiment_explanation)}</finsights:sentimentExplanation>"""
        
        # Include sentiment in description for readers that don't support custom namespaces
        description_with_sentiment = news_summary[:500]
        if len(news_summary) > 500:
            description_with_sentiment += "..."
        if sentiment_score is not None:
            description_with_sentiment += f" [Sentiment: {sentiment_label} ({sentiment_score:+d})]"
        
        item_xml = f"""    <item>
      <title>{news_title}</title>
      <link>{news_link}</link>
      <description>{description_with_sentiment}</description>
      <pubDate>{pub_date_str}</pubDate>
      <guid isPermaLink="true">{news_link}</guid>
      <category>{escape_xml(category_name)}</category>{sentiment_xml}
    </item>"""
        items_xml.append(item_xml)
    
    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:finsights="https://fin.afxo.in/rss/finsights">
  <channel>
    <title>{escape_xml(title)}</title>
    <link>{link}</link>
    <description>{escape_xml(description)}</description>
    <language>en-in</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="{link}/feed/rss" rel="self" type="application/rss+xml"/>
    <generator>AFXO Insights RSS Generator</generator>
    <ttl>30</ttl>
{chr(10).join(items_xml)}
  </channel>
</rss>"""
    
    return rss_xml


def create_rss_response(xml_content: str) -> Response:
    """Create proper RSS response with correct headers."""
    return Response(
        content=xml_content,
        media_type="application/rss+xml; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=300",  # Cache for 5 minutes
        }
    )


@router.get("/rss", response_class=Response)
async def rss_all_news(request: Request):
    """
    RSS feed for all latest news.
    
    Returns up to 50 most recent news items across all categories.
    """
    base_url = str(request.base_url).rstrip("/")
    news_items = cache_manager.get_latest_news(limit=50)
    
    xml = build_rss_feed(
        title="AFXO Insights - Indian Market News",
        description="Latest Indian stock market news, summaries, and analysis from AFXO Insights",
        link=base_url,
        news_items=news_items,
        base_url=base_url
    )
    
    return create_rss_response(xml)


@router.get("/rss/{category}", response_class=Response)
async def rss_category(request: Request, category: str):
    """
    RSS feed for a specific category.
    
    Categories: market, sector, macro, regulation, stock
    """
    base_url = str(request.base_url).rstrip("/")
    news_items = cache_manager.get_news_by_category(category, limit=50)
    
    category_name = CATEGORY_NAMES.get(category, category.title())
    
    xml = build_rss_feed(
        title=f"AFXO Insights - {category_name}",
        description=f"{category_name} news and updates from AFXO Insights",
        link=f"{base_url}/category/{category}",
        news_items=news_items,
        base_url=base_url
    )
    
    return create_rss_response(xml)


@router.get("/rss/{category}/{subcategory}", response_class=Response)
async def rss_subcategory(request: Request, category: str, subcategory: str):
    """
    RSS feed for a specific subcategory.
    
    Examples:
    - /feed/rss/market/pre_market
    - /feed/rss/sector/banking
    - /feed/rss/macro/rbi
    """
    base_url = str(request.base_url).rstrip("/")
    news_items = cache_manager.get_news_by_category(category, subcategory, limit=50)
    
    category_name = CATEGORY_NAMES.get(category, category.title())
    subcategory_name = SUBCATEGORY_NAMES.get(subcategory, subcategory.replace("_", " ").title())
    
    xml = build_rss_feed(
        title=f"AFXO Insights - {category_name}: {subcategory_name}",
        description=f"{subcategory_name} news and updates from AFXO Insights",
        link=f"{base_url}/category/{category}/{subcategory}",
        news_items=news_items,
        base_url=base_url
    )
    
    return create_rss_response(xml)


@router.get("/rss/stock/{symbol}", response_class=Response)
async def rss_stock(request: Request, symbol: str):
    """
    RSS feed for a specific stock symbol.
    
    Example: /feed/rss/stock/RELIANCE
    """
    base_url = str(request.base_url).rstrip("/")
    symbol = symbol.upper()
    news_items = cache_manager.get_stock_news(symbol, limit=30)
    
    # Get symbol info if available
    all_symbols = cache_manager.get_all_symbols()
    symbol_info = next((s for s in all_symbols if s.get("symbol") == symbol), None)
    company_name = symbol_info.get("company_name", symbol) if symbol_info else symbol
    
    xml = build_rss_feed(
        title=f"AFXO Insights - {symbol} News",
        description=f"Latest news and updates for {company_name} ({symbol})",
        link=f"{base_url}/stock/{symbol}",
        news_items=news_items,
        base_url=base_url
    )
    
    return create_rss_response(xml)


@router.get("/feeds", response_class=Response)
async def list_feeds(request: Request):
    """
    List all available RSS feeds in OPML format.
    
    OPML can be imported into RSS readers to subscribe to all feeds at once.
    """
    base_url = str(request.base_url).rstrip("/")
    
    feeds = [
        ("All News", f"{base_url}/feed/rss"),
    ]
    
    # Add category feeds
    for cat_key, cat_name in CATEGORY_NAMES.items():
        feeds.append((cat_name, f"{base_url}/feed/rss/{cat_key}"))
    
    # Add subcategory feeds
    subcategory_map = {
        "market": ["pre_market", "morning", "midday", "post_market", "evening"],
        "sector": ["auto", "banking", "pharma", "it"],
        "macro": ["economy", "rbi", "global"],
        "regulation": ["sebi", "exchange"],
    }
    
    for cat_key, subcats in subcategory_map.items():
        cat_name = CATEGORY_NAMES.get(cat_key, cat_key)
        for subcat in subcats:
            subcat_name = SUBCATEGORY_NAMES.get(subcat, subcat)
            feeds.append(
                (f"{cat_name}: {subcat_name}", f"{base_url}/feed/rss/{cat_key}/{subcat}")
            )
    
    # Build OPML
    outlines = []
    for title, url in feeds:
        outlines.append(
            f'    <outline type="rss" text="{escape_xml(title)}" '
            f'title="{escape_xml(title)}" xmlUrl="{url}" htmlUrl="{base_url}"/>'
        )
    
    opml = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head>
    <title>AFXO Insights RSS Feeds</title>
    <dateCreated>{format_rfc822_date(datetime.now(TIMEZONE))}</dateCreated>
  </head>
  <body>
{chr(10).join(outlines)}
  </body>
</opml>"""
    
    return Response(
        content=opml,
        media_type="application/xml; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="finsights-feeds.opml"'
        }
    )
