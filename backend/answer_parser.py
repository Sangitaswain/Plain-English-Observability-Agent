# answer_parser.py

import json
import re
from typing import Optional
from typing_extensions import TypedDict

class ChartData(TypedDict):
    labels: list[str]
    values: list[float]
    unit: str

class ParsedAnswer(TypedDict):
    headline: str
    paragraph: str
    chart_data: Optional[ChartData]
    uncertainty: bool
    needs_clarification: bool

def parse_agent_output(raw_text: str) -> ParsedAnswer:
    text = raw_text.strip()

    # Detect clarification responses (agent asking the user a question)
    needs_clarification = text.endswith("?") and len(text) < 300

    # Extract chart JSON block
    chart_data = None
    chart_match = re.search(r'\{"chart":\s*true.*?\}', text, re.DOTALL)
    if chart_match:
        try:
            raw_chart = json.loads(chart_match.group())
            labels = raw_chart.get("labels", [])
            values = raw_chart.get("values", [])
            unit = raw_chart.get("unit", "")
            # Validate types before accepting chart data
            if (isinstance(labels, list) and isinstance(values, list)
                    and isinstance(unit, str)
                    and all(isinstance(v, (int, float)) for v in values)):
                chart_data = {"labels": labels, "values": values, "unit": unit}
        except json.JSONDecodeError:
            chart_data = None
        text = text[:chart_match.start()] + text[chart_match.end():]

    # Detect uncertainty flag
    uncertainty = "UNCERTAIN:" in text
    text = re.sub(r"UNCERTAIN:.*", "", text).strip()

    # Split into headline (first sentence) and paragraph (rest)
    sentences = text.split(". ", 1)
    headline = sentences[0].strip()
    if not headline.endswith(".") and not headline.endswith("?") and not headline.endswith("!"):
        headline += "."
    paragraph = sentences[1].strip() if len(sentences) > 1 else ""

    # Guard: never return empty headline
    if not headline or headline == ".":
        headline = "I wasn't able to produce an answer. Please try again."
        paragraph = ""

    return ParsedAnswer(
        headline=headline[:300],
        paragraph=paragraph[:1000],
        chart_data=chart_data,
        uncertainty=uncertainty,
        needs_clarification=needs_clarification,
    )
