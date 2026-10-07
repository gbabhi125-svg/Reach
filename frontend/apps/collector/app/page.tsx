"use client";

import { useEffect, useState } from "react";
import { api, OpenRun, Stop } from "../lib/api";

type Profile = { collectorId: string; name: string };

const STORAGE_KEY = "reach_collector_profile";

export default function Page() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [otpSessionId, setOtpSessionId] = useState<string | null>(null);
  const [otpCode, setOtpCode] = useState("");
  const [otpVerified, setOtpVerified] = useState(false);

  // KYC (Aadhaar eKYC) state -- required before a collector can accept runs
  const [pendingCollectorId, setPendingCollectorId] = useState<string | null>(null);
  const [aadhaarNumber, setAadhaarNumber] = useState("");
  const [kycOtp, setKycOtp] = useState("");
  const [kycInitiated, setKycInitiated] = useState(false);

  const [openRuns, setOpenRuns] = useState<OpenRun[]>([]);
  const [activeRun, setActiveRun] = useState<OpenRun | null>(null);
  const [stops, setStops] = useState<Stop[]>([]);
  const [weights, setWeights] = useState<Record<string, string>>({});
  const [doneStops, setDoneStops] = useState<Set<string>>(new Set());
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    if (saved) setProfile(JSON.parse(saved));
  }, []);

  useEffect(() => {
    if (profile) refreshOpenRuns();
  }, [profile]);

  function refreshOpenRuns() {
    api.openRuns().then(setOpenRuns).catch((e) => setError(e.message));
  }

  async function handleRequestOtp(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await api.requestOtp(phone);
      setOtpSessionId(res.otp_session_id);
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleVerifyOtp(e: React.FormEvent) {
    e.preventDefault();
    if (!otpSessionId) return;
    setError(null);
    try {
      await api.verifyOtp(otpSessionId, otpCode);
      setOtpVerified(true);
    } catch (e: any) {
      setError("Incorrect code — try again.");
    }
  }

  async function handleOnboard(e: React.FormEvent) {
    e.preventDefault();
    if (!otpSessionId || !otpVerified) return;
    setError(null);
    try {
      const collector = await api.createCollector(name, phone, otpSessionId);
      setPendingCollectorId(collector.id);
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleInitiateKyc(e: React.FormEvent) {
    e.preventDefault();
    if (!pendingCollectorId) return;
    setError(null);
    try {
      await api.initiateKyc(pendingCollectorId, aadhaarNumber);
      setKycInitiated(true);
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleVerifyKyc(e: React.FormEvent) {
    e.preventDefault();
    if (!pendingCollectorId) return;
    setError(null);
    try {
      await api.verifyKyc(pendingCollectorId, aadhaarNumber, kycOtp);
      const newProfile = { collectorId: pendingCollectorId, name };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newProfile));
      setProfile(newProfile);
    } catch (e: any) {
      setError("Aadhaar verification failed — check the number and OTP.");
    }
  }

  async function handleAccept(run: OpenRun) {
    if (!profile) return;
    setError(null);
    try {
      await api.acceptRun(run.id, profile.collectorId);
      const runStops = await api.runStops(run.id);
      setActiveRun(run);
      setStops(runStops);
      setDoneStops(new Set());
      setStatus(null);
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleLogPickup(stop: Stop) {
    if (!activeRun) return;
    const w = parseFloat(weights[stop.posting_id] || String(stop.est_weight_kg));
    setError(null);
    try {
      await api.logPickup(activeRun.id, stop.posting_id, w);
      setDoneStops((prev) => new Set(prev).add(stop.posting_id));
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleCompleteRun() {
    if (!activeRun) return;
    setError(null);
    try {
      await api.completeRun(activeRun.id);
      setStatus(`Run completed — ${stops.length} pickups logged.`);
      setActiveRun(null);
      setStops([]);
      refreshOpenRuns();
    } catch (e: any) {
      setError(e.message);
    }
  }

  if (!profile) {
    return (
      <main style={{ maxWidth: 420, margin: "40px auto", padding: 24 }}>
        <h1>REACH — Collector</h1>
        <p>See villages that crossed quota, accept a run, do one consolidated trip.</p>

        {!otpSessionId && !pendingCollectorId && (
          <form onSubmit={handleRequestOtp} style={{ display: "grid", gap: 12 }}>
            <input placeholder="Phone number" value={phone} onChange={(e) => setPhone(e.target.value)} required />
            <button type="submit">Send OTP</button>
          </form>
        )}

        {otpSessionId && !otpVerified && !pendingCollectorId && (
          <form onSubmit={handleVerifyOtp} style={{ display: "grid", gap: 12 }}>
            <p style={{ fontSize: 14, color: "#666" }}>
              Enter the code sent to {phone}. (Local/dev mode: check the backend console log.)
            </p>
            <input placeholder="OTP code" value={otpCode} onChange={(e) => setOtpCode(e.target.value)} required />
            <button type="submit">Verify</button>
          </form>
        )}

        {otpVerified && !pendingCollectorId && (
          <form onSubmit={handleOnboard} style={{ display: "grid", gap: 12 }}>
            <input placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} required />
            <button type="submit">Continue to identity verification</button>
          </form>
        )}

        {pendingCollectorId && !kycInitiated && (
          <form onSubmit={handleInitiateKyc} style={{ display: "grid", gap: 12 }}>
            <p style={{ fontSize: 14, color: "#666" }}>
              One more step — verify your identity with Aadhaar so generators can trust who's picking up.
            </p>
            <input
              placeholder="Aadhaar number"
              value={aadhaarNumber}
              onChange={(e) => setAadhaarNumber(e.target.value)}
              required
            />
            <button type="submit">Send Aadhaar OTP</button>
          </form>
        )}

        {pendingCollectorId && kycInitiated && (
          <form onSubmit={handleVerifyKyc} style={{ display: "grid", gap: 12 }}>
            <p style={{ fontSize: 14, color: "#666" }}>
              Enter the OTP sent to your Aadhaar-linked mobile. (Local/dev mode: any value works with the
              sandbox test Aadhaar number.)
            </p>
            <input placeholder="Aadhaar OTP" value={kycOtp} onChange={(e) => setKycOtp(e.target.value)} required />
            <button type="submit">Verify identity</button>
          </form>
        )}

        {error && <p style={{ color: "crimson" }}>{error}</p>}
      </main>
    );
  }

  if (activeRun) {
    return (
      <main style={{ maxWidth: 480, margin: "40px auto", padding: 24 }}>
        <h1>REACH — Collector</h1>
        <p>
          Run: {activeRun.cluster_name} · {activeRun.category}
        </p>
        <div style={{ display: "grid", gap: 12, marginTop: 16 }}>
          {stops.map((s) => (
            <div key={s.posting_id} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <strong>{s.stop_name}</strong>
                <span>est. {s.est_weight_kg}kg</span>
              </div>
              {doneStops.has(s.posting_id) ? (
                <p style={{ color: "#2a7a2a", margin: "8px 0 0" }}>Picked up ✓</p>
              ) : (
                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="Actual weight (kg)"
                    value={weights[s.posting_id] || ""}
                    onChange={(e) => setWeights({ ...weights, [s.posting_id]: e.target.value })}
                  />
                  <button onClick={() => handleLogPickup(s)}>Log pickup</button>
                </div>
              )}
            </div>
          ))}
        </div>
        <button
          onClick={handleCompleteRun}
          disabled={doneStops.size < stops.length}
          style={{ marginTop: 16 }}
        >
          Complete run
        </button>
        {error && <p style={{ color: "crimson" }}>{error}</p>}
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 480, margin: "40px auto", padding: 24 }}>
      <h1>REACH — Collector</h1>
      <p>Welcome, {profile.name}</p>
      {status && <p style={{ color: "#2a7a2a" }}>{status}</p>}

      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 18 }}>Open runs near you</h2>
        {openRuns.length === 0 && <p>No villages have crossed quota yet.</p>}
        <div style={{ display: "grid", gap: 12 }}>
          {openRuns.map((r) => (
            <div key={r.id} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <strong>{r.cluster_name}</strong>
                  <div style={{ fontSize: 14, color: "#666" }}>{r.category}</div>
                </div>
                <button onClick={() => handleAccept(r)}>Accept</button>
              </div>
            </div>
          ))}
        </div>
        <button onClick={refreshOpenRuns} style={{ marginTop: 12 }}>
          Refresh
        </button>
      </section>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
    </main>
  );
}
