import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Mail } from "lucide-react";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { forgotPassword } from "@/services/authService";
import { ApiError } from "@/api/client";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await forgotPassword(email.trim());
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <AuthLayout eyebrow="Check your inbox" title="Reset link sent">
        <div className="flex flex-col items-center gap-3 text-center">
          <CheckCircle2 className="h-10 w-10 text-success" />
          <p className="text-sm text-muted-foreground">
            If an account exists for <span className="font-medium text-foreground">{email}</span>,
            we've sent a link to reset your password. It expires in 30 minutes.
          </p>
          <Link to="/login" className="text-sm font-medium text-primary hover:underline">
            Back to sign in
          </Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      eyebrow="Forgot password"
      title="Reset your password"
      description="Enter the email on your account and we'll send you a reset link."
      footer={
        <Link to="/login" className="font-medium text-primary hover:underline">
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label htmlFor="email" className="text-sm font-medium text-foreground">
            Email
          </label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
        </div>

        {error && (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        <Button type="submit" className="w-full" isLoading={isSubmitting}>
          <Mail className="h-4 w-4" />
          Send reset link
        </Button>
      </form>
    </AuthLayout>
  );
}
