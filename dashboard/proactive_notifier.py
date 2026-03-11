"""
ClawFounder — Proactive Notifier

Delivers proactive alerts and notifications to users through various channels.
This component works with the Event Monitor to deliver PM-like notifications.
"""

import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProactiveNotifier:
    """Delivers proactive notifications to users."""
    
    def __init__(self):
        self.notification_queue = []
        self.delivery_handlers = {}
        self.user_preferences = {}
        self.running = False
        self.delivery_thread = None
        
        # Default notification preferences
        self.default_preferences = {
            "enabled": True,
            "channels": {
                "dashboard": True,
                "email": False,
                "telegram": False,
                "slack": False
            },
            "quiet_hours": {
                "enabled": False,
                "start": "22:00",  # 10 PM
                "end": "08:00"     # 8 AM
            },
            "priority_threshold": "medium",  # Only notify medium and high priority
            "max_notifications_per_hour": 20
        }
        
    def initialize(self):
        """Initialize the notifier and load user preferences."""
        logger.info("Initializing Proactive Notifier...")
        
        # Load user preferences
        self._load_user_preferences()
        
        # Initialize delivery handlers
        self._initialize_delivery_handlers()
        
        return True
        
    def _initialize_delivery_handlers(self):
        """Set up notification delivery handlers."""
        self.delivery_handlers = {
            "dashboard": self._deliver_to_dashboard,
            "email": self._deliver_via_email,
            "telegram": self._deliver_via_telegram,
            "slack": self._deliver_via_slack
        }
        
    def _load_user_preferences(self):
        """Load user notification preferences."""
        prefs_file = Path.home() / ".clawfounder" / "notification_preferences.json"
        
        try:
            if prefs_file.exists():
                with open(prefs_file, 'r') as f:
                    self.user_preferences = json.load(f)
            else:
                # Create default preferences
                self.user_preferences = self.default_preferences.copy()
                self._save_user_preferences()
        except Exception as e:
            logger.error(f"Error loading notification preferences: {e}")
            self.user_preferences = self.default_preferences.copy()
            
    def _save_user_preferences(self):
        """Save user notification preferences."""
        prefs_file = Path.home() / ".clawfounder" / "notification_preferences.json"
        
        try:
            prefs_file.parent.mkdir(parents=True, exist_ok=True)
            with open(prefs_file, 'w') as f:
                json.dump(self.user_preferences, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving notification preferences: {e}")
            
    def start(self):
        """Start the notification delivery system."""
        if not self.initialize():
            return False
            
        logger.info("Starting Proactive Notifier...")
        self.running = True
        
        # Start delivery thread
        self.delivery_thread = threading.Thread(target=self._delivery_loop, daemon=True)
        self.delivery_thread.start()
        
        logger.info("Proactive Notifier started successfully")
        return True
        
    def stop(self):
        """Stop the notification delivery system."""
        logger.info("Stopping Proactive Notifier...")
        self.running = False
        if self.delivery_thread:
            self.delivery_thread.join(timeout=5)
        logger.info("Proactive Notifier stopped")
        
    def _delivery_loop(self):
        """Main delivery loop for processing notifications."""
        while self.running:
            try:
                # Check for new notifications
                notifications = self._get_pending_notifications()
                
                if notifications:
                    for notification in notifications:
                        if self._should_deliver_notification(notification):
                            self._deliver_notification(notification)
                            
                # Clean up old notifications
                self._cleanup_old_notifications()
                
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in delivery loop: {e}")
                time.sleep(60)  # Wait before retrying
                
    def _get_pending_notifications(self) -> List[Dict[str, Any]]:
        """Get pending notifications from storage."""
        notifications_file = Path.home() / ".clawfounder" / "notifications.json"
        
        try:
            if notifications_file.exists():
                with open(notifications_file, 'r') as f:
                    all_notifications = json.load(f)
                    
                # Filter for undelivered notifications
                pending = []
                for notif in all_notifications:
                    if not notif.get("delivered", False):
                        pending.append(notif)
                        
                return pending
        except Exception as e:
            logger.error(f"Error loading pending notifications: {e}")
            
        return []
        
    def _should_deliver_notification(self, notification: Dict[str, Any]) -> bool:
        """Check if a notification should be delivered based on preferences."""
        if not self.user_preferences.get("enabled", True):
            return False
            
        # Check priority threshold
        priority_threshold = self.user_preferences.get("priority_threshold", "medium")
        priority_order = {"low": 0, "medium": 1, "high": 2}
        
        if priority_order.get(notification["priority"], 0) < priority_order.get(priority_threshold, 1):
            return False
            
        # Check quiet hours
        if self._is_quiet_hours() and notification["priority"] != "high":
            # Only high priority notifications during quiet hours
            return False
            
        return True
        
    def _is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours."""
        quiet_config = self.user_preferences.get("quiet_hours", {})
        
        if not quiet_config.get("enabled", False):
            return False
            
        try:
            now = datetime.now().time()
            start_time = datetime.strptime(quiet_config["start"], "%H:%M").time()
            end_time = datetime.strptime(quiet_config["end"], "%H:%M").time()
            
            # Handle overnight quiet hours (e.g., 22:00 to 08:00)
            if start_time > end_time:
                return now >= start_time or now <= end_time
            else:
                return start_time <= now <= end_time
        except Exception:
            return False
            
    def _deliver_notification(self, notification: Dict[str, Any]):
        """Deliver a notification through all enabled channels."""
        logger.info(f"Delivering notification: {notification['event_type']}")
        
        # Get enabled channels
        channels = self.user_preferences.get("channels", {})
        enabled_channels = [channel for channel, enabled in channels.items() if enabled]
        
        # Always deliver to dashboard if enabled
        if "dashboard" in enabled_channels:
            self._deliver_to_dashboard(notification)
            
        # Deliver to other channels
        for channel in enabled_channels:
            if channel != "dashboard" and channel in self.delivery_handlers:
                try:
                    self.delivery_handlers[channel](notification)
                except Exception as e:
                    logger.error(f"Error delivering notification via {channel}: {e}")
                    
        # Mark notification as delivered
        self._mark_notification_delivered(notification)
        
    def _deliver_to_dashboard(self, notification: Dict[str, Any]):
        """Deliver notification to the dashboard."""
        # Store in dashboard notifications file
        dashboard_notifs_file = Path.home() / ".clawfounder" / "dashboard_notifications.json"
        
        try:
            dashboard_notifs_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing dashboard notifications
            if dashboard_notifs_file.exists():
                with open(dashboard_notifs_file, 'r') as f:
                    dashboard_notifications = json.load(f)
            else:
                dashboard_notifications = []
                
            # Add to dashboard notifications
            dashboard_notification = {
                **notification,
                "delivered_at": datetime.now().isoformat(),
                "read": False
            }
            
            dashboard_notifications.append(dashboard_notification)
            
            # Keep only last 50 notifications
            dashboard_notifications = dashboard_notifications[-50:]
            
            # Save back to file
            with open(dashboard_notifs_file, 'w') as f:
                json.dump(dashboard_notifications, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error delivering notification to dashboard: {e}")
            
    def _deliver_via_email(self, notification: Dict[str, Any]):
        """Deliver notification via email."""
        # This would use the Gmail connector to send an email notification
        # For now, it's a placeholder implementation
        
        try:
            # Get user's email address (this would be configured)
            user_email = self.user_preferences.get("email_address")
            
            if not user_email:
                logger.warning("No email address configured for notifications")
                return
                
            # Create email content
            subject = f"🦀 ClawFounder Alert: {notification['event_type'].replace('_', ' ').title()}"
            
            body = f"""
Hi there,

I've detected an important event that requires your attention:

{notification['message']}

**Priority:** {notification['priority'].upper()}
**Event Type:** {notification['event_type'].replace('_', ' ').title()}
**Time:** {notification['timestamp']}

**Suggested Actions:**
{chr(10).join(f"• {action}" for action in notification['suggested_actions'])}

---
This is an automated notification from ClawFounder, your AI Project Manager.
You can configure notification preferences in the ClawFounder dashboard.
"""
            
            # Send email using Gmail connector
            # This would require importing and using the Gmail connector
            # For now, we'll just log it
            logger.info(f"Would send email to {user_email}: {subject}")
            
        except Exception as e:
            logger.error(f"Error delivering notification via email: {e}")
            
    def _deliver_via_telegram(self, notification: Dict[str, Any]):
        """Deliver notification via Telegram."""
        # This would use the Telegram connector to send a message
        try:
            # Get user's Telegram chat ID
            telegram_chat_id = self.user_preferences.get("telegram_chat_id")
            
            if not telegram_chat_id:
                logger.warning("No Telegram chat ID configured for notifications")
                return
                
            # Create message
            message = f"🦀 *ClawFounder Alert*\n\n"
            message += f"*{notification['event_type'].replace('_', ' ').title()}*\n"
            message += f"Priority: {notification['priority'].upper()}\n\n"
            message += f"{notification['message']}\n\n"
            message += "*Suggested Actions:*\n"
            message += "\n".join(f"• {action}" for action in notification['suggested_actions'])
            
            # Send message using Telegram connector
            # This would require importing and using the Telegram connector
            logger.info(f"Would send Telegram message to {telegram_chat_id}: {message[:100]}...")
            
        except Exception as e:
            logger.error(f"Error delivering notification via Telegram: {e}")
            
    def _deliver_via_slack(self, notification: Dict[str, Any]):
        """Deliver notification via Slack."""
        # This would use the Slack connector to send a message
        try:
            # Get user's Slack channel or DM
            slack_channel = self.user_preferences.get("slack_channel")
            
            if not slack_channel:
                logger.warning("No Slack channel configured for notifications")
                return
                
            # Create message
            message = {
                "text": f"🦀 ClawFounder Alert: {notification['event_type'].replace('_', ' ').title()}",
                "attachments": [
                    {
                        "color": "danger" if notification["priority"] == "high" else "warning",
                        "fields": [
                            {
                                "title": "Priority",
                                "value": notification["priority"].upper(),
                                "short": True
                            },
                            {
                                "title": "Event",
                                "value": notification["event_type"].replace('_', ' ').title(),
                                "short": True
                            },
                            {
                                "title": "Message",
                                "value": notification["message"],
                                "short": False
                            },
                            {
                                "title": "Suggested Actions",
                                "value": "\n".join(f"• {action}" for action in notification["suggested_actions"]),
                                "short": False
                            }
                        ]
                    }
                ]
            }
            
            # Send message using Slack connector
            logger.info(f"Would send Slack message to {slack_channel}")
            
        except Exception as e:
            logger.error(f"Error delivering notification via Slack: {e}")
            
    def _mark_notification_delivered(self, notification: Dict[str, Any]):
        """Mark a notification as delivered in storage."""
        notifications_file = Path.home() / ".clawfounder" / "notifications.json"
        
        try:
            if notifications_file.exists():
                with open(notifications_file, 'r') as f:
                    all_notifications = json.load(f)
                    
                # Find and mark the notification as delivered
                for notif in all_notifications:
                    if (notif.get("event_type") == notification["event_type"] and 
                        notif.get("timestamp") == notification["timestamp"]):
                        notif["delivered"] = True
                        notif["delivered_at"] = datetime.now().isoformat()
                        break
                        
                # Save back to file
                with open(notifications_file, 'w') as f:
                    json.dump(all_notifications, f, indent=2)
                    
        except Exception as e:
            logger.error(f"Error marking notification as delivered: {e}")
            
    def _cleanup_old_notifications(self):
        """Clean up old notifications to prevent storage bloat."""
        notifications_file = Path.home() / ".clawfounder" / "notifications.json"
        
        try:
            if notifications_file.exists():
                with open(notifications_file, 'r') as f:
                    all_notifications = json.load(f)
                    
                # Remove notifications older than 7 days
                cutoff_time = datetime.now() - timedelta(days=7)
                recent_notifications = []
                
                for notif in all_notifications:
                    try:
                        notif_time = datetime.fromisoformat(notif["timestamp"])
                        if notif_time > cutoff_time:
                            recent_notifications.append(notif)
                    except:
                        continue
                        
                # Save back to file if we removed anything
                if len(recent_notifications) < len(all_notifications):
                    with open(notifications_file, 'w') as f:
                        json.dump(recent_notifications, f, indent=2)
                    logger.info(f"Cleaned up {len(all_notifications) - len(recent_notifications)} old notifications")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old notifications: {e}")
            
    def get_dashboard_notifications(self) -> List[Dict[str, Any]]:
        """Get notifications for the dashboard."""
        dashboard_notifs_file = Path.home() / ".clawfounder" / "dashboard_notifications.json"
        
        try:
            if dashboard_notifs_file.exists():
                with open(dashboard_notifs_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading dashboard notifications: {e}")
            
        return []
        
    def mark_notification_read(self, notification_id: str):
        """Mark a dashboard notification as read."""
        dashboard_notifs_file = Path.home() / ".clawfounder" / "dashboard_notifications.json"
        
        try:
            if dashboard_notifs_file.exists():
                with open(dashboard_notifs_file, 'r') as f:
                    notifications = json.load(f)
                    
                # Find and mark the notification as read
                for notif in notifications:
                    if notif.get("event_type") == notification_id:
                        notif["read"] = True
                        notif["read_at"] = datetime.now().isoformat()
                        break
                        
                # Save back to file
                with open(dashboard_notifs_file, 'w') as f:
                    json.dump(notifications, f, indent=2)
                    
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            
    def update_user_preferences(self, preferences: Dict[str, Any]):
        """Update user notification preferences."""
        self.user_preferences.update(preferences)
        self._save_user_preferences()
        
    def get_user_preferences(self) -> Dict[str, Any]:
        """Get current user notification preferences."""
        return self.user_preferences.copy()

# Global instance
_proactive_notifier = None

def get_proactive_notifier():
    """Get the global proactive notifier instance."""
    global _proactive_notifier
    if _proactive_notifier is None:
        _proactive_notifier = ProactiveNotifier()
    return _proactive_notifier

def start_proactive_notifier():
    """Start the proactive notifier."""
    notifier = get_proactive_notifier()
    return notifier.start()

def stop_proactive_notifier():
    """Stop the proactive notifier."""
    notifier = get_proactive_notifier()
    notifier.stop()

if __name__ == "__main__":
    # Test the proactive notifier
    notifier = ProactiveNotifier()
    if notifier.initialize():
        print("Proactive Notifier initialized successfully")
        
        # Test notification delivery
        test_notification = {
            "type": "proactive_alert",
            "priority": "high",
            "event_type": "test_alert",
            "message": "This is a test notification",
            "data": {"test": True},
            "timestamp": datetime.now().isoformat(),
            "suggested_actions": ["Action 1", "Action 2"]
        }
        
        notifier._deliver_notification(test_notification)
        print("Test notification delivered")
    else:
        print("Failed to initialize Proactive Notifier")