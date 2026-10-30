import { useState } from "react";
import { Modal, PasswordModal } from "../../components/ui";
import { useSetManager } from "../../api/hooks";
import { Btn, Label, PrimaryBtn } from "./controls";

// The aspirant adds the manager, or replaces `sitting`, whose login is then turned off.
export default function ManagerForm({ campaignId, sitting, onClose }) {
  const set = useSetManager();
  const [name, setName] = useState(""); const [username, setUsername] = useState(""); const [phone, setPhone] = useState("");
  const ok = name.trim() && username.trim().length >= 3;
  const made = set.data;

  if (made) {
    return (
      <PasswordModal title="Manager added" password={made.password} onClose={onClose}>
        <b>{made.username}</b> can now sign in and run this campaign.{made.replaced && <> {made.replaced} is off the campaign and can no longer sign in.</>}
      </PasswordModal>
    );
  }

  const save = () => {
    const [first, ...rest] = name.trim().split(/\s+/);
    set.mutate({ campaign: campaignId, username: username.trim().toLowerCase(), first_name: first, last_name: rest.join(" "), phone: phone.trim(), replace: !!sitting });
  };
  return (
    <Modal title={sitting ? "Replace manager" : "Add manager"} sub={sitting ? `${sitting.full_name || sitting.username} comes off the campaign and their login is turned off.` : "One manager per campaign. They add mobilizers and run the day-to-day."} onClose={onClose}>
      <Label>Full name</Label><input aria-label="Full name" className="app-field" value={name} onChange={(e) => setName(e.target.value)} />
      <div className="field-gap" /><Label>Username</Label><input aria-label="Username" className="app-field" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="amina" />
      <div className="field-gap" /><Label>Phone</Label><input aria-label="Phone" className="app-field" value={phone} onChange={(e) => setPhone(e.target.value)} />
      {set.error && <div className="form-error">{set.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || set.isPending} onClick={save}>{set.isPending ? "Saving…" : sitting ? "Replace manager" : "Add manager"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

