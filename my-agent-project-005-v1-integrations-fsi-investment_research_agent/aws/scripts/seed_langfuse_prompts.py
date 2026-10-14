#!/usr/bin/env python3
"""
Seed Langfuse prompt registry with the 5 agent prompts.

Reads credentials from environment variables:
    LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY

Usage:
    export LANGFUSE_HOST=https://us.cloud.langfuse.com
    export LANGFUSE_PUBLIC_KEY=pk-lf-...
    export LANGFUSE_SECRET_KEY=sk-lf-...
    python3 seed_langfuse_prompts.py
"""

import json
import os
import sys
import base64
from urllib import request as urllib_request
from urllib.error import URLError

HOST = os.environ.get("LANGFUSE_HOST", "")
PK = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
SK = os.environ.get("LANGFUSE_SECRET_KEY", "")

if not all([HOST, PK, SK]):
    print("ERROR: Set LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY")
    sys.exit(1)

AUTH = "Basic " + base64.b64encode(f"{PK}:{SK}".encode()).decode()

PROMPTS = {
    "financial-analysis-fair-value": (
        "You are a senior equity research analyst. Based on the following "
        "financial analysis data for {ticker}, write a concise fair value "
        "summary with:\n"
        "1. A one-paragraph executive summary\n"
        "2. Bull case (optimistic scenario with price target)\n"
        "3. Base case (most likely scenario with price target)\n"
        "4. Bear case (pessimistic scenario with price target)\n"
        "5. Key risks\n\n"
        "Analysis data:\n{analysis_context}"
    ),
    "sentiment-transcript-analysis": (
        "You are a senior equity research analyst specializing in earnings call "
        "analysis. Analyze the following earnings call transcript excerpt for "
        "{ticker}. Provide your analysis as JSON with these fields:\n"
        "- overall_sentiment: Bullish, Neutral, or Bearish\n"
        "- confidence: High, Medium, or Low\n"
        "- key_themes: list of 3-5 key themes discussed\n"
        "- management_tone: description of management's tone\n"
        "- forward_guidance: Positive, Mixed, or Cautious\n"
        "- guidance_details: one sentence on forward guidance\n"
        "- notable_quotes: list of 1-2 notable phrases\n\n"
        "Transcript:\n{transcript}\n\n"
        "Respond ONLY with valid JSON, no markdown."
    ),
    "sentiment-news-scoring": (
        "You are a financial news sentiment analyst. Based on the following "
        "recent news data for {ticker}, score the overall sentiment.\n\n"
        "News data:\n{news_data}\n\n"
        "Provide your analysis as JSON with these fields:\n"
        "- overall_sentiment: Bullish, Neutral, or Bearish\n"
        "- sentiment_score: number from -1.0 (very bearish) to 1.0 (very bullish)\n"
        "- reasoning: 2-3 sentence explanation\n"
        "- key_drivers: list of 3 main sentiment drivers\n"
        "- news_volume: High, Medium, or Low\n\n"
        "Respond ONLY with valid JSON, no markdown."
    ),
    "sentiment-tone-detection": (
        "You are an expert in executive communication analysis. Analyze the "
        "following text from {ticker} for tone shifts — places where the speaker "
        "changes from optimistic to cautious or vice versa.\n\n"
        "Text:\n{transcript}\n\n"
        "Provide your analysis as JSON with these fields:\n"
        "- tone_shifts: list of objects, each with 'topic', 'from_tone', "
        "'to_tone', and 'evidence' (quote from text)\n"
        "- overall_consistency: High, Medium, or Low\n"
        "- dominant_tone: Optimistic, Cautious, Neutral, or Mixed\n"
        "- red_flags: list of any concerning language patterns (empty if none)\n\n"
        "Respond ONLY with valid JSON, no markdown."
    ),
    "sentiment-aggregate": (
        "You are a senior equity research analyst. Synthesize the following "
        "sentiment analyses for {ticker} into a combined sentiment report.\n\n"
        "Data:\n{combined_data}\n\n"
        "Provide your synthesis as JSON with these fields:\n"
        "- overall_sentiment: Bullish, Neutral, or Bearish\n"
        "- confidence: High, Medium, or Low\n"
        "- executive_summary: 2-3 sentence summary\n"
        "- transcript_sentiment: one sentence\n"
        "- news_sentiment: one sentence\n"
        "- tone_assessment: one sentence\n"
        "- catalysts: list of positive catalysts\n"
        "- risks: list of negative risks\n"
        "- recommendation: one sentence investment implication\n\n"
        "Respond ONLY with valid JSON, no markdown."
    ),
}


def create_prompt(name, prompt_text):
    """Create or update a prompt in Langfuse."""
    url = f"{HOST.rstrip('/')}/api/public/v2/prompts"
    data = json.dumps({
        "name": name,
        "prompt": prompt_text,
        "labels": ["production"],
        "type": "text",
    }).encode("utf-8")
    req = urllib_request.Request(
        url, data=data, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": AUTH,
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=10) as resp:
            print(f"  ✓ {name} — HTTP {resp.status}")
    except URLError as exc:
        print(f"  ✗ {name} — {exc}")


if __name__ == "__main__":
    print(f"Seeding {len(PROMPTS)} prompts to {HOST} ...")
    for name, text in PROMPTS.items():
        create_prompt(name, text)
    print("Done.")
