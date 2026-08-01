import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut, User as UserIcon } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";

export function UserMenu() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!isAuthenticated || !user) {
    return (
      <div className="flex items-center gap-1.5">
        <Button variant="ghost" size="sm" onClick={() => navigate("/login")}>
          Sign in
        </Button>
        <Button size="sm" onClick={() => navigate("/signup")}>
          Sign up
        </Button>
      </div>
    );
  }

  const initial = (user.full_name || user.email).trim().charAt(0).toUpperCase();

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
      >
        {initial}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-56 rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-lg animate-fade-in"
        >
          <div className="px-3 py-2">
            <p className="truncate text-sm font-medium text-foreground">
              {user.full_name || "VisualFind user"}
            </p>
            <p className="truncate text-xs text-muted-foreground">{user.email}</p>
          </div>
          <div className="my-1 border-t border-border" />
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false);
              navigate("/profile");
            }}
            className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-sm transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            <UserIcon className="h-4 w-4" />
            Profile
          </button>
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false);
              logout();
              navigate("/");
            }}
            className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-sm text-destructive transition-colors hover:bg-destructive/10"
          >
            <LogOut className="h-4 w-4" />
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
