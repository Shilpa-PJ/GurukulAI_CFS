import React from 'react'
import { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [token, setToken] = useState(null);
  const [accountId, setAccountId] = useState(null);
  const [maskedAccountId, setMaskedAccountId] = useState(null);

  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);

  // Check for existing session on component mount
  useEffect(() => {
    const savedToken = localStorage.getItem("authToken");
    const savedUsername = localStorage.getItem("username");
    const savedAccountId = localStorage.getItem("accountId");
    const savedMaskedAccountId = localStorage.getItem("maskedAccountId");

    if (savedToken && savedUsername && savedAccountId) {
      setToken(savedToken);
      setUsername(savedUsername);
      setAccountId(savedAccountId);
      setMaskedAccountId(savedMaskedAccountId);
      setLoggedIn(true);
    }
  }, []);

  // Fetch and display welcome message when user logs in
  useEffect(() => {
    if (loggedIn && messages.length === 0) {
      const fetchWelcomeMessage = async () => {
        try {
          const res = await fetch("http://127.0.0.1:8000/welcome");
          const data = await res.json();
          setMessages([{ role: "bot", text: data.message }]);
        } catch (err) {
          setMessages([{
            role: "bot",
            text: "Hi, I am your banking assistant. How can I help you today?"
          }]);
        }
      };
      fetchWelcomeMessage();
    }
  }, [loggedIn, messages.length]);

  const login = async () => {
    setError("");
    try {
      const res = await fetch("http://127.0.0.1:8000/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (res.ok) {
        const data = await res.json();

        setToken(data.token);
        setAccountId(data.accountId);
        setMaskedAccountId(data.maskedAccountId);
        setLoggedIn(true);

        localStorage.setItem("authToken", data.token);
        localStorage.setItem("username", data.username);
        localStorage.setItem("accountId", data.accountId);
        localStorage.setItem("maskedAccountId", data.maskedAccountId);

        console.log("Login successful! Account:", data.maskedAccountId);
      } else {
        const errorData = await res.json();
        setError(errorData.detail || "Invalid username or password");
      }
    } catch (err) {
      setError("Connection error. Please try again.");
      console.error("Login error:", err);
    }
  };

  const logout = async () => {
    try {
      await fetch("http://127.0.0.1:8000/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
    } catch (err) {
      console.error("Logout error:", err);
    } finally {
      setLoggedIn(false);
      setToken(null);
      setAccountId(null);
      setMaskedAccountId(null);
      setUsername("");
      setPassword("");
      setMessages([]);

      localStorage.removeItem("authToken");
      localStorage.removeItem("username");
      localStorage.removeItem("accountId");
      localStorage.removeItem("maskedAccountId");
    }
  };

  const sendMessage = async (overrideInput = null) => {
    const messageText = overrideInput || input;
    if (!messageText.trim()) return;

    // Hide insight buttons from all previous messages
    setMessages((prev) => prev.map(m => ({ ...m, showInsightButtons: false })));
    setMessages((prev) => [...prev, { role: "user", text: messageText }]);
    if (!overrideInput) setInput("");

    try {
      const res = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: messageText,
          token: token
        }),
      });

      if (res.status === 401) {
        setMessages((prev) => [...prev, {
          role: "bot",
          text: "Your session has expired. Please login again."
        }]);
        setTimeout(() => { logout(); }, 2000);
        return;
      }

      const data = await res.json();

      // Check if response contains the insight prompt
      const hasInsightPrompt = data.response && data.response.includes("Would you like insights");

      // Split response and insight prompt if present
      let displayText = data.response;
      if (hasInsightPrompt) {
        displayText = data.response.split("\n\n---\n")[0];
      }

      setMessages((prev) => [...prev, {
        role: "bot",
        text: displayText,
        documents: data.documents || null,
        showInsightButtons: hasInsightPrompt
      }]);

    } catch (err) {
      setMessages((prev) => [...prev, {
        role: "bot",
        text: "Error connecting to server. Please try again."
      }]);
      console.error("Chat error:", err);
    }
  };

  const sendQuickMessage = (message) => {
    sendMessage(message);
  };

  const downloadDocument = (filename) => {
    const downloadUrl = `http://127.0.0.1:8000/api/download/${filename}?token=${token}`;
    window.open(downloadUrl, '_blank');
  };

  // ---- LOGIN PAGE ----
  if (!loggedIn) {
    return (
      <div className="login-container">
        <div className="login-left">
          <div className="login-form">
            <h2>CFS Banking Assistant Login</h2>

            <input
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && login()}
            />

            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && login()}
            />

            <button onClick={login}>Login</button>

            {error && <p className="error">{error}</p>}
          </div>
        </div>

        <div className="login-right">
          <div className="welcome-content">
            <h1>Welcome to Your FirstNet CFS Page</h1>
            <p className="subtitle">Your Intelligent Banking Assistant</p>

            <div className="features-list">
              <div className="feature-item">
                <span className="feature-icon">💰</span>
                <div>
                  <h3>Account Management</h3>
                  <p>Check your balance and account details instantly</p>
                </div>
              </div>

              <div className="feature-item">
                <span className="feature-icon">📊</span>
                <div>
                  <h3>Transaction History</h3>
                  <p>View and analyze your complete transaction records</p>
                </div>
              </div>

              <div className="feature-item">
                <span className="feature-icon">📄</span>
                <div>
                  <h3>Statement Downloads</h3>
                  <p>Access and download monthly and annual statements</p>
                </div>
              </div>

              <div className="feature-item">
                <span className="feature-icon">💡</span>
                <div>
                  <h3>Smart Insights</h3>
                  <p>Get personalized investment recommendations based on market trends</p>
                </div>
              </div>

              <div className="feature-item">
                <span className="feature-icon">🤖</span>
                <div>
                  <h3>AI-Powered Support</h3>
                  <p>24/7 intelligent assistance for all your banking needs</p>
                </div>
              </div>

              <div className="feature-item">
                <span className="feature-icon">🔒</span>
                <div>
                  <h3>Secure & Private</h3>
                  <p>Bank-grade security with account masking and encryption</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---- CHAT PAGE ----
  return (
    <div className="chat-container">
      <div className="chat-header">
        <div>
          <h2>CFS Banking Assistant</h2>
          <p className="user-info">
            Welcome, {username} | Account: {maskedAccountId}
          </p>
        </div>
        <button onClick={logout} className="logout-btn">Logout</button>
      </div>

      <div className="chat-main">
        <div className="chat-left">
          <div className="chat-box" style={{ display: "flex", flexDirection: "column" }}>
            {messages.map((m, i) => (
              <div key={i} className={m.role}>
                <div style={{ whiteSpace: "pre-line" }}>{m.text}</div>

                {/* Yes/No insight buttons */}
                {m.showInsightButtons && (
                  <div style={{ marginTop: "12px" }}>
                    <p style={{ margin: "0 0 8px 0", fontSize: "14px", opacity: 0.9 }}>
                      💡 Would you like insights on your account by comparing to market trends on how to improve your profit and investment?
                    </p>
                    <div style={{ display: "flex", gap: "10px" }}>
                      <button
                        onClick={() => sendQuickMessage("Yes")}
                        style={{
                          padding: "8px 20px",
                          backgroundColor: "#4CAF50",
                          color: "white",
                          border: "none",
                          borderRadius: "20px",
                          cursor: "pointer",
                          fontSize: "14px",
                          fontWeight: "600"
                        }}
                      >
                        ✅ Yes, Show Me Insights
                      </button>
                      <button
                        onClick={() => sendQuickMessage("No")}
                        style={{
                          padding: "8px 20px",
                          backgroundColor: "#dc3545",
                          color: "white",
                          border: "none",
                          borderRadius: "20px",
                          cursor: "pointer",
                          fontSize: "14px",
                          fontWeight: "600"
                        }}
                      >
                        ❌ No, Thanks
                      </button>
                    </div>
                  </div>
                )}

                {/* Document download buttons */}
                {m.documents && m.documents.length > 0 && (
                  <div className="document-section" style={{ marginTop: "10px" }}>
                    <h4 style={{ fontSize: "14px", marginBottom: "8px" }}>📄 Available Documents:</h4>
                    <div className="document-list">
                      {m.documents.map((doc, idx) => (
                        <button
                          key={idx}
                          className="download-btn"
                          onClick={() => downloadDocument(doc.name)}
                        >
                          📥 {doc.name} ({doc.type}) - {(doc.size / 1024).toFixed(1)} KB
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="input-box">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Type a message..."
            />
            <button onClick={() => sendMessage()}>Send</button>
          </div>
        </div>

        <div className="chat-right">
          <div className="features-sidebar">
            <h3>🤖 Assistant Features</h3>

            <div className="feature-card">
              <h4>💰 Account Services</h4>
              <ul>
                <li>Check account balance</li>
                <li>View account details</li>
                <li>Track spending patterns</li>
              </ul>
            </div>

            <div className="feature-card">
              <h4>📊 Transactions</h4>
              <ul>
                <li>View transaction history</li>
                <li>Filter by date or type</li>
                <li>Analyze spending trends</li>
              </ul>
            </div>

            <div className="feature-card">
              <h4>📄 Statements</h4>
              <ul>
                <li>Download monthly statements</li>
                <li>Access annual reports</li>
                <li>Export periodic statements</li>
              </ul>
            </div>

            <div className="feature-card">
              <h4>💡 Smart Insights</h4>
              <ul>
                <li>Investment recommendations</li>
                <li>Compare with market trends</li>
                <li>Personalized financial advice</li>
              </ul>
            </div>

            <div className="feature-card">
              <h4>🔒 Security</h4>
              <ul>
                <li>Account number masking</li>
                <li>Secure authentication</li>
                <li>Private data protection</li>
              </ul>
            </div>

            <div className="tips-section">
              <h4>💬 Try Asking:</h4>
              <div className="tip-item">"What's my account balance?"</div>
              <div className="tip-item">"Show my recent transactions"</div>
              <div className="tip-item">"Download my statements"</div>
              <div className="tip-item">"Give me investment insights"</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;