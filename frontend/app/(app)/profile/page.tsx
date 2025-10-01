"use client";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ProfilePage() {
  const { user, logout } = useAuth();

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <p className="text-xs uppercase tracking-[0.4em] text-sky-300">Profile</p>
        <h1 className="text-3xl font-semibold text-slate-100">Operator identity</h1>
        <p className="text-sm text-slate-400">
          Manage your console presence, refresh API keys, and control access tokens.
        </p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Account overview</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-slate-300">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Name</p>
            <p className="text-base font-medium text-slate-100">{user?.name ?? "Operator"}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Email</p>
            <p className="text-base font-medium text-slate-100">{user?.email}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Workspace tier</p>
            <p className="text-base font-medium text-emerald-300">SaaS Preview</p>
          </div>
          <Button onClick={logout} className="mt-4 w-full md:w-auto">
            Sign out
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
