import { useState, useEffect } from 'react';
import axios from 'axios';
import React from 'react';
import TextGenerator from '../components/TextGenerator';

interface WorkerStatus {
  worker_id: number;
  status: string;
  is_available: boolean;
  memory_usage_mb?: number;
  cpu_usage_percent?: number;
  uptime_seconds?: number;
}

interface SystemInfo {
  server_status: string;
  total_workers: number;
  available_workers: number;
  model_path: string;
  tokenizer_path: string;
}

export default function Home() {
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  
  // Fetch status on component mount
  useEffect(() => {
    Promise.all([
      fetchWorkerStatus(),
      fetchSystemInfo()
    ]).finally(() => {
      setLoading(false);
    });
    
    // Refresh status every 10 seconds
    const interval = setInterval(() => {
      fetchWorkerStatus();
      fetchSystemInfo();
    }, 10000);
    
    return () => clearInterval(interval);
  }, []);

  const fetchWorkerStatus = async () => {
    try {
      const response = await axios.get('/api/workers/status');
      setWorkers(response.data);
    } catch (err) {
      console.error('Error fetching worker status:', err);
      setError('Error fetching worker status');
    }
  };
  
  const fetchSystemInfo = async () => {
    try {
      const response = await axios.get('/api/system/status');
      setSystemInfo(response.data);
    } catch (err) {
      console.error('Error fetching system info:', err);
    }
  };
  
  const handleRestartWorkers = async () => {
    try {
      setLoading(true);
      await axios.post('/api/workers/restart');
      // Wait a moment for workers to restart
      setTimeout(() => {
        fetchWorkerStatus();
        fetchSystemInfo();
        setLoading(false);
      }, 5000);
    } catch (err) {
      console.error('Error restarting workers:', err);
      setError('Error restarting workers');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 py-6 flex flex-col justify-center sm:py-12">
      <div className="relative py-3 sm:max-w-4xl sm:mx-auto">
        <div className="absolute inset-0 bg-gradient-to-r from-cyan-400 to-sky-500 shadow-lg transform -skew-y-6 sm:skew-y-0 sm:-rotate-6 sm:rounded-3xl"></div>
        <div className="relative px-4 py-10 bg-white shadow-lg sm:rounded-3xl sm:p-20">
          <h1 className="text-4xl font-bold mb-5 text-gray-800">Distributed LLM Inference</h1>
          
          {/* System Information */}
          {systemInfo && (
            <div className="mb-6 p-4 bg-gray-50 rounded-lg">
              <h2 className="text-xl font-semibold mb-2">System Information</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium">Server Status: 
                    <span className={`ml-2 px-2 py-1 rounded-full text-xs ${
                      systemInfo.server_status === 'running' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {systemInfo.server_status}
                    </span>
                  </p>
                  <p className="text-sm font-medium">Workers: 
                    <span className="ml-2">{systemInfo.available_workers} / {systemInfo.total_workers} available</span>
                  </p>
                </div>
                <div>
                  <p className="text-sm truncate">Model: {systemInfo.model_path.split('/').pop()}</p>
                  <p className="text-sm truncate">Tokenizer: {systemInfo.tokenizer_path.split('/').pop()}</p>
                </div>
              </div>
              
              <button
                onClick={handleRestartWorkers}
                disabled={loading}
                className={`mt-3 text-sm px-3 py-1 bg-blue-500 text-white rounded-md ${
                  loading ? 'opacity-50 cursor-not-allowed' : 'hover:bg-blue-600'
                }`}
              >
                {loading ? 'Restarting...' : 'Restart Workers'}
              </button>
            </div>
          )}
          
          {/* Worker Status */}
          <div className="mb-6">
            <h2 className="text-xl font-semibold mb-2">Worker Status</h2>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
              {workers.map((worker) => (
                <div 
                  key={worker.worker_id}
                  className={`border p-3 rounded-lg ${
                    worker.is_available 
                      ? 'bg-green-100 border-green-400' 
                      : 'bg-red-100 border-red-400'
                  }`}
                >
                  <div className="font-medium">Worker {worker.worker_id}</div>
                  <div className="text-xs mb-1">{worker.status}</div>
                  
                  {worker.is_available && worker.memory_usage_mb !== undefined && (
                    <>
                      <div className="text-xs">Memory: {worker.memory_usage_mb.toFixed(1)} MB</div>
                      <div className="text-xs">CPU: {worker.cpu_usage_percent?.toFixed(1)}%</div>
                      <div className="text-xs">Uptime: {formatUptime(worker.uptime_seconds || 0)}</div>
                    </>
                  )}
                </div>
              ))}
            </div>
            
            {error && (
              <div className="mt-2 text-red-500 text-sm">{error}</div>
            )}
          </div>
          
          {/* Text Generator Component */}
          <TextGenerator />
        </div>
      </div>
    </div>
  );
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}