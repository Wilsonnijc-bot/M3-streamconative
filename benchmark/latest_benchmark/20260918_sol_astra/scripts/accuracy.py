"""Benchmark-owned exact-choice scoring and aggregate accuracy."""

import re


OPTION_PATTERN = re.compile(r'^\s*([A-E])\b')


def predicted_option(answer):
    match = OPTION_PATTERN.match(answer or '')
    return match.group(1) if match else None


def score_answer(answer, ground_truth):
    prediction = predicted_option(answer)
    return {
        'prediction': prediction,
        'correct': prediction == ground_truth,
        'evaluator': 'leading option letter exact match; missing letter is incorrect',
    }


def summarize(records):
    records = list(records)
    correct = sum(bool(record['correct']) for record in records)
    return {
        'correct': correct,
        'total': len(records),
        'accuracy': correct / len(records) if records else None,
    }
