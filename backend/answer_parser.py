# answer_parser.py

import json
import re
from typing import Optional
from typing_extensions import TypedDict

class ChartData(TypedDict):
    type: str
    labels: list[str]
    values: list[float]
    unit: str

class ParsedAnswer(TypedDict):
    headline: str
    paragraph: str
    chart_data: Optional[ChartData]
    uncertainty: bool
    needs_clarification: bool
    followup_questions: list

def parse_agent_output(raw_text: str) -> ParsedAnswer:
    text = raw_text.strip()

    # Detect clarification responses (agent asking the user a question)
    needs_clarification = text.endswith("?") and len(text) < 300

    # Extract follow-up questions (must happen before headline/paragraph split)
    followup_questions: list = []
    followup_match = re.search(r'^FOLLOWUP:\s*(\[.*?\])\s*$', text, re.MULTILINE)
    if followup_match:
        try:
            parsed = json.loads(followup_match.group(1))
            if isinstance(parsed, list):
                followup_questions = [q for q in parsed if isinstance(q, str) and q.strip()][:3]
        except (json.JSONDecodeError, ValueError):
            followup_questions = []
        text = text[:followup_match.start()] + text[followup_match.end():]
        text = text.strip()

    # Extract chart JSON block
    chart_data = None
    chart_match = re.search(r'\{"chart":\s*true.*?\}', text, re.DOTALL)
    if chart_match:
        try:
            raw_chart = json.loads(chart_match.group())
            labels = raw_chart.get("labels", [])
            values = raw_chart.get("values", [])
            unit = raw_chart.get("unit", "")
            chart_type = raw_chart.get("type", "line")
            if chart_type not in ("line", "bar"):
                chart_type = "line"
            # Validate types before accepting chart data
            if (isinstance(labels, list) and isinstance(values, list)
                    and isinstance(unit, str)
                    and all(isinstance(v, (int, float)) for v in values)):
                chart_data = {"type": chart_type, "labels": labels, "values": values, "unit": unit}
        except json.JSONDecodeError:
            chart_data = None
        text = text[:chart_match.start()] + text[chart_match.end():]

    # Detect uncertainty flag
    uncertainty = "UNCERTAIN:" in text
    text = re.sub(r"UNCERTAIN:.*", "", text).strip()

    # Parse labeled format: HEADLINE: ... PARAGRAPH: ...
    headline_match = re.search(r'HEADLINE:\s*(.+?)(?=\nPARAGRAPH:|\s+PARAGRAPH:|$)', text, re.DOTALL)
    paragraph_match = re.search(r'PARAGRAPH:\s*(.+?)(?=\nFOLLOWUP:|\nHEADLINE:|\{"chart"|$)', text, re.DOTALL)

    if headline_match:
        headline = headline_match.group(1).strip().replace("\n", " ")
        paragraph = paragraph_match.group(1).strip().replace("\n", " ") if paragraph_match else ""
    else:
        # Fall back to sentence split for unlabeled output
        sentences = text.split(". ", 1)
        headline = sentences[0].strip()
        if not headline.endswith(".") and not headline.endswith("?") and not headline.endswith("!"):
            headline += "."
        paragraph = sentences[1].replace("\n", " ").strip() if len(sentences) > 1 else ""

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
        followup_questions=followup_questions,
    )
