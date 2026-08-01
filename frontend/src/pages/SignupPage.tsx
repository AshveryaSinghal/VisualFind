import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Check, Eye, EyeOff, Loader2, UserPlus, X } from "lucide-react";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/context/AuthContext";
import { useDebounce } from "@/hooks/useDebounce";
import { ApiError } from "@/api/client";
import * as authService from "@/services/authService";

const USERNAME_PATTERN = /^[a-zA-Z][a-zA-Z0-9_.]{2,29}$/;

export function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const debouncedUsername = useDebounce(username.trim(), 400);
  const [isCheckingUsername, setIsCheckingUsername] = useState(false);
  const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null);
  const [usernameSuggestions, setUsernameSuggestions] = useState<string[]>([]);

  useEffect(() => {
    if (!USERNAME_PATTERN.test(debouncedUsername)) {
      setUsernameAvailable(null);
      setUsernameSuggestions([]);
      return;
    }

    let cancelled = false;
    setIsCheckingUsername(true);
    authService
      .checkUsername(debouncedUsername)
      .then((result) => {
        if (cancelled) return;
        setUsernameAvailable(result.available);
        setUsernameSuggestions(result.suggestions);
      })
      .catch(() => {
        if (!cancelled) {
          setUsernameAvailable(null);
          setUsernameSuggestions([]);
        }
      })
      .finally(() => {
        if (!cancelled) setIsCheckingUsername(false);
      });

    return () => {
      cancelled = true;
    };
  }, [debouncedUsername]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    const trimmedUsername = username.trim();
    if (!USERNAME_PATTERN.test(trimmedUsername)) {
      setError(
        "Username must be 3-30 characters, start with a letter, and contain only letters, numbers, underscores, or periods."
      );
      return;
    }
    if (usernameAvailable === false) {
      setError("That username is taken - pick one of the suggestions below or try another.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setIsSubmitting(true);
    try {
      await signup(trimmedUsername, email.trim(), password, fullName.trim() || undefined);
      navigate("/profile", { replace: true, state: { justSignedUp: true } });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create your account. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout
      eyebrow="Get started"
      title="Create your VisualFind account"
      description="Search history, deal tracking, and a profile that's yours alone."
      footer={
        <span>
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </span>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label htmlFor="full_name" className="text-sm font-medium text-foreground">
            Full name <span className="text-muted-foreground">(optional)</span>
          </label>
          <Input
            id="full_name"
            type="text"
            autoComplete="name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Jane Doe"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="username" className="text-sm font-medium text-foreground">
            Username
          </label>
          <div className="relative">
            <Input
              id="username"
              type="text"
              autoComplete="username"
              required
              minLength={3}
              maxLength={30}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="ashverya_dev"
              className="pr-9"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2">
              {isCheckingUsername && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
              {!isCheckingUsername && usernameAvailable === true && (
                <Check className="h-4 w-4 text-emerald-600" />
              )}
              {!isCheckingUsername && usernameAvailable === false && <X className="h-4 w-4 text-destructive" />}
            </span>
          </div>
          {!isCheckingUsername && usernameAvailable === false && (
            <div className="space-y-1.5">
              <p className="text-xs text-destructive">That username is taken.</p>
              {usernameSuggestions.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {usernameSuggestions.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => setUsername(suggestion)}
                      className="rounded-full border border-input bg-muted px-2.5 py-1 text-xs text-foreground transition-colors hover:bg-accent"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {!isCheckingUsername && usernameAvailable === true && (
            <p className="text-xs text-emerald-600">Username is available.</p>
          )}
        </div>

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

        <div className="space-y-1.5">
          <label htmlFor="password" className="text-sm font-medium text-foreground">
            Password
          </label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {error && (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        <Button type="submit" className="w-full" isLoading={isSubmitting}>
          <UserPlus className="h-4 w-4" />
          Create account
        </Button>

        <p className="text-center text-xs text-muted-foreground">
          By continuing you agree this is a demo project and not a real e-commerce checkout.
        </p>
      </form>
    </AuthLayout>
  );
}
