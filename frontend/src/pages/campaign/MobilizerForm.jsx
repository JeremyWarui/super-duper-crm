import { useState } from "react";
import { useAddMobilizer, useCreateUser, useUpdateMobilizer } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { Check, Field, Input, NativeSelect } from "@/components/ui/input";
import { InviteDialog } from "@/components/ui/invite-dialog";
import { holderOf } from "./helpers";
import { loginBody, loginReady } from "@/components/LoginFields";
import LoginFields from "@/components/LoginFields";
import { useForm } from "@/lib/form";

// Units (wards, or centres in a ward race) with no mobilizer, plus the one `keep` holds.
const freeUnits = (units, mobilizers, keep) =>
  units.filter((u) => { const h = holderOf(mobilizers, u); return !h || h.id === keep?.id; });

// Adds a mobilizer, or edits one when `mobilizer` is given; the unit is optional.
export default function MobilizerForm({ campaignId, units, byCentre, mobilizers, mobilizer, onClose }) {
  const add = useAddMobilizer();
  const update = useUpdateMobilizer();
  const createUser = useCreateUser();
  const [name, setName] = useState(mobilizer?.full_name || ""); const [phone, setPhone] = useState(mobilizer?.phone || "");
  const [picked, setPicked] = useState(null);  // null until the user changes the ward box
  const unitKey = picked ?? (units.find((u) => mobilizer && holderOf([mobilizer], u))?.key || "");
  const [withLogin, setWithLogin] = useState(false);
  const [login, , setLogin] = useForm({ username: "", email: "" });
  const [made, setMade] = useState(null);
  const busy = add.isPending || update.isPending || createUser.isPending;
  const error = add.error || update.error || createUser.error;
  const ok = name.trim() && (!withLogin || loginReady(login));
  const choices = freeUnits(units, mobilizers, mobilizer);
  const unitWord = byCentre ? "centre" : "ward";

  const save = () => {
    const unit = units.find((u) => u.key === unitKey);
    const place = { ward: unit?.ward ?? null, registration_centre: unit?.registration_centre ?? null };
    if (mobilizer) {
      const moved = picked !== null;
      update.mutate({ id: mobilizer.id, full_name: name.trim(), phone: phone.trim(), ...(moved && place) }, { onSuccess: onClose });
    } else if (withLogin) {
      createUser.mutate(
        { ...loginBody({ name, phone, ...login }), role: "mobilizer", campaign: campaignId, ...place },
        { onSuccess: (created) => setMade({ ...created, place: unit?.name }) },
      );
    } else {
      add.mutate({ campaign: campaignId, ...place, full_name: name.trim(), phone: phone.trim() }, { onSuccess: onClose });
    }
  };

  if (made) {
    return (
      <InviteDialog title="Mobilizer added" invite={made.invite} username={made.username} onClose={onClose}>
        {made.place ? <>They work {made.place}.</> : <>Assign them a {unitWord} from the Wards page.</>}
      </InviteDialog>
    );
  }

  return (
    <Dialog title={mobilizer ? "Edit mobilizer" : "Add mobilizer"} description={`One mobilizer per ${unitWord}. The ${unitWord} can be left for later.`} onClose={onClose}>
      <Field label="Full name"><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Phone"><Input value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
      <Field label={byCentre ? "Registration centre" : "Ward"}>
        <NativeSelect aria-label={byCentre ? "Registration centre" : "Ward"} value={unitKey} onChange={(e) => setPicked(e.target.value)}>
          <option value="">No {unitWord} yet</option>
          {choices.map((u) => <option key={u.key} value={u.key}>{u.name}</option>)}
        </NativeSelect>
      </Field>
      {!mobilizer && (
        <Check className="text-ui text-muted-foreground" checked={withLogin} onChange={(e) => setWithLogin(e.target.checked)}>
          Give them a login, so they can record their own events and supporters.
        </Check>
      )}
      {withLogin && (
        <LoginFields fields={["username", "email"]} form={login} set={setLogin} />
      )}
      <ErrorText error={error} />
      <FormActions>
        <Button variant="quiet" onClick={onClose}>Cancel</Button>
        <Button loading={busy} disabled={!ok || busy} onClick={save}>{busy ? "Saving…" : "Save mobilizer"}</Button>
      </FormActions>
    </Dialog>
  );
}
