"use client";

import { useEffect, useState } from "react";
import { api, Category, QuotaProgress } from "../lib/api";

type Profile = { generatorId: string; clusterId: string; clusterName: string };

const STORAGE_KEY = "reach_generator_profile";

export default function Page() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [progress, setProgress] = useState<QuotaProgress[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);

  // onboarding form state
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [clusterName, setClusterName] = useState("");
  const [otpSessionId, setOtpSessionId] = useState<string | null>(null);
  const [otpCode, setOtpCode] = useState("");
  const [otpVerified, setOtpVerified] = useState(false);

  // posting form state
  const [category, setCategory] = useState("");
  const [weight, setWeight] = useState("");

  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    if (saved) setProfile(JSON.parse(saved));
    api.listCategories().then(setCategories).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (profile) {
      refreshProgress(profile.clusterId);
    }
  }, [profile]);

  function refreshProgress(clusterId: string) {
    api.quotaProgress(clusterId).then(setProgress).catch((e) => setError(e.message));
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
      // village name is auto-geocoded server-side via Nominatim
      const cluster = await api.createCluster(clusterName);
      const generator = await api.createGenerator(name, phone, cluster.id, otpSessionId);
      const newProfile: Profile = { generatorId: generator.id, clusterId: cluster.id, clusterName: cluster.name };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newProfile));
      setProfile(newProfile);
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handlePost(e: React.FormEvent) {
    e.preventDefault();
    if (!profile || !category || !weight) return;
    setError(null);
    setLastResult(null);
    try {
      const result = await api.createPosting(profile.generatorId, profile.clusterId, category, parseFloat(weight));
      setWeight("");
      refreshProgress(profile.clusterId);
      setLastResult(
        result.quota_crossed
          ? `Quota crossed for ${category}! A collector run has been opened for your village.`
          : `Listed ${weight}kg of ${category}. Village total: ${result.quota_progress_kg}/${result.quota_kg}kg.`
      );
    } catch (e: any) {
      setError(e.message);
    }
  }

  if (!profile) {
    return (
      <main style={{ maxWidth: 420, margin: "40px auto", padding: 24 }}>
        <h1>REACH — Generator</h1>
        <p>List your waste. Once your village hits quota, a collector comes to you.</p>

        {!otpSessionId && (
          <form onSubmit={handleRequestOtp} style={{ display: "grid", gap: 12 }}>
            <input placeholder="Phone number" value={phone} onChange={(e) => setPhone(e.target.value)} required />
            <button type="submit">Send OTP</button>
          </form>
        )}

        {otpSessionId && !otpVerified && (
          <form onSubmit={handleVerifyOtp} style={{ display: "grid", gap: 12 }}>
            <p style={{ fontSize: 14, color: "#666" }}>
              Enter the code sent to {phone}. (Local/dev mode: check the backend console log.)
            </p>
            <input placeholder="OTP code" value={otpCode} onChange={(e) => setOtpCode(e.target.value)} required />
            <button type="submit">Verify</button>
          </form>
        )}

        {otpVerified && (
          <form onSubmit={handleOnboard} style={{ display: "grid", gap: 12 }}>
            <input placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} required />
            <input
              placeholder="Village/town name"
              value={clusterName}
              onChange={(e) => setClusterName(e.target.value)}
              required
            />
            <button type="submit">Get started</button>
          </form>
        )}

        {error && <p style={{ color: "crimson" }}>{error}</p>}
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 480, margin: "40px auto", padding: 24 }}>
      <h1>REACH — Generator</h1>
      <p>
        {name || "Welcome back"} · {profile.clusterName}
      </p>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 18 }}>List waste</h2>
        <form onSubmit={handlePost} style={{ display: "grid", gap: 12 }}>
          <select value={category} onChange={(e) => setCategory(e.target.value)} required>
            <option value="">Select category</option>
            {categories.map((c) => (
              <option key={c.id} value={c.name}>
                {c.name} (₹{c.rate_per_kg}/kg)
              </option>
            ))}
          </select>
          <input
            type="number"
            step="0.1"
            placeholder="Estimated weight (kg)"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            required
          />
          <button type="submit">List it</button>
        </form>
        {lastResult && <p style={{ color: "#2a7a2a" }}>{lastResult}</p>}
        {error && <p style={{ color: "crimson" }}>{error}</p>}
      </section>

      <section style={{ marginTop: 32 }}>
        <h2 style={{ fontSize: 18 }}>Village quota progress</h2>
        <div style={{ display: "grid", gap: 8 }}>
          {progress.map((p) => (
            <div key={p.category}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
                <span>{p.category}</span>
                <span>
                  {p.progress_kg}/{p.quota_kg}kg
                </span>
              </div>
              <div style={{ background: "#ddd", borderRadius: 4, height: 8 }}>
                <div
                  style={{
                    width: `${Math.min(p.percent, 100)}%`,
                    background: p.percent >= 100 ? "#2a7a2a" : "#4a90d9",
                    height: 8,
                    borderRadius: 4,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
