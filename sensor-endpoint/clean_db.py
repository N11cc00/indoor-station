#!/usr/bin/env python3
"""Clean sensor DB entries that look like short-span spikes.

The DB stores temperature/humidity values with factor 10.
So a threshold of 200 means 20.0 units in real values.
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_ts(timestamp: str) -> datetime:
	"""Parse timestamp values from SQLite rows."""
	try:
		return datetime.fromisoformat(timestamp)
	except ValueError:
		# Fallback for common SQLite datetime layout.
		return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")


def _seconds_between(ts_a: str, ts_b: str) -> float:
	return abs((_parse_ts(ts_b) - _parse_ts(ts_a)).total_seconds())


def find_spike_candidates(
	conn: sqlite3.Connection,
	threshold: float = 200,
	max_gap_seconds: float = 300,
) -> list[dict[str, Any]]:
	"""Return rows that look like local spikes compared to their neighbors.

	A row is considered a candidate when it differs from both adjacent rows by
	more than `threshold` (absolute value) and both time gaps are <=
	`max_gap_seconds`.
	"""
	cur = conn.cursor()
	cur.execute(
		"""
		SELECT id, timestamp, temperature, humidity
		FROM sensor_data
		ORDER BY timestamp ASC
		"""
	)
	rows = cur.fetchall()

	candidates: list[dict[str, Any]] = []
	if len(rows) < 3:
		return candidates

	for idx in range(1, len(rows) - 1):
		prev = rows[idx - 1]
		curr = rows[idx]
		next_row = rows[idx + 1]

		prev_id, prev_ts, prev_temp, prev_hum = prev
		curr_id, curr_ts, curr_temp, curr_hum = curr
		next_id, next_ts, next_temp, next_hum = next_row

		left_gap_seconds = _seconds_between(prev_ts, curr_ts)
		right_gap_seconds = _seconds_between(curr_ts, next_ts)
		temp_jump_left = curr_temp - prev_temp
		temp_jump_right = curr_temp - next_temp
		hum_jump_left = curr_hum - prev_hum
		hum_jump_right = curr_hum - next_hum

		if (
			left_gap_seconds <= max_gap_seconds
			and right_gap_seconds <= max_gap_seconds
			and (
				(abs(temp_jump_left) > threshold and abs(temp_jump_right) > threshold)
				or (abs(hum_jump_left) > threshold and abs(hum_jump_right) > threshold)
			)
		):
			reasons: list[str] = []
			if abs(temp_jump_left) > threshold and abs(temp_jump_right) > threshold:
				reasons.append(
					f"temperature local spike {prev_temp:+.1f} -> {curr_temp:+.1f} -> {next_temp:+.1f}"
				)
			if abs(hum_jump_left) > threshold and abs(hum_jump_right) > threshold:
				reasons.append(
					f"humidity local spike {prev_hum:+.1f} -> {curr_hum:+.1f} -> {next_hum:+.1f}"
				)

			candidates.append(
				{
					"id": curr_id,
					"timestamp": curr_ts,
					"temperature": curr_temp,
					"humidity": curr_hum,
					"prev_id": prev_id,
					"prev_timestamp": prev_ts,
					"prev_temperature": prev_temp,
					"prev_humidity": prev_hum,
					"next_id": next_id,
					"next_timestamp": next_ts,
					"next_temperature": next_temp,
					"next_humidity": next_hum,
					"left_gap_seconds": left_gap_seconds,
					"right_gap_seconds": right_gap_seconds,
					"temp_jump_left": temp_jump_left,
					"temp_jump_right": temp_jump_right,
					"hum_jump_left": hum_jump_left,
					"hum_jump_right": hum_jump_right,
					"reason": "; ".join(reasons),
				}
			)

	return candidates


def show_spike_candidates(
	candidates: list[dict[str, Any]],
	factor: float = 10.0,
	limit: int | None = 50,
) -> None:
	"""Print tentative spike candidates before deletion.

	`factor` converts stored values into display values.
	"""
	if not candidates:
		print("No spike candidates found.")
		return

	display_count = len(candidates) if limit is None else min(len(candidates), limit)
	print(f"Found {len(candidates)} spike candidates. Showing {display_count}:")
	print("-" * 120)

	for c in candidates[:display_count]:
		temp_left = c["prev_temperature"] / factor
		temp_mid = c["temperature"] / factor
		temp_right = c["next_temperature"] / factor
		hum_left = c["prev_humidity"] / factor
		hum_mid = c["humidity"] / factor
		hum_right = c["next_humidity"] / factor
		temp_jump_left = c["temp_jump_left"] / factor
		temp_jump_right = c["temp_jump_right"] / factor
		hum_jump_left = c["hum_jump_left"] / factor
		hum_jump_right = c["hum_jump_right"] / factor

		print(
			f"id={c['id']} at {c['timestamp']} | "
			f"temp {temp_left:.1f} -> {temp_mid:.1f} -> {temp_right:.1f} "
			f"({temp_jump_left:+.1f}, {temp_jump_right:+.1f}) | "
			f"hum {hum_left:.1f} -> {hum_mid:.1f} -> {hum_right:.1f} "
			f"({hum_jump_left:+.1f}, {hum_jump_right:+.1f}) | "
			f"dt={c['left_gap_seconds']:.1f}s/{c['right_gap_seconds']:.1f}s | "
			f"{c['reason']}"
		)

	if limit is not None and len(candidates) > limit:
		print(f"... {len(candidates) - limit} more not shown")


def delete_spike_candidates(conn: sqlite3.Connection, candidates: list[dict[str, Any]]) -> int:
	"""Delete candidate rows by id and return number of deleted rows."""
	if not candidates:
		return 0

	ids = [c["id"] for c in candidates]
	placeholders = ",".join("?" for _ in ids)
	cur = conn.cursor()
	cur.execute(f"DELETE FROM sensor_data WHERE id IN ({placeholders})", ids)
	conn.commit()
	return cur.rowcount


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Find and optionally delete temperature/humidity spike rows from sensor SQLite DB"
	)
	parser.add_argument(
		"--db-path",
		default="instance/sensor_data.db",
		help="Path to SQLite DB (default: instance/sensor_data.db)",
	)
	parser.add_argument(
		"--threshold",
		type=float,
		default=200,
		help="Spike threshold in stored units (default: 200 = 20.0 real units)",
	)
	parser.add_argument(
		"--max-gap-seconds",
		type=float,
		default=300,
		help="Maximum time span in seconds to consider a jump a spike (default: 300)",
	)
	parser.add_argument(
		"--preview-limit",
		type=int,
		default=50,
		help="How many candidates to print in preview (default: 50)",
	)
	parser.add_argument(
		"--apply",
		action="store_true",
		help="Actually delete the found candidates. Without this flag it is dry-run.",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	db_path = Path(args.db_path)

	if not db_path.exists():
		raise SystemExit(f"DB not found: {db_path}")

	conn = sqlite3.connect(str(db_path))
	try:
		candidates = find_spike_candidates(
			conn,
			threshold=args.threshold,
			max_gap_seconds=args.max_gap_seconds,
		)
		show_spike_candidates(candidates, factor=10.0, limit=args.preview_limit)

		if args.apply:
			deleted = delete_spike_candidates(conn, candidates)
			print(f"Deleted {deleted} rows.")
		else:
			print("Dry-run only. Use --apply to delete these rows.")
	finally:
		conn.close()


if __name__ == "__main__":
	main()
