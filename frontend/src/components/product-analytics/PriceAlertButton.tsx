import { useState, type FormEvent } from "react";
import { Bell, BellRing, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/context/ToastContext";
import { ApiError } from "@/api/client";
import { useCreatePriceAlert } from "@/hooks/usePersonalization";

interface PriceAlertButtonProps {
  productName: string;
  platform?: string | null;
  currency?: string | null;
  thumbnail?: string | null;
  link?: string | null;
  currentPrice?: number | null;
}

export function PriceAlertButton({
  productName,
  platform,
  currency,
  thumbnail,
  link,
  currentPrice,
}: PriceAlertButtonProps) {
  const { toast } = useToast();
  const createAlert = useCreatePriceAlert();
  const [open, setOpen] = useState(false);
  const [targetPrice, setTargetPrice] = useState(
    currentPrice ? String(Math.max(1, Math.round(currentPrice * 0.9))) : ""
  );
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const price = Number(targetPrice);
    if (!Number.isFinite(price) || price <= 0) {
      setError("Enter a valid price.");
      return;
    }
    try {
      await createAlert.mutateAsync({
        product_name: productName,
        target_price: price,
        currency: currency ?? "INR",
        platform: platform ?? undefined,
        thumbnail: thumbnail ?? undefined,
        link: link ?? undefined,
      });
      toast({ variant: "success", title: "Price alert set", description: `We'll notify you below ${currency ?? ""} ${price}.` });
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create this alert.");
    }
  }

  if (!open) {
    return (
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        <Bell className="h-3.5 w-3.5" />
        Set price alert
      </Button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <div className="flex items-center gap-1.5 rounded-md border border-input px-2">
        <BellRing className="h-3.5 w-3.5 shrink-0 text-primary" />
        <Input
          type="number"
          min={1}
          autoFocus
          placeholder="Target price"
          value={targetPrice}
          onChange={(e) => setTargetPrice(e.target.value)}
          className="h-8 w-28 border-0 px-1 shadow-none focus-visible:border-0"
        />
      </div>
      <Button type="submit" size="sm" isLoading={createAlert.isPending}>
        Save
      </Button>
      <Button type="button" variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label="Cancel">
        <X className="h-4 w-4" />
      </Button>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </form>
  );
}
