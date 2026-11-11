// A PDF's first page drawn on the page itself, with a link to download the file.
import { useEffect, useRef, useState } from "react";
import { Download } from "lucide-react";
import { Card, CardTitle } from "@/components/ui/card";
import { loadPdf } from "@/lib/pdf";

/** Shows the first page of the PDF at `url` at the width of its column; only the link when it cannot be drawn. */
export function PdfViewer({ url, title }) {
  const canvas = useRef(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let stopped = false;
    let doc = null;
    setFailed(false);
    (async () => {
      try {
        doc = await loadPdf(url);
        const page = await doc.getPage(1);
        if (stopped) return;
        const width = canvas.current.parentElement.clientWidth || 720;
        const scale = (width / page.getViewport({ scale: 1 }).width) * (window.devicePixelRatio || 1);
        const viewport = page.getViewport({ scale });
        canvas.current.width = Math.floor(viewport.width);
        canvas.current.height = Math.floor(viewport.height);
        await page.render({ canvas: canvas.current, viewport }).promise;
      } catch {
        if (!stopped) setFailed(true);
      }
    })();
    return () => {
      stopped = true;
      doc?.destroy();
    };
  }, [url]);

  return (
    <section aria-label={title} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <CardTitle>{title}</CardTitle>
        <a href={url} download className="inline-flex items-center gap-1.5 text-ui font-bold">
          <Download size={18} aria-hidden />Download the PDF
        </a>
      </div>
      {failed ? <p role="alert" className="text-muted-foreground">The PDF cannot be shown here. Download it to read it.</p> : null}
      <Card variant="outline" className="p-2" hidden={failed}>
        <canvas ref={canvas} role="img" aria-label={title} className="block h-auto w-full" />
      </Card>
    </section>
  );
}
