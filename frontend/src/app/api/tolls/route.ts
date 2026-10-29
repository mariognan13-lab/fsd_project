import { NextResponse } from "next/server";

type CachedTolls = {
  data: unknown;
  storedAt: number;
};

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:5050";
const CACHE_TTL_MS = 24 * 60 * 60 * 1000;
const tollCache = new Map<string, CachedTolls>();

function parseBbox(value: string | null) {
  if (!value) return null;

  const parts = value.split(",").map((part) => Number(part.trim()));
  if (parts.length !== 4 || parts.some((part) => !Number.isFinite(part))) {
    return null;
  }

  return parts;
}

function cacheKey(bbox: number[]) {
  return bbox.map((value) => value.toFixed(3)).join(",");
}

export async function GET(req: Request) {
  const incoming = new URL(req.url);
  const bbox = parseBbox(incoming.searchParams.get("bbox"));

  if (!bbox) {
    return NextResponse.json({ tolls: [] }, { status: 400 });
  }

  const key = cacheKey(bbox);
  const cached = tollCache.get(key);
  if (cached && Date.now() - cached.storedAt < CACHE_TTL_MS) {
    return NextResponse.json(cached.data);
  }

  const target = new URL("/api/tolls", BACKEND_URL);
  target.searchParams.set("bbox", bbox.join(","));

  try {
    const response = await fetch(target, {
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(8000),
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}.`);
    }

    const data: unknown = await response.json();
    tollCache.set(key, { data, storedAt: Date.now() });
    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to load toll data.", error);
    if (cached) {
      return NextResponse.json(cached.data);
    }
    return NextResponse.json({ elements: [] }, { status: 200 });
  }
}

