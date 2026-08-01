import { useCallback, useRef, useState, type DragEvent, type ChangeEvent } from "react";
import { motion } from "framer-motion";
import { Camera, ImagePlus, Upload, X } from "lucide-react";
import { cn } from "@/utils/cn";
import { Button } from "@/components/ui/button";
import { CameraCapture } from "@/components/upload/CameraCapture";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_SIZE_MB = 8;

interface UploadDropzoneProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
  className?: string;
}

export function UploadDropzone({ onFileSelected, disabled, className }: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndEmit = useCallback(
    (file: File | undefined) => {
      if (!file) return;
      setValidationError(null);

      if (!ACCEPTED_TYPES.includes(file.type)) {
        setValidationError("Please upload a JPEG, PNG, or WebP image.");
        return;
      }
      const sizeMb = file.size / (1024 * 1024);
      if (sizeMb > MAX_SIZE_MB) {
        setValidationError(`File is too large (${sizeMb.toFixed(1)}MB). Max is ${MAX_SIZE_MB}MB.`);
        return;
      }

      const objectUrl = URL.createObjectURL(file);
      setPreview(objectUrl);
      setFileName(file.name);
      onFileSelected(file);
    },
    [onFileSelected]
  );

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    validateAndEmit(event.dataTransfer.files?.[0]);
  };

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    validateAndEmit(event.target.files?.[0]);
  };

  const handleCameraCapture = (file: File) => {
    validateAndEmit(file);
  };

  const clearPreview = () => {
    setPreview(null);
    setFileName(null);
    setValidationError(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div className={className}>
      <motion.div
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && !preview && inputRef.current?.click()}
        animate={{
          borderColor: isDragging ? "hsl(var(--primary))" : "hsl(var(--border))",
          scale: isDragging ? 1.01 : 1,
        }}
        transition={{ duration: 0.15 }}
        className={cn(
          "relative flex min-h-[22rem] cursor-pointer flex-col items-center justify-center overflow-hidden rounded-2xl border-2 border-dashed bg-card/50 p-8 text-center transition-colors",
          disabled && "pointer-events-none opacity-60",
          !preview && "hover:border-primary/60 hover:bg-accent/30"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(",")}
          onChange={handleChange}
          className="hidden"
          disabled={disabled}
        />

        {preview ? (
          <div className="relative flex w-full max-w-sm flex-col items-center gap-4">
            <div className="relative w-full overflow-hidden rounded-xl border border-border shadow-lg">
              <img src={preview} alt="Selected product preview" className="max-h-72 w-full object-contain bg-black/5" />
              {!disabled && (
                <button
                  onClick={(event) => {
                    event.stopPropagation();
                    clearPreview();
                  }}
                  aria-label="Remove selected image"
                  className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full bg-background/90 text-foreground shadow-md transition hover:bg-background"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <p className="truncate text-sm text-muted-foreground">{fileName}</p>
          </div>
        ) : (
          <>
            <motion.div
              animate={{ y: isDragging ? -4 : 0 }}
              className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10"
            >
              {isDragging ? (
                <Upload className="h-7 w-7 text-primary" />
              ) : (
                <ImagePlus className="h-7 w-7 text-primary" />
              )}
            </motion.div>
            <p className="text-lg font-semibold text-foreground">
              {isDragging ? "Drop your image here" : "Drag & drop a product photo"}
            </p>
            <p className="mt-1.5 text-sm text-muted-foreground">
              or click to browse — JPEG, PNG, or WebP, up to {MAX_SIZE_MB}MB
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={(event) => {
                  event.stopPropagation();
                  inputRef.current?.click();
                }}
              >
                <Upload className="h-4 w-4" />
                Choose a photo
              </Button>
              <Button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  if (!disabled) setIsCameraOpen(true);
                }}
              >
                <Camera className="h-4 w-4" />
                Use camera
              </Button>
            </div>
          </>
        )}
      </motion.div>

      {validationError && (
        <p className="mt-3 text-center text-sm text-destructive">{validationError}</p>
      )}

      <CameraCapture
        open={isCameraOpen}
        onOpenChange={setIsCameraOpen}
        onCapture={handleCameraCapture}
      />
    </div>
  );
}
