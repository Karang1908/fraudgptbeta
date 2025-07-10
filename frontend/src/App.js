import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const FraudGPT = () => {
  const [sessions, setSessions] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [selectedImage, setSelectedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messageEndRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadSessions = async () => {
    try {
      const response = await axios.get(`${API}/chat/sessions`);
      setSessions(response.data);
    } catch (error) {
      console.error('Error loading sessions:', error);
    }
  };

  const createNewSession = async () => {
    try {
      const response = await axios.post(`${API}/chat/sessions`);
      const newSession = response.data;
      setSessions([newSession, ...sessions]);
      setCurrentSession(newSession);
      setMessages([]);
      setSidebarOpen(false);
    } catch (error) {
      console.error('Error creating session:', error);
    }
  };

  const loadMessages = async (sessionId) => {
    try {
      const response = await axios.get(`${API}/chat/sessions/${sessionId}/messages`);
      setMessages(response.data);
    } catch (error) {
      console.error('Error loading messages:', error);
    }
  };

  const selectSession = (session) => {
    setCurrentSession(session);
    loadMessages(session.id);
    setSidebarOpen(false);
  };

  const handleImageUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) { // 5MB limit
        alert('Image too large. Please select an image under 5MB.');
        return;
      }
      
      const reader = new FileReader();
      reader.onload = (e) => {
        setSelectedImage(e.target.result);
        setImagePreview(e.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const removeImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() && !selectedImage) return;
    if (!currentSession) {
      await createNewSession();
      return;
    }

    setLoading(true);
    const messageToSend = newMessage;
    const imageToSend = selectedImage;
    
    // Clear input immediately
    setNewMessage('');
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }

    try {
      const response = await axios.post(`${API}/chat/send`, {
        session_id: currentSession.id,
        message: messageToSend,
        image_base64: imageToSend
      });

      // Reload messages to get the latest conversation
      await loadMessages(currentSession.id);
      
    } catch (error) {
      console.error('Error sending message:', error);
      alert('Error sending message. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  const formatMessageContent = (content) => {
    // Simple markdown-like formatting
    return content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br/>');
  };

  return (
    <div className="fraud-gpt-container">
      {/* Sidebar */}
      <div className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h3>🔍 FraudGPT</h3>
          <button 
            className="new-chat-btn"
            onClick={createNewSession}
          >
            + New Chat
          </button>
        </div>
        
        <div className="session-list">
          {sessions.map((session) => (
            <div 
              key={session.id}
              className={`session-item ${currentSession?.id === session.id ? 'active' : ''}`}
              onClick={() => selectSession(session)}
            >
              <span className="session-title">{session.title}</span>
              <span className="session-date">
                {new Date(session.updated_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="chat-area">
        {/* Header */}
        <div className="chat-header">
          <button 
            className="sidebar-toggle"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            ☰
          </button>
          <h1>🔍 FraudGPT</h1>
          <p>Your AI-powered fraud detection assistant</p>
        </div>

        {/* Messages */}
        <div className="messages-container">
          {!currentSession ? (
            <div className="welcome-screen">
              <div className="welcome-content">
                <img 
                  src="https://images.pexels.com/photos/7663144/pexels-photo-7663144.jpeg" 
                  alt="Cybersecurity"
                  className="welcome-image"
                />
                <h2>Welcome to FraudGPT</h2>
                <p>Your AI-powered fraud detection assistant</p>
                <div className="features">
                  <div className="feature">
                    <span>💬</span>
                    <p>Analyze suspicious messages and communications</p>
                  </div>
                  <div className="feature">
                    <span>📷</span>
                    <p>Upload images to detect fraudulent content</p>
                  </div>
                  <div className="feature">
                    <span>🛡️</span>
                    <p>Get expert advice on scam prevention</p>
                  </div>
                </div>
                <button 
                  className="start-chat-btn"
                  onClick={createNewSession}
                >
                  Start New Chat
                </button>
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <div key={message.id} className={`message ${message.role}`}>
                  <div className="message-content">
                    {message.image_url && (
                      <img 
                        src={message.image_url} 
                        alt="Uploaded content"
                        className="message-image"
                      />
                    )}
                    <div 
                      className="message-text"
                      dangerouslySetInnerHTML={{ 
                        __html: formatMessageContent(message.content) 
                      }}
                    />
                  </div>
                  <div className="message-time">
                    {new Date(message.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              ))}
              
              {loading && (
                <div className="message assistant">
                  <div className="message-content">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messageEndRef} />
            </>
          )}
        </div>

        {/* Input Area */}
        <div className="input-area">
          {imagePreview && (
            <div className="image-preview">
              <img src={imagePreview} alt="Preview" />
              <button 
                className="remove-image-btn"
                onClick={removeImage}
              >
                ×
              </button>
            </div>
          )}
          
          <div className="input-container">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageUpload}
              style={{ display: 'none' }}
            />
            
            <button 
              className="upload-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
            >
              📎
            </button>
            
            <textarea
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask me to analyze a message, image, or help with fraud detection..."
              disabled={loading}
              rows="1"
            />
            
            <button 
              className="send-btn"
              onClick={sendMessage}
              disabled={loading || (!newMessage.trim() && !selectedImage)}
            >
              {loading ? '...' : '→'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FraudGPT;