import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Camera, RotateCcw, Check, AlertCircle, SwitchCamera, X } from "lucide-react";
import { Dialog, DialogHeader, DialogTitle, DialogDescription, DialogCloseButton } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface CameraCaptureProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCapture: (file: File) => void;
}

export function CameraCapture({ open, onOpenChange, onCapture }: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [snapshot, setSnapshot] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const startStream = useCallback(async () => {
    setError(null);
    setIsReady(false);
    stopStream();

    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Your browser doesn't support camera access. Try uploading a photo instead.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode, width: { ideal: 1280 }, height: { ideal: 1280 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setIsReady(true);
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setError("Camera access was denied. Allow camera permission and try again.");
      } else if (name === "NotFoundError" || name === "DevicesNotFoundError") {
        setError("No camera was found on this device.");
      } else {
        setError("Couldn't start the camera. Try uploading a photo instead.");
      }
    }
  }, [facingMode, stopStream]);

  useEffect(() => {
    if (!open) {
      stopStream();
      setSnapshot(null);
      setIsReady(false);
      return;
    }
    setSnapshot(null);
    startStream();
    return () => stopStream();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, facingMode]);

  const handleClose = () => {
    stopStream();
    onOpenChange(false);
  };

  const handleTakePhoto = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    setSnapshot(canvas.toDataURL("image/jpeg", 0.92));
  };

  const handleRetake = () => {
    setSnapshot(null);
  };

  const handleUseSnapshot = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const file = new File([blob], `camera-capture-${Date.now()}.jpg`, { type: "image/jpeg" });
        onCapture(file);
        stopStream();
        onOpenChange(false);
      },
      "image/jpeg",
      0.92
    );
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogCloseButton onClick={handleClose} />
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <Camera className="h-5 w-5 text-primary" />
          Take a photo
        </DialogTitle>
        <DialogDescription>
          Center the product in frame with good lighting, then snap a picture to search.
        </DialogDescription>
      </DialogHeader>

      <div className="relative aspect-square w-full overflow-hidden rounded-xl border border-border bg-black">
        {error ? (
          <div className="flex h-full w-full flex-col items-center justify-center gap-3 p-6 text-center">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button variant="outline" size="sm" onClick={startStream}>
              <RotateCcw className="h-4 w-4" />
              Try again
            </Button>
          </div>
        ) : snapshot ? (
          <img src={snapshot} alt="Captured product" className="h-full w-full object-contain" />
        ) : (
          <>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="h-full w-full object-cover"
            />
            {!isReady && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                <motion.div
                  animate={{ opacity: [0.4, 1, 0.4] }}
                  transition={{ repeat: Infinity, duration: 1.4 }}
                  className="text-sm text-white"
                >
                  Starting camera…
                </motion.div>
              </div>
            )}
          </>
        )}
        <canvas ref={canvasRef} className="hidden" />
      </div>

      <div className="mt-5 flex items-center justify-center gap-3">
        {snapshot ? (
          <>
            <Button variant="outline" onClick={handleRetake}>
              <RotateCcw className="h-4 w-4" />
              Retake
            </Button>
            <Button onClick={handleUseSnapshot}>
              <Check className="h-4 w-4" />
              Use this photo
            </Button>
          </>
        ) : (
          <>
            {!error && (
              <Button
                variant="outline"
                size="icon"
                aria-label="Switch camera"
                onClick={() => setFacingMode((mode) => (mode === "environment" ? "user" : "environment"))}
              >
                <SwitchCamera className="h-4 w-4" />
              </Button>
            )}
            <Button onClick={handleTakePhoto} disabled={!isReady || !!error}>
              <Camera className="h-4 w-4" />
              Capture
            </Button>
            <Button variant="outline" onClick={handleClose}>
              <X className="h-4 w-4" />
              Cancel
            </Button>
          </>
        )}
      </div>
    </Dialog>
  );
}
