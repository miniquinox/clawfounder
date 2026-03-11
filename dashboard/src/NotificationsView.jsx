import React, { useState, useEffect } from 'react';

const NotificationsView = () => {
  const [notifications, setNotifications] = useState([]);
  const [proactiveBriefing, setProactiveBriefing] = useState(null);
  const [preferences, setPreferences] = useState(null);
  const [monitorStatus, setMonitorStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showPreferences, setShowPreferences] = useState(false);

  // Load notifications
  const loadNotifications = async () => {
    try {
      const response = await fetch('/api/notifications');
      const data = await response.json();
      setNotifications(data.notifications || []);
    } catch (error) {
      console.error('Error loading notifications:', error);
    }
  };

  // Load proactive briefing
  const loadProactiveBriefing = async () => {
    try {
      const response = await fetch('/api/proactive-briefing');
      const data = await response.json();
      setProactiveBriefing(data);
    } catch (error) {
      console.error('Error loading proactive briefing:', error);
    }
  };

  // Load preferences
  const loadPreferences = async () => {
    try {
      const response = await fetch('/api/notification-preferences');
      const data = await response.json();
      setPreferences(data);
    } catch (error) {
      console.error('Error loading preferences:', error);
    }
  };

  // Load monitor status
  const loadMonitorStatus = async () => {
    try {
      const response = await fetch('/api/event-monitor/status');
      const data = await response.json();
      setMonitorStatus(data);
    } catch (error) {
      console.error('Error loading monitor status:', error);
    }
  };

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      await Promise.all([
        loadNotifications(),
        loadProactiveBriefing(),
        loadPreferences(),
        loadMonitorStatus()
      ]);
      setLoading(false);
    };
    loadData();

    // Refresh every 30 seconds
    const interval = setInterval(() => {
      loadNotifications();
      loadProactiveBriefing();
      loadMonitorStatus();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  // Mark notification as read
  const markAsRead = async (notificationId) => {
    try {
      await fetch(`/api/notifications/${notificationId}/read`, {
        method: 'POST'
      });
      await loadNotifications();
    } catch (error) {
      console.error('Error marking notification as read:', error);
    }
  };

  // Mark all notifications as read
  const markAllAsRead = async () => {
    try {
      await fetch('/api/notifications/read-all', {
        method: 'POST'
      });
      await loadNotifications();
    } catch (error) {
      console.error('Error marking all as read:', error);
    }
  };

  // Update preferences
  const updatePreferences = async (newPreferences) => {
    try {
      const response = await fetch('/api/notification-preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPreferences)
      });
      if (response.ok) {
        const data = await response.json();
        setPreferences(data.preferences);
        setShowPreferences(false);
      }
    } catch (error) {
      console.error('Error updating preferences:', error);
    }
  };

  // Toggle event monitor
  const toggleMonitor = async (action) => {
    try {
      await fetch(`/api/event-monitor/${action}`, {
        method: 'POST'
      });
      await loadMonitorStatus();
    } catch (error) {
      console.error('Error toggling monitor:', error);
    }
  };

  // Get priority color
  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high': return 'text-red-600 bg-red-50';
      case 'medium': return 'text-yellow-600 bg-yellow-50';
      case 'low': return 'text-green-600 bg-green-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  // Get priority icon
  const getPriorityIcon = (priority) => {
    switch (priority) {
      case 'high': return '🔴';
      case 'medium': return '🟡';
      case 'low': return '🟢';
      default: return '⚪';
    }
  };

  // Format timestamp
  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (minutes < 1440) return `${Math.floor(minutes / 60)}h ago`;
    return date.toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded mb-4"></div>
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-24 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">🦀 Proactive Assistant</h1>
          <p className="text-gray-600">Your AI Project Manager is watching for important events</p>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={() => setShowPreferences(!showPreferences)}
            className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            ⚙️ Preferences
          </button>
          {monitorStatus && (
            <button
              onClick={() => toggleMonitor(monitorStatus.running ? 'stop' : 'start')}
              className={`px-4 py-2 text-sm rounded-lg transition-colors ${
                monitorStatus.running
                  ? 'bg-red-100 hover:bg-red-200 text-red-700'
                  : 'bg-green-100 hover:bg-green-200 text-green-700'
              }`}
            >
              {monitorStatus.running ? '⏹️ Stop' : '▶️ Start'} Monitor
            </button>
          )}
        </div>
      </div>

      {/* Monitor Status */}
      {monitorStatus && (
        <div className="bg-white rounded-lg shadow-sm border p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className={`w-3 h-3 rounded-full ${
                monitorStatus.running ? 'bg-green-500' : 'bg-gray-400'
              }`}></div>
              <span className="font-medium">
                Event Monitor {monitorStatus.running ? 'Running' : 'Stopped'}
              </span>
            </div>
            <div className="text-sm text-gray-500">
              {monitorStatus.running && (
                <span>
                  Tracking {monitorStatus.known_events} events • 
                  Checks every {monitorStatus.check_interval}s
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Proactive Briefing */}
      {proactiveBriefing && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200 p-6">
          <div className="flex items-center mb-4">
            <div className="text-2xl mr-3">📋</div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Proactive Briefing</h2>
              <p className="text-sm text-gray-600">{proactiveBriefing.summary}</p>
            </div>
          </div>
          
          {(proactiveBriefing.high_priority?.length > 0 || proactiveBriefing.medium_priority?.length > 0) && (
            <div className="grid md:grid-cols-2 gap-4">
              {proactiveBriefing.high_priority?.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <h3 className="font-medium text-red-800 mb-2">🔴 High Priority ({proactiveBriefing.high_priority.length})</h3>
                  <div className="space-y-2">
                    {proactiveBriefing.high_priority.slice(0, 3).map((item, index) => (
                      <div key={index} className="text-sm text-red-700">
                        • {item.message}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {proactiveBriefing.medium_priority?.length > 0 && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                  <h3 className="font-medium text-yellow-800 mb-2">🟡 Medium Priority ({proactiveBriefing.medium_priority.length})</h3>
                  <div className="space-y-2">
                    {proactiveBriefing.medium_priority.slice(0, 3).map((item, index) => (
                      <div key={index} className="text-sm text-yellow-700">
                        • {item.message}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Notifications */}
      <div className="bg-white rounded-lg shadow-sm border">
        <div className="p-4 border-b flex justify-between items-center">
          <h2 className="text-lg font-semibold">Recent Alerts</h2>
          {notifications.length > 0 && (
            <button
              onClick={markAllAsRead}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Mark all as read
            </button>
          )}
        </div>
        
        <div className="divide-y">
          {notifications.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <div className="text-4xl mb-2">📭</div>
              <p>No new notifications</p>
              <p className="text-sm">Your AI PM will alert you when important events are detected</p>
            </div>
          ) : (
            notifications.map((notification) => (
              <div key={notification.event_type} className="p-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-start space-x-3">
                  <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${getPriorityColor(notification.priority)}`}>
                    <span className="text-sm">{getPriorityIcon(notification.priority)}</span>
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <h3 className="font-medium text-gray-900">
                        {notification.event_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </h3>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs text-gray-500">
                          {formatTime(notification.timestamp)}
                        </span>
                        <button
                          onClick={() => markAsRead(notification.event_type)}
                          className="text-gray-400 hover:text-gray-600"
                          title="Mark as read"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                    
                    <p className="text-gray-700 mt-1">{notification.message}</p>
                    
                    {notification.suggested_actions?.length > 0 && (
                      <div className="mt-3">
                        <p className="text-xs text-gray-500 mb-1">Suggested actions:</p>
                        <div className="flex flex-wrap gap-2">
                          {notification.suggested_actions.map((action, index) => (
                            <button
                              key={index}
                              className="text-xs bg-gray-100 hover:bg-gray-200 px-2 py-1 rounded transition-colors"
                              onClick={() => {
                                // Here you could implement action handling
                                console.log('Action clicked:', action);
                              }}
                            >
                              {action}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Preferences Modal */}
      {showPreferences && preferences && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold">Notification Preferences</h3>
                <button
                  onClick={() => setShowPreferences(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>
              
              <div className="space-y-4">
                {/* Enable/Disable */}
                <div>
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={preferences.enabled}
                      onChange={(e) => updatePreferences({...preferences, enabled: e.target.checked})}
                      className="rounded border-gray-300"
                    />
                    <span>Enable notifications</span>
                  </label>
                </div>

                {/* Priority Threshold */}
                <div>
                  <label className="block text-sm font-medium mb-1">Priority Threshold</label>
                  <select
                    value={preferences.priority_threshold}
                    onChange={(e) => updatePreferences({...preferences, priority_threshold: e.target.value})}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2"
                  >
                    <option value="low">Low and above</option>
                    <option value="medium">Medium and above</option>
                    <option value="high">High only</option>
                  </select>
                </div>

                {/* Channels */}
                <div>
                  <label className="block text-sm font-medium mb-2">Delivery Channels</label>
                  <div className="space-y-2">
                    {Object.entries(preferences.channels || {}).map(([channel, enabled]) => (
                      <label key={channel} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={(e) => updatePreferences({
                            ...preferences,
                            channels: {...preferences.channels, [channel]: e.target.checked}
                          })}
                          className="rounded border-gray-300"
                        />
                        <span className="capitalize">{channel.replace('_', ' ')}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Quiet Hours */}
                <div>
                  <label className="flex items-center space-x-2 mb-2">
                    <input
                      type="checkbox"
                      checked={preferences.quiet_hours?.enabled || false}
                      onChange={(e) => updatePreferences({
                        ...preferences,
                        quiet_hours: {...preferences.quiet_hours, enabled: e.target.checked}
                      })}
                      className="rounded border-gray-300"
                    />
                    <span>Enable quiet hours</span>
                  </label>
                  
                  {preferences.quiet_hours?.enabled && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-xs text-gray-500">Start time</label>
                        <input
                          type="time"
                          value={preferences.quiet_hours.start}
                          onChange={(e) => updatePreferences({
                            ...preferences,
                            quiet_hours: {...preferences.quiet_hours, start: e.target.value}
                          })}
                          className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-gray-500">End time</label>
                        <input
                          type="time"
                          value={preferences.quiet_hours.end}
                          onChange={(e) => updatePreferences({
                            ...preferences,
                            quiet_hours: {...preferences.quiet_hours, end: e.target.value}
                          })}
                          className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationsView;