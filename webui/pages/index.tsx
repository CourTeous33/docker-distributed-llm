import ChatInterface from '../components/ChatInterface';
import StatusPanel from '../components/StatusPanel';
import Head from 'next/head';

export default function Home() {
  return (
    <>
      <Head>
        <title>Distributed LLM Inference</title>
        <link
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css"
          rel="stylesheet"
          integrity="sha384-T3c6CoIi6uLrA9TneNEoa7RxnatzjcDSCmG1MXxSR1GAsXEV/Dwwykc2MPK8M2HN"
          crossOrigin="anonymous"
        />
        <script
          src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"
          integrity="sha384-C6RzsynM9kWDrMNeT87bh95OGNyZPhcTNXj1NW7RuBCsyN/o0jlpcV8Qyq46cDfL"
          crossOrigin="anonymous"
          defer
        />
      </Head>
      <div className="vh-100 d-flex flex-column bg-light">
        {/* Main Container */}
        <div className="flex-grow-1 d-flex position-relative">
          {/* Chat Interface - with right padding to avoid sidebar overlap */}
          <div 
            className="flex-grow-1 h-100 overflow-hidden" 
            style={{
              paddingRight: '320px', // Match the width of the sidebar when open
              transition: 'padding-right 0.3s ease-in-out'
            }}
          >
            <ChatInterface />
          </div>
          
          {/* Status Panel */}
          <StatusPanel />
        </div>
      </div>
    </>
  );
}