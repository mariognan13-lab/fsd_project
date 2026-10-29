LEVELS = ["free-flow", "light", "moderate", "heavy", "unknown"]


def summarize_traffic(payload):
    features = payload.get("features") or []
    distribution = {level: 0 for level in LEVELS}
    speed_sum = speed_count = delay_sum = delay_count = congested = 0
    for feature in features:
        level = feature.get("congestionLevel")
        if level not in distribution:
            level = "unknown"
        distribution[level] += 1
        if level in {"moderate", "heavy"}:
            congested += 1
        eligible = feature.get("observationBasis") in {"realtime", "historical"}
        speed = feature.get("observedSpeed")
        if eligible and isinstance(speed, (int, float)):
            speed_sum += speed
            speed_count += 1
        delay = feature.get("delay")
        if eligible and feature.get("delayEstimated") is True and isinstance(delay, (int, float)):
            delay_sum += delay
            delay_count += 1
    notes = [
        "Counts include every segment returned for this map area.",
        "Congested segments are those classified as moderate or heavy.",
        "Average speed uses segments whose provider confidence indicates realtime or historical speeds. Speed-limit fallbacks are excluded.",
        "Average delay uses the same segments. Delay is estimated from length and speeds when the provider does not send a delay field, and it is omitted when a speed is missing or zero.",
    ]
    if not features:
        notes.append("No road segments were returned for this area, so averages are not calculated.")
    elif speed_count == 0:
        notes.append("No eligible observed speeds were available, so average speed is not calculated.")
    return {
        "source": payload.get("source"),
        "fetchedAt": payload.get("fetchedAt"),
        "observedAt": payload.get("observedAt"),
        "stale": bool(payload.get("stale")),
        "staleReason": payload.get("staleReason"),
        "bbox": payload.get("bbox"),
        "units": payload.get("units"),
        "attribution": payload.get("attribution"),
        "omittedCount": payload.get("omittedCount"),
        "coverageNote": payload.get("coverageNote"),
        "segmentCount": len(features),
        "congestedCount": congested,
        "distribution": distribution,
        "averageObservedSpeedKmh": round(speed_sum / speed_count, 1) if speed_count else None,
        "averageDelaySeconds": round(delay_sum / delay_count) if delay_count else None,
        "speedSampleCount": speed_count,
        "delaySampleCount": delay_count,
        "notes": notes,
    }
