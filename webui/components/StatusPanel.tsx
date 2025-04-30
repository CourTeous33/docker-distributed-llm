import { useState, useEffect } from "react";
import axios from "axios";

interface WorkerStatus {
  worker_id: number;
  status: string;
  is_available: boolean;
  memory_usage_mb?: number;
  cpu_usage_percent?: number;
}

interface SystemInfo {
  server_status: string;
  total_workers: number;
  available_workers: number;
  model_path: string;
  tokenizer_path: string;
}

export default function StatusPanel() {
  const [isOpen, setIsOpen] = useState(true);
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [workersResponse, systemResponse] = await Promise.all([
          axios.get("/api/workers/status"),
          axios.get("/api/system/status"),
        ]);
        setWorkers(workersResponse.data);
        setSystemInfo(systemResponse.data);
      } catch (err) {
        console.error("Error fetching status:", err);
        setError("Error fetching status");
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 500);
    return () => clearInterval(interval);
  }, []);

  const formatUptime = (seconds: number): string => {
    if (seconds < 60) return `${seconds.toFixed(0)}s`;
    if (seconds < 3600)
      return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor(
      (seconds % 3600) / 60
    )}m`;
  };

  return (
    <div
      className="position-fixed top-0 end-0 h-100 bg-white border-start shadow-lg"
      style={{
        width: isOpen ? "320px" : "50px",
        transition: "width 0.3s ease-in-out",
        // Set a high z-index but still lower than form elements
        zIndex: 100,
      }}
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="position-absolute btn btn-light border rounded-circle shadow-sm"
        style={{
          left: "-20px",
          top: "50%",
          transform: "translateY(-50%)",
          width: "40px",
          height: "40px",
          padding: "0",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 101,
        }}
      >
        <svg
          style={{
            width: "16px",
            height: "16px",
            transition: "transform 0.3s",
            transform: isOpen ? "rotate(0deg)" : "rotate(180deg)",
          }}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
      </button>

      {isOpen && (
        <div className="p-3 h-100 overflow-auto">
          <h2 className="h5 fw-semibold mb-4">System Status</h2>

          {/* System Information */}
          {systemInfo && (
            <div className="mb-4">
              <h3 className="small fw-medium text-muted mb-2">Server</h3>
              <div className="card bg-light mb-3">
                <div className="card-body p-3">
                  <div className="d-flex justify-content-between align-items-center mb-2">
                    <span className="small">Status</span>
                    <span
                      className={`badge ${
                        systemInfo.server_status === "running"
                          ? "bg-success"
                          : "bg-danger"
                      }`}
                    >
                      {systemInfo.server_status}
                    </span>
                  </div>
                  <div className="d-flex justify-content-between align-items-center mb-2">
                    <span className="small">Workers</span>
                    <span className="small fw-medium">
                      {systemInfo.available_workers}/{systemInfo.total_workers}
                    </span>
                  </div>
                  <div className="small text-muted">
                    <span>Model:</span>
                    <div style={{ fontSize: 12 }}>{systemInfo.model_path}</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Workers Grid */}
          <div className="mb-4">
            <div className="d-flex justify-content-between align-items-center mb-2">
              <h3 className="small fw-medium text-muted">Workers</h3>
            </div>

            <div className="d-flex flex-column gap-2">
              {workers.map((worker) => (
                <div
                  key={worker.worker_id}
                  className={`card ${
                    worker.is_available ? "border-success" : "border-danger"
                  }`}
                  style={{ borderWidth: "1px" }}
                >
                  <div className="card-body p-3">
                    <div className="d-flex justify-content-between align-items-center mb-2">
                      <span className="fw-medium">
                        Worker {worker.worker_id}
                      </span>
                      <div
                        className={`rounded-circle ${
                          worker.is_available ? "bg-success" : "bg-danger"
                        }`}
                        style={{ width: "8px", height: "8px" }}
                      />
                    </div>

                    {worker.is_available && (
                      <div className="d-flex flex-wrap gap-2 small text-muted">
                        <div className="me-2">
                          Memory: {worker.memory_usage_mb?.toFixed(1)} MB
                        </div>
                        <div>CPU: {worker.cpu_usage_percent?.toFixed(1)}%</div>
                      </div>
                    )}

                    {!worker.is_available && (
                      <div className="small text-danger">
                        Status: {worker.status}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {error && (
            <div className="alert alert-danger py-2 small">{error}</div>
          )}
        </div>
      )}
    </div>
  );
}
