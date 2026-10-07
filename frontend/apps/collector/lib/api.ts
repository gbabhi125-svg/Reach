const COLLECTOR_URL = process.env.NEXT_PUBLIC_COLLECTOR_SERVICE_URL || "http://localhost:8003";
const PICKUP_URL = process.env.NEXT_PUBLIC_PICKUP_SERVICE_URL || "http://localhost:8004";

export type OpenRun = {
  id: string;
  cluster_name: string;
  category: string;
  status: string;
};

export type Stop = {
  posting_id: string;
  stop_name: string;
  est_weight_kg: number;
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Request failed (${res.status}): ${body}`);
  }
  return res.json();
}

export const api = {
  requestOtp: (phone: string) =>
    fetch(`${COLLECTOR_URL}/collectors/request-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone }),
    }).then((r) => json<{ otp_session_id: string }>(r)),

  verifyOtp: (otp_session_id: string, code: string) =>
    fetch(`${COLLECTOR_URL}/collectors/verify-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ otp_session_id, code }),
    }).then((r) => json<{ verified: boolean }>(r)),

  createCollector: (name: string, phone: string, otp_session_id: string) =>
    fetch(`${COLLECTOR_URL}/collectors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, phone, otp_session_id }),
    }).then((r) => json<{ id: string; name: string }>(r)),

  initiateKyc: (collectorId: string, aadhaarNumber: string) =>
    fetch(`${COLLECTOR_URL}/collectors/${collectorId}/kyc/initiate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aadhaar_number: aadhaarNumber }),
    }).then((r) => json<{ kyc_reference_id: string }>(r)),

  verifyKyc: (collectorId: string, aadhaarNumber: string, otp: string) =>
    fetch(`${COLLECTOR_URL}/collectors/${collectorId}/kyc/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aadhaar_number: aadhaarNumber, otp }),
    }).then((r) => json<{ identity_verified: boolean; kyc_verified_name: string }>(r)),

  openRuns: () => fetch(`${COLLECTOR_URL}/runs/open`).then((r) => json<OpenRun[]>(r)),

  acceptRun: (runId: string, collectorId: string) =>
    fetch(`${COLLECTOR_URL}/runs/${runId}/accept`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ collector_id: collectorId }),
    }).then((r) => json<{ id: string; status: string }>(r)),

  runStops: (runId: string) => fetch(`${COLLECTOR_URL}/runs/${runId}/stops`).then((r) => json<Stop[]>(r)),

  logPickup: (runId: string, postingId: string, actualWeightKg: number, photoUrl?: string) =>
    fetch(`${PICKUP_URL}/runs/${runId}/pickups`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ posting_id: postingId, actual_weight_kg: actualWeightKg, photo_url: photoUrl }),
    }).then((r) => json<{ transaction_id: string; amount_paid: number; hash: string }>(r)),

  completeRun: (runId: string) =>
    fetch(`${PICKUP_URL}/runs/${runId}/complete`, { method: "POST" }).then((r) =>
      json<{ id: string; status: string }>(r)
    ),
};
