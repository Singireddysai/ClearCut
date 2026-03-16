import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import { FileVideo, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const ALLOWED = [".mp4", ".mov", ".avi", ".mkv", ".webm"];
const MAX_MB = 500;

interface UploadZoneProps {
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
}

export function UploadZone({ onUpload, disabled }: UploadZoneProps) {
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validate = useCallback((file: File) => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED.includes(ext)) {
      setError(`Unsupported format. Use: ${ALLOWED.join(", ")}`);
      return false;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File too large (max ${MAX_MB} MB)`);
      return false;
    }
    setError(null);
    return true;
  }, []);

  const handleFile = useCallback(
    async (file: File | null) => {
      if (!file || disabled || uploading) return;
      if (!validate(file)) return;
      setUploading(true);
      setError(null);
      try {
        await onUpload(file);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [onUpload, disabled, uploading, validate]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDrag(false);
      handleFile(e.dataTransfer.files?.[0] ?? null);
    },
    [handleFile]
  );

  const onInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      handleFile(e.target.files?.[0] ?? null);
      e.target.value = "";
    },
    [handleFile]
  );

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
      className={cn(
        "relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 transition-colors duration-200",
        drag && !disabled ? "border-accent bg-accent-muted" : "border-border bg-surface-elevated/50 hover:border-zinc-500",
        disabled && "pointer-events-none opacity-60"
      )}
    >
      <input
        type="file"
        accept={ALLOWED.join(",")}
        onChange={onInput}
        className="absolute inset-0 cursor-pointer opacity-0"
        disabled={disabled || uploading}
      />
      {uploading ? (
        <Loader2 className="h-14 w-14 text-accent animate-spin" />
      ) : (
        <FileVideo className="h-14 w-14 text-muted mb-4" />
      )}
      <p className="text-center text-zinc-300 font-medium">
        {uploading ? "Uploading…" : "Drop your video here or click to browse"}
      </p>
      <p className="mt-1 text-sm text-muted">
        MP4, MOV, AVI, MKV, WebM · max {MAX_MB} MB
      </p>
      {error && (
        <p className="mt-3 text-sm text-red-400" role="alert">
          {error}
        </p>
      )}
    </motion.div>
  );
}
