import React, { useRef } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Download, QrCode } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

/**
 * Printable QR code for the public experience. The URL already carries
 * `src=qr`, so scanned visits are attributed separately from WhatsApp links.
 * Download is SVG (vector): sharper than a rasterized PNG on printed flyers.
 */
export default function ShareQrCard({ url, publicId }) {
  const boxRef = useRef(null);

  const download = () => {
    const svg = boxRef.current?.querySelector("svg");
    if (!svg) return;
    const clone = svg.cloneNode(true);
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    const blob = new Blob([new XMLSerializer().serializeToString(clone)],
      { type: "image/svg+xml;charset=utf-8" });
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = `qr-${publicId || "menumind"}.svg`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(href), 0);
    toast.success("QR code téléchargé");
  };

  if (!url) return null;

  return (
    <div className="rounded-xl border border-border p-4 flex flex-col sm:flex-row sm:items-center gap-4"
      data-testid="share-qr-card">
      <div ref={boxRef} className="bg-white p-2 rounded-lg shrink-0" data-testid="share-qr-code">
        <QRCodeSVG value={url} size={132} level="M" bgColor="#ffffff" fgColor="#0F172A" />
      </div>
      <div className="space-y-2 min-w-0">
        <p className="font-medium flex items-center gap-2">
          <QrCode className="w-4 h-4 text-primary" /> QR code à imprimer
        </p>
        <p className="text-xs text-muted-foreground">
          Tables, flyers, vitrine : le scan ouvre votre catalogue avec l'assistant et marque la source « QR ».
        </p>
        <Button variant="outline" size="sm" onClick={download} data-testid="download-share-qr">
          <Download className="w-3.5 h-3.5 mr-1" /> Télécharger (SVG)
        </Button>
      </div>
    </div>
  );
}
