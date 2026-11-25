import React, { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ImagePlus, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";

// Accepted upload: any browser image up to 5 MB, resized to 512 px and stored
// as a JPEG data URL (~30-120 KB). No file storage service is required.
const MAX_INPUT_BYTES = 5 * 1024 * 1024;
const MAX_OUTPUT_CHARS = 400_000;
const MAX_DIMENSION = 512;

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("image illisible")); };
    img.src = url;
  });
}

async function toLogoDataUrl(file) {
  const img = await loadImage(file);
  const scale = Math.min(1, MAX_DIMENSION / Math.max(img.width, img.height));
  const width = Math.max(1, Math.round(img.width * scale));
  const height = Math.max(1, Math.round(img.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(img, 0, 0, width, height);
  return canvas.toDataURL("image/jpeg", 0.85);
}

/**
 * Logo input accepting either a public URL or an uploaded image.
 * `value` is stored as-is on the restaurant document (`logo` field).
 */
export default function LogoField({ label = "Logo", value = "", onChange, disabled = false, testId = "logo" }) {
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const isUpload = typeof value === "string" && value.startsWith("data:");

  const pickFile = () => fileRef.current?.click();

  const handleFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Choisissez une image (JPG, PNG, WebP).");
      return;
    }
    if (file.size > MAX_INPUT_BYTES) {
      toast.error("Image trop lourde (5 Mo maximum).");
      return;
    }
    setBusy(true);
    try {
      const dataUrl = await toLogoDataUrl(file);
      if (dataUrl.length > MAX_OUTPUT_CHARS) {
        toast.error("Image trop détaillée — essayez un fichier plus simple.");
        return;
      }
      onChange(dataUrl);
      toast.success("Logo téléversé");
    } catch {
      toast.error("Impossible de lire cette image.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex items-center gap-3">
        <div className="w-14 h-14 rounded-xl border border-border bg-secondary/40 grid place-items-center overflow-hidden shrink-0"
          data-testid={`${testId}-preview`}>
          {value ? (
            <img src={value} alt="" className="w-full h-full object-contain" />
          ) : (
            <ImagePlus className="w-5 h-5 text-muted-foreground" />
          )}
        </div>
        <div className="flex-1 min-w-0 space-y-2">
          <Input
            value={isUpload ? "" : value}
            disabled={disabled || busy}
            onChange={(e) => onChange(e.target.value)}
            placeholder={isUpload ? "Image téléversée" : "https://..."}
            data-testid={`${testId}-input`}
          />
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" size="sm" disabled={disabled || busy}
              onClick={pickFile} data-testid={`${testId}-upload`}>
              {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <ImagePlus className="w-3.5 h-3.5 mr-1" />}
              {busy ? "Traitement…" : "Téléverser une image"}
            </Button>
            {value && (
              <Button type="button" variant="ghost" size="sm" disabled={disabled || busy}
                onClick={() => onChange("")} data-testid={`${testId}-remove`}>
                <Trash2 className="w-3.5 h-3.5 mr-1" /> Retirer
              </Button>
            )}
          </div>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        URL publique ou image téléversée (JPG/PNG, redimensionnée à 512 px).
      </p>
      <input ref={fileRef} type="file" accept="image/*" className="hidden"
        onChange={handleFile} data-testid={`${testId}-file`} />
    </div>
  );
}
