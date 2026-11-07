import { Button } from "@/components/ui/button";
import { useClipboard } from "@/lib/useClipboard";

// Copy a sign-up link, or send it on WhatsApp with a line saying what it is for.
export default function ShareLink({ link, message }) {
  const { copied, copy } = useClipboard();
  const whatsapp = `https://wa.me/?text=${encodeURIComponent(`${message} ${link}`)}`;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button shape="rounded" variant="quiet" onClick={() => copy(link)}>{copied ? "Copied" : "Copy link"}</Button>
      <Button asChild shape="rounded" variant="outline"><a href={whatsapp} target="_blank" rel="noreferrer">Share on WhatsApp</a></Button>
      {copied === false && <span className="text-small text-muted-foreground">This browser blocked copying; select the link above instead.</span>}
    </div>
  );
}
