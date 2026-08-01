import { NavLink } from "react-router-dom";
import { Search, ScanSearch, History, BarChart3, Menu, X, Sparkles, Heart, Bookmark } from "lucide-react";
import { useState } from "react";
import { cn } from "@/utils/cn";
import { ThemeToggle } from "@/components/layouts/ThemeToggle";
import { BackendStatusDot } from "@/components/common/BackendStatusDot";
import { Button } from "@/components/ui/button";
import { UserMenu } from "@/components/layouts/UserMenu";
import { NotificationBell } from "@/components/layouts/NotificationBell";

const NAV_ITEMS = [
  { to: "/search", label: "Search", icon: Search },
  { to: "/assistant", label: "AI Assistant", icon: Sparkles },
  { to: "/recommendations", label: "For You", icon: Heart },
  { to: "/saved", label: "Saved", icon: Bookmark },
  { to: "/history", label: "History", icon: History },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
];

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="dark sticky top-0 z-50 border-b border-border/60 bg-background text-foreground backdrop-blur-lg">
      <div className="container flex h-16 items-center justify-between">
        <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ScanSearch className="h-4 w-4" />
          </span>
          <span className="text-lg">VisualFind</span>
        </NavLink>

        <nav className="hidden items-center gap-0.5 md:flex">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-2 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground xl:text-sm",
                  isActive && "bg-accent text-foreground"
                )
              }
            >
              <item.icon className="hidden h-4 w-4 xl:block" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <BackendStatusDot className="mr-1 hidden sm:inline-flex" />
          <ThemeToggle />
          <NotificationBell />
          <UserMenu />
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileOpen((prev) => !prev)}
            aria-label="Toggle navigation menu"
          >
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {mobileOpen && (
        <nav className="border-t border-border/60 bg-background px-4 py-3 md:hidden">
          <div className="flex flex-col gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 rounded-md px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                    isActive && "bg-accent text-foreground"
                  )
                }
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </NavLink>
            ))}
          </div>
        </nav>
      )}
    </header>
  );
}
