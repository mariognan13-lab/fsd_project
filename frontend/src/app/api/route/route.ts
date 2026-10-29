import { forward } from "@/lib/proxy";

export async function GET(req: Request) {
  return forward(req, "/api/route");
}
