import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Search,
  Trash2,
  ShieldCheck,
} from "lucide-react";
import type { HistoryItem } from "@/types";
import { formatDateTimeInZone, formatDurationMs, formatPrice, formatRelativeDate } from "@/utils/format";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip } from "@/components/ui/tooltip";
import { useHistoryFilters } from "@/hooks/useHistoryFilters";

const PAGE_SIZE = 10;

interface HistoryTableProps {
  items: HistoryItem[];
  onDelete: (id: number) => void;
  isDeleting: boolean;
  pendingDeleteId?: number | null;
}

export function HistoryTable({ items, onDelete, isDeleting, pendingDeleteId = null }: HistoryTableProps) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { query, setQuery, officialOnly, setOfficialOnly, filtered } = useHistoryFilters(items);
  const [page, setPage] = useState(0);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const paginated = filtered.slice(currentPage * PAGE_SIZE, currentPage * PAGE_SIZE + PAGE_SIZE);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(0);
            }}
            placeholder="Search history…"
            className="pl-9"
          />
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={officialOnly}
            onChange={(event) => {
              setOfficialOnly(event.target.checked);
              setPage(0);
            }}
            className="h-4 w-4 rounded border-input accent-primary"
          />
          Official listings only
        </label>
      </div>

      <div className="overflow-hidden rounded-xl border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Product</TableHead>
              <TableHead>Brand</TableHead>
              <TableHead>Best deal</TableHead>
              <TableHead>Matches</TableHead>
              <TableHead>Time</TableHead>
              <TableHead>Searched ({user?.timezone ?? "local time"})</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginated.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="max-w-[16rem]">
                  <div className="truncate font-medium text-foreground">
                    {item.best_guess_label ?? item.product_query ?? "Untitled search"}
                  </div>
                  {item.product_query && item.product_query !== item.best_guess_label && (
                    <div className="truncate text-xs text-muted-foreground">{item.product_query}</div>
                  )}
                </TableCell>
                <TableCell>
                  {item.detected_brand ? (
                    <div className="flex items-center gap-1.5">
                      <span>{item.detected_brand}</span>
                      {item.official_domain && (
                        <Tooltip content={`Official domain: ${item.official_domain}`}>
                          <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                        </Tooltip>
                      )}
                    </div>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>
                  {item.best_deal_platform ? (
                    <div>
                      <div className="font-medium text-foreground">
                        {formatPrice(item.best_deal_price, null)}
                      </div>
                      <div className="text-xs text-muted-foreground">{item.best_deal_platform}</div>
                    </div>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant="muted">
                    {item.filtered_count} / {item.result_count}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDurationMs(item.execution_time_ms)}
                </TableCell>
                <TableCell>
                  <Tooltip content={formatDateTimeInZone(item.created_at, user?.timezone)}>
                    <span className="text-muted-foreground">{formatRelativeDate(item.created_at)}</span>
                  </Tooltip>
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-1">
                    <Tooltip content="View results">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => navigate(`/results/${item.id}`)}
                      >
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    </Tooltip>
                    <Tooltip content="Delete">
                      <Button
                        variant="ghost"
                        size="icon"
                        isLoading={isDeleting && pendingDeleteId === item.id}
                        disabled={isDeleting && pendingDeleteId !== item.id}
                        onClick={() => onDelete(item.id)}
                        className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </Tooltip>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {paginated.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-12 text-center text-muted-foreground">
                  No searches match your filters.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {filtered.length > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Page {currentPage + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage >= totalPages - 1}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
