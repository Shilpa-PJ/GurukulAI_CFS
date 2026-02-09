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
          // Fallback to default message if API fails
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
        
        // Store token and user info
        setToken(data.token);
        setAccountId(data.accountId);
        setMaskedAccountId(data.maskedAccountId);
        setLoggedIn(true);
        
        // Persist to localStorage
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
      // Call logout endpoint
      await fetch("http://127.0.0.1:8000/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
    } catch (err) {
      console.error("Logout error:", err);
    } finally {
      // Clear local state and storage
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

  const sendMessage = async () => {
    if (!input.trim()) return;

    setMessages((prev) => [...prev, { role: "user", text: input }]);
    const userInput = input;
    setInput("");

    try {
      const res = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          message: userInput,
          token: token  // Send token with every chat request
        }),
      });

      if (res.status === 401) {
        // Session expired or invalid
        setMessages((prev) => [...prev, { 
          role: "bot", 
          text: "Your session has expired. Please login again." 
        }]);
        
        // Auto logout after 2 seconds
        setTimeout(() => {
          logout();
        }, 2000);
        return;
      }

      const data = await res.json();
      setMessages((prev) => [...prev, { role: "bot", text: data.response }]);
    } catch (err) {
      setMessages((prev) => [...prev, { 
        role: "bot", 
        text: "Error connecting to server. Please try again." 
      }]);
      console.error("Chat error:", err);
    }
  };

  // ---- LOGIN PAGE ----
  if (!loggedIn) {
    return (
      <div className="login-container">
        <h2>Banking Assistant Login</h2>

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
    );
  }

  // ---- CHAT PAGE ----
  return (
    <div className="chat-container">
      <div className="chat-header">
        <div>
          <h2>Banking Assistant</h2>
          <p className="user-info">
            Welcome, {username} | Account: {maskedAccountId}
          </p>
        </div>
        <button onClick={logout} className="logout-btn">Logout</button>
      </div>

      <div className="chat-box" style={{ display: "flex", flexDirection: "column" }}>
        {messages.map((m, i) => (
          <div key={i} className={m.role}>
            {m.text}
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
        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
}

export default App;