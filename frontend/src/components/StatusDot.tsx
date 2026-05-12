import type { ConnStatus } from "@/lib/types";

const COLOR: Record<ConnStatus, string> = {
  connected: "#26d07c",
  reconnecting: "#ecad0a",
  disconnected: "#ef4d68",
};

const LABEL: Record<ConnStatus, string> = {
  connected: "LIVE",
  reconnecting: "RECONNECTING",
  disconnected: "OFFLINE",
};

export function StatusDot({ status }: { status: ConnStatus }) {
  return (
    <div
      className="flex items-center gap-2"
      data-testid="connection-status"
      data-state={status}
    >
      <span
        className={status !== "connected" ? "animate-pulse-dot" : ""}
        style={{
          display: "inline-block",
          width: 8,
          height: 8,
          borderRadius: 99,
          background: COLOR[status],
          boxShadow: `0 0 6px ${COLOR[status]}`,
        }}
      />
      <span className="panel-title" style={{ color: COLOR[status], letterSpacing: "0.22em" }}>
        {LABEL[status]}
      </span>
    </div>
  );
}
