import hashlib
import math

from .here import TRAFFIC_UNITS

LEVELS = ("free-flow", "light", "moderate", "heavy")
SPEED_RATIOS = {"free-flow": 0.94, "light": 0.76, "moderate": 0.55, "heavy": 0.28}


class SeedTrafficProvider:
    """Repeatable, clearly simulated traffic lines generated inside a requested bbox."""

    id = "seed"

    def fetch_flow(self, bbox):
        west, south, east, north = (bbox[key] for key in ("west", "south", "east", "north"))
        width, height = east - west, north - south
        seed = int(hashlib.sha256(",".join(f"{bbox[key]:.5f}" for key in ("west", "south", "east", "north")).encode()).hexdigest()[:8], 16)
        features = []
        for index in range(12):
            fraction = (index + 1) / 13
            level = LEVELS[(seed >> (index % 24)) % len(LEVELS)]
            if index % 2:
                x = west + width * fraction
                y1, y2 = south + height * 0.08, north - height * 0.08
                coords = [[x - width * 0.008, y1], [x, (y1 + y2) / 2], [x + width * 0.008, y2]]
            else:
                y = south + height * fraction
                x1, x2 = west + width * 0.08, east - width * 0.08
                coords = [[x1, y - height * 0.008], [(x1 + x2) / 2, y], [x2, y + height * 0.008]]
            coords = [[min(east, max(west, x)), min(north, max(south, y))] for x, y in coords]
            free_speed = 50
            ratio = SPEED_RATIOS[level]
            observed = round(free_speed * ratio, 1)
            length = sum(math.hypot((coords[i][0] - coords[i - 1][0]) * 111320 * math.cos(math.radians((coords[i][1] + coords[i - 1][1]) / 2)), (coords[i][1] - coords[i - 1][1]) * 111320) for i in range(1, len(coords)))
            delay = round(length / (observed / 3.6) - length / (free_speed / 3.6))
            raw_id = f"seed:{seed}:{index}"
            features.append({
                "id": hashlib.sha1(raw_id.encode()).hexdigest()[:16],
                "name": f"Simulated road segment {index + 1}",
                "geometry": {"type": "LineString", "coordinates": coords},
                "observedSpeed": observed,
                "freeFlowSpeed": free_speed,
                "delay": delay,
                "delayEstimated": True,
                "congestionLevel": level,
                "congestionMethod": "seed-simulation",
                "speedRatio": ratio,
                "jamFactor": None,
                "confidence": None,
                "observationBasis": "simulated",
                "roadStatus": "open",
                "functionalClass": None,
                "lengthMeters": round(length),
                "provider": "seed",
                "simulated": True,
            })
        return {
            "source": "seed-simulation",
            "observedAt": None,
            "features": features,
            "omittedCount": 0,
            "units": TRAFFIC_UNITS,
            "attribution": "Simulated traffic generated from deterministic seed data; not live traffic",
            "simulated": True,
        }
