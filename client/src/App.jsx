import React, { useEffect, useRef } from 'react';
import ChatBot from 'react-simple-chatbot';
import { ThemeProvider } from 'styled-components';
import './App.css';

const steps = [
  {
    id: 'start',
    message: 'What would you like Linda to post?',
    trigger: 'user_input',
  },
  {
    id: 'user_input',
    user: true,
    trigger: 'working',
  },
  {
    id: 'working',
    message: 'Working on it...',
    trigger: 'send',
  },
  {
    id: 'send',
    component: <SendToSocket />,
    waitAction: true,
    trigger: 'bot_reply',
  },
  {
    id: 'bot_reply',
    message: '{previousValue}',
    trigger: 'user_input',
  },
];

function SendToSocket({ steps, triggerNextStep }) {
  const userMessage = steps.user_input.value;
  const lastSentRef = useRef(null);

  useEffect(() => {
    if (lastSentRef.current === userMessage) {
      return undefined;
    }
    lastSentRef.current = userMessage;

    const socket = window.chatSocket;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      triggerNextStep({
        value: 'WebSocket is not connected. Start the backend at ws://localhost:8000/ws/chat.',
      });
      return undefined;
    }

    let settled = false;
    const handleMessage = (event) => {
      if (settled) return;
      settled = true;
      const response = (event.data || "").trim();
      triggerNextStep({ value: response || "No response returned." });
    };

    const handleError = () => {
      if (settled) return;
      settled = true;
      triggerNextStep({
        value: 'WebSocket error. Check the backend logs and API keys.',
      });
    };

    socket.addEventListener('message', handleMessage);
    socket.addEventListener('error', handleError);
    socket.send(userMessage);

    return () => {
      socket.removeEventListener('message', handleMessage);
      socket.removeEventListener('error', handleError);
    };
  }, [userMessage, triggerNextStep]);

  return null;
}

const theme = {
  background: '#0b0f14',
  headerBgColor: '#0b0f14',
  headerFontSize: '18px',
  botBubbleColor: '#111827',
  headerFontColor: '#e6edf3',
  botFontColor: '#e6edf3',
  userBubbleColor: '#1e3a8a',
  userFontColor: '#e6edf3',
};

const config = {
  floating: false,
};

function App() {
  useEffect(() => {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/chat';
    const socket = new WebSocket(wsUrl);

    socket.addEventListener('open', () => {
      console.log('WebSocket connected:', wsUrl);
    });

    socket.addEventListener('close', () => {
      console.log('WebSocket disconnected');
    });

    window.chatSocket = socket;

    return () => socket.close();
  }, []);

  return (
    <div className="app-root">
      <header className="hero">
        <div className="wave-text">
          {'WELCOME'.split('').map((letter, i) => (
            <span key={i} style={{ animationDelay: `${i * 0.2}s` }}>
              {letter}
            </span>
          ))}
        </div>
      </header>

      <ThemeProvider theme={theme}>
        <ChatBot
          steps={steps}
          headerTitle="LindaBot"
          {...config}
          style={{ width: '100%', height: '100%' }}
          contentStyle={{ height: '100%' }}
        />
      </ThemeProvider>
    </div>
  );
}

export default App;
