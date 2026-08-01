import { useState, type FormEvent } from "react";
import { Bell, BellRing, Plus, Store, Trash2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/common/EmptyState";
import { useToast } from "@/context/ToastContext";
import { ApiError } from "@/api/client";
import { useCreatePriceAlert, useDeletePriceAlert, usePriceAlerts } from "@/hooks/usePersonalization";
import { formatDateTime, formatPrice } from "@/utils/format";

export function AlertsPanel() {
  const { toast } = useToast();
  const { data: alerts = [], isLoading } = usePriceAlerts();
  const createAlert = useCreatePriceAlert();
  const deleteAlert = useDeletePriceAlert();

  const [productName, setProductName] = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setError(null);

    const price = Number(targetPrice);
    if (!productName.trim()) {
      setError("Enter the product name you want to track.");
      return;
    }
    if (!Number.isFinite(price) || price <= 0) {
      setError("Enter a valid target price.");
      return;
    }

    try {
      await createAlert.mutateAsync({ product_name: productName.trim(), target_price: price });
      setProductName("");
      setTargetPrice("");
      toast({ variant: "success", title: "Price alert created" });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create this alert.");
    }
  }

  async function handleDelete(alertId: number) {
    try {
      await deleteAlert.mutateAsync(alertId);
      toast({ variant: "success", title: "Alert removed" });
    } catch (err) {
      toast({
        variant: "error",
        title: "Couldn't remove alert",
        description: err instanceof ApiError ? err.message : undefined,
      });
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-4 w-4 text-primary" />
            Create a price alert
          </CardTitle>
          <CardDescription>
            e.g. "Notify me when Sony WH-1000XM5 falls below ₹20,000." We check this every time that
            product's price is tracked from a search or product page.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreate} className="grid gap-4 sm:grid-cols-[1fr_180px_auto] sm:items-end">
            <div className="space-y-1.5">
              <label htmlFor="alert_product" className="text-sm font-medium text-foreground">
                Product name
              </label>
              <Input
                id="alert_product"
                placeholder="e.g. Sony WH-1000XM5 Headphones"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="alert_price" className="text-sm font-medium text-foreground">
                Notify below (₹)
              </label>
              <Input
                id="alert_price"
                type="number"
                min={1}
                placeholder="e.g. 500"
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value)}
              />
            </div>
            <Button type="submit" isLoading={createAlert.isPending}>
              <Plus className="h-4 w-4" />
              Add alert
            </Button>
          </form>
          {error && (
            <p className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Your alerts</h2>

        {isLoading && <p className="text-sm text-muted-foreground">Loading alerts…</p>}

        {!isLoading && alerts.length === 0 && (
          <EmptyState
            icon={BellRing}
            title="No price alerts yet"
            description="Create one above, or click 'Set a price alert' from any product's analytics page."
          />
        )}

        {alerts.map((alert) => (
          <Card key={alert.id}>
            <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-border bg-muted">
                  {alert.thumbnail ? (
                    <img src={alert.thumbnail} alt={alert.product_name} className="h-full w-full object-contain p-1" />
                  ) : (
                    <Store className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{alert.product_name}</p>
                  <p className="text-xs text-muted-foreground">
                    Notify below {formatPrice(alert.target_price, alert.currency)}
                    {alert.platform ? ` · ${alert.platform}` : ""}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {alert.is_active ? (
                  <Badge variant="secondary">Watching</Badge>
                ) : (
                  <Badge variant="success">
                    Triggered {alert.triggered_price ? `at ${formatPrice(alert.triggered_price, alert.currency)}` : ""}
                  </Badge>
                )}
                <span className="hidden text-xs text-muted-foreground sm:inline">
                  {formatDateTime(alert.created_at)}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Delete alert"
                  onClick={() => handleDelete(alert.id)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
