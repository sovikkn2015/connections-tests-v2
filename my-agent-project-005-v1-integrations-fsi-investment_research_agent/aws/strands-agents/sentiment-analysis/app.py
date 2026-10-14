"""
Sentiment Analysis Agent — Lambda Handler

Provides sentiment analysis tools for investment research:
    POST /sentiment-analysis/analyze_transcript   — Earnings call transcript sentiment
    POST /sentiment-analysis/score_news_sentiment  — News sentiment scoring
    POST /sentiment-analysis/detect_tone_shifts    — Tone shift detection in text
    POST /sentiment-analysis/aggregate_sentiment   — Combined sentiment report

All tools use Bedrock Claude Sonnet 4 for NLP analysis.
No external dependencies beyond boto3 (included in Lambda runtime).
"""

import json
import os
import logging
import time
import boto3
from urllib import request as urllib_request
from urllib.error import URLError
from langfuse_wrapper import (
    create_trace, add_span, add_generation, end_trace, get_prompt, is_configured,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
)
NEWS_API_URL = os.environ.get("NEWS_API_URL", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")

# ---------------------------------------------------------------------------
# Sample transcript snippets for demo (used when no text is provided)
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
    """Call Bedrock Claude Sonnet 4 with the given prompt.

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

        # Log generation to Langfuse
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
def analyze_transcript(ticker, text=None, _trace_id=None):
    """Analyze earnings call transcript text for sentiment.

    Uses Bedrock Claude to identify key themes, management tone, and
    forward guidance sentiment. If no text is provided, uses a hardcoded
    sample transcript snippet for the ticker.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA').
        text: Optional transcript text to analyze.
        _trace_id: Internal trace ID for Langfuse (set by lambda_handler).

    Returns:
        dict with sentiment analysis including themes, tone, and guidance.
    """
    ticker = ticker.upper()
    transcript = text if text else SAMPLE_TRANSCRIPTS.get(ticker, DEFAULT_TRANSCRIPT)
    is_sample = text is None or text.strip() == ""

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
        f"Transcript:\n{transcript}\n\n"
        f"Respond ONLY with valid JSON, no markdown."
    )
    prompt_template = get_prompt("sentiment-transcript-analysis", default_prompt)
    try:
        prompt = prompt_template.format(ticker=ticker, transcript=transcript)
    except (KeyError, IndexError):
        prompt = prompt_template

    analysis_text = _call_bedrock(
        prompt, trace_id=_trace_id, generation_name="analyze_transcript",
    )

    try:
        analysis = json.loads(analysis_text)
    except json.JSONDecodeError:
        analysis = {"raw_analysis": analysis_text}

    return {
        "ticker": ticker,
        "tool": "analyze_transcript",
        "is_sample_data": is_sample,
        "analysis": analysis,
    }


# ---------------------------------------------------------------------------
# Tool 2: Score News Sentiment
# ---------------------------------------------------------------------------
def score_news_sentiment(ticker, _trace_id=None):
    """Score overall news sentiment for a ticker.

    Attempts to call the News Search MCP server to get recent news, then
    uses Bedrock Claude to score overall sentiment. Falls back to a
    hardcoded summary if the news API is unavailable.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA').
        _trace_id: Internal trace ID for Langfuse (set by lambda_handler).

    Returns:
        dict with sentiment score, reasoning, and news sources.
    """
    ticker = ticker.upper()
    news_data = _fetch_news(ticker)

    default_prompt = (
        f"You are a financial news sentiment analyst. Based on the following "
        f"recent news data for {ticker}, score the overall sentiment.\n\n"
        f"News data:\n{json.dumps(news_data, indent=2)}\n\n"
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

    analysis_text = _call_bedrock(
        prompt, trace_id=_trace_id, generation_name="score_news_sentiment",
    )

    try:
        analysis = json.loads(analysis_text)
    except json.JSONDecodeError:
        analysis = {"raw_analysis": analysis_text}

    return {
        "ticker": ticker,
        "tool": "score_news_sentiment",
        "news_source": "live" if news_data.get("source") == "news_api" else "fallback",
        "analysis": analysis,
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
def detect_tone_shifts(ticker, text=None, _trace_id=None):
    """Analyze text for tone shifts in management commentary.

    Identifies where management shifts between optimistic and cautious
    language, e.g. 'optimistic about revenue but cautious on margins'.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA').
        text: Optional text to analyze. Uses sample transcript if not provided.
        _trace_id: Internal trace ID for Langfuse (set by lambda_handler).

    Returns:
        dict with detected tone shifts and analysis.
    """
    ticker = ticker.upper()
    transcript = text if text else SAMPLE_TRANSCRIPTS.get(ticker, DEFAULT_TRANSCRIPT)
    is_sample = text is None or text.strip() == ""

    default_prompt = (
        f"You are an expert in executive communication analysis. Analyze the "
        f"following text from {ticker} for tone shifts — places where the speaker "
        f"changes from optimistic to cautious or vice versa.\n\n"
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

    analysis_text = _call_bedrock(
        prompt, trace_id=_trace_id, generation_name="detect_tone_shifts",
    )

    try:
        analysis = json.loads(analysis_text)
    except json.JSONDecodeError:
        analysis = {"raw_analysis": analysis_text}

    return {
        "ticker": ticker,
        "tool": "detect_tone_shifts",
        "is_sample_data": is_sample,
        "analysis": analysis,
    }


# ---------------------------------------------------------------------------
# Tool 4: Aggregate Sentiment
# ---------------------------------------------------------------------------
def aggregate_sentiment(ticker, _trace_id=None):
    """Orchestrate all sentiment tools into a combined sentiment report.

    Runs transcript analysis, news sentiment scoring, and tone detection,
    then synthesizes a combined sentiment assessment.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA').
        _trace_id: Internal trace ID for Langfuse (set by lambda_handler).

    Returns:
        dict with combined sentiment report from all three analyses.
    """
    ticker = ticker.upper()

    transcript_result = analyze_transcript(ticker, _trace_id=_trace_id)
    news_result = score_news_sentiment(ticker, _trace_id=_trace_id)
    tone_result = detect_tone_shifts(ticker, _trace_id=_trace_id)

    combined_data = json.dumps({
        "transcript_analysis": transcript_result,
        "news_sentiment": news_result,
        "tone_shifts": tone_result,
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

    synthesis_text = _call_bedrock(
        prompt, trace_id=_trace_id, generation_name="aggregate_sentiment",
    )

    try:
        synthesis = json.loads(synthesis_text)
    except json.JSONDecodeError:
        synthesis = {"raw_synthesis": synthesis_text}

    return {
        "ticker": ticker,
        "tool": "aggregate_sentiment",
        "synthesis": synthesis,
        "components": {
            "transcript": transcript_result,
            "news": news_result,
            "tone": tone_result,
        },
    }


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

    Routes requests based on the path parameter to the appropriate tool.
    Every invocation creates a Langfuse trace. All Bedrock LLM calls
    produce generation events in the trace.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response with JSON body.
    """
    logger.info("Event: %s", json.dumps(event))

    try:
        path = event.get("pathParameters", {}).get("proxy", "")
        tool_name = path.strip("/").split("/")[0] if path else ""

        body = json.loads(event.get("body", "{}") or "{}")
        ticker = body.get("ticker", "").upper()

        if not tool_name or tool_name not in TOOL_MAP:
            return _response(400, {
                "error": f"Unknown tool: '{tool_name}'",
                "available_tools": list(TOOL_MAP.keys()),
            })

        if not ticker:
            return _response(400, {"error": "Missing 'ticker' in request body."})

        # --- Langfuse trace ---
        trace_id = create_trace(
            f"sentiment-analysis-{tool_name}",
            input_data={"ticker": ticker, "tool": tool_name},
            metadata={"platform": "aws", "agent": "sentiment-analysis"},
        )

        kwargs = {"ticker": ticker, "_trace_id": trace_id}
        if tool_name in ("analyze_transcript", "detect_tone_shifts"):
            text = body.get("text", "")
            if text:
                kwargs["text"] = text

        start_time = time.time()
        result = TOOL_MAP[tool_name](**kwargs)
        duration_ms = int((time.time() - start_time) * 1000)

        # Log tool execution span
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
