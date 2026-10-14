"""
Sentiment Analysis Agent — Lambda Handler (V3: A2A-compliant)

Provides sentiment analysis tools for investment research:
    GET  /sentiment-analysis/.well-known/agent.json  — A2A AgentCard manifest
    POST /sentiment-analysis/agent                    — A2A JSON-RPC task endpoint
    POST /sentiment-analysis/analyze_transcript       — direct tool (V2 compat)
    POST /sentiment-analysis/score_news_sentiment     — direct tool (V2 compat)
    POST /sentiment-analysis/detect_tone_shifts       — direct tool (V2 compat)
    POST /sentiment-analysis/aggregate_sentiment      — direct tool (V2 compat)

V3 changes:
    - Routes ``.well-known/agent.json`` to a2a_manifest.handler
    - Routes ``POST /agent`` to a2a_handler.handler (JSON-RPC 2.0, tasks/send)
    - Keeps the V2 autonomous-agent natural-language fallback via ``POST /agent``
      when the body is not a JSON-RPC envelope.
    - Backward-compatible: all V2 direct tool endpoints still work.
"""

import json
import os
import logging
import time

import boto3

# --- Strands SDK import with graceful fallback ---
try:
    from strands import Agent, tool
    from strands.models import BedrockModel
    STRANDS_AVAILABLE = True
except ImportError:
    STRANDS_AVAILABLE = False
    def tool(fn):
        """No-op decorator when strands-agents is not installed."""
        fn._is_tool = True
        return fn

# --- Langfuse wrapper ---
try:
    from langfuse_wrapper import (
        create_trace, add_span, add_generation, end_trace, get_prompt, is_configured,
    )
except ImportError:
    def create_trace(*a, **kw): return "no-trace"
    def add_span(*a, **kw): pass
    def add_generation(*a, **kw): pass
    def end_trace(*a, **kw): pass
    def get_prompt(name, fallback): return fallback
    def is_configured(): return False

# --- Salesforce client (bidirectional, Gap 18) ---
try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
    from salesforce_client import SalesforceClient
    _sf_client = SalesforceClient()
except ImportError:
    _sf_client = None

from urllib import request as urllib_request
from urllib.error import URLError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
)
NEWS_API_URL = os.environ.get("NEWS_API_URL", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")


# ---------------------------------------------------------------------------
# Amazon Comprehend helper (Gap 11)
# ---------------------------------------------------------------------------
def _comprehend_detect_sentiment(text):
    """Use Amazon Comprehend to detect sentiment of text.

    Args:
        text: Text to analyze (max 5000 bytes for Comprehend).

    Returns:
        dict with Sentiment and SentimentScore, or empty dict on failure.
    """
    try:
        client = boto3.client("comprehend")
        truncated = text[:4900] if len(text.encode("utf-8")) > 5000 else text
        result = client.detect_sentiment(Text=truncated, LanguageCode="en")
        return {
            "sentiment": result.get("Sentiment", "UNKNOWN"),
            "scores": result.get("SentimentScore", {}),
        }
    except Exception as exc:
        logger.warning("Comprehend detect_sentiment failed: %s", exc)
        return {}


def _comprehend_detect_entities(text):
    """Use Amazon Comprehend to extract entities from text.

    Args:
        text: Text to analyze.

    Returns:
        list of entity dicts with Type, Text, and Score.
    """
    try:
        client = boto3.client("comprehend")
        truncated = text[:4900] if len(text.encode("utf-8")) > 5000 else text
        result = client.detect_entities(Text=truncated, LanguageCode="en")
        entities = []
        for ent in result.get("Entities", []):
            entities.append({
                "type": ent.get("Type", ""),
                "text": ent.get("Text", ""),
                "score": round(ent.get("Score", 0), 3),
            })
        return entities
    except Exception as exc:
        logger.warning("Comprehend detect_entities failed: %s", exc)
        return []


def _comprehend_detect_key_phrases(text):
    """Use Amazon Comprehend to extract key phrases from text.

    Args:
        text: Text to analyze.

    Returns:
        list of key phrase strings.
    """
    try:
        client = boto3.client("comprehend")
        truncated = text[:4900] if len(text.encode("utf-8")) > 5000 else text
        result = client.detect_key_phrases(Text=truncated, LanguageCode="en")
        phrases = []
        for phrase in result.get("KeyPhrases", []):
            if phrase.get("Score", 0) > 0.7:
                phrases.append(phrase.get("Text", ""))
        return phrases
    except Exception as exc:
        logger.warning("Comprehend detect_key_phrases failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Sample transcript snippets for demo
# ---------------------------------------------------------------------------
SAMPLE_TRANSCRIPTS = {
    "NVDA": (
        "Thank you for joining NVIDIA's earnings call. We are incredibly excited "
        "about the demand we're seeing for our data center products. Revenue grew "
        "122% year-over-year, driven by unprecedented AI infrastructure spending. "
        "Our Hopper architecture continues to see strong adoption. However, we are "
        "monitoring supply chain constraints carefully. Gross margins expanded to "
        "75.3%, though we expect some normalization as we ramp new product lines. "
        "Looking ahead, we see continued strong demand but want to be measured in "
        "our guidance given macro uncertainties."
    ),
    "AAPL": (
        "Good afternoon. Apple delivered a solid quarter with Services revenue "
        "reaching an all-time high. iPhone revenue was slightly below expectations "
        "due to timing of new model launches. We're very optimistic about our AI "
        "strategy with Apple Intelligence rolling out across our ecosystem. Margins "
        "remain healthy at 46.2%. We're cautious about the China market where we "
        "saw some softness, but India continues to be a bright spot for growth."
    ),
    "MSFT": (
        "Microsoft Cloud surpassed $35 billion in quarterly revenue, up 22%. "
        "Azure growth accelerated to 31%, driven by AI workloads. We're seeing "
        "strong enterprise adoption of Copilot across our productivity suite. "
        "Operating margins improved 200 basis points. We remain confident in our "
        "AI strategy but acknowledge increased capital expenditure requirements "
        "for data center buildout will pressure free cash flow in the near term."
    ),
}

DEFAULT_TRANSCRIPT = (
    "The company reported mixed results this quarter. Revenue grew modestly "
    "while margins came under pressure from increased competition. Management "
    "expressed cautious optimism about the pipeline but acknowledged headwinds "
    "in the macro environment. Capital allocation remains focused on R&D "
    "investment and selective M&A opportunities."
)


# ---------------------------------------------------------------------------
# Bedrock helper
# ---------------------------------------------------------------------------
def _call_bedrock(prompt, max_tokens=1024, trace_id=None, generation_name=None):
    """Call Bedrock Claude with the given prompt.

    Args:
        prompt: The user prompt to send to the model.
        max_tokens: Maximum tokens in the response.
        trace_id: Optional Langfuse trace ID for generation logging.
        generation_name: Optional name for the Langfuse generation event.

    Returns:
        The text response from the model, or an error string on failure.
    """
    try:
        client = boto3.client("bedrock-runtime")
        gen_start = time.time()
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        gen_duration_ms = int((time.time() - gen_start) * 1000)
        resp_body = json.loads(response["body"].read())
        text = resp_body["content"][0]["text"]
        usage = resp_body.get("usage", {})

        if trace_id and generation_name:
            add_generation(
                trace_id, generation_name,
                model=BEDROCK_MODEL_ID,
                input_data=prompt,
                output_data=text,
                usage={
                    "promptTokens": usage.get("input_tokens", 0),
                    "completionTokens": usage.get("output_tokens", 0),
                },
            )

        return text
    except Exception as exc:
        logger.error("Bedrock call failed: %s", exc)
        return f"[LLM unavailable: {exc}]"


# ---------------------------------------------------------------------------
# Tool 1: Analyze Earnings Call Transcript
# ---------------------------------------------------------------------------
@tool
def analyze_transcript(ticker: str, text: str = "") -> dict:
    """Analyze an earnings call transcript for sentiment, themes, and management tone.

    Uses Amazon Comprehend for entity extraction and key phrase detection,
    combined with Bedrock Claude for deeper thematic analysis. If no text
    is provided, uses a sample transcript for the ticker.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA', 'AAPL', 'MSFT').
        text: Optional transcript text to analyze. Uses sample if empty.

    Returns:
        dict with sentiment analysis including themes, tone, guidance,
        Comprehend entities, and key phrases.
    """
    ticker = ticker.upper()
    transcript = text if text.strip() else SAMPLE_TRANSCRIPTS.get(ticker, DEFAULT_TRANSCRIPT)
    is_sample = not text.strip()

    # Amazon Comprehend analysis (Gap 11)
    comprehend_sentiment = _comprehend_detect_sentiment(transcript)
    comprehend_entities = _comprehend_detect_entities(transcript)
    comprehend_phrases = _comprehend_detect_key_phrases(transcript)

    default_prompt = (
        f"You are a senior equity research analyst specializing in earnings call "
        f"analysis. Analyze the following earnings call transcript excerpt for "
        f"{ticker}. Provide your analysis as JSON with these fields:\n"
        f"- overall_sentiment: Bullish, Neutral, or Bearish\n"
        f"- confidence: High, Medium, or Low\n"
        f"- key_themes: list of 3-5 key themes discussed\n"
        f"- management_tone: description of management's tone\n"
        f"- forward_guidance: Positive, Mixed, or Cautious\n"
        f"- guidance_details: one sentence on forward guidance\n"
        f"- notable_quotes: list of 1-2 notable phrases\n\n"
        f"Comprehend NLP results (use to enrich your analysis):\n"
        f"- Comprehend sentiment: {json.dumps(comprehend_sentiment)}\n"
        f"- Key entities: {json.dumps(comprehend_entities[:10])}\n"
        f"- Key phrases: {json.dumps(comprehend_phrases[:10])}\n\n"
        f"Transcript:\n{transcript}\n\n"
        f"Respond ONLY with valid JSON, no markdown."
    )
    prompt_template = get_prompt("sentiment-transcript-analysis", default_prompt)
    try:
        prompt = prompt_template.format(ticker=ticker, transcript=transcript)
    except (KeyError, IndexError):
        prompt = prompt_template

    analysis_text = _call_bedrock(prompt, generation_name="analyze_transcript")

    try:
        analysis = json.loads(analysis_text)
    except json.JSONDecodeError:
        analysis = {"raw_analysis": analysis_text}

    return {
        "ticker": ticker,
        "tool": "analyze_transcript",
        "is_sample_data": is_sample,
        "analysis": analysis,
        "comprehend": {
            "sentiment": comprehend_sentiment,
            "entities": comprehend_entities[:15],
            "key_phrases": comprehend_phrases[:15],
        },
    }


# ---------------------------------------------------------------------------
# Tool 2: Score News Sentiment
# ---------------------------------------------------------------------------
@tool
def score_news_sentiment(ticker: str) -> dict:
    """Score overall news sentiment for a stock ticker using Comprehend and Bedrock.

    Fetches recent news from the News Search MCP server, runs Amazon
    Comprehend sentiment detection on each article, then uses Bedrock
    Claude to synthesize an overall sentiment score.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA', 'AAPL', 'MSFT').

    Returns:
        dict with sentiment score, reasoning, news sources, and Comprehend results.
    """
    ticker = ticker.upper()
    news_data = _fetch_news(ticker)

    # Run Comprehend on news content (Gap 11)
    news_comprehend_results = []
    articles = news_data.get("articles", [])
    for article in articles[:5]:
        content = article.get("content", article.get("summary", ""))
        if content:
            sent = _comprehend_detect_sentiment(content)
            news_comprehend_results.append({
                "title": article.get("title", ""),
                "comprehend_sentiment": sent,
            })

    default_prompt = (
        f"You are a financial news sentiment analyst. Based on the following "
        f"recent news data for {ticker}, score the overall sentiment.\n\n"
        f"News data:\n{json.dumps(news_data, indent=2)}\n\n"
        f"Comprehend NLP results per article:\n{json.dumps(news_comprehend_results, indent=2)}\n\n"
        f"Provide your analysis as JSON with these fields:\n"
        f"- overall_sentiment: Bullish, Neutral, or Bearish\n"
        f"- sentiment_score: number from -1.0 (very bearish) to 1.0 (very bullish)\n"
        f"- reasoning: 2-3 sentence explanation\n"
        f"- key_drivers: list of 3 main sentiment drivers\n"
        f"- news_volume: High, Medium, or Low\n\n"
        f"Respond ONLY with valid JSON, no markdown."
    )
    prompt_template = get_prompt("sentiment-news-scoring", default_prompt)
    try:
        prompt = prompt_template.format(
            ticker=ticker, news_data=json.dumps(news_data, indent=2),
        )
    except (KeyError, IndexError):
        prompt = prompt_template

    analysis_text = _call_bedrock(prompt, generation_name="score_news_sentiment")

    try:
        analysis = json.loads(analysis_text)
    except json.JSONDecodeError:
        analysis = {"raw_analysis": analysis_text}

    return {
        "ticker": ticker,
        "tool": "score_news_sentiment",
        "news_source": "live" if news_data.get("source") == "news_api" else "fallback",
        "analysis": analysis,
        "comprehend_per_article": news_comprehend_results,
    }


def _fetch_news(ticker):
    """Fetch news from the News Search MCP server or return fallback data.

    Args:
        ticker: Stock ticker symbol.

    Returns:
        dict with news articles or fallback summary.
    """
    if NEWS_API_URL and NEWS_API_KEY:
        try:
            url = f"{NEWS_API_URL}/search_financial_news"
            payload = json.dumps({"query": f"{ticker} stock", "max_results": 5}).encode()
            req = urllib_request.Request(
                url, data=payload, method="POST",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": NEWS_API_KEY,
                },
            )
            with urllib_request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                data["source"] = "news_api"
                return data
        except (URLError, Exception) as exc:
            logger.warning("News API call failed, using fallback: %s", exc)

    return {
        "source": "fallback",
        "ticker": ticker,
        "summary": (
            f"Recent news for {ticker} includes analyst upgrades, quarterly "
            f"earnings expectations, and sector-level market commentary. "
            f"No major negative catalysts identified in recent coverage."
        ),
        "article_count": 0,
    }


# ---------------------------------------------------------------------------
# Tool 3: Detect Tone Shifts
# ---------------------------------------------------------------------------
@tool
def detect_tone_shifts(ticker: str, text: str = "") -> dict:
    """Detect tone shifts in management commentary or earnings call text.

    Identifies where management shifts between optimistic and cautious
    language, using Comprehend for key phrase extraction and Bedrock
    Claude for deeper tone analysis.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA', 'AAPL', 'MSFT').
        text: Optional text to analyze. Uses sample transcript if empty.

    Returns:
        dict with detected tone shifts, consistency assessment, and red flags.
    """
    ticker = ticker.upper()
    transcript = text if text.strip() else SAMPLE_TRANSCRIPTS.get(ticker, DEFAULT_TRANSCRIPT)
    is_sample = not text.strip()

    # Comprehend key phrases for context (Gap 11)
    comprehend_phrases = _comprehend_detect_key_phrases(transcript)

    default_prompt = (
        f"You are an expert in executive communication analysis. Analyze the "
        f"following text from {ticker} for tone shifts — places where the speaker "
        f"changes from optimistic to cautious or vice versa.\n\n"
        f"Key phrases detected by NLP: {json.dumps(comprehend_phrases[:10])}\n\n"
        f"Text:\n{transcript}\n\n"
        f"Provide your analysis as JSON with these fields:\n"
        f"- tone_shifts: list of objects, each with 'topic', 'from_tone', "
        f"'to_tone', and 'evidence' (quote from text)\n"
        f"- overall_consistency: High, Medium, or Low\n"
        f"- dominant_tone: Optimistic, Cautious, Neutral, or Mixed\n"
        f"- red_flags: list of any concerning language patterns (empty if none)\n\n"
        f"Respond ONLY with valid JSON, no markdown."
    )
    prompt_template = get_prompt("sentiment-tone-detection", default_prompt)
    try:
        prompt = prompt_template.format(ticker=ticker, transcript=transcript)
    except (KeyError, IndexError):
        prompt = prompt_template

    analysis_text = _call_bedrock(prompt, generation_name="detect_tone_shifts")

    try:
        analysis = json.loads(analysis_text)
    except json.JSONDecodeError:
        analysis = {"raw_analysis": analysis_text}

    return {
        "ticker": ticker,
        "tool": "detect_tone_shifts",
        "is_sample_data": is_sample,
        "analysis": analysis,
        "comprehend_key_phrases": comprehend_phrases[:10],
    }


# ---------------------------------------------------------------------------
# Tool 4: Aggregate Sentiment
# ---------------------------------------------------------------------------
@tool
def aggregate_sentiment(ticker: str) -> dict:
    """Generate a combined sentiment report by orchestrating all sentiment analysis tools.

    Runs transcript analysis, news sentiment scoring, and tone detection,
    optionally enriches with Salesforce analyst coverage data, then
    synthesizes a combined sentiment assessment using Bedrock Claude.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA', 'AAPL', 'MSFT').

    Returns:
        dict with combined sentiment report from all analyses plus CRM context.
    """
    ticker = ticker.upper()

    transcript_result = analyze_transcript(ticker=ticker)
    news_result = score_news_sentiment(ticker=ticker)
    tone_result = detect_tone_shifts(ticker=ticker)

    # Enrich with Salesforce analyst coverage (Gap 18)
    analyst_context = {}
    if _sf_client and _sf_client.is_configured():
        try:
            analyst_context = _sf_client.get_analyst_coverage(ticker)
        except Exception as exc:
            logger.warning("SF analyst coverage fetch failed for %s: %s", ticker, exc)

    combined_data = json.dumps({
        "transcript_analysis": transcript_result,
        "news_sentiment": news_result,
        "tone_shifts": tone_result,
        "analyst_coverage": analyst_context if analyst_context else "No CRM data available",
    }, indent=2)

    default_prompt = (
        f"You are a senior equity research analyst. Synthesize the following "
        f"sentiment analyses for {ticker} into a combined sentiment report.\n\n"
        f"Data:\n{combined_data}\n\n"
        f"Provide your synthesis as JSON with these fields:\n"
        f"- overall_sentiment: Bullish, Neutral, or Bearish\n"
        f"- confidence: High, Medium, or Low\n"
        f"- executive_summary: 2-3 sentence summary\n"
        f"- transcript_sentiment: one sentence\n"
        f"- news_sentiment: one sentence\n"
        f"- tone_assessment: one sentence\n"
        f"- catalysts: list of positive catalysts\n"
        f"- risks: list of negative risks\n"
        f"- recommendation: one sentence investment implication\n\n"
        f"Respond ONLY with valid JSON, no markdown."
    )
    prompt_template = get_prompt("sentiment-aggregate", default_prompt)
    try:
        prompt = prompt_template.format(ticker=ticker, combined_data=combined_data)
    except (KeyError, IndexError):
        prompt = prompt_template

    synthesis_text = _call_bedrock(prompt, generation_name="aggregate_sentiment")

    try:
        synthesis = json.loads(synthesis_text)
    except json.JSONDecodeError:
        synthesis = {"raw_synthesis": synthesis_text}

    return {
        "ticker": ticker,
        "tool": "aggregate_sentiment",
        "synthesis": synthesis,
        "analyst_coverage": analyst_context if analyst_context else None,
        "components": {
            "transcript": transcript_result,
            "news": news_result,
            "tone": tone_result,
        },
    }


# ---------------------------------------------------------------------------
# Strands Agent Instance (V2)
# ---------------------------------------------------------------------------
AGENT_SYSTEM_PROMPT = (
    "You are a senior sentiment analysis agent specializing in investment research. "
    "You have access to four tools: analyze_transcript (earnings call analysis), "
    "score_news_sentiment (news sentiment scoring), detect_tone_shifts (tone shift "
    "detection), and aggregate_sentiment (combined report from all three). "
    "When given a query, reason about which tools to use and synthesize the "
    "results into a clear sentiment assessment. You combine Amazon Comprehend "
    "NLP with Bedrock Claude analysis for richer insights."
)

_agent_instance = None


def _get_agent():
    """Lazily initialize the Strands Agent with BedrockModel.

    Returns:
        Agent instance, or None if Strands SDK is not available.
    """
    global _agent_instance
    if _agent_instance is not None:
        return _agent_instance

    if not STRANDS_AVAILABLE:
        logger.warning("Strands SDK not available — agent endpoint disabled")
        return None

    try:
        model = BedrockModel(
            model_id=BEDROCK_MODEL_ID,
            max_tokens=2048,
        )
        _agent_instance = Agent(
            model=model,
            tools=[analyze_transcript, score_news_sentiment, detect_tone_shifts, aggregate_sentiment],
            system_prompt=get_prompt("sentiment-analysis-agent-system", AGENT_SYSTEM_PROMPT),
        )
        logger.info("Sentiment Analysis Strands Agent initialized")
        return _agent_instance
    except Exception as exc:
        logger.error("Failed to initialize Strands Agent: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------
TOOL_MAP = {
    "analyze_transcript": analyze_transcript,
    "score_news_sentiment": score_news_sentiment,
    "detect_tone_shifts": detect_tone_shifts,
    "aggregate_sentiment": aggregate_sentiment,
}


def lambda_handler(event, context):
    """AWS Lambda entry point for the Sentiment Analysis Agent.

    Routes requests based on the path parameter:
    - /sentiment-analysis/.well-known/agent.json  — A2A AgentCard manifest
    - /sentiment-analysis/agent                    — A2A JSON-RPC (POST) or V2 NL (legacy)
    - /sentiment-analysis/<tool>                   — direct tool invocation (V2 compat)

    Every invocation creates a Langfuse trace.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response with JSON body.
    """
    logger.info("Event: %s", json.dumps(event))

    try:
        path = event.get("pathParameters", {}).get("proxy", "") or ""
        segments = [s for s in path.strip("/").split("/") if s]
        tool_name = segments[0] if segments else ""
        http_method = (
            event.get("httpMethod")
            or event.get("requestContext", {}).get("http", {}).get("method")
            or ""
        ).upper()

        # --- V3: A2A AgentCard discovery endpoint ---
        if ".well-known" in segments:
            from a2a_manifest import handler as manifest_handler
            return manifest_handler(event, context)

        body_raw = event.get("body") or ""
        body = {}
        body_parse_error = False
        if body_raw:
            try:
                body = json.loads(body_raw) if isinstance(body_raw, str) else dict(body_raw)
            except (json.JSONDecodeError, TypeError):
                body = {}
                body_parse_error = True

        # --- V3: A2A task endpoint ---
        if tool_name == "agent":
            if http_method == "POST" and (body_parse_error or (isinstance(body, dict) and body.get("jsonrpc") == "2.0")):
                from a2a_handler import handler as a2a_task_handler
                return a2a_task_handler(event, context)
            if http_method == "POST":
                return _handle_agent_request(body)
            if http_method == "GET":
                from a2a_manifest import handler as manifest_handler
                return manifest_handler(event, context)
            return _response(405, {"error": f"Method {http_method} not allowed on /agent"})

        # --- V2: Direct tool endpoints (backward compatible) ---
        ticker = (body.get("ticker") or "").upper() if isinstance(body, dict) else ""

        if not tool_name or tool_name not in TOOL_MAP:
            return _response(400, {
                "error": f"Unknown tool: '{tool_name}'",
                "available_tools": list(TOOL_MAP.keys()) + ["agent", ".well-known/agent.json"],
            })

        if not ticker:
            return _response(400, {"error": "Missing 'ticker' in request body."})

        trace_id = create_trace(
            f"sentiment-analysis-{tool_name}",
            input_data={"ticker": ticker, "tool": tool_name},
            metadata={"platform": "aws", "agent": "sentiment-analysis"},
        )

        kwargs = {"ticker": ticker}
        if tool_name in ("analyze_transcript", "detect_tone_shifts"):
            text = body.get("text", "")
            if text:
                kwargs["text"] = text

        start_time = time.time()
        result = TOOL_MAP[tool_name](**kwargs)
        duration_ms = int((time.time() - start_time) * 1000)

        add_span(
            trace_id, tool_name,
            input_data={"ticker": ticker},
            output_data=result,
            duration_ms=duration_ms,
            metadata={"tool": tool_name},
        )
        end_trace(trace_id, output=result, metadata={"duration_ms": duration_ms})

        return _response(200, result)

    except Exception as exc:
        logger.exception("Unhandled error")
        return _response(500, {"error": str(exc)})


def _handle_agent_request(body):
    """Handle the autonomous agent endpoint (V2).

    Receives a natural language query, passes it to the Strands Agent,
    which reasons about which tools to call and returns a synthesized result.

    Args:
        body: Parsed JSON request body with 'query' field.

    Returns:
        API Gateway proxy response with agent result.
    """
    query = body.get("query", "").strip()
    if not query:
        return _response(400, {
            "error": "Missing 'query' in request body.",
            "example": {"query": "What is the market sentiment for NVDA based on recent news and earnings?"},
        })

    trace_id = create_trace(
        "sentiment-analysis-agent",
        input_data={"query": query},
        metadata={"platform": "aws", "agent": "sentiment-analysis", "mode": "autonomous"},
    )

    agent = _get_agent()
    if agent is None:
        logger.warning("Agent unavailable — falling back to aggregate_sentiment")
        ticker = _extract_ticker_from_query(query)
        if ticker:
            result = aggregate_sentiment(ticker=ticker)
            end_trace(trace_id, output=result, metadata={"fallback": True})
            return _response(200, {
                "mode": "fallback",
                "message": "Strands SDK not available. Ran aggregate_sentiment directly.",
                "result": result,
            })
        return _response(503, {
            "error": "Agent not available and could not extract ticker from query.",
        })

    start_time = time.time()
    try:
        response = agent(query)
        duration_ms = int((time.time() - start_time) * 1000)

        result_text = str(response)

        add_span(
            trace_id, "agent_reasoning",
            input_data={"query": query},
            output_data=result_text,
            duration_ms=duration_ms,
            metadata={"mode": "autonomous"},
        )
        end_trace(trace_id, output=result_text, metadata={"duration_ms": duration_ms})

        return _response(200, {
            "mode": "agent",
            "query": query,
            "response": result_text,
        })

    except Exception as exc:
        logger.exception("Agent execution failed")
        end_trace(trace_id, output={"error": str(exc)})
        return _response(500, {"error": f"Agent execution failed: {exc}"})


def _extract_ticker_from_query(query):
    """Best-effort extraction of a ticker symbol from a natural language query.

    Args:
        query: Natural language query string.

    Returns:
        str: Extracted ticker or empty string.
    """
    known_tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "JPM", "V", "JNJ", "XOM", "TSLA"]
    query_upper = query.upper()
    for ticker in known_tickers:
        if ticker in query_upper:
            return ticker
    return ""


def _response(status_code, body):
    """Build an API Gateway proxy response.

    Args:
        status_code: HTTP status code.
        body: Response body (will be JSON-serialized).

    Returns:
        dict formatted as API Gateway proxy response.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }
