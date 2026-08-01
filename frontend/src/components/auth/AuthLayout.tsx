import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { ScanSearch } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

interface AuthLayoutProps {
  eyebrow?: string;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function AuthLayout({ eyebrow, title, description, children, footer }: AuthLayoutProps) {
  return (
    <div className="container flex min-h-[calc(100vh-8rem)] items-center justify-center py-12">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="w-full max-w-md"
      >
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <ScanSearch className="h-6 w-6" />
          </span>
          {eyebrow && (
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">{eyebrow}</p>
          )}
        </div>

        <Card>
          <CardHeader className="items-center text-center">
            <h1 className="text-xl font-bold tracking-tight text-foreground">{title}</h1>
            {description && <p className="text-sm text-muted-foreground">{description}</p>}
          </CardHeader>
          <CardContent>{children}</CardContent>
        </Card>

        {footer && <div className="mt-6 text-center text-sm text-muted-foreground">{footer}</div>}
      </motion.div>
    </div>
  );
}
