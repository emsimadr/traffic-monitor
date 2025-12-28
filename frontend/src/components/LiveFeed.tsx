/**
 * LiveFeed component - displays the MJPEG stream from the backend.
 * Gate lines are drawn server-side in the video stream.
 */
export function LiveFeed() {
  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
      <img
        src="/api/camera/live.mjpg"
        alt="Live feed"
        className="h-full w-full object-contain"
      />
    </div>
  );
}

