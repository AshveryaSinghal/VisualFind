import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ChevronDown, Check } from "lucide-react";
import { cn } from "@/utils/cn";

export interface SelectOption {
  value: string;
  label: string;
  icon?: ReactNode;
}

interface SelectProps {
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  className?: string;
  triggerClassName?: string;
}

export function Select({
  value,
  onValueChange,
  options,
  placeholder = "Select…",
  className,
  triggerClassName,
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const selected = options.find((option) => option.value === value);

  return (
    <div ref={containerRef} className={cn("relative inline-block text-left", className)}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={cn(
          "flex h-10 w-full items-center justify-between gap-2 rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors hover:bg-accent",
          triggerClassName
        )}
      >
        <span className="flex items-center gap-2 truncate">
          {selected?.icon}
          {selected?.label ?? placeholder}
        </span>
        <ChevronDown
          className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute z-50 mt-1.5 max-h-64 w-full min-w-[10rem] overflow-auto rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-lg animate-fade-in"
        >
          {options.map((option) => (
            <button
              type="button"
              key={option.value}
              role="option"
              aria-selected={option.value === value}
              onClick={() => {
                onValueChange(option.value);
                setOpen(false);
              }}
              className={cn(
                "flex w-full items-center justify-between gap-2 rounded-sm px-2 py-1.5 text-left text-sm transition-colors hover:bg-accent hover:text-accent-foreground",
                option.value === value && "bg-accent/60"
              )}
            >
              <span className="flex items-center gap-2 truncate">
                {option.icon}
                {option.label}
              </span>
              {option.value === value && <Check className="h-4 w-4 text-primary" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
