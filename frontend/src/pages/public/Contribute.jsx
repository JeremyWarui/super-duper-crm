// /contribute: an amount and the giver's details. On the demo site nothing is charged or stored.
import { useState } from "react";
import { useContribute } from "@/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import PageHead from "./PageHead";

const AMOUNTS = [100, 500, 1000, 5000];

export default function Contribute() {
  const contribute = useContribute();
  const [form, setForm] = useState({ amount_kes: 500, name: "", phone: "", consent_given: false });
  const set = (key) => (e) =>
    setForm({ ...form, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  return (
    <div className="site-container py-12">
      <PageHead title="Contribute" lead="Your contribution funds the party's work in every county. Contributions are declared as the law requires." />
      <Card variant="elevated" className="max-w-[620px] gap-5 p-8">
        {contribute.data ? (
          <div role="status" className="flex flex-col gap-3">
            {contribute.data.demo ? <Badge tone="warn" kind="label" className="self-start">Demo</Badge> : null}
            <p className="text-base">{contribute.data.message}</p>
          </div>
        ) : (
          <form
            className="flex flex-col gap-5"
            onSubmit={(e) => {
              e.preventDefault();
              contribute.mutate({ ...form, amount_kes: Number(form.amount_kes) });
            }}
          >
            <fieldset className="flex flex-col gap-2">
              <legend className="pb-2 text-small font-semibold">Amount (KES)</legend>
              <div className="flex flex-wrap gap-2">
                {AMOUNTS.map((amount) => (
                  <Button
                    key={amount}
                    type="button"
                    variant={Number(form.amount_kes) === amount ? "primary" : "outline"}
                    aria-pressed={Number(form.amount_kes) === amount}
                    onClick={() => setForm({ ...form, amount_kes: amount })}
                  >
                    {amount.toLocaleString("en-KE")}
                  </Button>
                ))}
              </div>
            </fieldset>
            <Field label="Other amount (KES)">
              <Input size="lg" type="number" min={10} max={1000000} required value={form.amount_kes} onChange={set("amount_kes")} />
            </Field>
            <Field label="Full name">
              <Input size="lg" required value={form.name} onChange={set("name")} autoComplete="name" />
            </Field>
            <Field label="M-Pesa phone number">
              <Input size="lg" required type="tel" value={form.phone} onChange={set("phone")} placeholder="0712 345678" autoComplete="tel" />
            </Field>
            <label className="flex items-start gap-2.5 text-ui">
              <input type="checkbox" required checked={form.consent_given} onChange={set("consent_given")} className="mt-1 size-4 accent-primary" />
              <span>This contribution is my own money, and I am not a foreign or anonymous donor.</span>
            </label>
            {contribute.error ? <p role="alert" className="text-small font-semibold text-destructive">{contribute.error.message}</p> : null}
            <Button type="submit" size="lg" className="self-start" disabled={contribute.isPending}>
              Give KES {Number(form.amount_kes || 0).toLocaleString("en-KE")}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}
