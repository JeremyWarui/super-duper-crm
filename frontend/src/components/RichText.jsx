// Post text: a Tiptap editor with the site's toolbar.
import { useId, useRef, useState } from "react";
import { EditorContent, useEditor, useEditorState } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import { Bold, Heading2, Heading3, ImageUp, Italic, Link2, List, ListOrdered, Quote, Redo2, Strikethrough, Undo2 } from "lucide-react";
import { useUploadImage } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorText } from "@/components/ui/error-text";
import { useCopy } from "@/copy";
import { cn } from "@/lib/utils";

const LINK = /^(https:\/\/[^\s\\]+|mailto:[^\s\\]+|\/(?![/\\])[^\s\\]*)$/;

const extensions = [
  StarterKit.configure({
    heading: { levels: [2, 3] },
    code: false,
    codeBlock: false,
    horizontalRule: false,
    underline: false,
    link: { openOnClick: false, autolink: true, defaultProtocol: "https", HTMLAttributes: { rel: "noopener noreferrer", target: null } },
  }),
  Image.configure({ HTMLAttributes: { alt: "" } }),
];

function Tool({ label, icon: Icon, active, disabled, onClick }) {
  return (
    <button type="button" aria-label={label} title={label} aria-pressed={active ?? undefined} disabled={disabled} onClick={onClick}
      className={cn("grid size-9 place-items-center rounded-md text-ink hover:bg-stone disabled:opacity-40", active && "bg-ink text-white hover:bg-ink")}>
      <Icon size={18} aria-hidden />
    </button>
  );
}

/** A post's text. `onChange` gets the editor's HTML, or "" when it is empty. */
export function RichTextEditor({ label, hint, value, onChange, upload, area }) {
  const id = useId();
  const picker = useRef(null);
  const send = useUploadImage(upload);
  const copy = useCopy();
  const [linking, setLinking] = useState(null);
  const editor = useEditor({
    extensions,
    content: value || "",
    editorProps: {
      attributes: {
        role: "textbox",
        "aria-multiline": "true",
        "aria-labelledby": id,
        class: "rich-text min-h-[220px] px-3.5 py-3 outline-none",
      },
    },
    onUpdate: ({ editor: e }) => onChange(e.isEmpty ? "" : e.getHTML()),
  });
  const on = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      bold: e.isActive("bold"),
      italic: e.isActive("italic"),
      strike: e.isActive("strike"),
      h2: e.isActive("heading", { level: 2 }),
      h3: e.isActive("heading", { level: 3 }),
      bullets: e.isActive("bulletList"),
      numbers: e.isActive("orderedList"),
      quote: e.isActive("blockquote"),
      link: e.isActive("link"),
      undo: e.can().undo(),
      redo: e.can().redo(),
    }),
  });
  const run = (fn) => () => fn(editor.chain().focus()).run();
  const pick = (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) send.mutate({ file, area }, { onSuccess: (stored) => editor.chain().focus().setImage({ src: stored.url, alt: "" }).run() });
  };
  const openLink = () => setLinking(editor.getAttributes("link").href || "");
  const linkOk = linking !== null && LINK.test(linking.trim());
  const applyLink = () => {
    run((c) => c.extendMarkRange("link").setLink({ href: linking.trim() }))();
    setLinking(null);
  };
  const removeLink = () => {
    run((c) => c.extendMarkRange("link").unsetLink())();
    setLinking(null);
  };

  return (
    <div className="flex flex-col gap-1.5 text-small font-semibold">
      <span id={id}>{label}</span>
      <div className="overflow-hidden rounded-lg border border-line-control bg-white font-normal focus-within:border-ink">
        <div role="toolbar" aria-label={`${label} formatting`} className="flex flex-wrap items-center gap-0.5 border-b border-line bg-muted px-1.5 py-1">
          <Tool label="Bold" icon={Bold} active={on?.bold} onClick={run((c) => c.toggleBold())} />
          <Tool label="Italic" icon={Italic} active={on?.italic} onClick={run((c) => c.toggleItalic())} />
          <Tool label="Strikethrough" icon={Strikethrough} active={on?.strike} onClick={run((c) => c.toggleStrike())} />
          <span className="mx-1 h-6 w-px bg-line" aria-hidden />
          <Tool label="Heading" icon={Heading2} active={on?.h2} onClick={run((c) => c.toggleHeading({ level: 2 }))} />
          <Tool label="Subheading" icon={Heading3} active={on?.h3} onClick={run((c) => c.toggleHeading({ level: 3 }))} />
          <Tool label="Bulleted list" icon={List} active={on?.bullets} onClick={run((c) => c.toggleBulletList())} />
          <Tool label="Numbered list" icon={ListOrdered} active={on?.numbers} onClick={run((c) => c.toggleOrderedList())} />
          <Tool label="Quote" icon={Quote} active={on?.quote} onClick={run((c) => c.toggleBlockquote())} />
          <span className="mx-1 h-6 w-px bg-line" aria-hidden />
          <Tool label="Link" icon={Link2} active={on?.link} onClick={openLink} />
          <Tool label={send.isPending ? "Uploading image" : "Insert image"} icon={ImageUp} disabled={!upload || send.isPending} onClick={() => picker.current?.click()} />
          <input ref={picker} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" tabIndex={-1} aria-label={`Choose an image for ${label}`} onChange={pick} />
          <span className="ml-auto flex">
            <Tool label="Undo" icon={Undo2} disabled={!on?.undo} onClick={run((c) => c.undo())} />
            <Tool label="Redo" icon={Redo2} disabled={!on?.redo} onClick={run((c) => c.redo())} />
          </span>
        </div>
        {linking !== null ? (
          <div className="flex flex-wrap items-center gap-2 border-b border-line px-2 py-2">
            <Input aria-label="Link address" className="min-w-0 flex-[1_1_220px]" placeholder={copy.linkPlaceholder} value={linking} autoFocus
              onChange={(e) => setLinking(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && linkOk) { e.preventDefault(); applyLink(); } }} />
            <Button type="button" size="sm" shape="rounded" disabled={!linkOk} onClick={applyLink}>Apply link</Button>
            {on?.link ? <Button type="button" size="sm" shape="rounded" variant="quiet" onClick={removeLink}>Remove link</Button> : null}
            <Button type="button" size="sm" shape="rounded" variant="ghost" onClick={() => setLinking(null)}>Cancel</Button>
          </div>
        ) : null}
        <EditorContent editor={editor} />
      </div>
      {send.error ? <ErrorText error={send.error} />
        : hint ? <span className="font-normal text-muted-foreground">{hint}</span> : null}
    </div>
  );
}
