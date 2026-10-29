def classify_flow(observation, thresholds):
    jam_factor = observation.get("jamFactor")
    observed = observation.get("observedSpeed")
    free_flow = observation.get("freeFlowSpeed")
    traversability = observation.get("traversability")
    ratio = speed_ratio(observed, free_flow)

    if traversability == "reversibleNotRoutable":
        return {"congestionLevel": "unknown", "congestionMethod": "not-routable", "speedRatio": ratio}
    if traversability == "closed" or jam_factor == 10:
        return {"congestionLevel": "heavy", "congestionMethod": "provider-closure", "speedRatio": ratio}
    if isinstance(jam_factor, (int, float)) and 0 <= jam_factor <= 10:
        return {
            "congestionLevel": level_from_jam(jam_factor, thresholds["jamFactor"]),
            "congestionMethod": "provider-jam-factor",
            "speedRatio": ratio,
        }
    if ratio is None:
        return {"congestionLevel": "unknown", "congestionMethod": "insufficient-data", "speedRatio": None}
    return {
        "congestionLevel": level_from_ratio(ratio, thresholds["speedRatio"]),
        "congestionMethod": "speed-ratio",
        "speedRatio": ratio,
    }


def observation_basis(confidence):
    if not isinstance(confidence, (int, float)):
        return "unknown"
    if confidence > 0.7:
        return "realtime"
    if confidence > 0.5:
        return "historical"
    return "speed-limit"


def level_from_jam(jam_factor, bands):
    if jam_factor < bands["freeFlowBelow"]:
        return "free-flow"
    if jam_factor < bands["lightBelow"]:
        return "light"
    if jam_factor < bands["moderateBelow"]:
        return "moderate"
    return "heavy"


def level_from_ratio(ratio, bands):
    if ratio < bands["heavyBelow"]:
        return "heavy"
    if ratio < bands["moderateBelow"]:
        return "moderate"
    if ratio < bands["lightBelow"]:
        return "light"
    return "free-flow"


def speed_ratio(observed, free_flow):
    if not isinstance(observed, (int, float)) or not isinstance(free_flow, (int, float)):
        return None
    if free_flow <= 0 or observed < 0:
        return None
    return round(observed / free_flow, 3)
