import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "@/components/ChatPanel";
import type { ChatMessage } from "@/lib/types";

const baseTs = Date.now();

const messages: ChatMessage[] = [
  { id: "1", role: "user", content: "Buy 5 AAPL", created_at: baseTs },
  {
    id: "2",
    role: "assistant",
    content: "Done — bought 5 AAPL at the latest market price.",
    actions: { trades: [{ ticker: "AAPL", side: "buy", quantity: 5, status: "filled" }] },
    created_at: baseTs + 100,
  },
];

describe("ChatPanel", () => {
  it("renders user and assistant messages", () => {
    render(
      <ChatPanel messages={messages} busy={false} onSend={async () => {}} open onToggle={() => {}} />,
    );
    expect(screen.getByTestId("chat-message-user").textContent).toMatch(/Buy 5 AAPL/);
    expect(screen.getByTestId("chat-message-assistant").textContent).toMatch(/Done/);
  });

  it("renders structured actions inline", () => {
    render(
      <ChatPanel messages={messages} busy={false} onSend={async () => {}} open onToggle={() => {}} />,
    );
    expect(screen.getByText(/FILLED.*BUY 5 AAPL/i)).toBeInTheDocument();
  });

  it("calls onSend with trimmed text and clears input", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<ChatPanel messages={[]} busy={false} onSend={onSend} open onToggle={() => {}} />);
    const input = screen.getByTestId("chat-input") as HTMLInputElement;
    await user.type(input, "  hello  ");
    await user.click(screen.getByTestId("chat-send"));
    expect(onSend).toHaveBeenCalledWith("hello");
    expect(input.value).toBe("");
  });

  it("shows loading state when busy", () => {
    render(<ChatPanel messages={messages} busy onSend={async () => {}} open onToggle={() => {}} />);
    expect(screen.getByText(/FINALLY THINKING/i)).toBeInTheDocument();
  });

  it("collapsed state renders toggle button", () => {
    render(<ChatPanel messages={[]} busy={false} onSend={async () => {}} open={false} onToggle={() => {}} />);
    expect(screen.getByTestId("chat-toggle")).toBeInTheDocument();
  });
});
