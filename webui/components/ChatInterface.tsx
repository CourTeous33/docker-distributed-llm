import { useState, useRef, useEffect } from "react";
import ReactMarkdown from 'react-markdown';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  metrics?: {
    ttft?: number;
    totalDelay?: number;
    tokenCount?: number;
    generationTime?: number;
    cpuStats?: Record<string, { max: number; avg: number }>;
    memStats?: Record<string, { max: number; avg: number }>;
  };
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [maxTokens, setMaxTokens] = useState(256);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: input,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    const assistantMessageId = (Date.now() + 1).toString();
    // Initialize metrics
    let metrics: Message["metrics"] = {
      ttft: 0,
      totalDelay: 0,
      tokenCount: 0,
      generationTime: 0,
      cpuStats: undefined,
      memStats: undefined
    };
    let fullResponse = "";
    const startTime = Date.now();

    // Add placeholder assistant message
    setMessages(prev => [
      ...prev,
      {
        id: assistantMessageId,
        type: 'assistant',
        content: "",
        timestamp: new Date()
      }
    ]);

    try {
      const eventSource = new EventSource(
        `/api/stream?prompt=${encodeURIComponent(input)}&max_tokens=${maxTokens}`
      );

      eventSource.onmessage = (event) => {
        const data = event.data;
        if (data === "[DONE]") {
          metrics.generationTime = (Date.now() - startTime) / 1000;
          // Attach metrics to the assistant message
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessageId
                ? { ...msg, metrics }
                : msg
            )
          );
          setLoading(false);
          eventSource.close();
          return;
        }

        try {
          const parsed = JSON.parse(data);

          if (parsed.text) {
            // Only add space if:
            // 1. The new text doesn't start with punctuation
            // 2. The current response doesn't end with a special markdown character
            const needsSpace = 
              !/^[.,!?;:'\)\]\}\-]/.test(parsed.text) && 
              !/[\s\n#*_`\[\(]$/.test(fullResponse);
            
            fullResponse += needsSpace ? " " + parsed.text : parsed.text;
            metrics.tokenCount! += 1;
            setMessages(prev =>
              prev.map(msg =>
                msg.id === assistantMessageId
                  ? { ...msg, content: fullResponse }
                  : msg
              )
            );
          }
          if (parsed.ttft !== undefined) {
            metrics.ttft = parsed.ttft;
          }
          if (parsed.total_delay !== undefined) {
            metrics.totalDelay = parsed.total_delay;
          }
          if (parsed.cpu_stats) {
            metrics.cpuStats = parsed.cpu_stats;
          }
          if (parsed.mem_stats) {
            metrics.memStats = parsed.mem_stats;
          }
        } catch {
          // Non-JSON chunk
          fullResponse += data;
          metrics.tokenCount! += 1;
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessageId
                ? { ...msg, content: fullResponse }
                : msg
            )
          );
        }
      };

      eventSource.onerror = () => {
        console.error("Streaming error");
        eventSource.close();
        setLoading(false);
      };
    } catch (err) {
      console.error("Generation error:", err);
      setLoading(false);
    }
  };

  return (
    <div className="d-flex flex-column h-100 border-end">
      {/* Header */}
      <div className="p-3 border-bottom bg-white">
        <h1 className="h5 fw-semibold text-dark mb-1">Distributed LLM Inference</h1>
        <p className="small text-muted">Chat with our distributed LLM model</p>
      </div>

      {/* Messages */}
      <div className="flex-grow-1 overflow-auto p-3" style={{ gap: '1rem', display: 'flex', flexDirection: 'column' }}>
        {messages.length === 0 && (
          <div className="d-flex flex-column align-items-center justify-content-center h-100 text-center">
            <div className="mb-3 p-3 bg-black rounded-circle border border-primary">
              <span style={{ fontSize: '4rem' }}>🤖</span>
            </div>
            <h2 className="h4 fw-semibold text-dark mb-2">Hi there! 👋</h2>
            <p className="text-muted" style={{ maxWidth: '500px' }}>
              How can we help? Ask me anything to get started.
            </p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`d-flex ${message.type === 'user' ? 'justify-content-end' : 'justify-content-start'}`}
          >
            <div
              className={`card ${
                message.type === 'user'
                  ? 'bg-primary text-white'
                  : 'bg-light'
              }`}
              style={{
                maxWidth: '75%',
                borderRadius: '1rem',
                boxShadow: message.type === 'user' ? 'none' : '0 2px 4px rgba(0,0,0,0.05)'
              }}
            >
              <div className="card-body">
                <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {message.type === 'assistant' ? (
                    <ReactMarkdown>
                      {message.content}
                    </ReactMarkdown>
                  ) : (
                    message.content
                  )}
                </div>

                {message.metrics && (
                  <div className="mt-2 pt-2 border-top small opacity-75">
                  <div className="row row-cols-2 g-2">
                    <div className="col">TTFT: {message.metrics.ttft?.toFixed(2)}s</div>
                    <div className="col">Tokens: {message.metrics.tokenCount}</div>
                    <div className="col">Time: {message.metrics.generationTime?.toFixed(2)}s</div>
                    <div className="col">Delay: {message.metrics.totalDelay?.toFixed(2)}s</div>
                  </div>
                
                  {/* new side‑by‑side CPU & Memory */}
                  <div className="row mt-2">
                    {message.metrics.cpuStats && (
                      <div className="col">
                        <strong>CPU:</strong>
                        <ul className="ps-3 mb-0">
                          {Object.entries(message.metrics.cpuStats).map(([name, stats]) => (
                            <li key={name}>
                              {name}: max {stats.max.toFixed(2)}%, avg {stats.avg.toFixed(2)}%
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                
                    {message.metrics.memStats && (
                      <div className="col">
                        <strong>Memory:</strong>
                        <ul className="ps-3 mb-0">
                          {Object.entries(message.metrics.memStats).map(([name, stats]) => (
                            <li key={name}>
                              {name}: max {stats.max.toFixed(2)}MB, avg {stats.avg.toFixed(2)}MB
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
                
                )}
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="d-flex justify-content-start">
            <div className="card bg-light border-0" style={{ borderRadius: '1rem', padding: '0.75rem 1rem' }}>
              <div className="d-flex align-items-center">
                <div className="spinner-grow spinner-grow-sm text-secondary me-1" role="status" style={{ animationDelay: '0ms' }}></div>
                <div className="spinner-grow spinner-grow-sm text-secondary me-1" role="status" style={{ animationDelay: '150ms' }}></div>
                <div className="spinner-grow spinner-grow-sm text-secondary" role="status" style={{ animationDelay: '300ms' }}></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input form */}
      <div className="p-3 border-top bg-white">
        <form onSubmit={handleSubmit}>
          <div className="d-flex gap-2">
            <input
              type="text"
              className="form-control py-2"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask me anything..."
              disabled={loading}
            />
            <button
              type="submit"
              className={`btn ${loading || !input.trim() ? "btn-secondary" : "btn-primary"} px-4`}
              disabled={loading || !input.trim()}
            >
              Send
            </button>
          </div>

          <div className="mt-2 d-flex align-items-center gap-3">
            <label className="text-muted mb-0 small">
              Max tokens:
              <input
                type="number"
                className="form-control form-control-sm d-inline-block ms-2"
                value={maxTokens}
                onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                min={1}
                max={1024}
                style={{ width: '80px' }}
              />
            </label>
          </div>
        </form>
      </div>
    </div>
  );
}
