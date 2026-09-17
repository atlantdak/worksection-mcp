"""Every Worksection API action name used by this server, in one place.

Centralised so that a naming difference against the live API is a one-line
change rather than a hunt through the tool modules.
"""

from __future__ import annotations

# Projects
GET_PROJECTS = "get_projects"
GET_PROJECT = "get_project"
POST_PROJECT = "post_project"
UPDATE_PROJECT = "update_project"
CLOSE_PROJECT = "close_project"
ACTIVATE_PROJECT = "activate_project"
GET_PROJECT_GROUPS = "get_project_groups"

# Tasks
GET_ALL_TASKS = "get_all_tasks"
GET_TASKS = "get_tasks"
GET_TASK = "get_task"
POST_TASK = "post_task"
UPDATE_TASK = "update_task"
COMPLETE_TASK = "complete_task"
REOPEN_TASK = "reopen_task"
DELETE_TASK = "delete_task"
SUBSCRIBE = "subscribe"
UNSUBSCRIBE = "unsubscribe"

# Comments
GET_COMMENTS = "get_comments"
POST_COMMENT = "post_comment"
UPDATE_COMMENT = "update_comment"
DELETE_COMMENT = "delete_comment"

# Tags
GET_TAGS = "get_tags"
ADD_TAGS = "add_tags"
SET_TAGS = "set_tags"

# People
GET_MEMBERS = "get_users"
GET_CONTACTS = "get_contacts"
GET_MEMBER_GROUPS = "get_groups"

# Time and costs
GET_COSTS = "get_costs"
ADD_COSTS = "add_costs"
UPDATE_COSTS = "update_costs"
DELETE_COSTS = "delete_costs"
START_TIMER = "start_timer"
STOP_TIMER = "stop_timer"
GET_TIMERS = "get_timers"

# Files and activity
GET_FILES = "get_files"
UPLOAD_FILE = "upload_file"
GET_EVENTS = "get_events"
