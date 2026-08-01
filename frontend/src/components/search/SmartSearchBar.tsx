import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { ImagePlus, SendHorizontal, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];

interface SmartSearchBarProps {
  onTextSearch: (query: string) => void;
  onImageSelected: (file: File) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

export function SmartSearchBar({
  onTextSearch,
  onImageSelected,
  disabled,
  placeholder,
  className,
}: SmartSearchBarProps) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onTextSearch(trimmed);
    setValue("");
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!ACCEPTED_TYPES.includes(file.type)) return;
    onImageSelected(file);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={cn(
        "flex items-center gap-2 rounded-2xl border border-border bg-card p-2 shadow-sm focus-within:ring-2 focus-within:ring-primary/40",
        className
      )}
    >
      <Button
        type="button"
        variant="ghost"
        size="icon"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        aria-label="Upload a product image"
        className="shrink-0 text-muted-foreground hover:text-foreground"
      >
        <ImagePlus className="h-5 w-5" />
      </Button>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES.join(",")}
        className="hidden"
        onChange={handleFileChange}
      />

      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        disabled={disabled}
        placeholder={placeholder ?? "Describe what you need, or upload a photo…"}
        className="flex-1 bg-transparent px-1 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-60"
      />

      <Button
        type="submit"
        size="icon"
        disabled={disabled || !value.trim()}
        aria-label="Ask the AI Shopping Assistant"
        className="shrink-0"
      >
        {value.trim() ? <SendHorizontal className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
      </Button>
    </form>
  );
}
