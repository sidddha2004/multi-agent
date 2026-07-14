import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [taskPrompt, setTaskPrompt] = useState('');
  const [tasks, setTasks] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [showResultsModal, setShowResultsModal] = useState(false);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const API_BASE_URL = 'http://localhost:8000';

  // WebSocket connection
  useEffect(() => {
    if (token) {
      setIsAuthenticated(true);
      connectWebSocket();
      fetchTasks();

      return () => {
        if (wsRef.current) {
          wsRef.current.close();
        }
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
      };
    }
  }, [token]);

  const connectWebSocket = () => {
    setConnectionStatus('connecting');

    try {
      const ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionStatus('connected');
        console.log('WebSocket connected');
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('WebSocket message received:', data);

        if (data.type === 'task_update') {
          setTasks(prevTasks => {
            const existingIndex = prevTasks.findIndex(t => t.trace_id === data.trace_id);
            if (existingIndex !== -1) {
              const updatedTasks = [...prevTasks];
              updatedTasks[existingIndex] = data;
              return updatedTasks;
            } else {
              return [data, ...prevTasks];
            }
          });

          // Show notification for completed tasks
          if (data.status === 'completed' || data.status === 'failed') {
            showNotification(data);
          }
        } else if (data.type === 'error') {
          showNotification({ ...data, title: 'Error' });
        } else if (data.type === 'pong') {
          // Handle pong response
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionStatus('error');
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setConnectionStatus('disconnected');

        // Attempt to reconnect after 5 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isAuthenticated) {
            connectWebSocket();
          }
        }, 5000);
      };

      // Send periodic ping to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        } else {
          clearInterval(pingInterval);
        }
      }, 30000);

      ws.onclose = () => clearInterval(pingInterval);

    } catch (error) {
      console.error('WebSocket connection error:', error);
      setConnectionStatus('error');
    }
  };

  const showNotification = (task) => {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(`Task ${task.status}`, {
        body: task.description || task.message,
        icon: '/logo192.png'
      });
    }
  };

  // Request notification permission on mount
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  const fetchTasks = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/jobs`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      setTasks(data.jobs || []);
    } catch (error) {
      console.error('Failed to fetch tasks:', error);
      showMessage('Failed to load tasks', 'error');
    } finally {
      setLoading(false);
    }
  };

  const fetchTaskDetails = async (jobId) => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      setSelectedTask(data);
      setShowResultsModal(true);
    } catch (error) {
      console.error('Failed to fetch task details:', error);
      showMessage('Failed to load task details', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const endpoint = isLogin ? '/auth/login' : '/auth/register';
      const payload = isLogin
        ? { email: username, password }
        : { email: username, password, name: username };

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (response.ok) {
        if (isLogin) {
          // Store the JWT token
          localStorage.setItem('token', data.access_token);
          setIsAuthenticated(true);
          showMessage('Login successful!', 'success');
        } else {
          // Registration successful, switch to login
          showMessage('Registration successful! Please login.', 'success');
          setIsLogin(true);
        }
      } else {
        showMessage(data.detail || 'Authentication failed', 'error');
      }
    } catch (error) {
      showMessage('Network error. Please try again.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitTask = async (e) => {
    e.preventDefault();
    if (!taskPrompt.trim()) {
      showMessage('Please enter a task description', 'error');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          prompt: taskPrompt
        })
      });

      const data = await response.json();

      if (response.ok) {
        setTaskPrompt('');
        showMessage(`Task submitted! Job ID: ${data.job_id} | Trace ID: ${data.trace_id}`, 'success');
        fetchTasks(); // Refresh tasks list
      } else {
        showMessage(data.detail || 'Failed to submit task', 'error');
      }
    } catch (error) {
      showMessage('Network error. Please try again.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setIsAuthenticated(false);
    setTasks([]);
    setTaskPrompt('');
    if (wsRef.current) {
      wsRef.current.close();
    }
    showMessage('Logged out successfully', 'success');
  };

  const showMessage = (text, type) => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  const getTaskIcon = (agentType) => {
    const icons = {
      'research': '🔬',
      'browser': '🌐',
      'email': '📧',
      'sql': '🗄️',
      'default': '🤖'
    };
    return icons[agentType] || icons.default;
  };

  const getStatusInfo = (status) => {
    const statusMap = {
      'pending': { color: 'pending', icon: '⏳', label: 'Pending' },
      'processing': { color: 'processing', icon: '⚙️', label: 'Processing' },
      'completed': { color: 'completed', icon: '✅', label: 'Completed' },
      'failed': { color: 'failed', icon: '❌', label: 'Failed' },
      'retrying': { color: 'retrying', icon: '🔄', label: 'Retrying' }
    };
    return statusMap[status] || statusMap.pending;
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  // Auth Screen
  if (!isAuthenticated) {
    return (
      <div className="App">
        <div className="auth-container">
          <div className="auth-card">
            <div className="auth-header">
              <div className="logo-section">
                <div className="logo-icon">🤖</div>
                <h1>SecureAI</h1>
                <p>Distributed Agent Platform</p>
              </div>
            </div>

            <div className="auth-toggle">
              <button
                className={`toggle-btn ${isLogin ? 'active' : ''}`}
                onClick={() => setIsLogin(true)}
              >
                Login
              </button>
              <button
                className={`toggle-btn ${!isLogin ? 'active' : ''}`}
                onClick={() => setIsLogin(false)}
              >
                Sign Up
              </button>
            </div>

            <form onSubmit={handleAuth} className="auth-form">
              <div className="form-group">
                <label>Username</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                  required
                />
              </div>

              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                />
              </div>

              <button type="submit" className="auth-btn" disabled={loading}>
                {loading ? (
                  <span className="loading-text">
                    <span className="spinner"></span>
                    {isLogin ? 'Logging in...' : 'Creating account...'}
                  </span>
                ) : (
                  isLogin ? 'Login' : 'Create Account'
                )}
              </button>
            </form>

            <div className="auth-info">
              <p>💡 Tip: Use any username/password to get started</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Main Application
  return (
    <div className="App">
      <div className="background-elements">
        <div className="gradient-bg"></div>
        <div className="floating-shapes">
          <div className="shape shape-1"></div>
          <div className="shape shape-2"></div>
          <div className="shape shape-3"></div>
        </div>
      </div>

      <div className="main-container">
        {/* Header */}
        <header className="app-header">
          <div className="header-brand">
            <div className="logo-icon">🤖</div>
            <div>
              <h1>SecureAI</h1>
              <p className="header-subtitle">Distributed Agent Platform</p>
            </div>
          </div>

          <div className="header-actions">
            <div className={`connection-status ${connectionStatus}`}>
              <div className="status-dot"></div>
              <span>
                {connectionStatus === 'connected' ? 'Live' :
                 connectionStatus === 'connecting' ? 'Connecting...' :
                 connectionStatus === 'error' ? 'Error' : 'Offline'}
              </span>
            </div>
            <button onClick={handleLogout} className="logout-btn">
              <span>Logout</span>
              <span>→</span>
            </button>
          </div>
        </header>

        {/* Message Display */}
        {message && (
          <div className={`message ${message.type}`}>
            <div className="message-content">
              <span className="message-icon">
                {message.type === 'success' ? '✅' : '⚠️'}
              </span>
              <span>{message.text}</span>
            </div>
            <button onClick={() => setMessage(null)} className="message-close">×</button>
          </div>
        )}

        {/* Task Submission */}
        <div className="task-submission-section">
          <div className="section-header">
            <h2>🚀 Submit New Task</h2>
            <p>Describe what you want the AI agents to accomplish</p>
          </div>

          <form onSubmit={handleSubmitTask} className="task-form">
            <div className="task-input-wrapper">
              <textarea
                value={taskPrompt}
                onChange={(e) => setTaskPrompt(e.target.value)}
                placeholder="Example: Research the latest developments in quantum computing and summarize the key findings..."
                className="task-input"
                rows="4"
              />
              <div className="task-input-footer">
                <span className="char-count">{taskPrompt.length} characters</span>
                <button type="submit" className="submit-btn" disabled={loading || !taskPrompt.trim()}>
                  {loading ? (
                    <span className="loading-text">
                      <span className="spinner"></span>
                      Submitting...
                    </span>
                  ) : (
                    <>
                      <span>Submit Task</span>
                      <span>→</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>

          <div className="quick-actions">
            <div className="quick-prompts">
              <span className="quick-label">Quick prompts:</span>
              <button
                onClick={() => setTaskPrompt('Research the latest AI trends and summarize key developments')}
                className="quick-btn"
              >
                🔬 AI Research
              </button>
              <button
                onClick={() => setTaskPrompt('Scrape example.com and extract the main content')}
                className="quick-btn"
              >
                🌐 Web Scraping
              </button>
              <button
                onClick={() => setTaskPrompt('Send email to test@example.com about the project update')}
                className="quick-btn"
              >
                📧 Email Task
              </button>
            </div>
          </div>
        </div>

        {/* Task Stats */}
        <div className="task-stats">
          <div className="stat-card">
            <div className="stat-icon">📋</div>
            <div className="stat-content">
              <span className="stat-value">{tasks.length}</span>
              <span className="stat-label">Total Tasks</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">⚙️</div>
            <div className="stat-content">
              <span className="stat-value">{tasks.filter(t => t.status === 'processing').length}</span>
              <span className="stat-label">Processing</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">✅</div>
            <div className="stat-content">
              <span className="stat-value">{tasks.filter(t => t.status === 'completed').length}</span>
              <span className="stat-label">Completed</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">❌</div>
            <div className="stat-content">
              <span className="stat-value">{tasks.filter(t => t.status === 'failed').length}</span>
              <span className="stat-label">Failed</span>
            </div>
          </div>
        </div>

        {/* Tasks List */}
        <div className="tasks-section">
          <div className="section-header">
            <h2>📊 Your Tasks</h2>
            <button onClick={fetchTasks} className="refresh-btn" disabled={loading}>
              <span className={loading ? 'spinner' : '🔄'}></span>
              Refresh
            </button>
          </div>

          {loading && tasks.length === 0 ? (
            <div className="loading-state">
              <div className="loading-spinner"></div>
              <p>Loading your tasks...</p>
            </div>
          ) : tasks.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📭</div>
              <h3>No tasks yet</h3>
              <p>Submit your first task above to get started!</p>
            </div>
          ) : (
            <div className="tasks-list">
              {tasks.map((task) => {
                const statusInfo = getStatusInfo(task.status);
                return (
                  <div key={task.trace_id} className={`task-card ${statusInfo.color}`}>
                    <div className="task-card-header">
                      <div className="task-identity">
                        <span className="task-icon">
                          {getTaskIcon(task.agent_type)}
                        </span>
                        <div>
                          <span className="task-id">Task #{task.id}</span>
                          <span className="task-type-badge">{task.agent_type}</span>
                        </div>
                      </div>
                      <div className={`task-status ${statusInfo.color}`}>
                        <span className="status-icon">{statusInfo.icon}</span>
                        <span className="status-label">{statusInfo.label}</span>
                      </div>
                    </div>

                    <div className="task-body">
                      <p className="task-description">{task.description || task.prompt}</p>

                      {(task.status === 'completed' || task.status === 'failed') && (
                        <button
                          onClick={() => fetchTaskDetails(task.job_id)}
                          className="view-results-btn"
                        >
                          {task.status === 'completed' ? '📄 View Results' : '🔍 View Details'}
                        </button>
                      )}
                    </div>

                    <div className="task-footer">
                      <div className="task-meta">
                        <span className="trace-id" title={task.trace_id}>
                          ID: {task.trace_id.substring(0, 8)}...
                        </span>
                        <span className="task-time">
                          {formatTimestamp(task.created_at || task.timestamp)}
                        </span>
                      </div>
                      {task.status === 'failed' && (
                        <button
                          onClick={() => setTaskPrompt(task.description || task.prompt)}
                          className="retry-btn"
                        >
                          🔄 Retry
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Task Results Modal */}
        {showResultsModal && selectedTask && (
          <div className="modal-overlay" onClick={() => setShowResultsModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h3>📄 Task Details & Results</h3>
                <button onClick={() => setShowResultsModal(false)} className="modal-close">×</button>
              </div>
              <div className="modal-body">
                <div className="detail-section">
                  <h4>Task Information</h4>
                  <div className="detail-row">
                    <span className="detail-label">Status:</span>
                    <span className={`detail-value status-${selectedTask.status}`}>
                      {getStatusInfo(selectedTask.status).icon} {getStatusInfo(selectedTask.status).label}
                    </span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Agent Type:</span>
                    <span className="detail-value">{getTaskIcon(selectedTask.tasks?.[0]?.agent_type)} {selectedTask.tasks?.[0]?.agent_type || 'N/A'}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Job ID:</span>
                    <span className="detail-value">#{selectedTask.job_id}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Trace ID:</span>
                    <span className="detail-value trace-id">{selectedTask.trace_id}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Created:</span>
                    <span className="detail-value">{formatTimestamp(selectedTask.created_at)}</span>
                  </div>
                </div>

                <div className="detail-section">
                  <h4>Task Description</h4>
                  <p className="detail-prompt">{selectedTask.prompt}</p>
                </div>

                {selectedTask.tasks && selectedTask.tasks.length > 0 && (
                  <div className="detail-section">
                    <h4>Agent Results</h4>
                    {selectedTask.tasks.map((task) => (
                      <div key={task.task_id} className="task-result-detail">
                        <div className="result-meta">
                          <span className="agent-type">
                            {getTaskIcon(task.agent_type)} {task.agent_type}
                          </span>
                          <span className={`task-status status-${task.status}`}>
                            {getStatusInfo(task.status).icon} {getStatusInfo(task.status).label}
                          </span>
                        </div>
                        <div className="result-description">
                          <strong>Task:</strong> {task.description}
                        </div>
                        {task.result && (
                          <div className="result-content">
                            <div className="result-header">
                              <strong>🎯 Result:</strong>
                            </div>
                            <pre className="result-text">{task.result}</pre>
                          </div>
                        )}
                        {!task.result && task.status === 'processing' && (
                          <div className="result-processing">
                            <span className="spinner"></span>
                            <span>Processing...</span>
                          </div>
                        )}
                        {!task.result && task.status === 'failed' && (
                          <div className="result-error">
                            ❌ Task failed. No result available.
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="modal-footer">
                <button
                  onClick={() => setShowResultsModal(false)}
                  className="modal-btn modal-btn-primary"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <footer className="app-footer">
          <p>🤖 SecureAI Platform • Multi-Agent Orchestration System</p>
          <p className="footer-subtitle">Powered by Kafka, Redis & AI Agents</p>
        </footer>
      </div>
    </div>
  );
}

export default App;