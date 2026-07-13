import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import './App.css';

const API_URL = process.env.REACT_API_URL || 'http://localhost:8000';

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [prompt, setPrompt] = useState('');
  const [tasks, setTasks] = useState([]);
  const [taskUpdates, setTaskUpdates] = useState({});
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [isLogin, setIsLogin] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');

  const wsRef = useRef(null);

  // WebSocket connection
  const connectWebSocket = useCallback(() => {
    if (!token) return;

    const ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnectionStatus('connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('WebSocket update:', data);

        // Update task status
        if (data.type === 'job_created' || data.type === 'task_update') {
          setTaskUpdates(prev => ({
            ...prev,
            [data.job_id]: data
          }));

          // Refresh task list
          fetchTasks();
        }
      } catch (error) {
        console.error('WebSocket error:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('error');
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnectionStatus('disconnected');

      // Reconnect after 3 seconds
      setTimeout(() => {
        if (token) {
          connectWebSocket();
        }
      }, 3000);
    };

    wsRef.current = ws;

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [token]);

  useEffect(() => {
    if (token) {
      fetchTasks();
      connectWebSocket();
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [token, connectWebSocket]);

  const fetchTasks = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/tasks`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTasks(response.data.tasks || []);
    } catch (error) {
      console.error('Failed to fetch tasks:', error);
    }
  };

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');

    try {
      const endpoint = isLogin ? '/auth/login' : '/auth/register';
      const payload = isLogin
        ? { email, password }
        : { email, password, name };

      const response = await axios.post(`${API_URL}${endpoint}`, payload);

      if (isLogin) {
        localStorage.setItem('token', response.data.access_token);
        setToken(response.data.access_token);
        setMessage('Login successful!');
      } else {
        setMessage('Registration successful! Please login.');
        setIsLogin(true);
      }
    } catch (error) {
      setMessage(error.response?.data?.detail || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitTask = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setLoading(true);
    setMessage('');

    try {
      const response = await axios.post(
        `${API_URL}/api/tasks`,
        { prompt },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setMessage(`Task submitted! Job ID: ${response.data.job_id} | Trace ID: ${response.data.trace_id}`);
      setPrompt('');
      fetchTasks();
    } catch (error) {
      setMessage(error.response?.data?.detail || 'Failed to submit task');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    localStorage.removeItem('token');
    setToken(null);
    setTasks([]);
    setTaskUpdates({});
    setMessage('Logged out successfully');
  };

  const getTaskStatus = (job) => {
    // Check if we have a real-time update
    if (taskUpdates[job.job_id]) {
      return taskUpdates[job.job_id].status || job.status;
    }
    return job.status;
  };

  if (!token) {
    return (
      <div className="App">
        <div className="container">
          <h1>SecureAI Platform</h1>
          <p className="subtitle">Distributed AI Agent System</p>

          <form onSubmit={handleAuth} className="auth-form">
            <h2>{isLogin ? 'Login' : 'Register'}</h2>

            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />

            <input
              type="password"
              placeholder="Password (min 8 characters)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />

            {!isLogin && (
              <input
                type="text"
                placeholder="Name (optional)"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            )}

            <button type="submit" disabled={loading}>
              {loading ? 'Processing...' : (isLogin ? 'Login' : 'Register')}
            </button>

            <p className="toggle-auth">
              {isLogin ? "Don't have an account? " : 'Already have an account? '}
              <button type="button" onClick={() => setIsLogin(!isLogin)}>
                {isLogin ? 'Register' : 'Login'}
              </button>
            </p>
          </form>

          {message && <p className={`message ${message.includes('success') ? 'success' : 'error'}`}>{message}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="App">
      <div className="container">
        <header className="header">
          <div>
            <h1>SecureAI Platform</h1>
            <div className="connection-status">
              <span className={`status-dot ${connectionStatus}`}></span>
              {connectionStatus === 'connected' ? 'Live' : 'Reconnecting...'}
            </div>
          </div>
          <button onClick={handleLogout} className="logout-btn">Logout</button>
        </header>

        <form onSubmit={handleSubmitTask} className="task-form">
          <h2>Submit New Task</h2>
          <textarea
            placeholder="Enter your task prompt..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
            required
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Submitting...' : 'Submit Task'}
          </button>
        </form>

        {message && <p className={`message ${message.includes('success') || message.includes('submitted') ? 'success' : 'error'}`}>{message}</p>}

        <div className="tasks-list">
          <h2>Your Tasks</h2>
          {tasks.length === 0 ? (
            <p>No tasks yet. Submit your first task above!</p>
          ) : (
            tasks.map((task) => (
              <div key={task.job_id} className="task-item">
                <div className="task-header">
                  <span className="task-id">#{task.job_id}</span>
                  <span className={`status status-${getTaskStatus(task)}`}>{getTaskStatus(task)}</span>
                  {task.trace_id && (
                    <span className="trace-id" title={task.trace_id}>
                      ID: {task.trace_id.substring(0, 8)}...
                    </span>
                  )}
                </div>
                <p className="task-prompt">{task.prompt}</p>
                <small className="task-date">
                  {new Date(task.created_at).toLocaleString()}
                </small>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
