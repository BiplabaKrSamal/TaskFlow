export type Role = 'owner' | 'member'
export type Status = 'todo' | 'in_progress' | 'done'
export type Priority = 'low' | 'medium' | 'high'
export type Meta = Record<string, unknown>

export interface User {
  id: string
  name: string
  email: string
}
export interface UserRef {
  id: string
  name: string
}
export interface ProjectRef {
  id: string
  name: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface ProjectSummary {
  id: string
  name: string
  description: string
  role: Role
  member_count: number
  open_task_count: number
  created_at: string
}
export interface Member {
  user: User
  role: Role
  joined_at: string
}
export interface ProjectDetail {
  id: string
  name: string
  description: string
  role: Role
  created_at: string
  owner: UserRef
  members: Member[]
}

export interface Task {
  id: string
  project: ProjectRef
  title: string
  description: string
  status: Status
  priority: Priority
  due_date: string | null
  assignee_id: string | null
  assignee: UserRef | null
  creator: UserRef
  completed_at: string | null
  created_at: string
  updated_at: string
  comment_count: number
}
export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}
export interface Board {
  columns: Record<Status, Task[]>
}
export interface Comment {
  id: string
  task_id: string
  author: UserRef
  body: string
  created_at: string
}

export type ActivityType =
  | 'task_created'
  | 'task_moved'
  | 'task_assigned'
  | 'task_deleted'
  | 'member_invited'
  | 'member_removed'
  | 'comment_added'
export interface Activity {
  id: number
  type: ActivityType
  actor: UserRef
  meta: Meta
  created_at: string
  project: ProjectRef | null
}
export interface ActivityPage {
  items: Activity[]
  next_before: number | null
}

export interface Dashboard {
  project_count: number
  assigned: Record<Status, number>
  completed_this_week: number
  busiest_project: { id: string; name: string; open_tasks: number } | null
  recent_activity: Activity[]
}

/** A message pushed over the websocket. */
export interface LiveMessage {
  type: string
  project_id?: string
  project_name?: string
  actor?: UserRef
  meta?: Meta
  projects?: string[]
}
