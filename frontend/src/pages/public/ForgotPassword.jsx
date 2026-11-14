// Asks for a reset link by email; the answer is the same whether or not the address has a login.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useRequestReset } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { ErrorText } from "@/components/ui/error-text";
import { StatusText } from "@/components/ui/notice";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const request = useRequestReset();
  const submit = (e) => {
    e.preventDefault();
    if (email.trim()) request.mutate(email.trim());
  };
  return (
    <section className="mx-auto flex w-full max-w-[460px] flex-col gap-6 px-4 py-16">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-[34px] font-extrabold tracking-[-0.02em]">Forgot your password?</h1>
        <p className="text-muted-foreground">Give the email you sign in with. We send a link to choose a new password; it works for an hour.</p>
      </div>
      {request.isSuccess ? (
        <StatusText boxed>{request.data.detail}</StatusText>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-[18px]" noValidate>
          <Field label="Email">
            <Input size="lg" type="email" autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <ErrorText error={request.error} className="text-ui" />
          <Button loading={request.isPending} type="submit" size="lg" disabled={request.isPending || !email.trim()}>{request.isPending ? "Sending…" : "Send the link"}</Button>
        </form>
      )}
      <Link to="/signin" className="self-start font-bold">Back to sign in</Link>
    </section>
  );
}
