// /contribute: give by M-Pesa in a dialog, beside the how-to-give text from the site settings.
// `?amount=` (from the chip-in buttons) opens the dialog with that amount chosen.
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useSite } from "@/api/hooks";
import PayDialog from "@/components/PayDialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useCopy } from "@/copy";
import PageHead from "@/components/PageHead";

export default function Contribute() {
  const site = useSite().data;
  const copy = useCopy();
  const [params] = useSearchParams();
  const asked = Number(params.get("amount")) || 0;
  const [giving, setGiving] = useState(asked > 0);
  const instructions = site?.payment_instructions?.trim();
  return (
    <div className="site-container py-12">
      <PageHead title="Contribute" lead={copy.contributeLead} />
      <div className="flex flex-wrap items-start gap-6">
        <Card variant="elevated" className="max-w-[460px] flex-[1_1_320px] gap-3 p-8">
          <h2 className="text-[20px] font-bold">Give by M-Pesa</h2>
          <p className="text-text-2">Get a prompt on your phone, or pay by Paybill or Till and send us the code.</p>
          <Button className="self-start" onClick={() => setGiving(true)}>Give now</Button>
        </Card>
        {instructions ? (
          <Card className="max-w-[460px] flex-[1_1_320px] gap-3 p-8">
            <h2 className="text-[20px] font-bold">Other ways to give</h2>
            <p className="whitespace-pre-line text-base">{instructions}</p>
          </Card>
        ) : null}
      </div>
      {giving ? <PayDialog title="Contribute" amount={asked || undefined} onClose={() => setGiving(false)} /> : null}
    </div>
  );
}
