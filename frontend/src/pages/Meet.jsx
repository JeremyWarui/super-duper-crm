// One online call: check the microphone and camera, then join. Video calls show the LiveKit
// conference; audio calls show who is there and who is speaking.
import "@livekit/components-styles";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ControlBar,
  LiveKitRoom,
  PreJoin,
  RoomAudioRenderer,
  VideoConference,
  useIsSpeaking,
  useParticipants,
} from "@livekit/components-react";
import { useEndCall, useJoinCall } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { ErrorText } from "@/components/ui/error-text";
import { LoadingText } from "@/components/ui/loading-text";
import { useAuth } from "@/store/auth";
import { displayName } from "@/lib/format";

export default function Meet() {
  const { meetingId } = useParams();
  const user = useAuth((s) => s.user);
  const join = useJoinCall(meetingId);
  const end = useEndCall();
  const navigate = useNavigate();
  const [choices, setChoices] = useState(null);
  const [left, setLeft] = useState(false);

  if (join.isLoading) return <Frame><LoadingText /></Frame>;
  if (join.error) return <Frame><ErrorText error={join.error} /><Back /></Frame>;
  const { meeting, token, url, can_end: canEnd } = join.data;
  const video = meeting.mode === "video";
  if (left || meeting.status !== "live") {
    return <Frame title={meeting.title}><p className="text-ui">{left ? "You left the call." : "This call has ended."}</p><Back /></Frame>;
  }
  if (!choices) {
    return (
      <Frame title={meeting.title} note={video ? "Video call" : "Audio only: no camera, less data"}>
        <div data-lk-theme="default" className="overflow-hidden rounded-xl">
          <PreJoin
            defaults={{ username: displayName(user), videoEnabled: video, audioEnabled: true }}
            camLabel={video ? "Camera" : undefined}
            joinLabel="Join call"
            userLabel="Your name"
            onSubmit={setChoices}
            persistUserChoices={false}
          />
        </div>
      </Frame>
    );
  }
  return (
    <div data-lk-theme="default" className="flex h-dvh flex-col">
      <LiveKitRoom
        serverUrl={url}
        token={token}
        connect
        audio={choices.audioEnabled ? { deviceId: choices.audioDeviceId } : false}
        video={video && choices.videoEnabled ? { deviceId: choices.videoDeviceId } : false}
        onDisconnected={() => setLeft(true)}
        className="flex min-h-0 flex-1 flex-col"
      >
        {video ? <VideoConference /> : <AudioRoom title={meeting.title} />}
        {canEnd && (
          <div className="flex justify-center p-2">
            <Button variant="outline" loading={end.isPending} onClick={() => end.mutate(meeting.id, { onSuccess: () => navigate("/campaign/calls") })}>
              End for everyone
            </Button>
          </div>
        )}
      </LiveKitRoom>
    </div>
  );
}

function AudioRoom({ title }) {
  const people = useParticipants();
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center gap-4 p-6">
      <h1 className="font-display text-h2 font-extrabold">{title}</h1>
      <ul className="grid w-full max-w-md gap-2" aria-label="In the call">
        {people.map((p) => <Person key={p.identity} participant={p} />)}
      </ul>
      <RoomAudioRenderer />
      <ControlBar controls={{ microphone: true, camera: false, screenShare: false, chat: false, leave: true, settings: false }} />
    </div>
  );
}

function Person({ participant }) {
  const speaking = useIsSpeaking(participant);
  return (
    <li className="flex items-center justify-between rounded-lg border border-white/15 px-4 py-3">
      <span className="font-semibold">{participant.name || "Guest"}{participant.isLocal ? " (you)" : ""}</span>
      <span aria-label={speaking ? "Speaking" : "Quiet"} className={`h-3 w-3 rounded-full ${speaking ? "bg-green-400" : "bg-white/20"}`} />
    </li>
  );
}

function Frame({ title, note, children }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col gap-4 p-4 sm:p-8">
      {title && <h1 className="font-display text-h2 font-extrabold">{title}</h1>}
      {note && <p className="text-ui text-muted-foreground">{note}</p>}
      {children}
    </main>
  );
}

const Back = () => <Link to="/" className="font-bold">Back to the app</Link>;
