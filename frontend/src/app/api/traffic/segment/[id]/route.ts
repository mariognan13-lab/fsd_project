import { forward } from "@/lib/proxy";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return forward(req, `/api/traffic/segment/${id}`);
}
