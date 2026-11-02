// The superuser's editor for the public site's posts and leaders.
import { useState } from "react";
import {
  useDeleteLeader,
  useDeletePost,
  useSaveLeader,
  useSavePost,
  useSiteLeaders,
  useSitePosts,
} from "../../api/hooks";
import {
  Badge,
  Button,
  ErrorState,
  Field,
  LoadingState,
  Modal,
  PageTitle,
  Panel,
} from "../../components/ui";
import { formatDate } from "../../lib/format";

const HTTPS = /^https:\/\/\S+$/;
const imageOk = (url) => !url.trim() || HTTPS.test(url.trim());

function PublishedBadge({ published }) {
  return <Badge text={published ? "Published" : "Draft"} tone={published ? "good" : "neutral"} />;
}

function ImageField({ label, value, onChange }) {
  return (
    <>
      <Field label={`${label} (optional)`}>
        <input aria-label={label} className="app-field" maxLength={500} placeholder="https://" value={value} onChange={onChange} />
      </Field>
      {!imageOk(value) && <div className="field-hint text-bad">Use an address starting with https://.</div>}
    </>
  );
}

function Saving({ write, ready, label, onClose, onSave }) {
  return (
    <>
      {write.isError && <div className="form-error">{write.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button onClick={onClose}>Cancel</Button>
        <Button primary disabled={!ready || write.isPending} onClick={onSave}>
          {write.isPending ? "Saving…" : label}
        </Button>
      </div>
    </>
  );
}

// Only the fields that differ from `row` are sent when editing.
function changedFrom(row, body) {
  return row ? Object.fromEntries(Object.entries(body).filter(([k, v]) => v !== row[k])) : body;
}

function PostForm({ post, onClose }) {
  const save = useSavePost();
  const [form, setForm] = useState({
    kind: post?.kind || "news",
    title: post?.title || "",
    body: post?.body || "",
    image_url: post?.image_url || "",
    event_date: post?.event_date || "",
    venue: post?.venue || "",
  });
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const event = form.kind === "event";
  const ready = form.title.trim() && imageOk(form.image_url) && (!event || form.event_date);

  const submit = () => {
    const body = {
      title: form.title.trim(),
      body: form.body,
      image_url: form.image_url.trim(),
      ...(event ? { event_date: form.event_date, venue: form.venue.trim() } : {}),
    };
    const sent = post ? changedFrom(post, body) : { kind: form.kind, ...body };
    if (post && Object.keys(sent).length === 0) return onClose();
    save.mutate(post ? { id: post.id, ...sent } : sent, { onSuccess: onClose });
  };

  return (
    <Modal title={post ? `Edit ${post.title}` : "New post"} sub="Saved as a draft until you publish it." onClose={onClose}>
      {!post && (
        <Field label="Kind">
          <select aria-label="Kind" className="app-field" value={form.kind} onChange={set("kind")}>
            <option value="news">News</option>
            <option value="event">Event</option>
          </select>
        </Field>
      )}
      <div className="field-gap" />
      <Field label="Title">
        <input aria-label="Title" className="app-field" maxLength={150} value={form.title} onChange={set("title")} />
      </Field>
      {event && (
        <>
          <div className="field-gap" />
          <div className="field-pair">
            <Field label="Date">
              <input aria-label="Date" type="date" className="app-field" value={form.event_date} onChange={set("event_date")} />
            </Field>
            <Field label="Venue (optional)">
              <input aria-label="Venue" className="app-field" maxLength={150} value={form.venue} onChange={set("venue")} />
            </Field>
          </div>
          {!form.event_date && <div className="field-hint">An event needs a date.</div>}
        </>
      )}
      <div className="field-gap" />
      <Field label="Text">
        <textarea aria-label="Text" className="app-field textarea" maxLength={20000} value={form.body} onChange={set("body")} />
      </Field>
      <div className="field-gap" />
      <ImageField label="Image address" value={form.image_url} onChange={set("image_url")} />
      <Saving write={save} ready={ready} label={post ? "Save post" : "Add post"} onClose={onClose} onSave={submit} />
    </Modal>
  );
}

function LeaderForm({ leader, onClose }) {
  const save = useSaveLeader();
  const [form, setForm] = useState({
    name: leader?.name || "",
    position: leader?.position || "",
    bio: leader?.bio || "",
    photo_url: leader?.photo_url || "",
    sort_order: leader ? String(leader.sort_order) : "0",
  });
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const orderOk = /^\d{1,5}$/.test(form.sort_order) && Number(form.sort_order) <= 10000;
  const ready = form.name.trim() && form.position.trim() && imageOk(form.photo_url) && orderOk;

  const submit = () => {
    const body = {
      name: form.name.trim(),
      position: form.position.trim(),
      bio: form.bio,
      photo_url: form.photo_url.trim(),
      sort_order: Number(form.sort_order),
    };
    const sent = changedFrom(leader, body);
    if (leader && Object.keys(sent).length === 0) return onClose();
    save.mutate(leader ? { id: leader.id, ...sent } : sent, { onSuccess: onClose });
  };

  return (
    <Modal title={leader ? `Edit ${leader.name}` : "New leader"} sub="Saved as a draft until you publish it." onClose={onClose}>
      <div className="field-pair">
        <Field label="Name">
          <input aria-label="Name" className="app-field" maxLength={150} value={form.name} onChange={set("name")} />
        </Field>
        <Field label="Position">
          <input aria-label="Position" className="app-field" maxLength={150} placeholder="Secretary General" value={form.position} onChange={set("position")} />
        </Field>
      </div>
      <div className="field-gap" />
      <Field label="Order on the page">
        <input aria-label="Order" className="app-field" inputMode="numeric" value={form.sort_order} onChange={set("sort_order")} />
      </Field>
      <div className="field-hint">Lower numbers come first; equal numbers go by name.</div>
      <div className="field-gap" />
      <Field label="Bio (optional)">
        <textarea aria-label="Bio" className="app-field textarea" maxLength={20000} value={form.bio} onChange={set("bio")} />
      </Field>
      <div className="field-gap" />
      <ImageField label="Photo address" value={form.photo_url} onChange={set("photo_url")} />
      <Saving write={save} ready={ready} label={leader ? "Save leader" : "Add leader"} onClose={onClose} onSave={submit} />
    </Modal>
  );
}

function ConfirmDelete({ what, write, id, onClose }) {
  return (
    <Modal title={`Delete ${what}?`} sub="It leaves the public site at once and cannot be brought back." onClose={onClose}>
      {write.isError && <div className="form-error">{write.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Button onClick={onClose}>Cancel</Button>
        <Button tone="danger" disabled={write.isPending} onClick={() => write.mutate(id, { onSuccess: onClose })}>
          Delete
        </Button>
      </div>
    </Modal>
  );
}

function Rows({ query, empty, columns, render }) {
  if (query.isLoading) return <LoadingState />;
  if (query.error) return <ErrorState error={query.error} />;
  return (
    <Panel pad={0}>
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>{columns.map((c) => <th key={c}>{c}</th>)}<th /></tr>
          </thead>
          <tbody>
            {query.data.map(render)}
            {query.data.length === 0 && <tr><td colSpan={columns.length + 1} className="empty-row">{empty}</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

export default function Website() {
  const posts = useSitePosts();
  const leaders = useSiteLeaders();
  const savePost = useSavePost();
  const saveLeader = useSaveLeader();
  const deletePost = useDeletePost();
  const deleteLeader = useDeleteLeader();
  const [modal, setModal] = useState(null);
  const close = () => setModal(null);

  const actions = (row, save, kind, label) => (
    <td className="actions-cell">
      <div className="flex justify-end gap-2">
        <Button onClick={() => setModal({ type: kind, row })}>Edit</Button>
        <Button disabled={save.isPending} onClick={() => save.mutate({ id: row.id, published: !row.published })}>
          {row.published ? "Unpublish" : "Publish"}
        </Button>
        <Button tone="danger" onClick={() => setModal({ type: `delete-${kind}`, row, label })}>Delete</Button>
      </div>
    </td>
  );

  return (
    <>
      <PageTitle title="Website" sub="News, events and leaders on the public site. Drafts stay hidden until published." />
      <div className="flex items-center justify-between gap-2 chip-row">
        <span className="card-title">Posts</span>
        <Button primary onClick={() => setModal({ type: "post" })}>New post</Button>
      </div>
      <Rows
        query={posts}
        empty="No posts yet."
        columns={["Title", "Kind", "Date", "Status"]}
        render={(p) => (
          <tr key={p.id}>
            <td className="strong">{p.title}</td>
            <td>{p.kind === "event" ? "Event" : "News"}</td>
            <td>{formatDate(p.kind === "event" ? p.event_date : p.published_on)}</td>
            <td><PublishedBadge published={p.published} /></td>
            {actions(p, savePost, "post", p.title)}
          </tr>
        )}
      />
      <div className="flex items-center justify-between gap-2 chip-row">
        <span className="card-title">Leaders</span>
        <Button primary onClick={() => setModal({ type: "leader" })}>New leader</Button>
      </div>
      <Rows
        query={leaders}
        empty="No leaders yet."
        columns={["Name", "Position", "Order", "Status"]}
        render={(l) => (
          <tr key={l.id}>
            <td className="strong">{l.name}</td>
            <td>{l.position}</td>
            <td>{l.sort_order}</td>
            <td><PublishedBadge published={l.published} /></td>
            {actions(l, saveLeader, "leader", l.name)}
          </tr>
        )}
      />
      {modal?.type === "post" && <PostForm post={modal.row} onClose={close} />}
      {modal?.type === "leader" && <LeaderForm leader={modal.row} onClose={close} />}
      {modal?.type === "delete-post" && <ConfirmDelete what={modal.label} write={deletePost} id={modal.row.id} onClose={close} />}
      {modal?.type === "delete-leader" && <ConfirmDelete what={modal.label} write={deleteLeader} id={modal.row.id} onClose={close} />}
    </>
  );
}
