import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";
import { cn } from "@/utils/cn";

type ToastVariant = "success" | "error" | "info";

interface Toast {
  id: number;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  toast: (toast: Omit<Toast, "id">) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

let idCounter = 0;

const VARIANT_STYLES: Record<
  ToastVariant,
  { icon: typeof CheckCircle2; className: string }
> = {
  success: { icon: CheckCircle2, className: "text-success" },
  error: { icon: XCircle, className: "text-destructive" },
  info: { icon: Info, className: "text-primary" },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    ({ title, description, variant = "info" }: Omit<Toast, "id">) => {
      const id = ++idCounter;
      setToasts((prev) => [...prev, { id, title, description, variant }]);
      setTimeout(() => dismiss(id), 4500);
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
        <AnimatePresence>
          {toasts.map((t) => {
            const { icon: Icon, className } = VARIANT_STYLES[t.variant];
            return (
              <motion.div
                key={t.id}
                initial={{ opacity: 0, y: 12, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, x: 40, transition: { duration: 0.15 } }}
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
                className="pointer-events-auto flex items-start gap-3 rounded-lg border border-border bg-card/95 p-4 shadow-lg backdrop-blur"
              >
                <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", className)} />
                <div className="flex-1">
                  <p className="text-sm font-medium text-foreground">{t.title}</p>
                  {t.description && (
                    <p className="mt-0.5 text-sm text-muted-foreground">{t.description}</p>
                  )}
                </div>
                <button
                  onClick={() => dismiss(t.id)}
                  aria-label="Dismiss notification"
                  className="rounded-md p-1 text-muted-foreground transition hover:bg-accent hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}
