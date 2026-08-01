import { Bookmark } from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import { useSavedProductsContext, type SavableProduct } from "@/context/SavedProductsContext";

interface SaveButtonProps {
  product: SavableProduct;
  className?: string;
  variant?: "icon" | "full";
}

export function SaveButton({ product, className, variant = "icon" }: SaveButtonProps) {
  const { isSaved, toggle, isToggling } = useSavedProductsContext();
  const saved = isSaved(product);

  const handleClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    toggle(product);
  };

  if (variant === "full") {
    return (
      <Tooltip content={saved ? "Remove from saved" : "Save for later"}>
        <button
          type="button"
          aria-pressed={saved}
          aria-label={saved ? "Remove from saved" : "Save for later"}
          disabled={isToggling}
          onClick={handleClick}
          className={cn(
            buttonVariants({ variant: saved ? "default" : "outline", size: "sm" }),
            "flex-1 gap-1.5",
            !saved && "border-primary/40 text-primary hover:bg-primary/10 hover:text-primary",
            className
          )}
        >
          <Bookmark className={cn("h-3.5 w-3.5", saved && "fill-current")} />
          {saved ? "Saved" : "Save"}
        </button>
      </Tooltip>
    );
  }

  return (
    <Tooltip content={saved ? "Remove from saved" : "Save for later"}>
      <button
        type="button"
        aria-pressed={saved}
        aria-label={saved ? "Remove from saved" : "Save for later"}
        disabled={isToggling}
        onClick={handleClick}
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-full border border-border bg-background/90 text-muted-foreground shadow transition-colors hover:text-primary",
          saved && "border-primary/40 text-primary",
          className
        )}
      >
        <Bookmark className={cn("h-4 w-4", saved && "fill-current")} />
      </button>
    </Tooltip>
  );
}
