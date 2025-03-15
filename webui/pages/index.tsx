import { useState, useEffect } from 'react';
import axios from 'axios';
import React from 'react';

interface WorkerStatus {
  worker_id: number;
  status: string;
  is_available: boolean;
}

export default function Home() {
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);
  
  // Fetch worker status on component mount
  useEffect(() => {
    fetchWorkerStatus();
    // Refresh status every 10 seconds
    const interval = setInterval(fetchWorkerStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchWorkerStatus = async () => {
    try {
      const response = await axios.get('/api/workers/status');
      setWorkers(response.data);
    } catch (err) {
      console.error('Error fetching worker status:', err);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 py-6 flex flex-col justify-center sm:py-12">
      <div className="relative py-3 sm:max-w-4xl sm:mx-auto">
        <div className="absolute inset-0 bg-gradient-to-r from-cyan-400 to-sky-500 shadow-lg transform -skew-y-6 sm:skew-y-0 sm:-rotate-6 sm:rounded-3xl"></div>
        <div className="relative px-4 py-10 bg-white shadow-lg sm:rounded-3xl sm:p-20">
          <h1 className="text-4xl font-bold mb-5 text-gray-800">Sliced LLM</h1>
          
          {/* Worker Status */}
          <div className="mb-6">
            <h2 className="text-xl font-semibold mb-2">Worker Status</h2>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
              {workers.map((worker) => (
                <div 
                  key={worker.worker_id}
                  className={`border p-2 rounded ${
                    worker.is_available 
                      ? 'bg-green-100 border-green-400' 
                      : 'bg-red-100 border-red-400'
                  }`}
                >
                  <div className="font-medium">Worker {worker.worker_id}</div>
                  <div className="text-xs">{worker.status}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}