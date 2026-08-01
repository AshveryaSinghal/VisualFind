import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Compass, Home } from "lucide-react";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div className="container flex min-h-[70vh] flex-col items-center justify-center py-20 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 20 }}
        className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary"
      >
        <Compass className="h-8 w-8" />
      </motion.div>
      <h1 className="text-5xl font-extrabold tracking-tight text-foreground">404</h1>
      <p className="mt-3 max-w-sm text-muted-foreground">
        This page doesn't exist. Maybe it moved, or maybe you followed a broken link — either
        way, let's get you back on track.
      </p>
      <div className="mt-8 flex gap-3">
        <Button onClick={() => navigate("/")}>
          <Home className="h-4 w-4" />
          Back to home
        </Button>
        <Button variant="outline" onClick={() => navigate("/search")}>
          Start a search
        </Button>
      </div>
    </div>
  );
}
