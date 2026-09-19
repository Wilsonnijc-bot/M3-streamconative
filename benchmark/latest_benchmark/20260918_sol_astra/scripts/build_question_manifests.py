#!/usr/bin/env python3
"""Normalize supplied Jake and AEA question schedules without changing their times."""
import argparse
import json
from pathlib import Path


def clock_seconds(value):
    value = str(value).zfill(8)
    if len(value) != 8 or not value.isdigit():
        raise ValueError(f"Invalid Jake clock time: {value}")
    hours, minutes, seconds, centiseconds = (int(value[:2]), int(value[2:4]),
                                              int(value[4:6]), int(value[6:]))
    if hours > 23 or minutes > 59 or seconds > 59:
        raise ValueError(f"Invalid Jake clock time: {value}")
    return hours * 3600 + minutes * 60 + seconds + centiseconds / 100


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jake-qa", type=Path, required=True)
    parser.add_argument("--aea-schedule", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    jake = json.loads(args.jake_qa.read_text(encoding="utf-8"))
    day1 = sorted((row for row in jake if row.get("query_time", {}).get("date") == "DAY1"),
                  key=lambda row: clock_seconds(row["query_time"]["time"]))
    if len(day1) != 102:
        raise ValueError(f"Expected all 102 Jake Day 1 questions, got {len(day1)}")
    jake_rows = []
    for row in day1:
        answer = row["answer"]
        options = {letter: row[f"choice_{letter.lower()}"] for letter in "ABCD"}
        if answer not in options:
            raise ValueError(f"Invalid Jake answer for {row['ID']}")
        jake_rows.append(dict(dataset="jake", question_id=str(row["ID"]),
            question=row["question"], ground_truth=answer,
            query_timestamp=clock_seconds(row["query_time"]["time"]),
            source_annotation={"file": args.jake_qa.name, "ID": row["ID"],
                               "query_time": row["query_time"]}, options=options))
    aea = json.loads(args.aea_schedule.read_text(encoding="utf-8"))
    aea_rows = []
    for row in aea["questions"]:
        answer = row["answer"]
        options = {chr(65 + i): value for i, value in enumerate(row["options"])}
        timestamp = float(row["ask_global_s"])
        if answer not in options or timestamp <= float(row["evidence_global_s"]):
            raise ValueError(f"Invalid/noncausal AEA question {row['question_id']}")
        aea_rows.append(dict(dataset="aea", question_id=row["question_id"],
            question=row["question"], ground_truth=answer, query_timestamp=timestamp,
            source_annotation={"file": aea["source"], "source_video": row["source_video"],
                               "evidence_global_s": row["evidence_global_s"],
                               "schedule_file": args.aea_schedule.name,
                               "schedule_policy": aea["schedule_policy"]}, options=options))
    aea_rows.sort(key=lambda r:(r["query_timestamp"],r["question_id"]))
    aea_rows=[aea_rows[(i*(len(aea_rows)-1))//999] for i in range(1000)]
    for name, rows, basis in (("jake", jake_rows, "DAY1 HHMMSScc wall clock converted to seconds since midnight"),
                              ("aea", aea_rows, "derived causal seconds in assembled AEA stream")):
        if len({r["question_id"] for r in rows}) != len(rows):
            raise ValueError(f"Duplicate {name} question ID")
        write(args.output / f"{name}_questions.json", {"dataset": name,
              "timestamp_basis": basis, "questions": rows})
        print(f"{name}: {len(rows)} questions", flush=True)


if __name__ == "__main__":
    main()
