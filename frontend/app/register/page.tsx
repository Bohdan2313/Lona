"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthShell } from "@/components/marketing/auth-shell";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [team, setTeam] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!email || !password) {
      setError("Complete all fields to activate your console.");
      return;
    }
    try {
      setLoading(true);
      await register(email, password);
      router.push("/app/dashboard");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell title="Create your LonaMind workspace" subtitle="Spin up a dedicated environment for your strategies.">
      <form className="space-y-5" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <Label htmlFor="team">Workspace name</Label>
          <Input
            id="team"
            placeholder="Helios Capital"
            value={team}
            onChange={(event) => setTeam(event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="lead@helios.capital"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Create a strong passphrase"
          />
        </div>
        {error && <p className="text-sm text-amber-300/80">{error}</p>}
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Preparing workspace..." : "Create workspace"}
        </Button>
        <p className="text-center text-xs text-slate-400">
          Already have access? <Link href="/login" className="text-sky-300">Sign in</Link>
        </p>
      </form>
    </AuthShell>
  );
}
