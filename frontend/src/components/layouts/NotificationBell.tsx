import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Check, CheckCheck, Tag, Trash2 } from "lucide-react";
import { cn } from "@/utils/cn";
import { formatRelativeDate } from "@/utils/format";
import { useAuth } from "@/context/AuthContext";
import {
  useDeleteNotification,
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  useUnreadNotificationCount,
} from "@/hooks/usePersonalization";
import { Button } from "@/components/ui/button";
import type { AppNotification } from "@/types";

function NotificationRow({ notification }: { notification: AppNotification }) {
  const markRead = useMarkNotificationRead();
  const deleteOne = useDeleteNotification();

  return (
    <div
      className={cn(
        "group relative flex gap-2.5 rounded-md px-3 py-2.5 text-left transition-colors",
        !notification.is_read && "bg-primary/5"
      )}
    >
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-success/15 text-success">
        <Tag className="h-3.5 w-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">{notification.title}</p>
        <p className="line-clamp-2 text-xs text-muted-foreground">{notification.message}</p>
        <p className="mt-1 text-[11px] text-muted-foreground">
          {formatRelativeDate(notification.created_at)}
        </p>
      </div>
      <div className="flex shrink-0 flex-col gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        {!notification.is_read && (
          <button
            type="button"
            aria-label="Mark as read"
            onClick={() => markRead.mutate(notification.id)}
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <Check className="h-3.5 w-3.5" />
          </button>
        )}
        <button
          type="button"
          aria-label="Delete notification"
          onClick={() => deleteOne.mutate(notification.id)}
          className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

export function NotificationBell() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: unreadCount = 0 } = useUnreadNotificationCount();
  const { data: notifications = [], isLoading } = useNotifications();
  const markAllRead = useMarkAllNotificationsRead();

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!isAuthenticated) return null;

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Notifications"
        className="relative flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-destructive-foreground">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-80 max-w-[90vw] rounded-md border border-border bg-popover text-popover-foreground shadow-lg animate-fade-in"
        >
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <p className="text-sm font-semibold text-foreground">Notifications</p>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => markAllRead.mutate()}
                className="flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <CheckCheck className="h-3.5 w-3.5" />
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto p-1">
            {isLoading && (
              <p className="px-3 py-6 text-center text-xs text-muted-foreground">Loading…</p>
            )}
            {!isLoading && notifications.length === 0 && (
              <p className="px-3 py-6 text-center text-xs text-muted-foreground">
                No notifications yet. Set a price alert and we'll let you know here when it fires.
              </p>
            )}
            {notifications.map((n) => (
              <NotificationRow key={n.id} notification={n} />
            ))}
          </div>

          <div className="border-t border-border p-1">
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-center"
              onClick={() => {
                setOpen(false);
                navigate("/profile?tab=alerts");
              }}
            >
              Manage price alerts
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
