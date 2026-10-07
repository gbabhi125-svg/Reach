const GENERATOR_URL = process.env.NEXT_PUBLIC_GENERATOR_SERVICE_URL || "http://localhost:8002";
const PRICING_URL = process.env.NEXT_PUBLIC_PRICING_SERVICE_URL || "http://localhost:8001";

export type Category = {
  id: string;
  name: string;
  quota_kg: number;
  rate_per_kg: number;
};

export type QuotaProgress = {
  category: string;
  progress_kg: number;
  quota_kg: number;
  percent: number;
};

export type PostingResult = {
  id: string;
  status: string;
  quota_progress_kg: number;
  quota_kg: number;
  quota_crossed: boolean;
  run_id: string | null;
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Request failed (${res.status}): ${body}`);
  }
  return res.json();
}

export const api = {
  listCategories: () => fetch(`${PRICING_URL}/categories`).then((r) => json<Category[]>(r)),

  // name-only -- the backend auto-geocodes via Nominatim; pass lat/lng to override
  createCluster: (name: string) =>
    fetch(`${GENERATOR_URL}/clusters`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }).then((r) => json<{ id: string; name: string; lat: number; lng: number }>(r)),

  requestOtp: (phone: string) =>
    fetch(`${GENERATOR_URL}/generators/request-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone }),
    }).then((r) => json<{ otp_session_id: string }>(r)),

  verifyOtp: (otp_session_id: string, code: string) =>
    fetch(`${GENERATOR_URL}/generators/verify-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ otp_session_id, code }),
    }).then((r) => json<{ verified: boolean }>(r)),

  createGenerator: (name: string, phone: string, geo_cluster_id: string, otp_session_id: string) =>
    fetch(`${GENERATOR_URL}/generators`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, phone, geo_cluster_id, otp_session_id }),
    }).then((r) => json<{ id: string; name: string }>(r)),

  createPosting: (generator_id: string, geo_cluster_id: string, category_name: string, est_weight_kg: number) =>
    fetch(`${GENERATOR_URL}/postings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ generator_id, geo_cluster_id, category_name, est_weight_kg }),
    }).then((r) => json<PostingResult>(r)),

  quotaProgress: (geo_cluster_id: string) =>
    fetch(`${GENERATOR_URL}/clusters/${geo_cluster_id}/quota-progress`).then((r) => json<QuotaProgress[]>(r)),
};
