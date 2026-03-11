"""
ClawFounder — Event Monitor

Proactive event monitoring system that watches for important events
across all connected services and triggers automated responses.

This is the core of the PM-like behavior - it monitors for events that
require attention and takes initiative.
"""

import json
import time
import threading
import schedule
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Add project root to path
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.connector_loader import load_connectors, get_all_tools
from agent.tool_router import build_tool_map, route_tool_call
from dashboard.knowledge_base import search, quick_search
from dashboard.agent_shared import load_all_connectors, call_tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EventMonitor:
    """Proactive event monitoring and response system."""
    
    def __init__(self):
        self.connectors = {}
        self.tool_map = {}
        self.running = False
        self.monitor_thread = None
        self.event_handlers = {}
        self.known_events = set()  # Track events we've already processed
        
        # Configuration
        self.config = {
            "check_interval": 60,  # seconds
            "urgent_keywords": [
                "urgent", "asap", "immediately", "deadline", "critical",
                "emergency", "priority", "important", "action required"
            ],
            "response_triggers": {
                "email_urgent": {
                    "keywords": ["urgent", "asap", "deadline", "critical"],
                    "response_template": "I see you received an urgent email about {subject}. Would you like me to help you respond or take any action?"
                },
                "github_pr_review": {
                    "keywords": ["review", "pull request", "pr"],
                    "response_template": "There's a new PR waiting for review: {title}. Should I review it or notify the team?"
                },
                "github_issue_assigned": {
                    "keywords": ["assigned", "issue"],
                    "response_template": "You've been assigned to a new issue: {title}. Would you like me to help you get started?"
                },
                "deadline_approaching": {
                    "keywords": ["deadline", "due", "tomorrow", "today"],
                    "response_template": "I notice a deadline is approaching: {details}. Should I help you prepare or notify anyone?"
                }
            }
        }
        
    def initialize(self):
        """Load connectors and build tool map."""
        logger.info("Initializing Event Monitor...")
        
        # Load connectors
        connectors_dir = str(PROJECT_ROOT / "connectors")
        self.connectors = load_connectors(connectors_dir)
        
        if not self.connectors:
            logger.warning("No connectors found - event monitoring disabled")
            return False
            
        self.tool_map = build_tool_map(self.connectors)
        logger.info(f"Loaded {len(self.connectors)} connectors for monitoring")
        
        # Initialize event handlers for each connector
        self._initialize_event_handlers()
        
        return True
        
    def _initialize_event_handlers(self):
        """Set up event handlers for each connector type."""
        self.event_handlers = {
            "gmail": self._check_gmail_events,
            "work_email": self._check_work_email_events,
            "github": self._check_github_events,
            "telegram": self._check_telegram_events,
            "slack": self._check_slack_events,
            "google_calendar": self._check_calendar_events
        }
        
    def start(self):
        """Start the event monitoring loop."""
        if not self.initialize():
            return False
            
        logger.info("Starting Event Monitor...")
        self.running = True
        
        # Start monitoring in background thread
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        # Schedule regular briefings
        schedule.every(30).minutes.do(self._generate_proactive_briefing)
        schedule.every().hour.do(self._check_deadlines)
        
        logger.info("Event Monitor started successfully")
        return True
        
    def stop(self):
        """Stop the event monitoring."""
        logger.info("Stopping Event Monitor...")
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        schedule.clear()
        logger.info("Event Monitor stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                self._check_all_events()
                schedule.run_pending()
                time.sleep(self.config["check_interval"])
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(30)  # Wait before retrying
                
    def _check_all_events(self):
        """Check for events across all connectors."""
        for connector_name, handler in self.event_handlers.items():
            if connector_name in self.connectors:
                try:
                    handler()
                except Exception as e:
                    logger.error(f"Error checking {connector_name} events: {e}")
                    
    def _check_gmail_events(self):
        """Check for urgent Gmail events."""
        try:
            connector = self.connectors["gmail"]
            result = connector["handle"]("gmail_get_unread", {"max_results": 20})
            
            if isinstance(result, str):
                emails = json.loads(result)
                for email in emails:
                    event_id = f"gmail_{email['id']}"
                    if event_id not in self.known_events:
                        self._process_email_event(email, "gmail")
                        self.known_events.add(event_id)
        except Exception as e:
            logger.error(f"Error checking Gmail events: {e}")
            
    def _check_work_email_events(self):
        """Check for urgent work email events."""
        try:
            connector = self.connectors["work_email"]
            result = connector["handle"]("work_email_get_unread", {"max_results": 20})
            
            if isinstance(result, str):
                emails = json.loads(result)
                for email in emails:
                    event_id = f"work_email_{email['id']}"
                    if event_id not in self.known_events:
                        self._process_email_event(email, "work_email")
                        self.known_events.add(event_id)
        except Exception as e:
            logger.error(f"Error checking work email events: {e}")
            
    def _check_github_events(self):
        """Check for GitHub events (PRs, issues, mentions)."""
        try:
            connector = self.connectors["github"]
            
            # Check notifications
            result = connector["handle"]("github_notifications", {})
            if isinstance(result, str):
                notifications = json.loads(result)
                for notification in notifications:
                    event_id = f"github_notif_{notification['id']}"
                    if event_id not in self.known_events:
                        self._process_github_notification(notification)
                        self.known_events.add(event_id)
                        
            # Check assigned issues/PRs
            result = connector["handle"]("github_list_issues", {"state": "open", "assignee": "@me"})
            if isinstance(result, str):
                issues = json.loads(result)
                for issue in issues:
                    event_id = f"github_issue_{issue['id']}"
                    if event_id not in self.known_events:
                        self._process_github_issue(issue)
                        self.known_events.add(event_id)
                        
        except Exception as e:
            logger.error(f"Error checking GitHub events: {e}")
            
    def _check_telegram_events(self):
        """Check for important Telegram messages."""
        try:
            connector = self.connectors["telegram"]
            result = connector["handle"]("telegram_get_updates", {"limit": 20})
            
            if isinstance(result, str):
                messages = json.loads(result)
                for message in messages:
                    event_id = f"telegram_{message['date']}_{message.get('from', 'unknown')}"
                    if event_id not in self.known_events:
                        self._process_telegram_message(message)
                        self.known_events.add(event_id)
        except Exception as e:
            logger.error(f"Error checking Telegram events: {e}")
            
    def _check_slack_events(self):
        """Check for important Slack messages."""
        try:
            connector = self.connectors["slack"]
            # Check for mentions and direct messages
            result = connector["handle"]("slack_get_messages", {"channel": "general", "limit": 20})
            
            if isinstance(result, str):
                messages = json.loads(result)
                for message in messages:
                    if "bot" not in message.get("subtype", ""):  # Skip bot messages
                        event_id = f"slack_{message['ts']}"
                        if event_id not in self.known_events:
                            self._process_slack_message(message)
                            self.known_events.add(event_id)
        except Exception as e:
            logger.error(f"Error checking Slack events: {e}")
            
    def _check_calendar_events(self):
        """Check for upcoming calendar events and deadlines."""
        try:
            connector = self.connectors["google_calendar"]
            # Check today's events
            result = connector["handle"]("calendar_list_events", {"time_range": "today"})
            
            if isinstance(result, str):
                events = json.loads(result)
                for event in events:
                    event_id = f"calendar_{event['id']}"
                    if event_id not in self.known_events:
                        self._process_calendar_event(event)
                        self.known_events.add(event_id)
        except Exception as e:
            logger.error(f"Error checking calendar events: {e}")
            
    def _process_email_event(self, email: Dict[str, Any], source: str):
        """Process an email event and determine if it requires attention."""
        subject = email.get("subject", "").lower()
        snippet = email.get("snippet", "").lower()
        from_email = email.get("from", "")
        
        # Check for urgent keywords
        urgent_keywords = self.config["urgent_keywords"]
        is_urgent = any(keyword in subject or keyword in snippet for keyword in urgent_keywords)
        
        if is_urgent:
            self._trigger_proactive_response(
                event_type="email_urgent",
                priority="high",
                data={
                    "subject": email.get("subject", ""),
                    "from": from_email,
                    "source": source,
                    "email_id": email["id"]
                }
            )
            
    def _process_github_notification(self, notification: Dict[str, Any]):
        """Process a GitHub notification."""
        reason = notification.get("reason", "").lower()
        subject = notification.get("subject", {})
        
        if isinstance(subject, dict):
            title = subject.get("title", "").lower()
            type_ = subject.get("type", "").lower()
        else:
            title = str(subject).lower()
            type_ = "notification"
            
        # Check for review requests or assignments
        if "review" in reason or "assigned" in reason:
            self._trigger_proactive_response(
                event_type="github_pr_review" if "pr" in type_ else "github_issue_assigned",
                priority="high",
                data={
                    "title": notification.get("subject", {}).get("title", ""),
                    "repo": notification.get("repository", ""),
                    "url": notification.get("url", ""),
                    "notification_id": notification["id"]
                }
            )
            
    def _process_github_issue(self, issue: Dict[str, Any]):
        """Process a GitHub issue assignment."""
        title = issue.get("title", "").lower()
        labels = [label.lower() for label in issue.get("labels", [])]
        
        # Check for urgent labels or keywords
        urgent_labels = ["urgent", "priority", "critical", "bug"]
        is_urgent = any(label in urgent_labels for label in labels) or any(keyword in title for keyword in self.config["urgent_keywords"])
        
        if is_urgent:
            self._trigger_proactive_response(
                event_type="github_issue_assigned",
                priority="high",
                data={
                    "title": issue.get("title", ""),
                    "repo": issue.get("repo", ""),
                    "url": issue.get("url", ""),
                    "issue_id": issue["id"]
                }
            )
            
    def _process_telegram_message(self, message: Dict[str, Any]):
        """Process a Telegram message."""
        text = message.get("text", "").lower()
        from_user = message.get("from", {})
        
        # Check for urgent keywords or mentions
        urgent_keywords = self.config["urgent_keywords"]
        is_urgent = any(keyword in text for keyword in urgent_keywords)
        
        if is_urgent:
            self._trigger_proactive_response(
                event_type="telegram_urgent",
                priority="medium",
                data={
                    "message": text,
                    "from": from_user.get("first_name", "Unknown"),
                    "message_id": message.get("message_id", "")
                }
            )
            
    def _process_slack_message(self, message: Dict[str, Any]):
        """Process a Slack message."""
        text = message.get("text", "").lower()
        
        # Check for mentions or urgent keywords
        has_mention = "@" in text  # Simple check for mentions
        urgent_keywords = self.config["urgent_keywords"]
        is_urgent = has_mention or any(keyword in text for keyword in urgent_keywords)
        
        if is_urgent:
            self._trigger_proactive_response(
                event_type="slack_urgent",
                priority="medium",
                data={
                    "message": text,
                    "channel": message.get("channel", ""),
                    "timestamp": message.get("ts", "")
                }
            )
            
    def _process_calendar_event(self, event: Dict[str, Any]):
        """Process a calendar event."""
        title = event.get("title", "").lower()
        start_time = event.get("start", "")
        
        # Check if event is soon (within next 2 hours)
        is_soon = self._is_event_soon(start_time)
        
        if is_soon:
            self._trigger_proactive_response(
                event_type="deadline_approaching",
                priority="high",
                data={
                    "title": event.get("title", ""),
                    "start_time": start_time,
                    "event_id": event["id"]
                }
            )
            
    def _is_event_soon(self, event_time: str) -> bool:
        """Check if an event is within the next 2 hours."""
        try:
            # Parse the event time (this is simplified - in practice you'd need proper date parsing)
            if "T" in event_time:
                event_dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
            else:
                # Assume it's today if no time specified
                event_dt = datetime.now().replace(hour=9, minute=0)  # Default to 9 AM
                
            time_diff = event_dt - datetime.now()
            return timedelta(0) <= time_diff <= timedelta(hours=2)
        except:
            return False
            
    def _trigger_proactive_response(self, event_type: str, priority: str, data: Dict[str, Any]):
        """Trigger a proactive response to an event."""
        logger.info(f"Triggering proactive response for {event_type}: {data}")
        
        # Get the response template
        trigger_config = self.config["response_triggers"].get(event_type, {})
        template = trigger_config.get("response_template", "I noticed something important: {details}")
        
        # Format the response message
        try:
            message = template.format(**data)
        except KeyError:
            message = f"I noticed something important: {data}"
            
        # Create the proactive notification
        notification = {
            "type": "proactive_alert",
            "priority": priority,
            "event_type": event_type,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "suggested_actions": self._get_suggested_actions(event_type, data)
        }
        
        # Store the notification for delivery
        self._store_notification(notification)
        
    def _get_suggested_actions(self, event_type: str, data: Dict[str, Any]) -> List[str]:
        """Get suggested actions for an event type."""
        actions = {
            "email_urgent": [
                "Read the email",
                "Compose a response",
                "Schedule a meeting",
                "Dismiss for now"
            ],
            "github_pr_review": [
                "Review the PR",
                "Assign to someone else",
                "Add to project board",
                "Dismiss"
            ],
            "github_issue_assigned": [
                "View the issue",
                "Start working on it",
                "Estimate effort",
                "Dismiss"
            ],
            "deadline_approaching": [
                "View calendar",
                "Prepare for deadline",
                "Notify team",
                "Dismiss"
            ]
        }
        
        return actions.get(event_type, ["View details", "Dismiss"])
        
    def _store_notification(self, notification: Dict[str, Any]):
        """Store a notification for delivery to the user."""
        # Store in a simple JSON file for now
        # In a production system, this would use a proper database
        notifications_file = Path.home() / ".clawfounder" / "notifications.json"
        
        try:
            notifications_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing notifications
            if notifications_file.exists():
                with open(notifications_file, 'r') as f:
                    notifications = json.load(f)
            else:
                notifications = []
                
            # Add new notification
            notifications.append(notification)
            
            # Keep only last 100 notifications
            notifications = notifications[-100:]
            
            # Save back to file
            with open(notifications_file, 'w') as f:
                json.dump(notifications, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error storing notification: {e}")
            
    def _generate_proactive_briefing(self):
        """Generate a proactive briefing based on recent events."""
        logger.info("Generating proactive briefing...")
        
        # Get recent notifications
        notifications = self._get_recent_notifications()
        
        if not notifications:
            return
            
        # Group by priority
        high_priority = [n for n in notifications if n["priority"] == "high"]
        medium_priority = [n for n in notifications if n["priority"] == "medium"]
        
        briefing = {
            "type": "proactive_briefing",
            "timestamp": datetime.now().isoformat(),
            "summary": f"Found {len(high_priority)} high priority and {len(medium_priority)} medium priority items requiring attention.",
            "high_priority": high_priority[:5],  # Top 5 high priority
            "medium_priority": medium_priority[:3],  # Top 3 medium priority
            "total_items": len(notifications)
        }
        
        # Store the briefing
        briefing_file = Path.home() / ".clawfounder" / "proactive_briefing.json"
        try:
            with open(briefing_file, 'w') as f:
                json.dump(briefing, f, indent=2)
        except Exception as e:
            logger.error(f"Error storing briefing: {e}")
            
    def _get_recent_notifications(self) -> List[Dict[str, Any]]:
        """Get recent notifications from storage."""
        notifications_file = Path.home() / ".clawfounder" / "notifications.json"
        
        try:
            if notifications_file.exists():
                with open(notifications_file, 'r') as f:
                    notifications = json.load(f)
                    
                # Get notifications from last 24 hours
                cutoff_time = datetime.now() - timedelta(hours=24)
                recent = []
                
                for notif in notifications:
                    try:
                        notif_time = datetime.fromisoformat(notif["timestamp"])
                        if notif_time > cutoff_time:
                            recent.append(notif)
                    except:
                        continue
                        
                return recent
        except Exception as e:
            logger.error(f"Error loading notifications: {e}")
            
        return []
        
    def _check_deadlines(self):
        """Check for approaching deadlines and send alerts."""
        # This would integrate with calendar and task systems
        # For now, it's a placeholder that could be expanded
        logger.info("Checking for approaching deadlines...")
        
        # Check calendar events for today
        if "google_calendar" in self.connectors:
            try:
                connector = self.connectors["google_calendar"]
                result = connector["handle"]("calendar_list_events", {"time_range": "today"})
                
                if isinstance(result, str):
                    events = json.loads(result)
                    for event in events:
                        if self._is_event_soon(event.get("start", "")):
                            self._trigger_proactive_response(
                                event_type="deadline_approaching",
                                priority="high",
                                data={
                                    "title": event.get("title", ""),
                                    "start_time": event.get("start", ""),
                                    "event_id": event["id"]
                                }
                            )
            except Exception as e:
                logger.error(f"Error checking calendar deadlines: {e}")

# Global instance
_event_monitor = None

def get_event_monitor():
    """Get the global event monitor instance."""
    global _event_monitor
    if _event_monitor is None:
        _event_monitor = EventMonitor()
    return _event_monitor

def start_event_monitor():
    """Start the event monitor."""
    monitor = get_event_monitor()
    return monitor.start()

def stop_event_monitor():
    """Stop the event monitor."""
    monitor = get_event_monitor()
    monitor.stop()

if __name__ == "__main__":
    # Test the event monitor
    monitor = EventMonitor()
    if monitor.initialize():
        print("Event Monitor initialized successfully")
        
        # Test a few event checks
        monitor._check_gmail_events()
        monitor._check_github_events()
        
        print("Event checks completed")
    else:
        print("Failed to initialize Event Monitor")