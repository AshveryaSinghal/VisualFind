import { useNavigate } from "react-router-dom";
import { Sparkles, ArrowRight } from "lucide-react";
import type { BestDealFound } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatPrice } from "@/utils/format";

interface BestDealCardProps {
  deal: BestDealFound | null;
}

export function BestDealCard({ deal }: BestDealCardProps) {
  const navigate = useNavigate();

  if (!deal) return null;

  return (
    <Card className="overflow-hidden border-success/30 bg-gradient-to-br from-success/10 via-transparent to-transparent">
      <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-success/15 text-success">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Best deal found so far
            </p>
            <p className="line-clamp-1 text-sm font-semibold text-foreground">{deal.label}</p>
            <p className="text-xs text-muted-foreground">
              {formatPrice(deal.price, null)}
              {deal.platform ? ` on ${deal.platform}` : ""}
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => navigate(`/results/${deal.search_id}`)}>
          View search
          <ArrowRight className="h-3.5 w-3.5" />
        </Button>
      </CardContent>
    </Card>
  );
}
