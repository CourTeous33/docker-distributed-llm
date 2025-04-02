import { useState, useEffect } from 'react';
import axios from 'axios';

export default function TextGenerator() {
  const [prompt, setPrompt] = useState('');
  const [generatedText, setGeneratedText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [generationTime, setGenerationTime] = useState(0);
  const [tokenCount, setTokenCount] = useState(0);
  const [workers, setWorkers] = useState([]);
  const [maxTokens, setMaxTokens] = useState(256);
  const [debugMode, setDebugMode] = useState(false);
  const [debugOutput, setDebugOutput] = useState([]);

  useEffect(() => {
    fetchWorkerStatus();
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

  const handleReset = () => {
    setPrompt('');
    setGeneratedText('');
    setError('');
    setGenerationTime(0);
    setTokenCount(0);
    setDebugOutput([]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;
  
    handleReset();
    setLoading(true);
    setGeneratedText('');
    const startTime = Date.now();
    const debugLines = [];
  
    try {
      const eventSource = new EventSource(
        `/api/stream?prompt=${encodeURIComponent(prompt)}&max_tokens=${maxTokens}`
      );
  
      let combinedText = '';
      let tokens = 0;
      
      // Log when the connection is opened
      eventSource.onopen = () => {
        console.log("EventSource connection opened.");
        debugLines.push("EventSource connection opened");
        setDebugOutput(debugLines);
      };
      
      eventSource.onmessage = (event) => {
        const data = event.data;
        console.log("Event data:", data);
        debugLines.push(`Raw: ${data}`);
        setDebugOutput([...debugLines]);
        
        // Check if the message is the completion marker
        if (data === '[DONE]') {
          setLoading(false);
          setGenerationTime((Date.now() - startTime) / 1000);
          eventSource.close();
          return;
        }

        // Try parsing as JSON first (future-proofing)
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            setError(parsed.error);
            setLoading(false);
            eventSource.close();
            return;
          }
          if (parsed.text) {
            combinedText += parsed.text;
            tokens += 1;
            setGeneratedText(combinedText);
            setTokenCount(tokens);
            return;
          }
        } catch (err) {
          // Not JSON, continue with plain text processing
        }

        // Handle prediction token lines (based on your backend output format)
        if (data.includes('🔶 Pred')) {
          // Extract the token from the line (after the last | character)
          const parts = data.split('|');
          if (parts.length > 0) {
            const token = parts[parts.length - 1].trim();
            combinedText += token;
            tokens += 1;
            setGeneratedText(combinedText);
            setTokenCount(tokens);
          }
        } 
        // Check if this is the raw prompt being echoed back
        else if (!data.startsWith('🔷') && 
                !data.startsWith('💡') && 
                !data.startsWith('📄') && 
                !data.startsWith('Evaluation') && 
                !data.startsWith('Prediction') && 
                !data.includes('tokens/s') && 
                !data.includes('nBatches') && 
                !data.includes('nTokens') && 
                !data.includes('Network is') && 
                data.trim().length > 0) {
          // This could be the prompt being echoed back, or other important text
          // Let's log it in debug but not add it to the output
          debugLines.push(`Possible prompt echo: ${data}`);
          setDebugOutput([...debugLines]);
        }
      };
  
      eventSource.onerror = (err) => {
        console.error('Streaming error:', err);
        debugLines.push(`Error: ${err}`);
        setDebugOutput([...debugLines]);
        setError('Streaming connection failed');
        eventSource.close();
        setLoading(false);
      };
    } catch (err) {
      console.error('Generation error:', err);
      setError('Failed to connect to generation stream');
      setLoading(false);
    }
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-lg">
      <h2 className="text-2xl font-semibold mb-4">Distributed LLM Text Generation</h2>
      
      {/* Worker Status */}
      <div className="mb-6">
        <h3 className="text-lg font-medium mb-2">Worker Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-2 mb-4">
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
      
      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1" htmlFor="prompt">
            Prompt
          </label>
          <textarea 
            id="prompt"
            className="w-full p-3 border rounded-md focus:ring-blue-500 focus:border-blue-500"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
            placeholder="Enter your prompt here..."
            required
          />
        </div>
        
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1" htmlFor="max-tokens">
            Max Tokens
          </label>
          <input
            id="max-tokens"
            type="number"
            className="w-full p-2 border rounded-md focus:ring-blue-500 focus:border-blue-500"
            value={maxTokens}
            onChange={(e) => setMaxTokens(parseInt(e.target.value))}
            min={1}
            max={1024}
          />
          <p className="text-sm text-gray-500 mt-1">
            Maximum number of tokens to generate (1-1024)
          </p>
        </div>
        
        <div className="flex space-x-2">
          <button
            type="submit"
            disabled={loading}
            className={`flex-1 bg-blue-500 text-white py-2 px-4 rounded-md ${
              loading ? 'opacity-50 cursor-not-allowed' : 'hover:bg-blue-600'
            }`}
          >
            {loading ? 'Generating...' : 'Generate'}
          </button>
          
          <button
            type="button"
            onClick={handleReset}
            className="bg-gray-300 text-gray-800 py-2 px-4 rounded-md hover:bg-gray-400"
          >
            Reset
          </button>
          
          <button
            type="button"
            onClick={() => setDebugMode(!debugMode)}
            className="bg-amber-300 text-gray-800 py-2 px-4 rounded-md hover:bg-amber-400"
          >
            {debugMode ? 'Hide Debug' : 'Show Debug'}
          </button>
        </div>
      </form>
      
      {loading && (
        <div className="mt-4 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          <span className="ml-2">Generating text across distributed workers...</span>
        </div>
      )}
      
      {error && (
        <div className="mt-4 p-3 bg-red-100 text-red-700 rounded-md">
          <p className="font-bold">Error:</p>
          <p>{error}</p>
        </div>
      )}
      
      {generatedText && (
        <div className="mt-4">
          <h3 className="text-lg font-medium mb-2">Generated Text:</h3>
          <div className="p-4 bg-gray-100 rounded-md whitespace-pre-wrap border border-gray-300">
            {generatedText.length > 0 ? generatedText : "(No output generated yet)"}
          </div>
          
          <div className="mt-2 grid grid-cols-2 gap-2">
            <div className="bg-blue-50 p-2 rounded border border-blue-200">
              <span className="text-sm font-medium">Generation Time:</span>
              <span className="text-sm ml-1">{generationTime.toFixed(2)} seconds</span>
            </div>
            <div className="bg-green-50 p-2 rounded border border-green-200">
              <span className="text-sm font-medium">Total Tokens:</span>
              <span className="text-sm ml-1">{tokenCount}</span>
            </div>
          </div>
        </div>
      )}
      
      {/* Debug Output */}
      {debugMode && (
        <div className="mt-6 border-t pt-4">
          <h3 className="text-lg font-medium mb-2">Debug Output:</h3>
          <div className="p-4 bg-gray-900 text-green-400 rounded-md text-xs font-mono h-64 overflow-auto">
            {debugOutput.map((line, i) => (
              <div key={i}>{line}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}