import { useState } from "react";
import { Modal, PasswordModal } from "../../components/ui";
import { useAddMobilizer, useCreateUser, useUpdateMobilizer } from "../../api/hooks";
import { Btn, Label, PrimaryBtn } from "./controls";
import { holderOf } from "./helpers";

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
  const [username, setUsername] = useState("");
  const [made, setMade] = useState(null);
  const busy = add.isPending || update.isPending || createUser.isPending;
  const error = add.error || update.error || createUser.error;
  const ok = name.trim() && (!withLogin || username.trim().length >= 3);
  const choices = freeUnits(units, mobilizers, mobilizer);
  const unitWord = byCentre ? "centre" : "ward";

  const save = () => {
    const [first, ...rest] = name.trim().split(/\s+/);
    const unit = units.find((u) => u.key === unitKey);
    const place = { ward: unit?.ward ?? null, registration_centre: unit?.registration_centre ?? null };
    if (mobilizer) {
      const moved = picked !== null;
      update.mutate({ id: mobilizer.id, full_name: name.trim(), phone: phone.trim(), ...(moved && place) }, { onSuccess: onClose });
    } else if (withLogin) {
      createUser.mutate(
        { username: username.trim().toLowerCase(), role: "mobilizer", first_name: first, last_name: rest.join(" "), phone: phone.trim(), campaign: campaignId, ...place },
        { onSuccess: (created) => setMade({ ...created, place: unit?.name }) },
      );
    } else {
      add.mutate({ campaign: campaignId, ...place, full_name: name.trim(), phone: phone.trim() }, { onSuccess: onClose });
    }
  };

  if (made) {
    return (
      <PasswordModal title="Mobilizer added" password={made.password} onClose={onClose}>
        <b>{made.username}</b> can now sign in{made.place ? <> and work {made.place}.</> : <>. Assign them a {unitWord} from the Overview.</>}
      </PasswordModal>
    );
  }

  return (
    <Modal title={mobilizer ? "Edit mobilizer" : "Add mobilizer"} sub={`One mobilizer per ${unitWord}. The ${unitWord} can be left for later.`} onClose={onClose}>
      <Label>Full name</Label><input className="app-field" value={name} onChange={(e) => setName(e.target.value)} />
      <div className="field-gap" /><Label>Phone</Label><input className="app-field" value={phone} onChange={(e) => setPhone(e.target.value)} />
      <div className="field-gap" /><Label>{byCentre ? "Registration centre" : "Ward"}</Label>
      <select aria-label={byCentre ? "Registration centre" : "Ward"} className="app-field" value={unitKey} onChange={(e) => setPicked(e.target.value)}>
        <option value="">No {unitWord} yet</option>
        {choices.map((u) => <option key={u.key} value={u.key}>{u.name}</option>)}
      </select>
      {!mobilizer && (
        <label className="flex items-start gap-2 checkbox-row">
          <input type="checkbox" checked={withLogin} onChange={(e) => setWithLogin(e.target.checked)} className="checkbox" />
          Give them a login, so they can record their own events and supporters.
        </label>
      )}
      {withLogin && (
        <>
          <div className="field-gap" /><Label>Username</Label>
          <input className="app-field" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="juma" />
        </>
      )}
      {error && <div className="form-error">{error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || busy} onClick={save}>{busy ? "Saving…" : "Save mobilizer"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

