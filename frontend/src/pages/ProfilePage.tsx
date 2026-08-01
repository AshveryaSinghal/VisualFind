import { useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Clock3, Globe2, KeyRound, MapPin, Save, User as UserIcon, SlidersHorizontal, Bell } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { changePassword } from "@/services/authService";
import { ApiError } from "@/api/client";
import { COUNTRIES, timezonesForCountry } from "@/utils/countryTimezones";
import { formatDateTime } from "@/utils/format";
import { PreferencesPanel } from "@/components/profile/PreferencesPanel";
import { AlertsPanel } from "@/components/profile/AlertsPanel";
import { cn } from "@/utils/cn";

const COUNTRY_OPTIONS = COUNTRIES.map((c) => ({ value: c.code, label: c.name }));

type ProfileTab = "account" | "preferences" | "alerts";

const TABS: { value: ProfileTab; label: string; icon: typeof UserIcon }[] = [
  { value: "account", label: "Account", icon: UserIcon },
  { value: "preferences", label: "Preferences", icon: SlidersHorizontal },
  { value: "alerts", label: "Price Alerts", icon: Bell },
];

export function ProfilePage() {
  const { user, updateProfile } = useAuth();
  const { toast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const activeTab: ProfileTab = useMemo(() => {
    const raw = searchParams.get("tab");
    return raw === "preferences" || raw === "alerts" ? raw : "account";
  }, [searchParams]);

  function setActiveTab(tab: ProfileTab) {
    setSearchParams(tab === "account" ? {} : { tab }, { replace: true });
  }

  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [countryCode, setCountryCode] = useState(user?.country_code ?? "");
  const [city, setCity] = useState(user?.city ?? "");
  const [tz, setTz] = useState(user?.timezone ?? "UTC");
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [isSavingPassword, setIsSavingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const timezoneOptions = useMemo(() => {
    const zones = countryCode ? timezonesForCountry(countryCode) : [];
    const pool = zones.length > 0 ? zones : [tz || "UTC"];
    return pool.map((z) => ({ value: z, label: z.replace(/_/g, " ") }));
  }, [countryCode, tz]);

  function handleCountryChange(code: string) {
    setCountryCode(code);
    const zones = timezonesForCountry(code);
    if (zones.length > 0) setTz(zones[0]);
  }

  async function handleProfileSubmit(event: FormEvent) {
    event.preventDefault();
    setProfileError(null);
    setIsSavingProfile(true);
    try {
      const country = COUNTRIES.find((c) => c.code === countryCode);
      await updateProfile({
        full_name: fullName.trim() || null,
        country_code: countryCode || null,
        country_name: country?.name ?? null,
        city: city.trim() || null,
        timezone: tz || "UTC",
      });
      toast({ variant: "success", title: "Profile updated" });
    } catch (err) {
      setProfileError(err instanceof ApiError ? err.message : "Couldn't save your profile.");
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function handlePasswordSubmit(event: FormEvent) {
    event.preventDefault();
    setPasswordError(null);

    if (newPassword.length < 8) {
      setPasswordError("New password must be at least 8 characters.");
      return;
    }

    setIsSavingPassword(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      toast({ variant: "success", title: "Password changed" });
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : "Couldn't change your password.");
    } finally {
      setIsSavingPassword(false);
    }
  }

  if (!user) return null;

  return (
    <div className="container max-w-4xl py-10">
      <PageHeader
        eyebrow="Your account"
        title="Profile"
        description="Your country and city set the timezone your search history is displayed in."
      />

      <div className="mt-8 flex flex-wrap gap-2 border-b border-border pb-4">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => setActiveTab(tab.value)}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              activeTab === tab.value
                ? "bg-accent text-foreground"
                : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
            )}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "preferences" && (
        <div className="mt-6">
          <PreferencesPanel />
        </div>
      )}

      {activeTab === "alerts" && (
        <div className="mt-6">
          <AlertsPanel />
        </div>
      )}

      {activeTab === "account" && (
      <div className="mt-6 space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserIcon className="h-4 w-4 text-primary" />
              Account details
            </CardTitle>
            <CardDescription>
              Signed in as {user.email} · joined {formatDateTime(user.created_at)}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleProfileSubmit} className="space-y-5">
              <div className="space-y-1.5">
                <label htmlFor="full_name" className="text-sm font-medium text-foreground">
                  Full name
                </label>
                <Input
                  id="full_name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Doe"
                />
              </div>

              <div className="grid gap-5 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
                    <Globe2 className="h-3.5 w-3.5" /> Country
                  </label>
                  <Select
                    value={countryCode}
                    onValueChange={handleCountryChange}
                    options={COUNTRY_OPTIONS}
                    placeholder="Select your country"
                  />
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="city" className="flex items-center gap-1.5 text-sm font-medium text-foreground">
                    <MapPin className="h-3.5 w-3.5" /> City
                  </label>
                  <Input
                    id="city"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="e.g. Ghaziabad"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
                  <Clock3 className="h-3.5 w-3.5" /> Timezone
                </label>
                <Select
                  value={tz}
                  onValueChange={setTz}
                  options={timezoneOptions}
                  placeholder="Select timezone"
                />
                <p className="text-xs text-muted-foreground">
                  Every search history timestamp is shown in this timezone, wherever you're signed in from.
                </p>
              </div>

              {profileError && (
                <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {profileError}
                </p>
              )}

              <Button type="submit" isLoading={isSavingProfile}>
                <Save className="h-4 w-4" />
                Save profile
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-primary" />
              Change password
            </CardTitle>
            <CardDescription>Use a password you're not using anywhere else.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <div className="grid gap-5 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label htmlFor="current_password" className="text-sm font-medium text-foreground">
                    Current password
                  </label>
                  <Input
                    id="current_password"
                    type="password"
                    autoComplete="current-password"
                    required
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="new_password" className="text-sm font-medium text-foreground">
                    New password
                  </label>
                  <Input
                    id="new_password"
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={8}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                  />
                </div>
              </div>

              {passwordError && (
                <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {passwordError}
                </p>
              )}

              <Button type="submit" variant="outline" isLoading={isSavingPassword}>
                Update password
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
      )}
    </div>
  );
}
