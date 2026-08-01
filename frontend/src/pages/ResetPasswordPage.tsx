import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2, KeyRound } from "lucide-react";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { resetPassword } from "@/services/authService";
import { ApiError } from "@/api/client";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (!token) {
      setError("This reset link is missing its token. Please request a new one.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }

    setIsSubmitting(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reset your password. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (done) {
    return (
      <AuthLayout eyebrow="All set" title="Password reset">
        <div className="flex flex-col items-center gap-3 text-center">
          <CheckCircle2 className="h-10 w-10 text-success" />
          <p className="text-sm text-muted-foreground">
            Your password has been changed. You can now sign in with your new password.
          </p>
          <Button onClick={() => navigate("/login", { replace: true })}>Go to sign in</Button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      eyebrow="Reset password"
      title="Choose a new password"
      footer={
        <Link to="/forgot-password" className="font-medium text-primary hover:underline">
          Request a new link
        </Link>
      }
    >
      {!token && (
        <p className="mb-4 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning-foreground">
          No reset token found in this link. Open the link from your email again, or request a new one.
        </p>
      )}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label htmlFor="password" className="text-sm font-medium text-foreground">
            New password
          </label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="confirm_password" className="text-sm font-medium text-foreground">
            Confirm new password
          </label>
          <Input
            id="confirm_password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Re-enter your new password"
          />
        </div>

        {error && (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        <Button type="submit" className="w-full" isLoading={isSubmitting} disabled={!token}>
          <KeyRound className="h-4 w-4" />
          Reset password
        </Button>
      </form>
    </AuthLayout>
  );
}
